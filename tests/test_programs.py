"""Whole-program tests: challenging W++ that must produce the right answer.

Everything here is a complete program with an exact expected output.  These are
the cases that go wrong when a translator is only "mostly" right: ternaries,
comprehensions, loop-else, f-strings, identifiers that merely look like
keywords, definitions named after keywords, and real algorithms whose answers
are easy to check.
"""

import io
import textwrap
import unittest
from contextlib import redirect_stdout

from wpplang import run_source, translate


def wpp(text):
    """Let a test hold readable, indented W++ source."""
    return textwrap.dedent(text).lstrip("\n")


def execute(source, answers=()):
    """Run W++ and return (stdout, error details or None)."""
    supply = iter(answers)
    printed = io.StringIO()

    def fake_input(prompt=""):
        printed.write(str(prompt))
        return next(supply)

    with redirect_stdout(printed):
        result = run_source(source, "t.wpp", extra_globals={"input": fake_input})
    return printed.getvalue(), result.error_details


class ProgramTestCase(unittest.TestCase):
    def assertProgram(self, name, source, expected, answers=()):
        with self.subTest(program=name):
            got, error = execute(source, answers)
            self.assertIsNone(
                error,
                "{}: unexpected {}\n{}".format(
                    name, error and error["message"], translate(source)
                ),
            )
            self.assertEqual(got, expected, name)

    def assertFails(self, name, source, message, line=None, snippet=None,
                    output=None, detail=None):
        with self.subTest(program=name):
            got, error = execute(source)
            self.assertIsNotNone(error, name + ": expected a skill issue")
            self.assertEqual(error["message"], message, name)
            if line is not None:
                self.assertEqual(error["line"], line, name + ": line")
            if snippet is not None:
                self.assertEqual(error["source_line"], snippet, name + ": snippet")
            if output is not None:
                self.assertEqual(got, output, name + ": output before the failure")
            if detail is not None:
                self.assertIn(detail, error["detail"], name + ": detail")


class ControlFlowTests(ProgramTestCase):
    def test_ternary(self):
        self.assertProgram("ternary", 'x = 5\nyap("big" bet x > 3 nah "small")\n', "big\n")
        self.assertProgram(
            "nested ternary",
            wpp("""
                cook grade(n):
                    spill "A" bet n > 90 nah ("B" bet n > 80 nah "C")
                yap(grade(95), grade(85), grade(10))
            """),
            "A B C\n",
        )

    def test_comprehensions(self):
        self.assertProgram(
            "list with filter", "yap([i * i spam i in range(10) bet i % 2 == 0])\n",
            "[0, 4, 16, 36, 64]\n")
        self.assertProgram(
            "nested", "yap([[r * c spam c in range(1, 4)] spam r in range(1, 4)])\n",
            "[[1, 2, 3], [2, 4, 6], [3, 6, 9]]\n")
        self.assertProgram(
            "dict braces", 'yap({k: bodycount(k) spam k in ["a", "bb"]})\n',
            "{'a': 1, 'bb': 2}\n")
        self.assertProgram(
            "set", "yap(sorted({i % 3 spam i in range(10)}))\n", "[0, 1, 2]\n")
        self.assertProgram(
            "generator expression", "yap(sum(i spam i in range(101)))\n", "5050\n")
        self.assertProgram(
            "with a ternary inside",
            'yap(["even" bet i % 2 == 0 nah "odd" spam i in range(4)])\n',
            "['even', 'odd', 'even', 'odd']\n")

    def test_loop_else(self):
        self.assertProgram(
            "for-else runs without a break",
            wpp("""
                spam i in range(3):
                    yap(i)
                nah:
                    yap("finished")
            """),
            "0\n1\n2\nfinished\n",
        )
        self.assertProgram(
            "for-else skipped by dip",
            wpp("""
                spam i in range(5):
                    bet i == 2:
                        dip
                nah:
                    yap("never")
                yap("after")
            """),
            "after\n",
        )
        self.assertProgram(
            "while-else",
            wpp("""
                n = 0
                grind n < 2:
                    n = n + 1
                nah:
                    yap("clean exit", n)
            """),
            "clean exit 2\n",
        )

    def test_try_shapes(self):
        self.assertProgram(
            "try/except/else/finally",
            wpp("""
                cook risky(n):
                    try:
                        v = 10 // n
                    except ZeroDivisionError:
                        yap("caught")
                    nah:
                        yap("ok", v)
                    finally:
                        yap("always")
                risky(2)
                risky(0)
            """),
            "ok 5\nalways\ncaught\nalways\n",
        )
        self.assertProgram(
            "custom exception",
            wpp("""
                class Nope(Exception):
                    pass

                try:
                    raise Nope("bad vibes")
                except Nope as e:
                    yap("caught:", str(e))
            """),
            "caught: bad vibes\n",
        )

    def test_modern_python_still_works(self):
        self.assertProgram(
            "chained comparison and boolean ops",
            "x = 5\nyap(1 < x < 10, nocap and cap, nocap or cap, not cap)\n",
            "True False True True\n")
        self.assertProgram(
            "walrus",
            wpp("""
                items = [1, 2, 3, 4]
                bet (n := bodycount(items)) > 3:
                    yap("count", n)
            """),
            "count 4\n",
        )
        self.assertProgram(
            "match statement",
            wpp("""
                cook describe(v):
                    match v:
                        case 0:
                            spill "zero"
                        case [_, _]:
                            spill "pair"
                        case _:
                            spill "other"
                yap(describe(0), describe([1, 2]), describe("x"))
            """),
            "zero pair other\n",
        )

    def test_nested_loops_with_skrrt_and_dip(self):
        self.assertProgram(
            "nested loops",
            wpp("""
                found = squad()
                spam a in range(1, 5):
                    spam b in range(1, 5):
                        bet b == a:
                            skrrt
                        bet a * b > 8:
                            dip
                        found.append((a, b))
                yap(found)
            """),
            "[(1, 2), (1, 3), (1, 4), (2, 1), (2, 3), (2, 4), (3, 1), (3, 2), (4, 1), (4, 2)]\n",
        )


