"""Translation tests: keyword swaps, word boundaries and literal safety."""

import unittest

from wpplang import KEYWORDS, translate


class KeywordTranslationTests(unittest.TestCase):
    """Every entry in the Official Dictionary must translate."""

    def test_every_keyword_translates(self):
        for word, target in KEYWORDS.items():
            with self.subTest(keyword=word):
                self.assertEqual(translate(word), target)

    def test_every_keyword_translates_in_context(self):
        for word, target in KEYWORDS.items():
            with self.subTest(keyword=word):
                self.assertEqual(
                    translate("x = {} + 1".format(word)),
                    "x = {} + 1".format(target),
                )

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


class WordBoundaryTests(unittest.TestCase):
    """Keywords are words, not substrings."""

    def test_identifier_with_keyword_prefix_survives(self):
        self.assertEqual(translate("cookie = 10"), "cookie = 10")

    def test_identifier_with_keyword_suffix_survives(self):
        self.assertEqual(translate("recap = 1"), "recap = 1")

    def test_identifier_containing_keyword_survives(self):
        self.assertEqual(translate("scrapyard = 1"), "scrapyard = 1")

    def test_underscored_identifier_survives(self):
        self.assertEqual(translate("cap_rate = bet_size"), "cap_rate = bet_size")

    def test_longer_keyword_wins_over_shorter_one(self):
        # `nocap` must not be read as `no` + `cap`.
        self.assertEqual(translate("x = nocap"), "x = True")

    def test_attribute_access_is_not_a_keyword(self):
        self.assertEqual(translate("shopping.cart.dip()"), "shopping.cart.dip()")

    def test_keyword_like_argument_name_survives(self):
        self.assertEqual(translate("f(cap_size=1, bet_on=2)"), "f(cap_size=1, bet_on=2)")

    def test_keywords_are_reserved_words(self):
        # A bare keyword is always translated, wherever it appears - exactly as
        # `if` cannot be a parameter name in Python, `bet` cannot be one in W++.
        self.assertEqual(translate("f(bet=1)"), "f(if=1)")

    def test_keyword_surrounded_by_punctuation_translates(self):
        self.assertEqual(translate("yap(bodycount([1]))"), "print(len([1]))")


class LiteralSafetyTests(unittest.TestCase):
    """Strings and comments are data, not code."""

    def test_double_quoted_string_is_untouched(self):
        self.assertEqual(translate('yap("cook")'), 'print("cook")')

    def test_single_quoted_string_is_untouched(self):
        self.assertEqual(translate("yap('spill the tea')"), "print('spill the tea')")

    def test_triple_quoted_string_is_untouched(self):
        source = 'x = """\ncook spill\n"""'
        self.assertEqual(translate(source), source)

    def test_comment_is_untouched(self):
        self.assertEqual(translate("x = 1  # cook yap bet"), "x = 1  # cook yap bet")

    def test_escaped_quote_inside_string(self):
        self.assertEqual(translate(r'yap("she said \"cook\"")'), r'print("she said \"cook\"")')

    def test_hash_inside_string_does_not_start_a_comment(self):
        self.assertEqual(translate('yap("# cook")'), 'print("# cook")')

    def test_quote_inside_comment_does_not_start_a_string(self):
        self.assertEqual(translate("yap(1)  # it's cook"), "print(1)  # it's cook")

    def test_raw_string_is_untouched(self):
        self.assertEqual(translate(r'yap(r"\cook")'), r'print(r"\cook")')

    def test_fstring_text_is_untouched_but_fields_translate(self):
        self.assertEqual(
            translate('yap(f"cook: {bodycount(x)}")'),
            'print(f"cook: {len(x)}")',
        )

    def test_fstring_escaped_braces(self):
        self.assertEqual(translate('yap(f"{{cook}}")'), 'print(f"{{cook}}")')

    def test_unterminated_string_is_passed_through(self):
        # Invalid code must survive translation so Python can report the error.
        self.assertEqual(translate('yap("oops'), 'print("oops')


class ReservedWordTests(unittest.TestCase):
    """Translation refuses a keyword where only a name can go."""

    def test_definition_named_after_a_keyword_raises(self):
        with self.assertRaises(SyntaxError) as caught:
            translate("cook dip(self):\n    spill 1\n")
        self.assertIn("'dip' is a W++ keyword", str(caught.exception))

    def test_the_reported_line_is_the_definition(self):
        with self.assertRaises(SyntaxError) as caught:
            translate('yap("one")\nyap("two")\nclass nah:\n    pass\n')
        self.assertEqual(caught.exception.lineno, 3)

    def test_a_builtin_target_is_allowed(self):
        # `squad` becomes `list`, which is a name rather than a reserved word.
        self.assertEqual(translate("cook squad(x):"), "def list(x):")

    def test_ordinary_definitions_do_not_raise(self):
        self.assertEqual(translate("cook cookie(x):"), "def cookie(x):")
        self.assertEqual(translate("class Recap:"), "class Recap:")

    def test_a_keyword_inside_a_string_does_not_raise(self):
        self.assertEqual(translate('yap("cook dip():")'), 'print("cook dip():")')

    def test_a_keyword_in_a_comment_does_not_raise(self):
        self.assertEqual(translate("yap(1)  # cook dip():"), "print(1)  # cook dip():")


class StructureTests(unittest.TestCase):
    """Indentation and line numbering must survive translation."""

    def test_indentation_is_preserved(self):
        source = "cook f():\n    bet nocap:\n        spill 1\n"
        expected = "def f():\n    if True:\n        return 1\n"
        self.assertEqual(translate(source), expected)

    def test_tabs_are_preserved(self):
        self.assertEqual(translate("cook f():\n\tspill 1"), "def f():\n\treturn 1")

    def test_line_count_is_unchanged(self):
        source = "yap(1)\n# cook\nx = '''\ncook\n'''\nyap(2)\n"
        self.assertEqual(len(translate(source).splitlines()), len(source.splitlines()))

    def test_empty_source(self):
        self.assertEqual(translate(""), "")


if __name__ == "__main__":
    unittest.main()
