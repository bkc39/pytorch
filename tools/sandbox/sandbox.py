import argparse
import sys

from tools.sandbox import cmd
from tools.sandbox.common import username
from tools.sandbox.logger import log


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tools.sandbox")
    subparsers = parser.add_subparsers()
    for command in (cmd.create, cmd.list, cmd.rm, cmd.stop):
        command.add_parser(subparsers)
    args = parser.parse_args()
    if not hasattr(args, "run"):
        parser.print_help()
        sys.exit(1)
    log.debug(f"signed in as {username()}")
    args.run(args)
