"""Execution tests: run real W++ programs and check what they print."""

import io
import unittest
from contextlib import redirect_stdout

from wpplang import run_source


def run(source, stdin=None):
    """Run W++ source and return (captured stdout, Result)."""
    buffer = io.StringIO()
    original_input = __builtins__["input"] if isinstance(__builtins__, dict) else __builtins__.input

    if stdin is not None:
        answers = iter(stdin)

        def fake_input(prompt=""):
            print(prompt, end="")
            return next(answers)

        _set_builtin_input(fake_input)
    try:
        with redirect_stdout(buffer):
            result = run_source(source, "test.wpp")
    finally:
        if stdin is not None:
            _set_builtin_input(original_input)
    return buffer.getvalue(), result


def _set_builtin_input(func):
    if isinstance(__builtins__, dict):
        __builtins__["input"] = func
    else:
        __builtins__.input = func


class OutputTests(unittest.TestCase):
    def test_hello_world(self):
        out, result = run('yap("Hello world")')
        self.assertEqual(out, "Hello world\n")
        self.assertTrue(result.ok)

    def test_multiple_arguments(self):
        out, _ = run('yap("a", 1, nocap)')
        self.assertEqual(out, "a 1 True\n")

    def test_input(self):
        out, result = run('name = dm("Who? ")\nyap(name)', stdin=["Claude"])
        self.assertEqual(out, "Who? Claude\n")
        self.assertTrue(result.ok)


class ExpressionTests(unittest.TestCase):
    def test_arithmetic_and_modulo(self):
        out, _ = run("yap(7 // 2, 7 % 2, 2 ** 3, 7 / 2)")
        self.assertEqual(out, "3 1 8 3.5\n")

    def test_booleans_and_none(self):
        out, _ = run("yap(nocap, cap, npc)")
        self.assertEqual(out, "True False None\n")

    def test_variables_and_reassignment(self):
        out, _ = run("x = 1\nx = x + 41\nyap(x)")
        self.assertEqual(out, "42\n")

    def test_string_methods_still_work(self):
        out, _ = run('yap("wpp".upper())')
        self.assertEqual(out, "WPP\n")


class FunctionTests(unittest.TestCase):
    def test_function_and_return(self):
        out, _ = run("cook double(n):\n    spill n * 2\n\nyap(double(21))")
        self.assertEqual(out, "42\n")

    def test_default_arguments(self):
        out, _ = run("cook greet(who='world'):\n    spill 'hi ' + who\n\nyap(greet())")
        self.assertEqual(out, "hi world\n")

    def test_recursion(self):
        source = (
            "cook fact(n):\n"
            "    bet n <= 1:\n"
            "        spill 1\n"
            "    spill n * fact(n - 1)\n"
            "\n"
            "yap(fact(5))"
        )
        out, _ = run(source)
        self.assertEqual(out, "120\n")


class ConditionalTests(unittest.TestCase):
    def test_if_elif_else(self):
        source = (
            "cook grade(n):\n"
            "    bet n > 90:\n"
            "        spill 'W'\n"
            "    plotwist n > 50:\n"
            "        spill 'mid'\n"
            "    nah:\n"
            "        spill 'L'\n"
            "\n"
            "yap(grade(95), grade(60), grade(10))"
        )
        out, _ = run(source)
        self.assertEqual(out, "W mid L\n")

    def test_nested_conditionals(self):
        source = (
            "cook check(a, b):\n"
            "    bet a:\n"
            "        bet b:\n"
            "            spill 'both'\n"
            "        nah:\n"
            "            spill 'just a'\n"
            "    spill 'neither'\n"
            "\n"
            "yap(check(nocap, nocap), check(nocap, cap), check(cap, cap))"
        )
        out, _ = run(source)
        self.assertEqual(out, "both just a neither\n")


class LoopTests(unittest.TestCase):
    def test_for_over_range(self):
        out, _ = run("spam i in range(3):\n    yap(i)")
        self.assertEqual(out, "0\n1\n2\n")

    def test_while_with_break(self):
        out, _ = run("i = 0\ngrind nocap:\n    bet i == 2:\n        dip\n    yap(i)\n    i = i + 1")
        self.assertEqual(out, "0\n1\n")

    def test_continue(self):
        out, _ = run("spam i in range(4):\n    bet i % 2 == 0:\n        skrrt\n    yap(i)")
        self.assertEqual(out, "1\n3\n")

    def test_nested_loops(self):
        out, _ = run("spam i in range(2):\n    spam j in range(2):\n        yap(i, j)")
        self.assertEqual(out, "0 0\n0 1\n1 0\n1 1\n")


class CollectionTests(unittest.TestCase):
    def test_list(self):
        out, _ = run("s = squad([3, 1, 2])\nyap(sorted(s), bodycount(s))")
        self.assertEqual(out, "[1, 2, 3] 3\n")

    def test_list_literal_and_indexing(self):
        out, _ = run("s = [10, 20, 30]\nyap(s[0], s[-1], s[1:])")
        self.assertEqual(out, "10 30 [20, 30]\n")

    def test_dict(self):
        out, _ = run("t = tea(a=1)\nt['b'] = 2\nyap(t['a'], t['b'], bodycount(t))")
        self.assertEqual(out, "1 2 2\n")

    def test_set(self):
        out, _ = run("c = cult([1, 1, 2])\nyap(sorted(c), bodycount(c))")
        self.assertEqual(out, "[1, 2] 2\n")

    def test_comprehension(self):
        out, _ = run("yap([i * 2 spam i in range(3)])")
        self.assertEqual(out, "[0, 2, 4]\n")


class ExtraGlobalsTests(unittest.TestCase):
    """`extra_globals` shadows builtins, which is how the playground makes
    dm() interactive without this module knowing anything about the web."""

    def test_supplied_input_shadows_the_builtin(self):
        asked = []

        def fake_input(prompt=""):
            asked.append(prompt)
            return "from the caller"

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = run_source(
                'yap(dm("prompt: "))', "test.wpp", extra_globals={"input": fake_input}
            )
        self.assertTrue(result.ok)
        self.assertEqual(asked, ["prompt: "])
        self.assertEqual(buffer.getvalue(), "from the caller\n")

    def test_extra_globals_are_optional(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = run_source('yap("no extras")', "test.wpp")
        self.assertTrue(result.ok)
        self.assertEqual(buffer.getvalue(), "no extras\n")


class ExitCodeTests(unittest.TestCase):
    def test_success_exit_code(self):
        _, result = run("yap(1)")
        self.assertEqual(result.exit_code, 0)

    def test_failure_exit_code(self):
        _, result = run("yap(nope)")
        self.assertEqual(result.exit_code, 1)

    def test_explicit_exit_code_is_respected(self):
        _, result = run("import sys\nsys.exit(3)")
        self.assertEqual(result.exit_code, 3)
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