class LexicalTests(ProgramTestCase):
    """Strings, comments and names are where a regex translator earns its keep."""

    def test_keywords_inside_literals_stay_literal(self):
        self.assertProgram(
            "every keyword in a string",
            'yap("cook spill yap bet nah spam grind dip skrrt")\n',
            "cook spill yap bet nah spam grind dip skrrt\n")
        self.assertProgram(
            "single quotes", "yap('cook the books')\n", "cook the books\n")
        self.assertProgram(
            "triple quoted",
            'text = ' + '"""' + 'cook\nspill\n' + '"""' + '\nyap(text, end="")\n',
            "cook\nspill\n")
        self.assertProgram(
            "escaped quotes",
            'yap("she said \\"cook\\" loudly")\n', 'she said "cook" loudly\n')
        self.assertProgram(
            "raw string", 'yap(r"C:\\cook\\nah")\n', "C:\\cook\\nah\n")
        self.assertProgram(
            "hash in a string", 'yap("# cook this")\n', "# cook this\n")
        self.assertProgram(
            "apostrophe in a comment",
            'yap("fine")  # it\'s cook, don\'t worry\nyap("still fine")\n',
            "fine\nstill fine\n")
        self.assertProgram(
            "adjacent literals", 'yap("cook" "spill")\n', "cookspill\n")
        self.assertProgram("byte string", 'yap(b"cook")\n', "b'cook'\n")

    def test_fstrings(self):
        self.assertProgram(
            "field translated, text not",
            'items = squad([1, 2, 3])\nyap(f"cook has {bodycount(items)} items")\n',
            "cook has 3 items\n")
        self.assertProgram(
            "format spec", 'v = 3.14159\nyap(f"{v:.2f} and {42:>5}")\n',
            "3.14 and    42\n")
        self.assertProgram(
            "repr conversion", 'yap(f"{\'cook\'!r}")\n', "'cook'\n")
        self.assertProgram(
            "dict access with quotes",
            't = tea(name="wpp")\nyap(f"name is {t[\'name\']}")\n', "name is wpp\n")
        self.assertProgram(
            "escaped braces", 'yap(f"{{cook}} is literal")\n', "{cook} is literal\n")
        self.assertProgram(
            "ternary inside a field",
            'n = 4\nyap(f"n is {\'even\' bet n % 2 == 0 nah \'odd\'}")\n', "n is even\n")
        self.assertProgram(
            "nested f-string",
            'inner = 3\nyap(f"outer {f\'inner {inner}\'}")\n', "outer inner 3\n")

    def test_identifiers_that_contain_keywords(self):
        names = [
            "cookie", "capacity", "recap", "spamalot", "betting", "dipper",
            "teapot", "npcs", "bodycounts", "ranger", "grinder", "skrrting",
            "cultist", "squadron", "nahual", "plotwisted", "spillage",
            "yapping", "dms",
        ]
        source = "".join("{} = {}\n".format(name, i + 1) for i, name in enumerate(names))
        source += "yap(" + " + ".join(names) + ")\n"
        self.assertProgram("keyword-shaped identifiers", source, "190\n")

    def test_python_builtins_are_still_reachable(self):
        self.assertProgram(
            "unaliased builtins",
            'yap(list(range(3)), dict(a=1), sorted(set([2, 1])), len("abcd"), str(9))\n',
            "[0, 1, 2] {'a': 1} [1, 2] 4 9\n")
        self.assertProgram(
            "methods that start like keywords",
            'yap("cook".capitalize(), "wpp".center(7, "-"), "a,b".split(","))\n',
            "Cook --wpp-- ['a', 'b']\n")

    def test_output_shaping(self):
        self.assertProgram(
            "sep and end", 'yap("a", "b", sep="-", end="!")\nyap()\n', "a-b!\n")
        self.assertProgram(
            "empty end then more", 'yap("no newline", end="")\nyap("|done")\n',
            "no newline|done\n")
        self.assertProgram(
            "unicode", 'yap("caf\\u00e9 \\u4f60\\u597d")\n', "caf\u00e9 \u4f60\u597d\n")

    def test_interactive_input(self):
        self.assertProgram(
            "dm reads a line",
            'name = dm("who? ")\nyap("hi", name)\n', "who? hi Claude\n", answers=["Claude"])
        self.assertProgram(
            "several dm calls",
            'a = dm("a: ")\nb = dm("b: ")\nyap(a + b)\n', "a: b: 12\n",
            answers=["1", "2"])


