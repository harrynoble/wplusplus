"""End-to-end tests: the CLI and the official example programs from the spec."""

import os
import subprocess
import sys
import unittest

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


class CommandLineTests(unittest.TestCase):
    def test_emit_prints_python_without_running(self):
        done = wpp("--emit", os.path.join(EXAMPLES, "hello.wpp"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), 'print("Hello world")')

    def test_keywords_table(self):
        done = wpp("--keywords")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("bodycount", done.stdout)
        self.assertIn("len", done.stdout)

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
