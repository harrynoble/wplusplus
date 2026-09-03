"""The Official W++ Dictionary.

Straight from the W++ Language Spec v1.1.  This mapping is the single source of
truth for the language: everything else in the translator is driven by it, so
adding a keyword is a one-line change here.
"""

# W++ keyword -> Python target.  Order follows the spec's table.
KEYWORDS = {
    "cook": "def",          # Function declaration
    "spill": "return",      # Return statement
    "yap": "print",         # Console output
    "dm": "input",          # User input
    "bodycount": "len",     # Length / size
    "bet": "if",            # Primary conditional
    "plotwist": "elif",     # Secondary conditional
    "nah": "else",          # Fallback conditional
    "spam": "for",          # Iteration
    "grind": "while",       # Looping
    "dip": "break",         # Exit loop
    "skrrt": "continue",    # Skip iteration
    "nocap": "True",        # Boolean True
    "cap": "False",         # Boolean False
    "npc": "None",          # Null value
    "squad": "list",        # Array / list
    "tea": "dict",          # Dictionary / map
    "cult": "set",          # Unique set
    "range": "range",       # Sequence generator (identity mapping)
}

# What each keyword is for, used by `wpp.py --keywords`.
CATEGORIES = {
    "cook": "Function declaration",
    "spill": "Return statement",
    "yap": "Console Output",
    "dm": "User Input",
    "bodycount": "Length / Size",
    "bet": "Primary Conditional",
    "plotwist": "Secondary Conditional",
    "nah": "Fallback Conditional",
    "spam": "Iteration",
    "grind": "Looping",
    "dip": "Exit Loop",
    "skrrt": "Skip Iteration",
    "nocap": "Boolean True",
    "cap": "Boolean False",
    "npc": "Null Value",
    "squad": "Array / List",
    "tea": "Dictionary / Map",
    "cult": "Unique Set",
    "range": "Sequence Generator",
}