class ReservedWordTests(ProgramTestCase):
    """The 19 keywords are reserved words, and saying so clearly matters.

    A definition cannot be named after one: `cook dip(self)` would become
    `def break(self)`, and even if that parsed, a call written `dip()` would
    become `break()`.  What must not happen is Python reporting "invalid
    syntax" about generated code the author never saw, so the translator names
    the offending word itself.
    """

    def test_method_named_after_a_keyword_is_rejected_clearly(self):
        self.assertFails(
            "method called dip",
            wpp("""
                class Stack:
                    cook dip(self):
                        spill 1
            """),
            "Negative Aura: Bro forgot how to type (SyntaxError)",
            line=2,
            snippet="cook dip(self):",
            detail="'dip' is a W++ keyword (it becomes Python's 'break')",
        )

    def test_function_named_after_a_keyword_is_rejected_clearly(self):
        self.assertFails(
            "function called nah",
            "cook nah(x):\n    spill x * 2\n",
            "Negative Aura: Bro forgot how to type (SyntaxError)",
            line=1,
            detail="'nah' is a W++ keyword (it becomes Python's 'else')",
        )

    def test_class_named_after_a_keyword_is_rejected_clearly(self):
        self.assertFails(
            "class called bet",
            "class bet:\n    pass\n",
            "Negative Aura: Bro forgot how to type (SyntaxError)",
            line=1,
            detail="'bet' is a W++ keyword (it becomes Python's 'if')",
        )

    def test_names_that_only_shadow_a_builtin_are_allowed(self):
        # `squad` -> `list` is not a reserved word, so this parses and keeps
        # behaving the way it always has: the definition shadows the builtin.
        self.assertEqual(translate("cook squad(x):"), "def list(x):")

    def test_ordinary_definitions_are_untouched(self):
        self.assertEqual(translate("cook greet(name):"), "def greet(name):")
        self.assertEqual(translate("class Box:"), "class Box:")
        self.assertEqual(translate("cookie = 1"), "cookie = 1")

    def test_a_keyword_in_a_string_is_not_a_definition(self):
        self.assertEqual(
            translate('yap("cook dip(self):")'), 'print("cook dip(self):")')

    def test_methods_may_be_named_around_a_keyword(self):
        # The workaround, and the thing that should keep working.
        self.assertProgram(
            "stack with ordinary method names",
            wpp("""
                class Stack:
                    cook __init__(self):
                        self.items = squad()
                    cook push(self, v):
                        self.items.append(v)
                    cook pop_it(self):
                        spill self.items.pop()
                    cook size(self):
                        spill bodycount(self.items)

                s = Stack()
                s.push(1)
                s.push(2)
                yap(s.pop_it(), s.size())
            """),
            "2 1\n",
        )

    def test_attributes_named_after_keywords_still_work(self):
        # Attribute access is guarded, so data called `cap` is fine.
        self.assertProgram(
            "attribute called cap",
            wpp("""
                class Box:
                    cook __init__(self):
                        self.cap = 10
                        self.spillover = 2

                b = Box()
                yap(b.cap, b.spillover, b.cap - b.spillover)
            """),
            "10 2 8\n",
        )


