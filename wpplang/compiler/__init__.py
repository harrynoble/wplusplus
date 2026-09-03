"""The W++ compiler frontend.

    W++ source
        -> lexer      (tokens, with line and column)
        -> parser     (a W++ AST)
        -> semantic   (W++ rules that need the whole tree)
        -> codegen    (Python source, plus a W++ line map)

Python is the execution target, not the language: nothing here rewrites W++
text into Python text.  The only place the two vocabularies meet is the
KEYWORDS table, which the code generator consults when it emits a construct.

The one public entry point is `compile_source`.
"""

from .codegen import SourceMap, generate
from .errors import WppError, WppSemanticError, WppSyntaxError
from .lexer import tokenize_source
from .parser import parse
from .semantic import validate

__all__ = [
    "CompiledProgram", "SourceMap", "WppError", "WppSemanticError",
    "WppSyntaxError", "compile_source", "generate", "parse", "tokenize_source",
    "validate",
]


class CompiledProgram:
    """The result of compiling W++: Python source, the AST, and the line map."""

    __slots__ = ("python", "ast", "source_map", "tokens")

    def __init__(self, python, ast, source_map, tokens=None):
        self.python = python
        self.ast = ast
        self.source_map = source_map
        self.tokens = tokens

    def wpp_line_for(self, python_line):
        """Which W++ line a generated Python line came from."""
        return self.source_map.wpp_line_for(python_line)


def compile_source(source, keep_tokens=False):
    """Compile W++ source to Python.

    Raises WppSyntaxError or WppSemanticError, both of which carry a W++ line
    and column and can be turned into a SyntaxError for the Skill Issue
    Protocol via `as_syntax_error()`.
    """
    tokens = tokenize_source(source)
    tree = parse(tokens, source)
    validate(tree, source)
    python, source_map = generate(tree)
    return CompiledProgram(python, tree, source_map,
                           tokens if keep_tokens else None)
