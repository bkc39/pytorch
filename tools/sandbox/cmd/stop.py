import argparse
import sys

import modal

from tools.sandbox.common import (
    last_sandbox_by_filesystem,
    output,
    save_filesystem,
    username,
)
from tools.sandbox.logger import log


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "stop", help="save the filesystem and terminate a sandbox"
    )
    parser.add_argument("sandbox_id")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> None:
    try:
        sandbox = modal.Sandbox.from_id(args.sandbox_id)
        tags = sandbox.get_tags()
    except (modal.exception.NotFoundError, modal.exception.InvalidError):
        log.error(f"no running sandbox: {args.sandbox_id}")
        sys.exit(1)
    if tags.get("username") != username():
        log.error(f"sandbox {args.sandbox_id} does not belong to {username()}")
        sys.exit(1)
    if sandbox.poll() is not None:
        log.error(
            f"sandbox {args.sandbox_id} has already exited, `create` will restore its exit snapshot"
        )
        sys.exit(1)
    save_filesystem(sandbox, tags["filesystem"])
    log.debug(f"terminating sandbox: {args.sandbox_id}")
    sandbox.terminate()
    last_sandbox_by_filesystem().pop(tags["filesystem"], None)
    output({"sandbox_id": args.sandbox_id, "filesystem": tags["filesystem"]})