class FunctionTests(ProgramTestCase):
    def test_arguments(self):
        self.assertProgram(
            "star args and kwargs",
            wpp("""
                cook tally(*nums, **opts):
                    base = opts.get("base", 0)
                    spill sum(nums) + base
                yap(tally(1, 2, 3), tally(1, 2, base=10))
            """),
            "6 13\n",
        )
        self.assertProgram(
            "keyword only with a default",
            wpp("""
                cook greet(name, *, loud=cap):
                    msg = "hi " + name
                    spill msg.upper() bet loud nah msg
                yap(greet("wpp"), greet("wpp", loud=nocap))
            """),
            "hi wpp HI WPP\n",
        )

    def test_scoping(self):
        self.assertProgram(
            "closure with nonlocal",
            wpp("""
                cook counter():
                    n = 0
                    cook step():
                        nonlocal n
                        n = n + 1
                        spill n
                    spill step

                c = counter()
                yap(c(), c(), c())
            """),
            "1 2 3\n",
        )
        self.assertProgram(
            "global",
            wpp("""
                total = 0
                cook add(n):
                    global total
                    total = total + n
                add(3)
                add(4)
                yap(total)
            """),
            "7\n",
        )

    def test_lambdas_and_sorting(self):
        self.assertProgram(
            "lambda as a sort key",
            wpp("""
                words = squad(["pear", "fig", "banana"])
                yap(sorted(words, key=lambda w: bodycount(w)))
                yap(sorted(words, key=lambda w: (bodycount(w), w), reverse=nocap))
            """),
            "['fig', 'pear', 'banana']\n['banana', 'pear', 'fig']\n",
        )

    def test_generators(self):
        self.assertProgram(
            "yield in a grind loop",
            wpp("""
                cook countdown(n):
                    grind n > 0:
                        yield n
                        n = n - 1

                yap(squad(countdown(4)))
            """),
            "[4, 3, 2, 1]\n",
        )
        self.assertProgram(
            "bare spill ends a generator",
            wpp("""
                cook take_until_zero(items):
                    spam v in items:
                        bet v == 0:
                            spill
                        yield v

                yap(squad(take_until_zero([3, 2, 0, 9])))
            """),
            "[3, 2]\n",
        )
        self.assertProgram(
            "yield from",
            wpp("""
                cook inner():
                    yield 1
                    yield 2
                cook outer():
                    yield from inner()
                    yield 3
                yap(squad(outer()))
            """),
            "[1, 2, 3]\n",
        )

    def test_classes(self):
        self.assertProgram(
            "inheritance and super",
            wpp("""
                class Animal:
                    cook __init__(self, name):
                        self.name = name
                    cook speak(self):
                        spill "..."
                    cook __str__(self):
                        spill self.name + " says " + self.speak()

                class Dog(Animal):
                    cook speak(self):
                        spill "woof"

                class Puppy(Dog):
                    cook speak(self):
                        spill super().speak() + "!"

                yap(str(Animal("thing")))
                yap(str(Dog("rex")))
                yap(str(Puppy("bit")))
            """),
            "thing says ...\nrex says woof\nbit says woof!\n",
        )
        self.assertProgram(
            "property, staticmethod, classmethod",
            wpp("""
                class Temp:
                    scale = "C"
                    cook __init__(self, c):
                        self._c = c
                    @property
                    cook f(self):
                        spill self._c * 9 / 5 + 32
                    @staticmethod
                    cook zero():
                        spill 0
                    @classmethod
                    cook unit(cls):
                        spill cls.scale

                t = Temp(100)
                yap(t.f, Temp.zero(), Temp.unit())
            """),
            "212.0 0 C\n",
        )
        self.assertProgram(
            "dunder len, getitem and eq",
            wpp("""
                class Bag:
                    cook __init__(self, items):
                        self.items = squad(items)
                    cook __len__(self):
                        spill bodycount(self.items)
                    cook __getitem__(self, i):
                        spill self.items[i]
                    cook __eq__(self, other):
                        spill self.items == other.items

                a = Bag([1, 2, 3])
                b = Bag([1, 2, 3])
                yap(bodycount(a), a[1], a == b, a is b)
            """),
            "3 2 True False\n",
        )
        self.assertProgram(
            "context manager",
            wpp("""
                class Tracker:
                    cook __enter__(self):
                        yap("enter")
                        spill self
                    cook __exit__(self, *info):
                        yap("exit")
                        spill cap

                with Tracker() as t:
                    yap("inside")
            """),
            "enter\ninside\nexit\n",
        )
        self.assertProgram(
            "decorator",
            wpp("""
                cook twice(fn):
                    cook wrapper(*a):
                        spill fn(*a) * 2
                    spill wrapper

                @twice
                cook add(a, b):
                    spill a + b

                yap(add(2, 3))
            """),
            "10\n",
        )


