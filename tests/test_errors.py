"""Skill Issue Protocol tests: exact wording, correct mapping, useful context."""

import io
import unittest
from contextlib import redirect_stdout

from wpplang import SKILL_ISSUES, format_skill_issue, run_source, skill_issue_message


def run_quietly(source):
    """Run W++ source, swallow its stdout, return the Result."""
    with redirect_stdout(io.StringIO()):
        return run_source(source, "test.wpp")


class SpecWordingTests(unittest.TestCase):
    """The messages are fixed by the spec and must match it character for character."""

    def test_official_messages(self):
        self.assertEqual(
            SKILL_ISSUES,
            {
                "SyntaxError": "Negative Aura: Bro forgot how to type (SyntaxError)",
                "NameError": "Bro is making up words now (NameError)",
                "TypeError": "Oil up bro, you can't combine those (TypeError)",
                "IndexError": "Blud thinks he has more items than he does (IndexError)",
                "ZeroDivisionError": "Bro just broke the matrix (ZeroDivisionError)",
                "IndentationError": "Your spaces are looking a little sus (IndentationError)",
                "KeyboardInterrupt": "Go touch grass, you've been looping forever (KeyboardInterrupt)",
            },
        )

    def test_report_starts_with_the_siren_and_the_message(self):
        report = format_skill_issue(NameError("x"), "test.wpp", ["yap(x)"])
        self.assertTrue(report.startswith("\U0001f6a8 " + SKILL_ISSUES["NameError"]))


class MappingTests(unittest.TestCase):
    """Each Python exception reaches its W++ message."""

    def test_name_error(self):
        result = run_quietly("yap(mystery_meat)")
        self.assertIn(SKILL_ISSUES["NameError"], result.error_report)

    def test_type_error(self):
        result = run_quietly('yap("a" + 1)')
        self.assertIn(SKILL_ISSUES["TypeError"], result.error_report)

    def test_index_error(self):
        result = run_quietly("s = [1]\nyap(s[9])")
        self.assertIn(SKILL_ISSUES["IndexError"], result.error_report)

    def test_zero_division_error(self):
        result = run_quietly("yap(1 / 0)")
        self.assertIn(SKILL_ISSUES["ZeroDivisionError"], result.error_report)

    def test_syntax_error(self):
        result = run_quietly("cook f(:")
        self.assertIn(SKILL_ISSUES["SyntaxError"], result.error_report)

    def test_indentation_error(self):
        result = run_quietly("cook f():\n  yap(1)\n     yap(2)")
        self.assertIn(SKILL_ISSUES["IndentationError"], result.error_report)

    def test_indentation_error_is_not_reported_as_syntax_error(self):
        # IndentationError subclasses SyntaxError, so lookup order matters.
        result = run_quietly("yap(1)\n    yap(2)")
        self.assertIn(SKILL_ISSUES["IndentationError"], result.error_report)
        self.assertNotIn(SKILL_ISSUES["SyntaxError"], result.error_report)

    def test_keyboard_interrupt(self):
        self.assertEqual(
            skill_issue_message(KeyboardInterrupt()),
            SKILL_ISSUES["KeyboardInterrupt"],
        )

    def test_keyboard_interrupt_during_a_program(self):
        result = run_quietly("raise KeyboardInterrupt")
        self.assertIn(SKILL_ISSUES["KeyboardInterrupt"], result.error_report)
        self.assertEqual(result.exit_code, 130)

    def test_subclass_maps_to_its_parent_message(self):
        # ZeroDivisionError's siblings still land somewhere sensible.
        self.assertEqual(
            skill_issue_message(FloatingPointError()),
            "Unspecified skill issue (FloatingPointError)",
        )

    def test_unmapped_exception_gets_a_generic_message(self):
        result = run_quietly("t = tea()\nyap(t['nope'])")
        self.assertIn("Unspecified skill issue (KeyError)", result.error_report)


class ContextTests(unittest.TestCase):
    """Reports point at the offending W++ line."""

    def test_runtime_error_reports_the_right_line(self):
        result = run_quietly("yap(1)\nyap(2)\nyap(broken)")
        self.assertIn("line 3", result.error_report)
        self.assertIn("yap(broken)", result.error_report)

    def test_error_inside_a_function_reports_the_function_body(self):
        result = run_quietly("cook boom():\n    spill 1 / 0\n\nboom()")
        self.assertIn("line 2", result.error_report)
        self.assertIn("spill 1 / 0", result.error_report)

    def test_syntax_error_reports_the_right_line(self):
        result = run_quietly("yap(1)\nyap(2)\ncook f(:")
        self.assertIn("line 3", result.error_report)

    def test_report_names_the_source_file(self):
        result = run_quietly("yap(nope)")
        self.assertIn("test.wpp", result.error_report)

    def test_output_before_the_error_is_kept(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run_source('yap("made it")\nyap(nope)', "test.wpp")
        self.assertEqual(buffer.getvalue(), "made it\n")


if __name__ == "__main__":
    unittest.main()
