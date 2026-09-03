"""Subprocess entry point for one playground run.

The playground never executes user code inside the web server.  Each run is a
fresh child process, which gives us three things for free: a hard timeout for
runaway loops, isolation from the server's own state, and a clean stdin.

The program's own output goes to this process's stdout.  The skill issue (if
any) is written as JSON to the path given on the command line, so the two can
never be confused with one another.
"""

import json
import os
import sys

# The repository root, so `wpplang` imports without installation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wpplang import run_source  # noqa: E402  (path setup must come first)


def main():
    source_path, result_path = sys.argv[1], sys.argv[2]

    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()

    # `main.wpp` keeps the reported path short and stable in the UI.
    result = run_source(source, "main.wpp")

    sys.stdout.flush()
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"exitCode": result.exit_code, "error": result.error_details},
            handle,
        )

    # Always exit 0: the envelope carries the program's real exit code, so a
    # non-zero status here would only mean the worker itself failed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