class CollectionTests(ProgramTestCase):
    def test_sequences(self):
        self.assertProgram(
            "slicing with a negative step",
            "s = squad(range(10))\nyap(s[2:5], s[::-1][:3], s[::3], s[-2:])\n",
            "[2, 3, 4] [9, 8, 7] [0, 3, 6, 9] [8, 9]\n")
        self.assertProgram(
            "starred unpacking",
            "first, *middle, last = [1, 2, 3, 4, 5]\nyap(first, middle, last)\n",
            "1 [2, 3, 4] 5\n")
        self.assertProgram(
            "enumerate, zip, map, filter",
            wpp("""
                names = squad(["a", "b", "c"])
                nums = squad([3, 1, 2])
                yap(squad(enumerate(names)))
                yap(squad(zip(names, nums)))
                yap(squad(map(lambda n: n * 10, nums)))
                yap(squad(filter(lambda n: n > 1, nums)))
            """),
            "[(0, 'a'), (1, 'b'), (2, 'c')]\n"
            "[('a', 3), ('b', 1), ('c', 2)]\n"
            "[30, 10, 20]\n"
            "[3, 2]\n",
        )

    def test_mappings_and_sets(self):
        self.assertProgram(
            "dict methods and sorting by value",
            wpp("""
                scores = tea(amy=3, bob=1, cal=2)
                yap(sorted(scores.items(), key=lambda kv: kv[1]))
                yap(sorted(scores.keys()), sorted(scores.values()))
                yap(scores.get("nobody", "npc"))
            """),
            "[('bob', 1), ('cal', 2), ('amy', 3)]\n"
            "['amy', 'bob', 'cal'] [1, 2, 3]\n"
            "npc\n",
        )
        self.assertProgram(
            "set algebra",
            wpp("""
                a = cult([1, 2, 3, 4])
                b = cult([3, 4, 5])
                yap(sorted(a & b), sorted(a | b), sorted(a - b), sorted(a ^ b))
            """),
            "[3, 4] [1, 2, 3, 4, 5] [1, 2] [1, 2, 5]\n",
        )

    def test_arithmetic(self):
        self.assertProgram(
            "floor division and modulo with negatives",
            "yap(-7 // 2, -7 % 2, 7 // -2, 7 % -2, divmod(-7, 2))\n",
            "-4 1 -4 -1 (-4, 1)\n")
        self.assertProgram(
            "big integers and rounding",
            "yap(2 ** 100)\nyap(round(1 / 3, 4), 10 / 4, 10 // 4, abs(-3.5))\n",
            "1267650600228229401496703205376\n0.3333 2.5 2 3.5\n")
        self.assertProgram(
            "numeric literal forms",
            "yap(1_000_000, 0x1f, 0b1010, 0o17, 1e3, 2j)\n",
            "1000000 31 10 15 1000.0 2j\n")


