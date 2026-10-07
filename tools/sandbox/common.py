import json
import shutil
import subprocess
import sys
from functools import cache

import modal

from tools.sandbox.logger import log


BASE_IMAGE = modal.Image.debian_slim().apt_install("openssh-server")
SSH_PORT = 22
SANDBOX_TIMEOUT_SECONDS = 24 * 60 * 60  # the maximum Modal allows
SANDBOX_IDLE_TIMEOUT_SECONDS = 60 * 60


@cache
def username() -> str:
    github_cli = shutil.which("gh")
    if github_cli is None:
        log.error("gh is not installed, install it and run `gh auth login`")
        sys.exit(1)
    result = subprocess.run(
        [github_cli, "api", "user", "--jq", ".login"], capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error(
            f"not logged in to GitHub, run `gh auth login`: {result.stderr.strip()}"
        )
        sys.exit(1)
    return result.stdout.strip()


@cache
def github_keys() -> str:
    """The user's public SSH keys registered on GitHub, one per line."""
    result = subprocess.run(
        ["gh", "api", f"users/{username()}/keys", "--jq", ".[].key"],
        capture_output=True,
        text=True,
        check=True,
    )
    if not result.stdout.strip():
        log.error(
            f"no SSH keys on GitHub for {username()}, add one at https://github.com/settings/keys"
        )
        sys.exit(1)
    return result.stdout


@cache
def app() -> modal.App:
    return modal.App.lookup("pytorch", create_if_missing=True)


@cache
def last_sandbox_by_filesystem() -> modal.Dict:
    """Filesystem name -> id of the last sandbox created on it; `stop` clears the entry."""
    return modal.Dict.from_name("last-sandbox-by-filesystem", create_if_missing=True)


def exit_snapshot(sandbox_id: str) -> modal.Image | None:
    """The filesystem Modal captured when the sandbox exited, or None if the sandbox is gone.

    Exits with an error if the exit snapshot is not ready yet, so a stale filesystem is never
    used in its place.
    """
    try:
        sandbox = modal.Sandbox.from_id(sandbox_id)
    except (modal.exception.NotFoundError, modal.exception.InvalidError):
        return None
    try:
        return sandbox._experimental_get_exit_snapshot(timeout=120)
    except modal.exception.TimeoutError:
        log.error(
            f"the exit snapshot of {sandbox_id} is not ready yet, try again in a minute"
        )
        sys.exit(1)
    except modal.exception.SnapshotCreationError as exception:
        log.warning(
            f"Modal failed to capture the exit snapshot of {sandbox_id}: {exception}"
        )
        return None


def filesystem_name(name: str) -> str:
    return f"{username()}:{name}"


def save_filesystem(sandbox: modal.Sandbox, name: str) -> None:
    log.info(f"saving filesystem: {name}")
    sandbox.snapshot_filesystem(timeout=600, ttl=None).publish(name)


def filesystems() -> dict[str, dict[str, str]]:
    """This user's filesystem names mapped to what Modal knows about the image."""
    result = subprocess.run(
        [sys.executable, "-m", "modal", "image", "names", "list", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    name_prefix = f"{username()}:"
    return {
        entry["tag"]: {
            field: entry[field] for field in ("image_id", "created_at", "updated_at")
        }
        for entry in json.loads(result.stdout)
        if entry["tag"].startswith(name_prefix) and image_exists(entry["image_id"])
    }


def image_exists(image_id: str) -> bool:
    # Deleting an image leaves its name behind, so probe the image itself.
    # The logs call is lazy, so it has to be iterated to reach the server.
    # Snapshot images have no build logs and answer with a server error, which
    # still proves they exist; only NotFoundError means the image is gone.
    try:
        for _ in modal.Image.from_id(image_id).logs.fetch():
            break
    except modal.exception.NotFoundError:
        return False
    except modal.exception.Error:
        return True
    return True


def sandboxes() -> list[modal.Sandbox]:
    return list(modal.Sandbox.list(app_id=app().app_id, tags={"username": username()}))


def sandboxes_using(filesystem: str) -> list[modal.Sandbox]:
    """Running sandboxes of this user that were created on the given filesystem."""
    return [
        sandbox
        for sandbox in sandboxes()
        if sandbox.get_tags().get("filesystem") == filesystem
    ]


def output(result: dict[str, object]) -> None:
    """Print a command result as JSON on stdout; logs go to stderr via `log`."""
    print(json.dumps(result, indent=2))
