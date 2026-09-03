"""W++ - a Gen Z programming language that translates to Python.

Public API:

    from wpplang import translate, run_file, KEYWORDS
"""

from .errors import (
    SKILL_ISSUES,
    format_skill_issue,
    skill_issue_details,
    skill_issue_message,
)
from .keywords import CATEGORIES, KEYWORDS
from .runner import Result, run_file, run_source
from .translator import translate, translate_code, translate_file

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
    "translate",
    "translate_code",
    "translate_file",
]
