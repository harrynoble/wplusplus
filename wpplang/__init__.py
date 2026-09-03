"""W++ - a Gen Z programming language that compiles to Python.

Since v1.2 the language has a real frontend: a lexer, a parser, a W++ AST, a
semantic pass and a Python code generator, all under `wpplang.compiler`.

Public API:

    from wpplang import translate, compile_wpp, run_file, KEYWORDS
"""

from .errors import (
    SKILL_ISSUES,
    format_skill_issue,
    skill_issue_details,
    skill_issue_message,
)
from .keywords import CATEGORIES, KEYWORDS
from .runner import Result, run_file, run_source
from .translator import CompiledProgram, compile_wpp, translate, translate_file

__version__ = "1.1.0"

__all__ = [
    "CATEGORIES",
    "KEYWORDS",
    "Result",
    "SKILL_ISSUES",
    "__version__",
    "format_skill_issue",
    "run_file",
    "run_source",
    "skill_issue_details",
    "skill_issue_message",
    "CompiledProgram",
    "compile_wpp",
    "translate",
    "translate_file",
]