class AlgorithmTests(ProgramTestCase):
    """Programs whose answers are independently checkable."""

    def test_quicksort(self):
        self.assertProgram(
            "quicksort",
            wpp("""
                cook quicksort(items):
                    bet bodycount(items) <= 1:
                        spill items
                    pivot = items[bodycount(items) // 2]
                    less = [i spam i in items bet i < pivot]
                    same = [i spam i in items bet i == pivot]
                    more = [i spam i in items bet i > pivot]
                    spill quicksort(less) + same + quicksort(more)

                yap(quicksort([5, 3, 8, 1, 9, 2, 7, 3]))
            """),
            "[1, 2, 3, 3, 5, 7, 8, 9]\n",
        )

    def test_memoised_fibonacci(self):
        self.assertProgram(
            "fibonacci with a memo dict",
            wpp("""
                memo = tea()
                cook fib(n):
                    bet n in memo:
                        spill memo[n]
                    bet n < 2:
                        spill n
                    memo[n] = fib(n - 1) + fib(n - 2)
                    spill memo[n]

                yap([fib(i) spam i in range(15)])
                yap(fib(60))
            """),
            "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]\n"
            "1548008755920\n",
        )

    def test_sieve(self):
        self.assertProgram(
            "sieve of eratosthenes",
            wpp("""
                cook primes_upto(n):
                    sieve = [nocap] * (n + 1)
                    sieve[0] = cap
                    bet n >= 1:
                        sieve[1] = cap
                    p = 2
                    grind p * p <= n:
                        bet sieve[p]:
                            m = p * p
                            grind m <= n:
                                sieve[m] = cap
                                m = m + p
                        p = p + 1
                    spill [i spam i in range(n + 1) bet sieve[i]]

                yap(primes_upto(50))
            """),
            "[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]\n",
        )

    def test_word_frequency(self):
        self.assertProgram(
            "word frequency",
            wpp("""
                text = "the cook will cook the meal the way we cook"
                counts = tea()
                spam word in text.split():
                    counts[word] = counts.get(word, 0) + 1
                ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
                spam word, n in ranked[:3]:
                    yap(word, n)
            """),
            "cook 3\nthe 3\nmeal 1\n",
        )

    def test_matrix_multiply(self):
        self.assertProgram(
            "matrix multiply",
            wpp("""
                cook matmul(a, b):
                    rows = bodycount(a)
                    cols = bodycount(b[0])
                    inner = bodycount(b)
                    out = squad()
                    spam r in range(rows):
                        row = squad()
                        spam c in range(cols):
                            row.append(sum(a[r][k] * b[k][c] spam k in range(inner)))
                        out.append(row)
                    spill out

                yap(matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]))
            """),
            "[[19, 22], [43, 50]]\n",
        )

    def test_breadth_first_search(self):
        self.assertProgram(
            "shortest path",
            wpp("""
                graph = tea()
                graph["a"] = squad(["b", "c"])
                graph["b"] = squad(["d"])
                graph["c"] = squad(["d", "e"])
                graph["d"] = squad(["f"])
                graph["e"] = squad(["f"])
                graph["f"] = squad()

                cook shortest(start, goal):
                    queue = squad([[start]])
                    seen = cult([start])
                    grind bodycount(queue) > 0:
                        path = queue.pop(0)
                        node = path[-1]
                        bet node == goal:
                            spill path
                        spam nxt in graph[node]:
                            bet nxt in seen:
                                skrrt
                            seen.add(nxt)
                            queue.append(path + [nxt])
                    spill npc

                yap(shortest("a", "f"))
                yap(shortest("b", "e"))
            """),
            # `npc` is a keyword in the source; the value still prints as Python
            # prints it.
            "['a', 'b', 'd', 'f']\nNone\n",
        )

    def test_fizzbuzz_one_liner(self):
        self.assertProgram(
            "fizzbuzz in a comprehension",
            'yap(", ".join(["FizzBuzz" bet i % 15 == 0 nah "Fizz" bet i % 3 == 0 '
            'nah "Buzz" bet i % 5 == 0 nah str(i) spam i in range(1, 16)]))\n',
            "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz\n",
        )


