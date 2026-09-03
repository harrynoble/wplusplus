"""W++ -> Python source translation.

W++ is Python with a different vocabulary, so translation is a single pass over
the source that swaps W++ keywords for their Python targets.  Two rules keep the
swap honest:

1. Keywords are matched as whole words (regex word boundaries), so ``cookie``
   and ``cap_rate`` are left alone.
2. String literals and comments are copied through verbatim, so
   ``yap("cook dinner")`` prints ``cook dinner`` and not ``def dinner``.

The translator never adds or removes newlines, so line N of the generated Python
is always line N of the .wpp file.  That 1:1 mapping is what lets the Skill Issue
Protocol point at the original W++ source.
"""

import re

from .keywords import KEYWORDS

# One alternation for every keyword, longest first so the regex engine prefers
# `nocap` over `cap` (the word boundaries already guarantee this, but being
# explicit makes the intent obvious).
_ALTERNATION = "|".join(
    re.escape(word) for word in sorted(KEYWORDS, key=len, reverse=True)
)

# `(?<![\w.])` is the word boundary plus one extra guard: a name after a dot is
# an attribute (`shopping.cart.dip`), never a keyword, so it must survive.
_KEYWORD_RE = re.compile(r"(?<![\w.])(" + _ALTERNATION + r")(?!\w)")

# Anything that ends a stretch of plain code: a comment, or the start of a string.
_INTERESTING_RE = re.compile(r"#|'''|\"\"\"|'|\"")

# A trailing whole word of 1-3 letters, i.e. a possible string prefix (f"...").
_PREFIX_RE = re.compile(r"(?<!\w)[A-Za-z]{1,3}$")

# The string prefixes Python actually accepts.  Anything else that happens to sit
# in front of a quote is ordinary code and must still be translated.
_STRING_PREFIXES = {"r", "u", "b", "f", "br", "rb", "fr", "rf"}


def translate_code(fragment):
    """Swap W++ keywords in a fragment that is known to contain no strings."""
    return _KEYWORD_RE.sub(lambda match: KEYWORDS[match.group(1)], fragment)


def translate(source):
    """Translate W++ source text into Python source text."""
    pieces = []
    pos = 0

    while True:
        match = _INTERESTING_RE.search(source, pos)
        if match is None:
            pieces.append(translate_code(source[pos:]))
            break

        code = source[pos:match.start()]

        # A comment runs to the end of the line and is never translated.
        if match.group() == "#":
            pieces.append(translate_code(code))
            end = source.find("\n", match.start())
            end = len(source) if end == -1 else end
            pieces.append(source[match.start():end])
            pos = end
            continue

        # A string literal may be introduced by a prefix (f, r, rb, ...).  That
        # prefix is part of the literal, so peel it off the code we translate.
        prefix = ""
        prefix_match = _PREFIX_RE.search(code)
        if prefix_match and prefix_match.group().lower() in _STRING_PREFIXES:
            prefix = prefix_match.group()
            code = code[:-len(prefix)]
        pieces.append(translate_code(code))

        quote = match.group()
        body_start = match.start() + len(quote)
        end, terminated = _find_string_end(source, body_start, quote)

        if not terminated:
            # Unterminated literal: emit it untouched and let Python raise the
            # SyntaxError, which the Skill Issue Protocol will translate.
            pieces.append(source[match.start():end])
            pos = end
            continue

        body = source[body_start:end - len(quote)]
        if "f" in prefix.lower():
            # Inside an f-string only the {...} replacement fields are code.
            body = _translate_fstring_body(body)
        pieces.append(prefix + quote + body + quote)
        pos = end

    return "".join(pieces)


def translate_file(path):
    """Read a .wpp file and return its Python translation."""
    with open(path, "r", encoding="utf-8") as handle:
        return translate(handle.read())


def _find_string_end(source, start, quote):
    """Locate the end of a string literal.

    Returns ``(index_just_past_the_closing_quote, terminated)``.  A backslash
    escapes the next character even in raw strings, because Python's tokenizer
    treats ``r"\\"`` as unterminated too.
    """
    index = start
    length = len(source)
    triple = len(quote) == 3

    while index < length:
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if not triple and char == "\n":
            return index, False
        if source.startswith(quote, index):
            return index + len(quote), True
        index += 1

    return length, False


def _translate_fstring_body(body):
    """Translate the ``{...}`` replacement fields of an f-string body."""
    pieces = []
    index = 0
    length = len(body)

    while index < length:
        char = body[index]

        # `{{` and `}}` are escaped literal braces, not a field.
        if char in "{}" and index + 1 < length and body[index + 1] == char:
            pieces.append(body[index:index + 2])
            index += 2
            continue

        if char == "{":
            depth = 1
            end = index + 1
            while end < length and depth:
                if body[end] == "{":
                    depth += 1
                elif body[end] == "}":
                    depth -= 1
                end += 1
            if depth:  # Unbalanced braces: leave the remainder alone.
                pieces.append(body[index:])
                break
            pieces.append("{" + translate(body[index + 1:end - 1]) + "}")
            index = end
            continue

        pieces.append(char)
        index += 1

    return "".join(pieces)
