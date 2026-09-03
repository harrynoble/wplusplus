"""Errors raised by the W++ frontend.

These always describe W++ source: a W++ line, a W++ column, and wording about
W++ rather than about the Python the compiler happens to generate.  The Skill
Issue Protocol turns them into the messages the spec defines.
"""


class WppError(Exception):
    """Base class for anything the W++ frontend rejects."""

    def __init__(self, message, line=None, column=None, source_line=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line

    def as_syntax_error(self, filename="<wpp>"):
        """Convert to a SyntaxError so existing error handling keeps working.

        The runner and the Skill Issue Protocol already know how to report a
        SyntaxError with a line number, so a frontend rejection travels the same
        road as any other one rather than needing a second code path.
        """
        error = SyntaxError(self.message)
        error.lineno = self.line
        error.offset = None if self.column is None else self.column + 1
        error.text = self.source_line
        error.filename = filename
        return error


class WppSyntaxError(WppError):
    """The source is not valid W++: the lexer or the parser could not read it."""


class WppIndentationError(WppSyntaxError):
    """The indentation does not line up.

    Kept apart from a plain syntax error so the Skill Issue Protocol can reach
    the spec's own wording for it: as_syntax_error returns Python's
    IndentationError, and the protocol's lookup walks the exception's MRO.
    """

    def as_syntax_error(self, filename="<wpp>"):
        error = IndentationError(self.message)
        error.lineno = self.line
        error.offset = None if self.column is None else self.column + 1
        error.text = self.source_line
        error.filename = filename
        return error


class WppSemanticError(WppError):
    """The source parses, but breaks a W++ rule that meaning depends on."""
