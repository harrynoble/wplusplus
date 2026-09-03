"""Translation behaviour: keyword mapping, word boundaries and literal safety.

These tests describe what translation must *mean*, not how the generated text
is laid out.  Since v1.2 the Python comes out of a code generator walking an
AST rather than out of a regular expression, so whitespace and redundant
parentheses are the generator's business; what matters is that the Python means
the right thing.  So each check compares the parsed Python, which is exactly the
comparison the old text equality was standing in for.

tests/test_compiler_equivalence.py backs this up from the other side: it
confirms the compiler agrees with the pre-v1.2 regex translator on every
program in the repository.
"""

import ast
import unittest

from wpplang import KEYWORDS, translate


def python_meaning(source):
    """The parsed form of some Python, ignoring layout and spare brackets."""
    return ast.dump(ast.parse(source))


class TranslationTestCase(unittest.TestCase):
    def assertTranslates(self, wpp, python, message=None):
        """The W++ must compile to Python that means what `python` means."""
        self.assertEqual(python_meaning(translate(wpp)), python_meaning(python),
                         message or wpp)

    def assertUnchanged(self, source):
        """This source must survive translation with its meaning intact."""
        self.assertTranslates(source, source)


# Every keyword, in a context where it is the word being tested.  Standalone
# words are not programs - `dip` on its own is a `break` outside a loop - so
# each one is exercised where it actually belongs.
KEYWORD_PROGRAMS = {
    "cook": ("cook f():\n    yap(1)\n", "def f():\n    print(1)\n"),
    "spill": ("cook f():\n    spill 7\n", "def f():\n    return 7\n"),
    "yap": ('yap("hi")\n', 'print("hi")\n'),
    "dm": ('x = dm("? ")\n', 'x = input("? ")\n'),
    "bodycount": ("n = bodycount([1, 2])\n", "n = len([1, 2])\n"),
    "bet": ("bet 1:\n    yap(1)\n", "if 1:\n    print(1)\n"),
    "plotwist": ("bet 1:\n    yap(1)\nplotwist 2:\n    yap(2)\n",
                 "if 1:\n    print(1)\nelif 2:\n    print(2)\n"),
    "nah": ("bet 1:\n    yap(1)\nnah:\n    yap(2)\n",
            "if 1:\n    print(1)\nelse:\n    print(2)\n"),
    "spam": ("spam i in range(3):\n    yap(i)\n",
             "for i in range(3):\n    print(i)\n"),
    "grind": ("grind 0:\n    yap(1)\n", "while 0:\n    print(1)\n"),
    "dip": ("spam i in range(3):\n    dip\n", "for i in range(3):\n    break\n"),
    "skrrt": ("spam i in range(3):\n    skrrt\n",
              "for i in range(3):\n    continue\n"),
    "nocap": ("x = nocap\n", "x = True\n"),
    "cap": ("x = cap\n", "x = False\n"),
    "npc": ("x = npc\n", "x = None\n"),
    "squad": ("x = squad([1])\n", "x = list([1])\n"),
    "tea": ("x = tea(a=1)\n", "x = dict(a=1)\n"),
    "cult": ("x = cult([1])\n", "x = set([1])\n"),
    "range": ("x = range(3)\n", "x = range(3)\n"),
}


class KeywordTranslationTests(TranslationTestCase):
    """Every entry in the Official Dictionary must translate."""

    def test_every_keyword_translates_in_its_own_context(self):
        for word in KEYWORDS:
            wpp, python = KEYWORD_PROGRAMS[word]
            with self.subTest(keyword=word):
                self.assertTranslates(wpp, python)

    def test_every_keyword_is_covered_by_a_program(self):
        self.assertEqual(set(KEYWORD_PROGRAMS), set(KEYWORDS))

    def test_value_keywords_translate_in_an_expression(self):
        for word in ("nocap", "cap", "npc", "squad", "tea", "cult", "range",
                     "bodycount", "dm", "yap"):
            with self.subTest(keyword=word):
                self.assertTranslates(
                    "x = {}\n".format(word), "x = {}\n".format(KEYWORDS[word]))

    def test_dictionary_matches_the_spec(self):
        self.assertEqual(
            KEYWORDS,
            {
                "cook": "def",
                "spill": "return",
                "yap": "print",
                "dm": "input",
                "bodycount": "len",
                "bet": "if",
                "plotwist": "elif",
                "nah": "else",
                "spam": "for",
                "grind": "while",
                "dip": "break",
                "skrrt": "continue",
                "nocap": "True",
                "cap": "False",
                "npc": "None",
                "squad": "list",
                "tea": "dict",
                "cult": "set",
                "range": "range",
            },
        )


