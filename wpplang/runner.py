"""Execute translated W++ programs.

The pipeline is deliberately thin:

    .wpp source -> translate() -> Python source -> compile() -> exec()

Because the translated Python keeps the original line numbering, the .wpp path
is handed to compile() as the filename.  Tracebacks then point straight at the
W++ file and the Skill Issue Protocol can quote the offending line.
"""

import os

from .errors import format_skill_issue
from .translator import translate

# Process exit codes.
EXIT_OK = 0
EXIT_SKILL_ISSUE = 1
EXIT_INTERRUPTED = 130  # Conventional shell code for Ctrl-C.


class Result:
    """Outcome of running a W++ program."""

    def __init__(self, exit_code, error_report=None):
        self.exit_code = exit_code
        self.error_report = error_report

    @property
    def ok(self):
        return self.error_report is None


def run_source(source, source_path="<wpp>"):
    """Translate and execute W++ source text.  Never raises for user errors."""
    display_path = str(source_path)
    source_lines = source.splitlines()

    try:
        python_source = translate(source)
        code = compile(python_source, display_path, "exec")
    except (SyntaxError, ValueError) as exc:
        return Result(
            EXIT_SKILL_ISSUE,
            format_skill_issue(exc, display_path, source_lines),
        )

    # A fresh namespace that looks like a normal top-level script.
    namespace = {"__name__": "__main__", "__file__": display_path}

    try:
        exec(code, namespace)
    except SystemExit as exc:  # `exit(2)` inside a W++ program is not an error.
        return Result(exc.code if isinstance(exc.code, int) else EXIT_OK)
    except KeyboardInterrupt as exc:
        return Result(
            EXIT_INTERRUPTED,
            format_skill_issue(exc, display_path, source_lines),
        )
    except BaseException as exc:  # noqa: BLE001 - every failure becomes a skill issue.
        return Result(
            EXIT_SKILL_ISSUE,
            format_skill_issue(exc, display_path, source_lines),
        )

    return Result(EXIT_OK)


def run_file(path):
    """Translate and execute a .wpp file."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    return run_source(source, os.fspath(path))
