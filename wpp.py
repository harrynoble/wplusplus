#!/usr/bin/env python3
"""W++ command line interface.

    python wpp.py examples/hello.wpp        run a W++ program
    python wpp.py --emit examples/hello.wpp print the generated Python
    python wpp.py --keywords                show the Official Dictionary
"""

import argparse
import os
import sys

from wpplang import CATEGORIES, KEYWORDS, __version__, format_skill_issue, translate
from wpplang.runner import EXIT_SKILL_ISSUE, run_file

EXIT_USAGE = 2


def main(argv=None):
    _use_utf8(sys.stdout)
    _use_utf8(sys.stderr)

    parser = argparse.ArgumentParser(
        prog="wpp",
        description="Run W++ programs. No skill issues, only vibes.",
    )
    parser.add_argument("source", nargs="?", help="path to a .wpp file")
    parser.add_argument(
        "-e",
        "--emit",
        action="store_true",
        help="print the translated Python instead of running it",
    )
    parser.add_argument(
        "-k",
        "--keywords",
        action="store_true",
        help="print the Official Dictionary and exit",
    )
    parser.add_argument("-V", "--version", action="version", version="W++ " + __version__)
    args = parser.parse_args(argv)

    if args.keywords:
        _print_keywords()
        return 0

    if args.source is None:
        parser.print_usage(sys.stderr)
        print("wpp: give me a .wpp file to run", file=sys.stderr)
        return EXIT_USAGE

    if not os.path.isfile(args.source):
        print("wpp: no such file: {}".format(args.source), file=sys.stderr)
        return EXIT_USAGE

    if args.emit:
        return emit(args.source)

    result = run_file(args.source)
    if result.error_report is not None:
        print(result.error_report, file=sys.stderr)
    return result.exit_code


def emit(path):
    """Print the generated Python, reporting a bad program the usual way."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    try:
        sys.stdout.write(translate(source))
    except (SyntaxError, ValueError) as exc:
        # Translation can refuse a program outright - a keyword used where only
        # a name can go - and that deserves a skill issue, not a traceback.
        print(format_skill_issue(exc, path, source.splitlines()), file=sys.stderr)
        return EXIT_SKILL_ISSUE
    return 0


def _print_keywords():
    """Render the keyword table."""
    width = max(len(word) for word in KEYWORDS)
    print("{:<{w}}  {:<10}  {}".format("W++", "PYTHON", "CATEGORY", w=width))
    print("{:<{w}}  {:<10}  {}".format("-" * width, "-" * 10, "-" * 20, w=width))
    for word, target in KEYWORDS.items():
        print("{:<{w}}  {:<10}  {}".format(word, target, CATEGORIES[word], w=width))


def _use_utf8(stream):
    """Best-effort UTF-8 output so the siren emoji survives older consoles."""
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ctrl-C outside of program execution (e.g. while reading the file).
        sys.exit(EXIT_SKILL_ISSUE)
