"""The AST compiler must agree with the translator it replaced.

Both the pre-v1.2 regex translator (kept in tests/reference_translator.py) and
the v1.2 compiler target Python, so for any valid W++ program the two must
produce Python that *parses to the same tree*.  Comparing parsed trees rather
than text ignores layout and redundant brackets, which are the code generator's
business, and catches anything that would actually change behaviour.

This is the check that showed the refactor was safe: it runs over every example
in the repository and every program the rest of the suite exercises.
"""

import ast
import glob
import os
import unittest

from wpplang import translate
from wpplang.compiler import compile_source

from . import reference_translator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def meaning(python_source):
    """The parsed form of some Python, ignoring layout."""
    return ast.dump(ast.parse(python_source))


# A spread of programs covering every construct the language supports.  Kept
# here as text so a failure names the construct rather than a file.
PROGRAMS = {
    "hello": 'yap("Hello world")\n',
    "variables": "x = 10\ny = x + 1\nyap(x, y)\n",
    "chained assignment": "a = b = 2\na, b = b, a\nyap(a, b)\n",
    "augmented": "x = 1\nx += 2\nx *= 3\nyap(x)\n",
    "conditions": "x = 9\nbet x > 5:\n    yap(1)\nnah:\n    yap(2)\n",
    "elif chain": ("bet 0:\n    yap(1)\nplotwist 0:\n    yap(2)\n"
                   "plotwist 1:\n    yap(3)\nnah:\n    yap(4)\n"),
    "nested conditions": ("bet 1:\n    bet 0:\n        yap(1)\n    nah:\n"
                          "        yap(2)\n"),
    "function": "cook add(a, b):\n    spill a + b\n\nyap(add(1, 2))\n",
    "defaults": "cook f(a, b=2, *rest, **named):\n    spill a\n\nyap(f(1))\n",
    "decorated": ("cook deco(fn):\n    spill fn\n\n@deco\ncook g():\n"
                  "    spill 1\n\nyap(g())\n"),
    "for loop": "spam i in range(5):\n    yap(i)\n",
    "for else": "spam i in range(2):\n    yap(i)\nnah:\n    yap(9)\n",
    "while loop": "n = 2\ngrind n > 0:\n    n -= 1\nyap(n)\n",
    "while else": "n = 0\ngrind n < 1:\n    n += 1\nnah:\n    yap(7)\n",
    "break continue": ("spam i in range(9):\n    bet i == 1:\n        skrrt\n"
                       "    bet i > 3:\n        dip\n    yap(i)\n"),
    "loop else with inner if": ("spam n in [1, 2]:\n    bet n == 5:\n"
                                "        dip\nnah:\n    yap(\"none\")\n"),
    "lists": "s = squad([3, 1])\ns.append(2)\nyap(sorted(s), s[0], s[-1], s[0:2])\n",
    "dicts": 't = tea(a=1)\nt["b"] = 2\nyap(t["a"], t.get("z", 0), bodycount(t))\n',
    "sets": "c = cult([1, 1, 2])\nyap(sorted(c), bodycount(c))\n",
    "literals": "yap([1], (1,), {1}, {1: 2}, ())\n",
    "booleans and null": "yap(nocap, cap, npc, nocap and cap, not npc)\n",
    "comparisons": "x = 5\nyap(1 < x < 10, x == 5, x != 4, x is npc, x in [5])\n",
    "arithmetic": "yap(7 + 2 * 3, 7 // 2, 7 % 2, 2 ** 8, -7 // 2, ~1)\n",
    "bitwise": "yap(6 & 3, 6 | 3, 6 ^ 3, 6 << 1, 6 >> 1)\n",
    "ternary": 'yap("y" bet 1 nah "n")\n',
    "comprehensions": ("yap([i spam i in range(4) bet i % 2 == 0])\n"
                       "yap({i: i spam i in range(2)})\n"
                       "yap(sorted({i spam i in range(2)}))\n"
                       "yap(sum(i spam i in range(4)))\n"),
    "nested comprehension": "yap([[c spam c in range(2)] spam r in range(2)])\n",
    "lambda": "f = lambda n, m=2: n * m\nyap(f(3))\n",
    "strings with keywords": 'yap("cook bet spill yap")\n',
    "fstrings": 'x = 2\nyap(f"{x} and {bodycount([1])} and {{brace}} and {x:>3}")\n',
    "nested fstring": 'i = 1\nyap(f"a {f\'b {i}\'}")\n',
    "input": 'name = dm("who? ")\nyap(name)\n',
    "class": ("class Dog:\n    cook __init__(self, n):\n        self.name = n\n"
              "    cook speak(self):\n        spill \"woof\"\n\n"
              "yap(Dog(\"d\").speak())\n"),
    "inheritance": ("class A:\n    cook go(self):\n        spill 1\n\n"
                    "class B(A):\n    cook go(self):\n        spill super().go() + 1\n\n"
                    "yap(B().go())\n"),
    "try": ("try:\n    yap(1)\nexcept ValueError as e:\n    yap(e)\nnah:\n"
            "    yap(2)\nfinally:\n    yap(3)\n"),
    "raise assert": ("try:\n    raise ValueError(\"x\")\nexcept ValueError:\n"
                     "    yap(1)\nassert 1, \"ok\"\n"),
    "with": ("class C:\n    cook __enter__(self):\n        spill self\n"
             "    cook __exit__(self, *a):\n        spill cap\n\n"
             "with C() as c:\n    yap(1)\n"),
    "imports": "import math\nfrom math import sqrt as root\nyap(math.pi > 3, root(4))\n",
    "generators": ("cook g():\n    yield 1\n    yield from [2]\n\nyap(squad(g()))\n"),
    "scope": ("total = 0\ncook add():\n    global total\n    total += 1\n\n"
              "add()\nyap(total)\n"),
    "closure": ("cook outer():\n    n = 0\n    cook inner():\n        nonlocal n\n"
                "        n += 1\n        spill n\n    spill inner\n\n"
                "yap(outer()())\n"),
    "walrus": "items = [1, 2]\nbet (n := bodycount(items)) > 1:\n    yap(n)\n",
    "match": ("cook f(v):\n    match v:\n        case 0:\n            spill \"z\"\n"
              "        case [_, _]:\n            spill \"p\"\n"
              "        case _:\n            spill \"o\"\n\nyap(f(0), f([1, 2]))\n"),
    "delete": "d = tea(a=1)\ndel d[\"a\"]\nyap(d)\n",
    "slices": "s = squad(range(9))\nyap(s[::2], s[1:4], s[::-1], s[-2:])\n",
    "starred": "a, *rest = [1, 2, 3]\nyap(a, rest, [*rest, 4], {**tea(a=1)})\n",
    "semicolons": "a = 1; b = 2\nyap(a, b)\n",
    "one line body": "bet 1: yap(1)\n",
    "keyword attributes": ("class B:\n    cook __init__(self):\n"
                           "        self.cap = 1\n        self.range = 2\n\n"
                           "b = B()\nyap(b.cap, b.range)\n"),
    "identifiers like keywords": ("cookie = 1\nrecap = 2\ncap_rate = 3\n"
                                  "spamalot = 4\nyap(cookie + recap + cap_rate + spamalot)\n"),
    "comments": "# cook bet yap\nyap(1)  # spill nah\n",
}


