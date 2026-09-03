"""The W++ lexer.

Turns W++ source into a stream of W++ tokens carrying line and column.

W++ and Python are *lexically* identical: the same numbers, the same string
forms, the same operators, the same indentation rules.  They differ only in
which bare words are keywords, and that is a question for the parser, not the
scanner.  So the character-level scanning is delegated to Python's `tokenize`
module - which is keyword-agnostic and battle-tested on every string, f-string
and indentation corner case - and this module adds the parts that are W++'s
own:

* classifying the 19 words of the Official Dictionary as KEYWORD tokens,
* collapsing an f-string into a single token that carries its already-lexed
  replacement fields,
* dropping the noise the parser does not need (blank lines, comments),
* reporting a scanning failure as a W++ error with a W++ line and column.

The important consequence is structural rather than cosmetic: a keyword inside
a string is never a keyword here, because the scanner hands back the whole
literal as one token.  `yap("cook bet")` cannot become `print("def if")` by
construction, not by a carefully written regular expression.
"""

import io
import tokenize

from ..keywords import KEYWORDS
from .errors import WppIndentationError, WppSyntaxError
from .tokens import Token, TokenType

# tokenize types that carry no meaning for the parser.
_IGNORED = frozenset({tokenize.NL, tokenize.COMMENT, tokenize.ENCODING})

# Present from Python 3.12; guarded so the module still imports on 3.8-3.11,
# where an f-string arrives as one ordinary STRING token instead.
_FSTRING_START = getattr(tokenize, "FSTRING_START", None)
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)
_FSTRING_END = getattr(tokenize, "FSTRING_END", None)
_HAS_FSTRING_TOKENS = None not in (_FSTRING_START, _FSTRING_MIDDLE, _FSTRING_END)


def tokenize_source(source):
    """Lex W++ source.  Returns a list of Tokens ending with EOF."""
    return _Lexer(source).run()


