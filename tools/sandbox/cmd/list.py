import argparse

from tools.sandbox.common import filesystems, output, sandboxes


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("list", help="list your sandboxes and filesystems")
    parser.set_defaults(run=run)


def run(args: argparse.Namespace) -> None:
    output(
        {
            "sandboxes": [
                {
                    "sandbox_id": sandbox.object_id,
                    "filesystem": sandbox.get_tags()["filesystem"],
                    "dashboard_url": sandbox.get_dashboard_url(),
                }
                for sandbox in sandboxes()
            ],
            "filesystems": [
                {"name": name, **details} for name, details in filesystems().items()
            ],
        }
    )