def repository_programs():
    """Every example shipped with the project."""
    found = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "examples", "*.wpp"))):
        with open(path, encoding="utf-8") as handle:
            found[os.path.basename(path)] = handle.read()
    return found


class EquivalenceTests(unittest.TestCase):
    def assertSameMeaning(self, name, source):
        reference = reference_translator.translate(source)
        try:
            expected = meaning(reference)
        except SyntaxError:  # pragma: no cover - guards a bad fixture
            self.fail("{}: the reference translator produced invalid Python"
                      .format(name))
        actual = meaning(translate(source))
        self.assertEqual(
            actual, expected,
            "{}: the compiler and the reference translator disagree\n"
            "--- compiler ---\n{}\n--- reference ---\n{}".format(
                name, translate(source), reference))

    def test_every_construct_matches_the_reference(self):
        for name, source in PROGRAMS.items():
            with self.subTest(program=name):
                self.assertSameMeaning(name, source)

    def test_every_shipped_example_matches_the_reference(self):
        examples = repository_programs()
        self.assertGreaterEqual(len(examples), 5)
        for name, source in examples.items():
            with self.subTest(example=name):
                self.assertSameMeaning(name, source)

    def test_the_reference_is_not_on_the_execution_path(self):
        """Nothing the language ships may import the old translator."""
        import wpplang
        package = os.path.dirname(os.path.abspath(wpplang.__file__))
        offenders = []
        for folder, _dirs, files in os.walk(package):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    if "reference_translator" in handle.read():
                        offenders.append(path)
        self.assertEqual(offenders, [])


class GeneratedPythonTests(unittest.TestCase):
    """The generated Python must be valid, and say what it means."""

    def test_generated_python_always_parses(self):
        for name, source in dict(PROGRAMS, **repository_programs()).items():
            with self.subTest(program=name):
                ast.parse(translate(source))

    def test_no_wpp_keyword_survives_into_the_python(self):
        from wpplang import KEYWORDS

        # `range` maps to itself, so seeing it in the output proves nothing.
        renamed = {word for word, target in KEYWORDS.items() if word != target}

        for name, source in PROGRAMS.items():
            tree = ast.parse(translate(source))
            for node in ast.walk(tree):
                # A W++ keyword may legitimately appear as an attribute name
                # (`self.cap`) or inside a string, but never as a bare name.
                if isinstance(node, ast.Name) and node.id in renamed:
                    self.fail("{}: `{}` reached the Python untranslated".format(
                        name, node.id))


if __name__ == "__main__":
    unittest.main()