class WordBoundaryTests(TranslationTestCase):
    """Keywords are words, not substrings."""

    def test_identifier_with_keyword_prefix_survives(self):
        self.assertUnchanged("cookie = 10\n")

    def test_identifier_with_keyword_suffix_survives(self):
        self.assertUnchanged("recap = 1\n")

    def test_identifier_containing_keyword_survives(self):
        self.assertUnchanged("scrapyard = 1\n")

    def test_underscored_identifier_survives(self):
        self.assertUnchanged("cap_rate = bet_size\n")

    def test_longer_keyword_wins_over_shorter_one(self):
        # `nocap` must not be read as `no` + `cap`.
        self.assertTranslates("x = nocap\n", "x = True\n")

    def test_attribute_access_is_not_a_keyword(self):
        self.assertUnchanged("shopping.cart.dip()\n")

    def test_keyword_like_argument_name_survives(self):
        self.assertUnchanged("f(cap_size=1, bet_on=2)\n")

    def test_keyword_surrounded_by_punctuation_translates(self):
        self.assertTranslates("yap(bodycount([1]))\n", "print(len([1]))\n")

    def test_a_keyword_cannot_be_a_keyword_argument_name(self):
        # `f(bet=1)` would have to become `f(if=1)`. The compiler says so
        # rather than emitting Python that cannot parse.
        with self.assertRaises(SyntaxError) as caught:
            translate("f(bet=1)\n")
        self.assertIn("W++ keyword", str(caught.exception))


class LiteralSafetyTests(TranslationTestCase):
    """Strings and comments are data, not code."""

    def test_double_quoted_string_is_untouched(self):
        self.assertTranslates('yap("cook")\n', 'print("cook")\n')

    def test_single_quoted_string_is_untouched(self):
        self.assertTranslates("yap('spill the tea')\n", "print('spill the tea')\n")

    def test_every_keyword_inside_a_string_is_untouched(self):
        words = " ".join(KEYWORDS)
        self.assertTranslates('yap("{}")\n'.format(words),
                              'print("{}")\n'.format(words))

    def test_triple_quoted_string_is_untouched(self):
        self.assertUnchanged('x = """\ncook spill\n"""\n')

    def test_comment_is_untouched(self):
        # The comment does not survive into the generated Python - comments are
        # not code - but it must not change what the code means either.
        self.assertTranslates("x = 1  # cook yap bet\n", "x = 1\n")

    def test_escaped_quote_inside_string(self):
        self.assertTranslates(r'yap("she said \"cook\"")' + "\n",
                              r'print("she said \"cook\"")' + "\n")

    def test_hash_inside_string_does_not_start_a_comment(self):
        self.assertTranslates('yap("# cook")\n', 'print("# cook")\n')

    def test_quote_inside_comment_does_not_start_a_string(self):
        self.assertTranslates("yap(1)  # it's cook\n", "print(1)\n")

    def test_raw_string_is_untouched(self):
        self.assertTranslates(r'yap(r"\cook")' + "\n", r'print(r"\cook")' + "\n")

    def test_fstring_text_is_untouched_but_fields_translate(self):
        self.assertTranslates('yap(f"cook: {bodycount(x)}")\n',
                              'print(f"cook: {len(x)}")\n')

    def test_fstring_escaped_braces(self):
        self.assertTranslates('yap(f"{{cook}}")\n', 'print(f"{{cook}}")\n')

    def test_unterminated_string_is_reported(self):
        with self.assertRaises(SyntaxError):
            translate('yap("oops\n')


class StructureTests(TranslationTestCase):
    """Indentation and line numbering must survive translation."""

    def test_indentation_structure_is_preserved(self):
        self.assertTranslates(
            "cook f():\n    bet nocap:\n        spill 1\n",
            "def f():\n    if True:\n        return 1\n")

    def test_tabs_are_accepted(self):
        # The generator writes spaces; what matters is the nesting it produces.
        self.assertTranslates("cook f():\n\tspill 1\n", "def f():\n    return 1\n")

    def test_statements_keep_their_line_numbers(self):
        # The generator lines its output up with the source, which is what lets
        # a runtime error be reported against the W++ line.
        source = 'yap(1)\n# cook\nx = """\ncook\n"""\nyap(2)\n'
        generated = translate(source)
        tree = ast.parse(generated)
        self.assertEqual([node.lineno for node in tree.body], [1, 3, 6])

    def test_empty_source(self):
        self.assertEqual(translate("").strip(), "")

    def test_blank_and_comment_only_source(self):
        self.assertEqual(translate("\n# just a comment\n\n").strip(), "")


if __name__ == "__main__":
    unittest.main()
