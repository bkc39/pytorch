# tools/sandbox

CLI for Modal dev sandboxes: `python -m tools.sandbox <command>`. Subcommands live in `cmd/<command>.py`, each exposing `add_parser(subparsers)` and `run(args)`.

## Best practices

- Never use `print` for logs. Always use `log` from `logger.py` (`from tools.sandbox.logger import log`). It writes to stderr, so logs never mix with command output.
- Whenever outputting results, print JSON to stdout so the output can be piped into `jq` or another command. Use `output(...)` from `common.py` (`from tools.sandbox.common import output`) rather than calling `print` or `json.dumps` yourself, so every command formats its result the same way.
- Use descriptive variable names and spell words out: `sandbox` rather than `sb`, `filesystem_exists` rather than `exists`, `sandboxes_using_filesystem` rather than `users`. Single-letter names are fine inside lambdas.
