#!/usr/bin/env python3
"""W++ command line interface.

    python wpp.py examples/hello.wpp        run a W++ program
    python wpp.py --emit examples/hello.wpp print the generated Python
    python wpp.py --keywords                show the Official Dictionary
    python wpp.py --ast examples/hello.wpp  show the W++ AST
    python wpp.py --tokens examples/hello.wpp   show the W++ tokens

A failing program also plays audio/fah.mp3 when the terminal is interactive.
Use --mute to silence it, or --sound to force it on when output is piped.
"""

import argparse
import os
import sys

from wpplang import CATEGORIES, KEYWORDS, __version__, format_skill_issue, translate
from wpplang import sound
from wpplang.compiler import compile_source, tokenize_source
from wpplang.compiler.errors import WppError
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
        "-a",
        "--ast",
        action="store_true",
        help="print the W++ abstract syntax tree instead of running it",
    )
    parser.add_argument(
        "-t",
        "--tokens",
        action="store_true",
        help="print the W++ token stream instead of running it",
    )
    parser.add_argument(
        "-k",
        "--keywords",
        action="store_true",
        help="print the Official Dictionary and exit",
    )
    parser.add_argument(
        "-m",
        "--mute",
        action="store_true",
        help="do not play the error sound",
    )
    parser.add_argument(
        "-s",
        "--sound",
        action="store_true",
        help="play the error sound even when output is not a terminal",
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

    if args.tokens:
        return show_tokens(args.source, args)

    if args.ast:
        return show_ast(args.source, args)

    if args.emit:
        return emit(args.source, args)

    result = run_file(args.source)
    if result.error_report is not None:
        # The report goes out first: the sound is an accompaniment, and it
        # must never delay the message the user actually needs.
        print(result.error_report, file=sys.stderr)
        sys.stderr.flush()
        announce_failure(args)
    return result.exit_code


def emit(path, args):
    """Print the generated Python, reporting a bad program the usual way."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    try:
        sys.stdout.write(translate(source))
    except (SyntaxError, ValueError) as exc:
        # Translation can refuse a program outright - a keyword used where only
        # a name can go - and that deserves a skill issue, not a traceback.
        print(format_skill_issue(exc, path, source.splitlines()), file=sys.stderr)
        sys.stderr.flush()
        announce_failure(args)
        return EXIT_SKILL_ISSUE
    return 0


def show_tokens(path, args):
    """Print the token stream: the first stage of the compiler."""
    def render(source):
        return chr(10).join(
            "{:>4}:{:<3} {:<8} {!r}".format(t.line, t.column, t.type, t.value)
            for t in tokenize_source(source))

    return _inspect(path, args, render)


def show_ast(path, args):
    """Print the W++ AST: what the parser built, before any Python exists."""
    return _inspect(path, args, lambda source: compile_source(source).ast.dump())


def _inspect(path, args, render):
    """Run one inspection stage, reporting a bad program the usual way."""
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    try:
        print(render(source))
    except WppError as error:
        exc = error.as_syntax_error(path)
        print(format_skill_issue(exc, path, source.splitlines()), file=sys.stderr)
        sys.stderr.flush()
        announce_failure(args)
        return EXIT_SKILL_ISSUE
    return 0


def announce_failure(args):
    """Play the error sound, if the user wants one and we can manage it."""
    if not wants_sound(args):
        return
    sound.play_error_sound(muted=False)


def wants_sound(args):
    """Decide whether this run should make a noise.

    Unmuted is the default, but only for an interactive terminal: a program
    whose output is being piped into a file or another tool should not start
    playing audio, and neither should the test suite.  --sound overrides that.

    Precedence, most specific first: --mute, --sound, WPP_MUTE, then whether
    stderr is a terminal.
    """
    if args.mute:
        return False
    if args.sound:
        return True
    if sound.is_muted():
        return False
    try:
        return bool(sys.stderr.isatty())
    except (AttributeError, ValueError):
        return False


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