class DiagnosticTests(ProgramTestCase):
    """The Skill Issue Protocol must point at the right W++ line."""

    def test_line_numbers_survive_hard_cases(self):
        self.assertFails(
            "deep inside nested calls",
            wpp("""
                cook a():
                    spill b()
                cook b():
                    spill c()
                cook c():
                    spill 1 / 0

                yap("before")
                a()
            """),
            "Math ain't mathing: Bro tried to divide by zero (ZeroDivisionError)",
            line=6, snippet="spill 1 / 0", output="before\n")

        self.assertFails(
            "after a multi-line string",
            'blurb = ' + '"""' + '\none\ntwo\n' + '"""' + '\nyap(missing_name)\n',
            "Bro is making up words now (NameError)",
            line=5, snippet="yap(missing_name)")

        self.assertFails(
            "inside a comprehension",
            'rows = squad([1, 2, 0, 4])\nyap([10 // r spam r in rows])\n',
            "Math ain't mathing: Bro tried to divide by zero (ZeroDivisionError)", line=2)

        self.assertFails(
            "inside a generator body",
            wpp("""
                cook gen():
                    spam i in range(3):
                        yield 10 // (i - 1)

                yap(squad(gen()))
            """),
            "Math ain't mathing: Bro tried to divide by zero (ZeroDivisionError)",
            line=3, snippet="yield 10 // (i - 1)")

        self.assertFails(
            "inside a class method",
            wpp("""
                class Thing:
                    cook boom(self):
                        spill self.nope

                Thing().boom()
            """),
            "Unspecified skill issue (AttributeError)",
            line=3, snippet="spill self.nope")

        self.assertFails(
            "inside a decorated function",
            wpp("""
                cook deco(fn):
                    spill fn

                @deco
                cook work():
                    spill undefined_here

                work()
            """),
            "Bro is making up words now (NameError)",
            line=6, snippet="spill undefined_here")

    def test_error_kinds(self):
        self.assertFails(
            "nested index", 'grid = squad([[1, 2], [3]])\nyap(grid[1][5])\n',
            "Blud thinks he has more items than he does (IndexError)", line=2)
        self.assertFails(
            "missing key", 't = tea(a=1)\nyap(t["b"])\n',
            "Unspecified skill issue (KeyError)", line=2)
        self.assertFails(
            "not callable", "n = 5\nyap(n())\n",
            "Oil up bro, you can't combine those (TypeError)", line=2)
        self.assertFails(
            "wrong argument count",
            "cook two(a, b):\n    spill a + b\nyap(two(1))\n",
            "Oil up bro, you can't combine those (TypeError)", line=3)
        self.assertFails(
            "assertion", 'x = 1\nassert x == 2, "x should be two"\n',
            "Unspecified skill issue (AssertionError)", line=2)
        self.assertFails(
            "runaway recursion",
            "cook forever(n):\n    spill forever(n + 1)\nforever(0)\n",
            "Unspecified skill issue (RecursionError)")

    def test_broken_source(self):
        self.assertFails(
            "syntax error on a later line",
            'yap("fine")\nyap("also fine")\ncook broken(:\n',
            "Negative Aura: Bro forgot how to type (SyntaxError)", line=3, output="")
        self.assertFails(
            "unterminated string", 'yap("open\n',
            "Negative Aura: Bro forgot how to type (SyntaxError)", line=1)
        self.assertFails(
            "bad indentation",
            "cook f():\n    yap(1)\n        yap(2)\n",
            "Your spaces are looking a little sus (IndentationError)", line=3)
        self.assertFails(
            # TabError subclasses IndentationError and only the parent has a
            # message in the spec, so the parent's wording is what shows.
            "tabs mixed with spaces",
            "cook f():\n    yap(1)\n\tyap(2)\n",
            "Your spaces are looking a little sus (IndentationError)", line=3)


if __name__ == "__main__":
    unittest.main()
