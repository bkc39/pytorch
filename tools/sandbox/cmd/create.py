import argparse
import sys

import modal

from tools.sandbox.common import (
    app,
    BASE_IMAGE,
    exit_snapshot,
    filesystem_name,
    filesystems,
    github_keys,
    last_sandbox_by_filesystem,
    output,
    SANDBOX_IDLE_TIMEOUT_SECONDS,
    SANDBOX_TIMEOUT_SECONDS,
    sandboxes_using,
    save_filesystem,
    SSH_PORT,
    username,
)
from tools.sandbox.logger import log


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("create", help="create a sandbox on a filesystem")
    parser.add_argument(
        "--filesystem", default="default", help="filesystem name (default: %(default)s)"
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> None:
    name = filesystem_name(args.filesystem)
    in_use_by = [sandbox.object_id for sandbox in sandboxes_using(name)]
    if in_use_by:
        log.error(
            f"filesystem {name} is already used by {', '.join(in_use_by)}, stop it first"
        )
        sys.exit(1)
    filesystem_exists = name in filesystems()
    image = modal.Image.from_name(name) if filesystem_exists else BASE_IMAGE
    # A previous sandbox that was not stopped with `stop` (idle or 24 h timeout, crash)
    # left an exit snapshot; make that the filesystem so nothing is lost.
    previous_sandbox_id = last_sandbox_by_filesystem().get(name)
    previous_exit_snapshot = (
        exit_snapshot(previous_sandbox_id) if previous_sandbox_id else None
    )
    if previous_exit_snapshot is not None:
        log.info(
            f"restoring filesystem from the exit snapshot of {previous_sandbox_id}"
        )
        previous_exit_snapshot.publish(name)
        image, filesystem_exists = previous_exit_snapshot, True
    log.debug(f"{'using' if filesystem_exists else 'creating'} filesystem: {name}")
    # The entrypoint installs the user's GitHub keys and runs sshd in the foreground.
    start_sshd = (
        "mkdir -p /root/.ssh /run/sshd"
        " && printf '%s\\n' \"$AUTHORIZED_KEYS\" > /root/.ssh/authorized_keys"
        " && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys"
        " && ssh-keygen -A > /dev/null && exec /usr/sbin/sshd -D -e"
    )
    log.debug("starting sandbox")
    sandbox = modal.Sandbox.create(
        "bash",
        "-c",
        start_sshd,
        app=app(),
        image=image,
        runtime="gvisor",
        timeout=SANDBOX_TIMEOUT_SECONDS,
        idle_timeout=SANDBOX_IDLE_TIMEOUT_SECONDS,
        tags={"username": username(), "filesystem": name},
        env={"AUTHORIZED_KEYS": github_keys()},
        unencrypted_ports=[SSH_PORT],
        experimental_options={"enable_exit_snapshot": True},
    )
    last_sandbox_by_filesystem()[name] = sandbox.object_id
    host, port = sandbox.tunnels()[SSH_PORT].tcp_socket
    log.debug(f"sandbox started: {sandbox.object_id}")
    log.info(f"ssh into the sandbox: ssh -p {port} root@{host}")
    if not filesystem_exists:
        save_filesystem(sandbox, name)
    output(
        {
            "sandbox_id": sandbox.object_id,
            "filesystem": name,
            "dashboard_url": sandbox.get_dashboard_url(),
            "ssh": {"host": host, "port": port},
        }
    )
