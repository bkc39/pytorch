import argparse
import sys

import modal

from tools.sandbox.common import (
    filesystems,
    image_exists,
    last_sandbox_by_filesystem,
    output,
    sandboxes_using,
)
from tools.sandbox.logger import log


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("rm", help="delete a filesystem")
    parser.add_argument(
        "filesystem",
        help="full filesystem name (user:name) or image id, as shown by `list`",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> None:
    filesystems_by_name = filesystems()
    names_by_image_id = {
        details["image_id"]: name for name, details in filesystems_by_name.items()
    }
    name = (
        args.filesystem
        if args.filesystem in filesystems_by_name
        else names_by_image_id.get(args.filesystem)
    )
    if name is None:
        log.error(f"no such filesystem: {args.filesystem}")
        sys.exit(1)
    sandboxes_using_filesystem = [
        sandbox.object_id for sandbox in sandboxes_using(name)
    ]
    if sandboxes_using_filesystem:
        log.error(
            f"filesystem {name} is in use by {', '.join(sandboxes_using_filesystem)}, stop them first"
        )
        sys.exit(1)
    log.debug(f"deleting filesystem: {name}")
    image_id = filesystems_by_name[name]["image_id"]
    try:
        modal.experimental.image_delete(image_id)
        error_message = None
    except modal.exception.Error as exception:
        error_message = str(exception)
    # image_delete returns nothing, so confirm the image is really gone.
    deleted = error_message is None and not image_exists(image_id)
    if deleted:
        last_sandbox_by_filesystem().pop(name, None)
    output(
        {
            "filesystem": name,
            "image_id": image_id,
            "deleted": deleted,
            "error": error_message,
        }
    )
    if not deleted:
        sys.exit(1)
