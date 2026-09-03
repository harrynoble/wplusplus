"""The Skill Issue Protocol.

Python tracebacks are intercepted and re-presented using the W++ messages from
the spec.  The message wording is fixed by the spec and must not be edited; the
surrounding context (file, line, source line) is ours to add.
"""

import traceback

# Exception class name -> official W++ message.  Wording is verbatim from the
# W++ Language Spec v1.1, section 2.
SKILL_ISSUES = {
    "SyntaxError": "Negative Aura: Bro forgot how to type (SyntaxError)",
    "NameError": "Bro is making up words now (NameError)",
    "TypeError": "Oil up bro, you can't combine those (TypeError)",
    "IndexError": "Blud thinks he has more items than he does (IndexError)",
    "ZeroDivisionError": "Bro just broke the matrix (ZeroDivisionError)",
    "IndentationError": "Your spaces are looking a little sus (IndentationError)",
    "KeyboardInterrupt": "Go touch grass, you've been looping forever (KeyboardInterrupt)",
}

SIREN = "\U0001f6a8"  # The spec prints every skill issue behind a siren.


def skill_issue_message(exc):
    """Return the official W++ message for an exception.

    The lookup walks the exception's MRO, so subclasses land on the right
    message: IndentationError is a SyntaxError, but it has its own entry and
    the MRO reaches it first.  Anything outside the spec gets a generic line
    rather than a raw Python traceback.
    """
    for klass in type(exc).__mro__:
        if klass.__name__ in SKILL_ISSUES:
            return SKILL_ISSUES[klass.__name__]
    return "Unspecified skill issue ({})".format(type(exc).__name__)


def skill_issue_details(exc, source_path=None, source_lines=None):
    """Describe a skill issue as plain data.

    Returns a dict with the official ``message``, the Python ``exception``
    name, the ``line`` in the .wpp source, that ``source_line`` itself and the
    original Python ``detail``.  The terminal renderer and the web playground
    both build their output from this, so they can never disagree about the
    wording.
    """
    lineno = _locate(exc, source_path)
    return {
        "message": skill_issue_message(exc),
        "exception": type(exc).__name__,
        "path": None if source_path is None else str(source_path),
        "line": lineno,
        "source_line": _source_line(source_lines, lineno),
        "detail": _detail(exc),
    }


def format_skill_issue(exc, source_path=None, source_lines=None):
    """Render a full W++ error report for *exc* as terminal text."""
    info = skill_issue_details(exc, source_path, source_lines)
    lines = ["{} {}".format(SIREN, info["message"])]

    if info["path"] is not None and info["line"] is not None:
        lines.append("   where: {}, line {}".format(info["path"], info["line"]))
        if info["source_line"] is not None:
            lines.append("   {:>4} | {}".format(info["line"], info["source_line"]))
    elif info["path"] is not None:
        lines.append("   where: {}".format(info["path"]))

    if info["detail"]:
        lines.append("   details: {}".format(info["detail"]))

    return "\n".join(lines)


def _locate(exc, source_path):
    """Find the .wpp line number an exception came from, if we can."""
    # Compile-time errors carry the line directly.
    if isinstance(exc, SyntaxError) and exc.lineno:
        return exc.lineno

    # Runtime errors: walk the traceback and keep the innermost frame that is
    # still inside the user's .wpp file.  Line numbers survive translation
    # unchanged, so the frame's lineno is already the W++ line.
    lineno = None
    for frame in traceback.extract_tb(exc.__traceback__):
        if source_path is None or frame.filename == str(source_path):
            lineno = frame.lineno
    return lineno


def _source_line(source_lines, lineno):
    """Return the stripped source line *lineno*, or None if unavailable."""
    if not source_lines or lineno is None or not 1 <= lineno <= len(source_lines):
        return None
    return source_lines[lineno - 1].strip()


def _detail(exc):
    """A short, human-readable version of the original Python complaint."""
    if isinstance(exc, KeyboardInterrupt):
        return ""
    if isinstance(exc, SyntaxError):
        return exc.msg or ""
    return str(exc)