class _Lexer:
    def __init__(self, source):
        self.source = source
        self.lines = source.splitlines()
        # Absolute offset of the start of each 1-based line, so a (line, column)
        # can be turned back into a slice of the original source.
        self._line_starts = [0]
        for line in source.splitlines(keepends=True):
            self._line_starts.append(self._line_starts[-1] + len(line))

    # -- public

    def run(self):
        raw = self._scan()
        tokens = []
        index = 0
        while index < len(raw):
            item = raw[index]

            if item.type in _IGNORED:
                index += 1
                continue

            if item.type == tokenize.ENDMARKER:
                break

            if _HAS_FSTRING_TOKENS and item.type == _FSTRING_START:
                token, index = self._collapse_fstring(raw, index)
                tokens.append(token)
                continue

            tokens.append(self._convert(item))
            index += 1

        last_line = len(self.lines) + 1
        tokens.append(Token(TokenType.EOF, "", last_line, 0))
        return tokens

    # -- scanning

    def _scan(self):
        """Run tokenize, translating its failures into W++ errors."""
        try:
            return list(tokenize.generate_tokens(io.StringIO(self.source).readline))
        except tokenize.TokenError as exc:
            # Raised for an unclosed bracket or an unterminated triple-quote.
            line = 1
            if len(exc.args) > 1 and isinstance(exc.args[1], tuple):
                line = exc.args[1][0]
            raise WppSyntaxError(
                str(exc.args[0]) if exc.args else "could not read the source",
                line=line, column=0, source_line=self._text_of(line))
        except IndentationError as exc:
            # Covers TabError too, which is a kind of IndentationError.
            raise WppIndentationError(
                exc.msg, line=exc.lineno, column=(exc.offset or 1) - 1,
                source_line=self._text_of(exc.lineno))
        except SyntaxError as exc:
            raise WppSyntaxError(
                exc.msg, line=exc.lineno, column=(exc.offset or 1) - 1,
                source_line=self._text_of(exc.lineno))

    def _convert(self, item):
        """Turn one tokenize token into a W++ token."""
        kind = item.type
        text = item.string

        if kind == tokenize.NAME:
            token_type = (TokenType.KEYWORD if text in KEYWORDS else TokenType.NAME)
        elif kind == tokenize.NUMBER:
            token_type = TokenType.NUMBER
        elif kind == tokenize.STRING:
            # On 3.8-3.11 an f-string arrives here whole; mark it so the parser
            # can still tell the two apart.
            token_type = (TokenType.FSTRING if _is_fstring_literal(text)
                          else TokenType.STRING)
        elif kind == tokenize.OP:
            token_type = TokenType.OP
        elif kind == tokenize.NEWLINE:
            token_type = TokenType.NEWLINE
        elif kind == tokenize.INDENT:
            token_type = TokenType.INDENT
        elif kind == tokenize.DEDENT:
            token_type = TokenType.DEDENT
        else:
            token_type = TokenType.OP

        token = Token(token_type, text, item.start[0], item.start[1],
                      item.end[0], item.end[1])

        if token_type == TokenType.FSTRING:
            # Whole-literal form: no pre-lexed fields, the parser re-lexes it.
            token.extra = {"raw": text, "fields": None}
        return token

    # -- f-strings

    def _collapse_fstring(self, raw, index):
        """Gather one f-string into a single token.

        Returns (token, index just past the f-string).  The token carries the
        literal's exact source text plus, for every ``{...}`` field, the tokens
        of the expression inside it and the span it occupies.  The code
        generator regenerates the expressions from their AST and leaves the
        literal text between them untouched, which is the only correct thing to
        do with the contents of a string.
        """
        start = raw[index]
        start_offset = self._offset(start.start)
        index += 1  # past our own FSTRING_START

        bracket_depth = 0
        fields = []
        field = None

        while index < len(raw):
            item = raw[index]

            # A nested f-string inside one of our fields is collapsed whole by
            # recursion, so this loop only ever sees its own structure.
            if item.type == _FSTRING_START:
                nested, index = self._collapse_fstring(raw, index)
                if field is not None and field["spec"] is None:
                    field["tokens"].append(nested)
                    if field["start"] is None:
                        field["start"] = self._offset((nested.line, nested.column))
                    field["end"] = self._offset((nested.end_line, nested.end_column))
                continue

            if item.type == _FSTRING_END:
                end_offset = self._offset(item.end)
                token = Token(
                    TokenType.FSTRING,
                    self.source[start_offset:end_offset],
                    start.start[0], start.start[1], item.end[0], item.end[1])
                token.extra = {
                    "raw": self.source[start_offset:end_offset],
                    "start": start_offset,
                    "fields": fields,
                }
                return token, index + 1

            if field is None:
                if item.type == tokenize.OP and item.string == "{":
                    field = {"tokens": [], "start": None, "end": None,
                             "conversion": None, "spec": None}
                    bracket_depth = 0
                index += 1
                continue

            # Inside a replacement field.
            if item.type == tokenize.OP and item.string in "([{":
                bracket_depth += 1
            elif item.type == tokenize.OP and item.string in ")]}":
                if item.string == "}" and bracket_depth == 0:
                    fields.append(self._finish_field(field))
                    field = None
                    index += 1
                    continue
                bracket_depth -= 1
            elif (bracket_depth == 0 and item.type == tokenize.OP
                    and item.string in ("!", ":") and field["spec"] is None):
                # `!r` conversion or `:spec` format specifier: the expression
                # has ended and the rest is presentation, not code.
                field["spec"] = True
                index += 1
                continue

            if field["spec"] is None:
                field["tokens"].append(self._convert(item))
                if field["start"] is None:
                    field["start"] = self._offset(item.start)
                field["end"] = self._offset(item.end)
            index += 1

        raise WppSyntaxError(
            "this f-string is never closed",
            line=start.start[0], column=start.start[1],
            source_line=self._text_of(start.start[0]))

    def _finish_field(self, field):
        field.pop("spec", None)
        return field

    # -- helpers

    def _offset(self, position):
        """Absolute offset in the source for a (line, column) pair."""
        line, column = position
        return self._line_starts[line - 1] + column

    def _text_of(self, line):
        if line and 1 <= line <= len(self.lines):
            return self.lines[line - 1]
        return None


def _is_fstring_literal(text):
    """Does this whole-literal string token carry an f prefix?"""
    prefix = text[:3].lower()
    for char in prefix:
        if char in "\"'":
            break
        if char == "f":
            return True
    return False
