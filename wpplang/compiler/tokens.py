"""W++ tokens.

A token is one meaningful piece of W++ source, carrying where it came from so
that every later stage - parser, semantic checks, code generator - can point an
error back at the line and column the author actually typed.
"""


class TokenType:
    """The kinds of token the W++ lexer produces.

    Plain strings rather than an enum: they print readably in test failures and
    keep the lexer easy to follow.
    """

    KEYWORD = "KEYWORD"      # one of the 19 words in the Official Dictionary
    NAME = "NAME"            # an identifier, or a Python word W++ does not rename
    NUMBER = "NUMBER"
    STRING = "STRING"        # a complete literal, including its quotes
    FSTRING = "FSTRING"      # an f-string, kept apart because it holds code
    OP = "OP"                # operators and punctuation
    NEWLINE = "NEWLINE"      # end of a logical line
    INDENT = "INDENT"
    DEDENT = "DEDENT"
    COMMENT = "COMMENT"
    EOF = "EOF"


class Token:
    """One token, and the span of W++ source it came from."""

    __slots__ = ("type", "value", "line", "column", "end_line", "end_column", "extra")

    def __init__(self, type, value, line, column, end_line=None, end_column=None,
                 extra=None):
        self.type = type
        self.value = value
        self.line = line              # 1-based, as a person counts lines
        self.column = column          # 0-based, as an editor reports columns
        self.end_line = end_line if end_line is not None else line
        self.end_column = end_column if end_column is not None else column + len(str(value))
        # Used by f-strings to carry their already-lexed pieces.
        self.extra = extra

    @property
    def position(self):
        """The (line, column) pair, which is what error messages want."""
        return (self.line, self.column)

    def is_keyword(self, *words):
        """True when this token is one of the given W++ keywords."""
        return self.type == TokenType.KEYWORD and self.value in words

    def is_op(self, *symbols):
        """True when this token is one of the given operators."""
        return self.type == TokenType.OP and self.value in symbols

    def is_name(self, *names):
        """True when this token is one of the given bare words."""
        return self.type == TokenType.NAME and self.value in names

    def __repr__(self):
        return "Token({}, {!r}, line={}, col={})".format(
            self.type, self.value, self.line, self.column)
