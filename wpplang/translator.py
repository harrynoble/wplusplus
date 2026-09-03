"""W++ -> Python translation.

This module is the stable front door.  Since v1.2 the work behind it is done by
a real compiler frontend rather than by rewriting text:

    W++ source
        -> wpplang.compiler.lexer      tokens, with line and column
        -> wpplang.compiler.parser     a W++ AST
        -> wpplang.compiler.semantic   W++ rules needing the whole tree
        -> wpplang.compiler.codegen    Python source + a W++ line map

`translate()` keeps the signature it always had, so the CLI, the playground and
the documentation builder did not have to change.  Callers that want more than
the generated text - the AST, or the line map for reporting errors against W++
source - should use `compile_wpp()` instead.
"""

from .compiler import CompiledProgram, compile_source
from .compiler.errors import WppError

__all__ = ["CompiledProgram", "compile_wpp", "translate", "translate_file"]


def compile_wpp(source, filename="<wpp>"):
    """Compile W++ source and return the CompiledProgram.

    Raises SyntaxError - carrying the W++ line, column and source line - if the
    program is not valid W++, so a frontend rejection is reported by the Skill
    Issue Protocol exactly like any other syntax error.
    """
    try:
        return compile_source(source)
    except WppError as error:
        raise error.as_syntax_error(filename) from None


def translate(source):
    """Translate W++ source text into Python source text."""
    return compile_wpp(source).python


def translate_file(path):
    """Read a .wpp file and return its Python translation."""
    with open(path, "r", encoding="utf-8") as handle:
        return translate(handle.read())
