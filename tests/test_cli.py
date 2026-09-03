"""End-to-end tests: the CLI and the official example programs from the spec."""

import os
import re
import subprocess
import sys
import unittest

from wpplang import KEYWORDS, translate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def wpp(*args, stdin=""):
    """Invoke `python wpp.py ...` and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "wpp.py"), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )


class OfficialExampleTests(unittest.TestCase):
    """The examples printed in the W++ spec, run verbatim."""

    def test_hello_world(self):
        done = wpp(os.path.join(EXAMPLES, "hello.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "Hello world")

    def test_vibe_check_w_ai(self):
        done = wpp(os.path.join(EXAMPLES, "vibe_check.wpp"), stdin="Claude\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Vibe check:  W AI", done.stdout)

    def test_vibe_check_mid(self):
        done = wpp(os.path.join(EXAMPLES, "vibe_check.wpp"), stdin="somebody else\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Vibe check:  Mid", done.stdout)

    def test_fizzbuzz(self):
        done = wpp(os.path.join(EXAMPLES, "fizzbuzz.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            done.stdout.split(),
            ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8",
             "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"],
        )

    def test_oops_example_reports_a_skill_issue(self):
        done = wpp(os.path.join(EXAMPLES, "oops.wpp"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("about to fumble", done.stdout)
        self.assertIn("Bro is making up words now", done.stderr)

    def test_collections_example(self):
        done = wpp(os.path.join(EXAMPLES, "collections.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("npc confirmed", done.stdout)


class KeywordTourTests(unittest.TestCase):
    """examples/keyword_tour.wpp must exercise the whole dictionary."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(EXAMPLES, "keyword_tour.wpp"), encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_every_keyword_is_exercised(self):
        # Compare against the translated Python with comments and strings
        # removed, so a keyword only counts when it was really translated.
        code = _strip_literals(translate(self.source))
        missing = [
            word for word, target in KEYWORDS.items()
            if not re.search(r"(?<![\w.])" + re.escape(target) + r"(?!\w)", code)
        ]
        self.assertEqual(missing, [], "keywords never exercised: {}".format(missing))

    def test_it_runs_and_prints_every_section(self):
        done = wpp(os.path.join(EXAMPLES, "keyword_tour.wpp"), stdin="Claude\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        for expected in (
            "numbers:    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]",
            "bodycount:  10",
            "countdown:  0",
            "flags:      [True, False, None]",
            "sum:        6",
            "gm, Claude",
        ):
            self.assertIn(expected, done.stdout)

    def test_it_falls_back_when_no_name_is_given(self):
        done = wpp(os.path.join(EXAMPLES, "keyword_tour.wpp"), stdin="\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("gm, anon", done.stdout)


def _strip_literals(code):
    """Remove comments and string literals from Python source."""
    without_strings = re.sub(
        r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"",
        "''",
        code,
    )
    return re.sub(r"#[^\n]*", "", without_strings)


class CommandLineTests(unittest.TestCase):
    def test_emit_prints_python_without_running(self):
        done = wpp("--emit", os.path.join(EXAMPLES, "hello.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), 'print("Hello world")')

    def test_ast_prints_the_wpp_tree(self):
        done = wpp("--ast", os.path.join(EXAMPLES, "vibe_check.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        # The tree describes W++ constructs, and carries positions.
        for expected in ("Program", "FunctionDeclaration", "IfStatement",
                         "ReturnStatement", "keyword='cook'", "@1:0"):
            self.assertIn(expected, done.stdout)
        # And no Python appears in it: the AST is not translated text.
        self.assertNotIn("def ", done.stdout)

    def test_tokens_prints_the_token_stream(self):
        done = wpp("--tokens", os.path.join(EXAMPLES, "hello.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("KEYWORD", done.stdout)
        self.assertIn("'yap'", done.stdout)
        # The whole string is one token, keywords inside it and all.
        self.assertIn("STRING", done.stdout)

    def test_ast_reports_a_bad_program_as_a_skill_issue(self):
        path = os.path.join(ROOT, "tests", "_ast_probe.wpp")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("cook dip(self):\n    spill 1\n")
        try:
            done = wpp("--ast", path)
            self.assertEqual(done.returncode, 1)
            self.assertNotIn("Traceback", done.stderr)
            self.assertIn("Bro forgot how to type", done.stderr)
        finally:
            os.remove(path)

    def test_keywords_table(self):
        done = wpp("--keywords")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("bodycount", done.stdout)
        self.assertIn("len", done.stdout)

    def test_emit_reports_a_refused_program_as_a_skill_issue(self):
        # Translation can reject a program; --emit must not leak a traceback.
        path = os.path.join(ROOT, "tests", "_reserved.wpp")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("cook dip(self):\n    spill 1\n")
        try:
            done = wpp("--emit", path)
            self.assertEqual(done.returncode, 1)
            self.assertNotIn("Traceback", done.stderr)
            self.assertIn("Bro forgot how to type", done.stderr)
            self.assertIn("'dip' is a W++ keyword", done.stderr)
            self.assertEqual(done.stdout, "")
        finally:
            os.remove(path)

    def test_missing_file_is_a_usage_error(self):
        done = wpp("does_not_exist.wpp")
        self.assertEqual(done.returncode, 2)
        self.assertIn("no such file", done.stderr)

    def test_no_arguments_is_a_usage_error(self):
        self.assertEqual(wpp().returncode, 2)

    def test_failing_program_exits_nonzero_and_reports_to_stderr(self):
        path = os.path.join(EXAMPLES, "hello.wpp")
        broken = os.path.join(os.path.dirname(path), "..", "tests", "_broken.wpp")
        with open(broken, "w", encoding="utf-8") as handle:
            handle.write("yap(nope)\n")
        try:
            done = wpp(broken)
            self.assertEqual(done.returncode, 1)
            self.assertIn("Bro is making up words now", done.stderr)
            self.assertEqual(done.stdout, "")
        finally:
            os.remove(broken)


if __name__ == "__main__":
    unittest.main()
