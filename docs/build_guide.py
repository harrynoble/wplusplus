"""Build the W++ learning guide as a PDF.

Every W++ example in the guide is executed by the real interpreter while the
PDF is being written, and the output printed in the guide is the output that
actually came back.  If an example stops working, this script fails instead of
producing a guide that lies.

    python docs/build_guide.py

Writes docs/WPP_Guide.pdf.
"""

import io
import os
import re
import sys
import textwrap
from contextlib import redirect_stdout
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle,
)

from wpplang import (  # noqa: E402
    KEYWORDS, SKILL_ISSUES, __version__, run_source, translate,
)

# --------------------------------------------------------------------- colours

INK = colors.HexColor("#1a1d21")
MUTED = colors.HexColor("#5b6672")
FAINT = colors.HexColor("#8a95a1")
RULE = colors.HexColor("#d7dce2")
ACCENT = colors.HexColor("#1f5fbf")
CODE_BG = colors.HexColor("#f4f6f8")
CODE_EDGE = colors.HexColor("#dfe4ea")
OUT_BG = colors.HexColor("#eef3ee")
OUT_EDGE = colors.HexColor("#cfdccf")
ERR_BG = colors.HexColor("#fbf0f0")
ERR_EDGE = colors.HexColor("#e6cfcf")

MAX_CODE_COLUMNS = 84  # what fits the code box without wrapping


# ----------------------------------------------------------------------- fonts

def register_fonts():
    """Use Segoe UI and Consolas when present, else fall back to the builtins."""
    windows = r"C:\Windows\Fonts"
    wanted = {
        "Body": "segoeui.ttf",
        "Body-Bold": "segoeuib.ttf",
        "Body-Italic": "segoeuii.ttf",
        "Mono": "consola.ttf",
        "Mono-Bold": "consolab.ttf",
    }
    try:
        for name, filename in wanted.items():
            path = os.path.join(windows, filename)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily(
            "Body", normal="Body", bold="Body-Bold", italic="Body-Italic")
        pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold")
        return "Body", "Body-Bold", "Body-Italic", "Mono", "Mono-Bold"
    except Exception:
        return ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique",
                "Courier", "Courier-Bold")


BODY, BODY_BOLD, BODY_ITALIC, MONO, MONO_BOLD = register_fonts()


# ---------------------------------------------------------------- running W++

PROBLEMS = []


def strip_unrenderable(text):
    """Drop characters the PDF fonts cannot draw (the siren emoji, mainly)."""
    return "".join(ch for ch in text if ord(ch) < 0x2500)


def run(source, answers=(), expect_error=False, label=""):
    """Execute W++ and return its real output, or its real error report."""
    supply = iter(answers)
    captured = io.StringIO()

    def fake_input(prompt=""):
        captured.write(str(prompt))
        try:
            value = next(supply)
        except StopIteration:
            raise AssertionError("example %r ran out of input" % label)
        captured.write(value + "\n")  # echo, the way a terminal does
        return value

    with redirect_stdout(captured):
        result = run_source(source, "example.wpp",
                            extra_globals={"input": fake_input})

    output = captured.getvalue()
    error = result.error_details

    if expect_error and error is None:
        PROBLEMS.append("%s: expected a skill issue, got none" % label)
    if not expect_error and error is not None:
        PROBLEMS.append("%s: unexpected %s (line %s)"
                        % (label, error["message"], error["line"]))

    if error is not None:
        report = [error["message"]]
        if error["line"]:
            report.append("   where: example.wpp, line %d" % error["line"])
            if error["source_line"]:
                report.append("   %4d | %s" % (error["line"], error["source_line"]))
        if error["detail"]:
            report.append("   details: %s" % error["detail"])
        output = output + "\n".join(report) + "\n"

    return output.rstrip("\n")


# ------------------------------------------------------------- content helpers

def wpp(text):
    """Dedent an indented W++ block written inside this file."""
    return textwrap.dedent(text).strip("\n")


def read_example(name):
    """Read one of the programs in examples/."""
    with open(os.path.join(ROOT, "examples", name), encoding="utf-8") as handle:
        return handle.read()


def h1(text):
    return ("h1", text)


def h2(text):
    return ("h2", text)


def p(text):
    return ("p", text)


def note(text):
    return ("note", text)


def bullets(items):
    return ("bullets", items)


def table(headers, rows, widths=None):
    return ("table", headers, rows, widths)


def code(source, answers=(), expect_error=False, caption=None, run_it=True):
    """A W++ example.  Its output is produced by running it, not by hand."""
    return ("code", source, answers, expect_error, caption, run_it)


def shell(command, output=None):
    return ("shell", command, output)


def snippet(text):
    """A fragment shown for shape only - not a runnable program."""
    return ("snippet", text)


# ============================================================ the guide itself

def part_intro():
    return [
        h1("1. What W++ is"),
        p("W++ is a programming language that reads like group chat and runs "
          "like Python. Every W++ keyword is a nickname for a Python one: "
          "<b>cook</b> means <font face='%s'>def</font>, <b>yap</b> means "
          "<font face='%s'>print</font>, <b>bet</b> means "
          "<font face='%s'>if</font>. There are nineteen of these nicknames "
          "and that is the whole language." % (MONO, MONO, MONO)),
        p("This matters more than it sounds, and it is the single most useful "
          "thing to understand as a beginner: <b>anything Python can do, W++ "
          "can do</b>. Classes, generators, decorators, the entire standard "
          "library, f-strings, the walrus operator - all of it works, "
          "unchanged. You are not learning a small toy language with a short "
          "list of features. You are learning Python with a different set of "
          "words for nineteen things."),
        h2("How your program actually runs"),
        p("When you run a <font face='%s'>.wpp</font> file, four things happen "
          "in order:" % MONO),
        snippet(
            "  your_program.wpp\n"
            "        |\n"
            "        v\n"
            "  lexer            your source becomes W++ tokens\n"
            "        |           see them with --tokens\n"
            "        v\n"
            "  parser           the tokens become a W++ syntax tree\n"
            "        |           see it with --ast\n"
            "        v\n"
            "  checks           is `dip` in a loop? is `spill` in a `cook`?\n"
            "        |\n"
            "        v\n"
            "  code generator   the tree becomes ordinary Python\n"
            "        |           see it with --emit\n"
            "        v\n"
            "  Python runs it -> your output, or a Skill Issue"
        ),
        p("You do not need those stage names to write W++. They matter for one "
          "reason: W++ reads your program properly rather than swapping words "
          "in text, which is why the two rules below hold and why an error can "
          "point at your line."),
        p("Two rules are worth knowing early, because they explain nearly "
          "every surprise:"),
        bullets([
            "<b>Keywords are matched as whole words.</b> A variable called "
            "<font face='%s'>cookie</font> is left alone; only a standalone "
            "<font face='%s'>cook</font> becomes "
            "<font face='%s'>def</font>." % (MONO, MONO, MONO),
            "<b>Text inside strings and comments is never translated.</b> "
            "<font face='%s'>yap(\"cook dinner\")</font> prints "
            "<i>cook dinner</i>, not <i>def dinner</i>." % MONO,
        ]),
        p("Line numbers are preserved exactly, so when something goes wrong "
          "the error points at the line you wrote, not at generated code you "
          "have never seen."),
    ]


def part_setup():
    return [
        h1("2. Getting set up"),
        p("You need <b>Python 3.8 or newer</b> and nothing else. W++ has no "
          "dependencies to install."),
        shell("git clone https://github.com/harrynoble/wplusplus.git\n"
              "cd wplusplus"),
        p("Check that it works:"),
        shell("python wpp.py examples/hello.wpp", "Hello world"),
        p("If you see <i>Hello world</i>, you are done. There is nothing to "
          "build and nothing to configure."),
        h2("The two ways to run W++"),
        p("<b>1. From the terminal.</b> Put your program in a file ending in "
          "<font face='%s'>.wpp</font> and run it:" % MONO),
        shell("python wpp.py my_program.wpp"),
        p("<b>2. In the playground.</b> A local web page with a code editor "
          "and a terminal-style output panel, which is the friendlier place "
          "to start:"),
        shell("python playground/server.py"),
        p("That opens <font face='%s'>http://127.0.0.1:8000</font> in your "
          "browser. Pick something from the <b>Examples</b> menu, press "
          "<b>Run</b> (or Ctrl+Enter), and the output appears beside your "
          "code. When a program asks you a question, you type your answer "
          "straight into the output panel." % MONO),
        note("The playground runs the code you give it on your own machine. "
             "That is fine for learning, but do not expose it to a network."),
        h2("Your first program"),
        p("Create a file called <font face='%s'>hello.wpp</font> containing "
          "one line:" % MONO),
        code('yap("Hello world")'),
        p("Then run it with <font face='%s'>python wpp.py hello.wpp</font>. "
          "That is a complete W++ program - there is no boilerplate, no main "
          "function, no imports needed." % MONO),
    ]


def part_dictionary():
    rows = []
    explanations = {
        "cook": "start a function",
        "spill": "send a value back",
        "yap": "print to the screen",
        "dm": "ask the user for input",
        "bodycount": "how many items",
        "bet": "if this is true",
        "plotwist": "otherwise, if this is true",
        "nah": "otherwise",
        "spam": "repeat for each item",
        "grind": "repeat while true",
        "dip": "leave the loop now",
        "skrrt": "skip to the next round",
        "nocap": "true",
        "cap": "false",
        "npc": "nothing / no value",
        "squad": "a list",
        "tea": "a dictionary",
        "cult": "a set",
        "range": "a run of numbers",
    }
    for word, target in KEYWORDS.items():
        rows.append([word, target, explanations[word]])

    return [
        h1("3. The Official Dictionary"),
        p("These nineteen words are the entire language. Everything else you "
          "write in W++ is ordinary Python. Learn this table and you have "
          "learned W++; the rest of this guide is about what to do with it."),
        table(["W++", "Python", "What it means"], rows,
              widths=[1.15 * inch, 1.15 * inch, 3.9 * inch]),
        note("These nineteen words are <b>reserved</b>. You cannot use one as "
             "the name of your own variable, function or class - see section "
             "16, which explains the one error every beginner hits."),
    ]


def part_output_input():
    return [
        h1("4. Printing with yap"),
        p("<b>yap</b> puts things on the screen. Give it as many values as "
          "you like and it separates them with a space:"),
        code(wpp("""
            yap("Hello world")
            yap("one", 2, nocap)
            yap()
            yap("three", "values", "again")
        """)),
        p("An empty <b>yap()</b> prints a blank line. Two options let you "
          "control the spacing and the line ending:"),
        code(wpp("""
            yap("a", "b", "c", sep="-")
            yap("no line break yet", end=" ... ")
            yap("continued on the same line")
        """)),
        p("Anything can be printed, not just text:"),
        code(wpp("""
            yap(42, 3.5, nocap, npc)
            yap(squad([1, 2, 3]))
            yap(tea(name="wpp", fun=nocap))
        """)),
        note("Notice that <b>nocap</b> printed as <i>True</i> and <b>npc</b> "
             "printed as <i>None</i>. The keywords are how you <i>write</i> "
             "the values; by the time the program runs it really is Python, "
             "so the values print the way Python prints them."),

        h1("5. Reading input with dm"),
        p("<b>dm</b> asks the person running your program for a line of text. "
          "Whatever you pass to it is shown as the prompt:"),
        code(wpp("""
            name = dm("What is your name? ")
            yap("Nice to meet you,", name)
        """), answers=["Ada"]),
        p("In the guide above, <i>Ada</i> is what was typed at the prompt. In "
          "the playground the cursor appears right after the question in the "
          "output panel; in the terminal you type and press Enter as usual."),
        p("<b>dm always gives you text</b>, even when the user types digits. "
          "To do maths with it, convert it first:"),
        code(wpp("""
            raw = dm("Pick a number: ")
            n = int(raw)
            yap("Doubled:", n * 2)
            yap("But without converting:", raw * 2)
        """), answers=["7"]),
        p("Use <font face='%s'>int()</font> for whole numbers and "
          "<font face='%s'>float()</font> for decimals. If the user types "
          "something that is not a number, the conversion fails - section 15 "
          "shows how to handle that gracefully." % (MONO, MONO)),
        p("You can ask more than once, including inside a loop:"),
        code(wpp("""
            total = 0
            spam i in range(3):
                total = total + int(dm("Score " + str(i + 1) + ": "))
            yap("Total:", total)
        """), answers=["10", "20", "30"]),
    ]


def part_values():
    return [
        h1("6. Variables and values"),
        p("A variable is a name for a value. You make one by assigning to it, "
          "and you never declare a type:"),
        code(wpp("""
            score = 10
            name = "Ada"
            ready = nocap

            yap(score, name, ready)

            score = score + 5
            yap("after a change:", score)

            score = "now a string"
            yap("a name can hold anything:", score)
        """)),
        p("You can assign several names at once, which makes swapping two "
          "values a one-liner:"),
        code(wpp("""
            a, b = 1, 2
            yap(a, b)

            a, b = b, a
            yap("swapped:", a, b)

            x = y = z = 0
            yap(x, y, z)
        """)),
        h2("Finding out what you have"),
        p("<font face='%s'>type()</font> tells you what kind of value "
          "something is, which is useful while you are learning:" % MONO),
        code(wpp("""
            yap(type(10))
            yap(type(3.5))
            yap(type("text"))
            yap(type(nocap))
            yap(type(npc))
            yap(type(squad()))
        """)),

        h1("7. Numbers and arithmetic"),
        p("The usual operators all work. Two are worth pointing out because "
          "beginners trip on them:"),
        code(wpp("""
            yap(7 + 2, 7 - 2, 7 * 2)
            yap(7 / 2)
            yap(7 // 2)
            yap(7 % 2)
            yap(7 ** 2)
        """)),
        bullets([
            "<font face='%s'>/</font> always gives a decimal, even for "
            "numbers that divide evenly: 4 / 2 is 2.0, not 2." % MONO,
            "<font face='%s'>//</font> throws away the remainder, and "
            "<font face='%s'>%%</font> keeps only the remainder. Together "
            "they answer 'how many times, and what is left over'." % (MONO, MONO),
        ]),
        p("<b>%%</b> is the workhorse of beginner programs, because "
          "<i>divisible by</i> means <i>remainder is zero</i>:"),
        code(wpp("""
            yap(10 % 2 == 0, 11 % 2 == 0)
            yap("15 divisible by 3 and 5:", 15 % 3 == 0 and 15 % 5 == 0)
        """)),
        p("Handy number tools:"),
        code(wpp("""
            yap(abs(-4), round(3.7), round(3.14159, 2))
            yap(min(4, 2, 9), max(4, 2, 9), sum([1, 2, 3]))
            yap(int("42") + 1, float("2.5") * 2, str(99) + "!")
            yap(divmod(17, 5))
        """)),
        p("Whole numbers in W++ have no size limit:"),
        code('yap(2 ** 128)'),
    ]


def part_strings():
    return [
        h1("8. Text"),
        p("Text goes in single or double quotes - use whichever avoids "
          "clashing with the quotes inside it:"),
        code(wpp("""
            a = "double quoted"
            b = 'single quoted'
            c = "she said \\"hello\\""
            d = 'she said "hello"'
            yap(a)
            yap(b)
            yap(c)
            yap(d)
        """)),
        p("Triple quotes hold text that runs over several lines:"),
        code(wpp('''
            blurb = """line one
            line two"""
            yap(blurb)
        ''')),
        h2("Joining and repeating"),
        code(wpp("""
            first = "Ada"
            last = "Lovelace"
            yap(first + " " + last)
            yap("ha" * 3)
            yap("-" * 20)
        """)),
        note("You cannot add text to a number with <font face='%s'>+</font>. "
             "<font face='%s'>\"Score: \" + 10</font> fails; write "
             "<font face='%s'>\"Score: \" + str(10)</font>, or use "
             "<b>yap</b>'s several-values form, or an f-string." % (MONO, MONO, MONO)),
        h2("f-strings: the tidy way to build text"),
        p("Put <font face='%s'>f</font> in front of a string and anything in "
          "curly braces is worked out and dropped in. This is the "
          "recommended way to build messages:" % MONO),
        code(wpp("""
            name = "Ada"
            score = 91.5
            items = squad([1, 2, 3])

            yap(f"{name} scored {score}")
            yap(f"{name} has {bodycount(items)} items")
            yap(f"one more than the score is {score + 1}")
            yap(f"rounded to one decimal: {score:.1f}")
            yap(f"padded: [{name:>10}]")
        """)),
        p("The words inside the braces are real W++, so keywords work there "
          "too - notice <b>bodycount</b> above. Text outside the braces is "
          "left exactly as written, so a stray keyword in your sentence is "
          "safe:"),
        code('yap(f"the word cook stays put, {1 + 1} does not")'),
        h2("Picking text apart"),
        p("Text is a sequence, so you can index and slice it. Counting starts "
          "at zero, and negative numbers count from the end:"),
        code(wpp("""
            word = "playground"
            yap(word[0], word[3], word[-1])
            yap(word[0:4])
            yap(word[4:])
            yap(word[::-1])
            yap(bodycount(word))
        """)),
        h2("Useful text methods"),
        code(wpp("""
            messy = "  Hello, World  "
            yap(f"[{messy.strip()}]")
            yap(messy.strip().upper())
            yap(messy.strip().lower())
            yap("a,b,c".split(","))
            yap("-".join(squad(["a", "b", "c"])))
            yap("hello".replace("l", "L"))
            yap("hello".startswith("he"), "hello".endswith("lo"))
            yap("cook" in "cookbook", "steak" in "cookbook")
            yap("hello".find("ll"), "Hello".capitalize())
        """)),
    ]


def part_truth():
    return [
        h1("9. Yes, no and nothing"),
        p("Three keywords cover truth and emptiness:"),
        table(["W++", "Means", "Python"],
              [["nocap", "true", "True"],
               ["cap", "false", "False"],
               ["npc", "no value at all", "None"]],
              widths=[1.3 * inch, 3.0 * inch, 1.9 * inch]),
        code(wpp("""
            ready = nocap
            finished = cap
            winner = npc

            yap(ready, finished, winner)
            yap(type(ready), type(winner))
        """)),
        h2("Comparing things"),
        p("Comparisons produce <b>nocap</b> or <b>cap</b>:"),
        code(wpp("""
            yap(5 == 5, 5 != 5)
            yap(5 > 3, 5 < 3, 5 >= 5, 5 <= 4)
            yap("abc" == "abc", "abc" == "ABC")
        """)),
        note("<font face='%s'>=</font> assigns a value; "
             "<font face='%s'>==</font> asks whether two things are equal. "
             "Mixing them up is the most common beginner slip in any "
             "language." % (MONO, MONO)),
        p("You can chain comparisons, which reads exactly how you would say "
          "it out loud:"),
        code(wpp("""
            age = 25
            yap(18 <= age < 65)
        """)),
        h2("Combining conditions"),
        p("<font face='%s'>and</font>, <font face='%s'>or</font> and "
          "<font face='%s'>not</font> stay as they are - they were never "
          "given nicknames:" % (MONO, MONO, MONO)),
        code(wpp("""
            age = 25
            member = nocap

            yap(age > 18 and member)
            yap(age > 65 or member)
            yap(not member)
        """)),
        h2("Emptiness counts as false"),
        p("Empty things behave as <b>cap</b> when used as a condition, which "
          "lets you write natural checks:"),
        code(wpp("""
            items = squad()
            name = ""

            bet not items:
                yap("the squad is empty")
            bet not name:
                yap("no name given")

            items.append("first")
            bet items:
                yap("now it has", bodycount(items), "item")
        """)),
        p("Zero, an empty string, an empty list, an empty dictionary and "
          "<b>npc</b> are all falsey. Everything else is truthy."),
        h2("is and in"),
        code(wpp("""
            value = npc
            yap(value is npc)
            yap(value is not npc)

            squad_goals = squad(["a", "b"])
            yap("a" in squad_goals, "z" in squad_goals)
            yap("z" not in squad_goals)
        """)),
        note("Use <font face='%s'>is npc</font> rather than "
             "<font face='%s'>== npc</font> when checking for nothing. It is "
             "the habit Python programmers expect." % (MONO, MONO)),
    ]


def part_decisions():
    return [
        h1("10. Making decisions"),
        p("<b>bet</b> runs a block only when something is true. The block is "
          "the indented lines underneath it:"),
        code(wpp("""
            score = 91

            bet score >= 50:
                yap("You passed")
                yap("Well done")
        """)),
        note("Indentation is not decoration in W++ - it is how the language "
             "knows which lines belong to the block. Use four spaces, and be "
             "consistent. Mixing tabs and spaces is an error."),
        p("<b>nah</b> covers everything else:"),
        code(wpp("""
            score = 32

            bet score >= 50:
                yap("Pass")
            nah:
                yap("Fail")
        """)),
        p("<b>plotwist</b> adds more questions in between. They are checked "
          "in order and the first true one wins:"),
        code(wpp("""
            cook grade(score):
                bet score >= 90:
                    spill "A"
                plotwist score >= 80:
                    spill "B"
                plotwist score >= 70:
                    spill "C"
                plotwist score >= 50:
                    spill "Pass"
                nah:
                    spill "Fail"

            spam mark in [95, 83, 71, 55, 20]:
                yap(mark, "->", grade(mark))
        """)),
        p("Because they are checked in order, you can write "
          "<font face='%s'>score >= 80</font> for a B without also saying "
          "<i>and less than 90</i> - if it were 90 or more, the first "
          "question would already have answered." % MONO),
        h2("Conditions inside conditions"),
        code(wpp("""
            age = 25
            member = cap

            bet age >= 18:
                bet member:
                    yap("adult member")
                nah:
                    yap("adult, not a member")
            nah:
                yap("too young")
        """)),
        h2("Choosing a value in one line"),
        p("When you only want to pick between two values, you can put the "
          "whole decision on one line. The shape is "
          "<i>value</i> <b>bet</b> <i>condition</i> <b>nah</b> "
          "<i>other value</i>:"),
        code(wpp("""
            score = 91
            label = "pass" bet score >= 50 nah "fail"
            yap(label)

            count = 1
            yap(f"{count} item" bet count == 1 nah f"{count} items")
        """)),
    ]


def part_loops():
    return [
        h1("11. Repeating things"),
        p("There are two loops. <b>spam</b> walks through a collection; "
          "<b>grind</b> keeps going while something stays true."),
        h2("spam: once for each item"),
        code(wpp("""
            spam colour in squad(["red", "green", "blue"]):
                yap(colour)
        """)),
        p("With <b>range</b> you loop a set number of times. "
          "<font face='%s'>range(5)</font> counts 0, 1, 2, 3, 4 - it stops "
          "<i>before</i> the number you give it:" % MONO),
        code(wpp("""
            spam i in range(5):
                yap(i)

            yap("---")
            spam i in range(1, 6):
                yap(i)

            yap("---")
            spam i in range(0, 10, 3):
                yap(i)

            yap("---")
            spam i in range(3, 0, -1):
                yap(i)
        """)),
        p("You can walk through text, and through a dictionary:"),
        code(wpp("""
            spam letter in "wpp":
                yap(letter)

            ages = tea(ada=36, alan=41)
            spam name in ages:
                yap(name, "is", ages[name])
        """)),
        h2("Knowing where you are: enumerate and zip"),
        code(wpp("""
            names = squad(["Ada", "Alan", "Grace"])

            spam i, name in enumerate(names):
                yap(i, name)

            yap("---")
            spam i, name in enumerate(names, 1):
                yap(f"{i}. {name}")

            yap("---")
            scores = squad([91, 84, 99])
            spam name, score in zip(names, scores):
                yap(name, score)
        """)),
        h2("grind: keep going while true"),
        code(wpp("""
            countdown = 3
            grind countdown > 0:
                yap(countdown)
                countdown = countdown - 1
            yap("liftoff")
        """)),
        note("Whatever the <b>grind</b> condition depends on must change "
             "inside the loop, or the loop never ends. Forgetting the "
             "<font face='%s'>countdown = countdown - 1</font> line above is "
             "the classic way to write a program that runs forever. In the "
             "playground a runaway loop is stopped for you after ten seconds; "
             "in the terminal press Ctrl+C." % MONO),
        h2("dip and skrrt"),
        p("<b>dip</b> leaves the loop immediately. <b>skrrt</b> skips the "
          "rest of this round and starts the next one:"),
        code(wpp("""
            spam n in range(1, 11):
                bet n % 2 == 0:
                    skrrt
                bet n > 7:
                    dip
                yap(n)
        """)),
        p("A common pattern is <b>grind nocap</b> - loop forever, and "
          "<b>dip</b> out when you are done. This is how you keep asking "
          "until the answer makes sense:"),
        code(wpp("""
            grind nocap:
                answer = dm("Type yes to continue: ")
                bet answer == "yes":
                    dip
                yap("That was not yes. Try again.")
            yap("Continuing")
        """), answers=["no", "maybe", "yes"]),
        h2("A loop can have a nah too"),
        p("Attached to a loop, <b>nah</b> runs when the loop finished "
          "normally - meaning it was never cut short by <b>dip</b>. It is "
          "perfect for searching:"),
        code(wpp("""
            numbers = squad([4, 9, 16, 25])

            spam n in numbers:
                bet n % 2 == 1:
                    yap("found an odd one:", n)
                    dip
            nah:
                yap("they were all even")
        """)),
        h2("Loops inside loops"),
        code(wpp("""
            spam row in range(1, 4):
                line = ""
                spam col in range(1, 4):
                    line = line + f"{row * col:3}"
                yap(line)
        """)),
    ]


def part_collections():
    return [
        h1("12. Collections"),
        p("Three keywords cover the three collections you will use "
          "constantly. <b>bodycount</b> tells you how many items any of them "
          "holds."),
        table(["W++", "What it is", "Good for", "Written as"],
              [["squad", "a list", "an ordered run of things", "[1, 2, 3]"],
               ["tea", "a dictionary", "looking things up by name", "{\"a\": 1}"],
               ["cult", "a set", "unique things, fast checks", "{1, 2, 3}"]],
              widths=[0.85 * inch, 1.15 * inch, 2.2 * inch, 1.9 * inch]),

        h2("squad: lists"),
        p("A list keeps things in order. You can build one with square "
          "brackets or with <b>squad</b>:"),
        code(wpp("""
            empty = squad()
            numbers = squad([3, 1, 2])
            letters = ["a", "b", "c"]
            mixed = [1, "two", nocap, npc]

            yap(empty, numbers, letters, mixed)
            yap(bodycount(numbers))
            yap(squad(range(5)))
            yap(squad("abc"))
        """)),
        p("Reach into a list by position, starting at zero:"),
        code(wpp("""
            days = squad(["mon", "tue", "wed", "thu", "fri"])

            yap(days[0], days[2], days[-1])
            yap(days[1:3])
            yap(days[:2])
            yap(days[-2:])

            days[0] = "MON"
            yap(days)
        """)),
        p("Changing a list:"),
        code(wpp("""
            items = squad(["b"])

            items.append("c")
            items.insert(0, "a")
            yap(items)

            items.extend(["d", "e"])
            yap(items)

            removed = items.pop()
            yap("removed", removed, "leaving", items)

            items.remove("a")
            yap(items)

            yap("index of c:", items.index("c"))
            yap("how many b:", items.count("b"))
        """)),
        p("Sorting and reversing:"),
        code(wpp("""
            numbers = squad([3, 1, 4, 1, 5])

            yap(sorted(numbers))
            yap(sorted(numbers, reverse=nocap))
            yap("original untouched:", numbers)

            numbers.sort()
            yap("now sorted in place:", numbers)

            words = squad(["pear", "fig", "banana"])
            yap(sorted(words, key=bodycount))
            yap(squad(reversed(words)))
            yap(sum(numbers), min(numbers), max(numbers))
        """)),

        h2("tea: dictionaries"),
        p("A dictionary stores values under names, so you can look them up "
          "instantly. Each entry is a <i>key</i> and a <i>value</i>:"),
        code(wpp("""
            scores = tea(ada=91, alan=84)
            also = {"grace": 99, "edsger": 77}

            yap(scores)
            yap(also)
            yap(scores["ada"])
            yap(bodycount(scores))
        """)),
        p("Adding, changing and removing entries:"),
        code(wpp("""
            player = tea()

            player["name"] = "Ada"
            player["score"] = 0
            yap(player)

            player["score"] = player["score"] + 10
            yap(player)

            del player["score"]
            yap(player)
        """)),
        p("Asking for a key that is not there is an error. <b>get</b> is the "
          "safe way, and it lets you supply a fallback:"),
        code(wpp("""
            scores = tea(ada=91)

            yap(scores.get("ada"))
            yap(scores.get("nobody"))
            yap(scores.get("nobody", 0))
            yap("ada" in scores, "nobody" in scores)
        """)),
        p("Looping over a dictionary:"),
        code(wpp("""
            scores = tea(ada=91, alan=84, grace=99)

            spam name in scores:
                yap(name)

            yap("---")
            spam name, score in scores.items():
                yap(name, score)

            yap("---")
            yap(sorted(scores.keys()))
            yap(sorted(scores.values()))
            yap("best:", max(scores, key=scores.get))
        """)),

        h2("cult: sets"),
        p("A set holds each item only once and answers <i>is this in "
          "there?</i> very quickly. It has no order:"),
        code(wpp("""
            tags = cult(["red", "blue", "red", "green"])
            yap(bodycount(tags))
            yap(sorted(tags))

            tags.add("blue")
            yap("adding a duplicate changes nothing:", bodycount(tags))

            tags.add("pink")
            tags.discard("red")
            yap(sorted(tags))
            yap("blue" in tags)
        """)),
        p("The classic use is removing duplicates from a list:"),
        code(wpp("""
            numbers = squad([3, 1, 3, 2, 1, 3])
            unique = squad(cult(numbers))
            yap(sorted(unique))
        """)),
        p("Sets can be compared against each other:"),
        code(wpp("""
            a = cult([1, 2, 3, 4])
            b = cult([3, 4, 5])

            yap("in both:", sorted(a & b))
            yap("in either:", sorted(a | b))
            yap("only in a:", sorted(a - b))
            yap("in one but not both:", sorted(a ^ b))
        """)),

        h2("Tuples: fixed little groups"),
        p("A tuple is like a list that cannot be changed. It has no W++ "
          "nickname; write it with round brackets. You have already seen "
          "them coming out of <font face='%s'>enumerate</font> and "
          "<font face='%s'>items</font>:" % (MONO, MONO)),
        code(wpp("""
            point = (3, 4)
            yap(point, point[0], bodycount(point))

            x, y = point
            yap("unpacked:", x, y)

            cook middle(a, b):
                spill (a + b) / 2, a * b

            average, product = middle(4, 6)
            yap(average, product)
        """)),

        h2("Collections inside collections"),
        code(wpp("""
            grid = squad([[1, 2, 3], [4, 5, 6]])
            yap(grid[0])
            yap(grid[1][2])

            people = squad([
                tea(name="Ada", langs=squad(["W++", "Python"])),
                tea(name="Alan", langs=squad(["Maths"])),
            ])

            spam person in people:
                yap(person["name"], "knows", ", ".join(person["langs"]))
        """)),
    ]


def part_comprehensions():
    return [
        h1("13. Building collections in one line"),
        p("A <i>comprehension</i> builds a collection from another one. It is "
          "the same <b>spam</b> you already know, written inside the "
          "brackets. Start with the long way:"),
        code(wpp("""
            squares = squad()
            spam n in range(6):
                squares.append(n * n)
            yap(squares)
        """)),
        p("Now the short way. Read it as <i>n times n, for each n in "
          "range(6)</i>:"),
        code('yap([n * n spam n in range(6)])'),
        p("Add a <b>bet</b> at the end to keep only some of the items:"),
        code(wpp("""
            yap([n spam n in range(20) bet n % 3 == 0])
            words = squad(["fig", "banana", "pear", "kiwi"])
            yap([w.upper() spam w in words bet bodycount(w) > 3])
        """)),
        p("Put a one-line decision in the front half to transform items "
          "differently:"),
        code('yap(["even" bet n % 2 == 0 nah "odd" spam n in range(5)])'),
        p("The same shape builds dictionaries and sets:"),
        code(wpp("""
            words = squad(["fig", "banana", "pear"])

            yap({w: bodycount(w) spam w in words})
            yap(sorted({bodycount(w) spam w in words}))
        """)),
        p("Without brackets around it, the same expression can be fed "
          "straight into something that adds things up - no list is built at "
          "all, which matters when the numbers get large:"),
        code(wpp("""
            yap(sum(n spam n in range(1, 101)))
            yap(max(bodycount(w) spam w in squad(["fig", "banana"])))
            yap(any(n > 90 spam n in squad([10, 95])))
            yap(all(n > 90 spam n in squad([10, 95])))
        """)),
        p("Comprehensions can nest, which is how you flatten or build grids:"),
        code(wpp("""
            grid = squad([[1, 2], [3, 4]])
            yap([cell spam row in grid spam cell in row])
            yap([[r * c spam c in range(1, 4)] spam r in range(1, 4)])
        """)),
        note("Comprehensions are lovely for one clear step. If you need two "
             "steps and a couple of conditions, a normal <b>spam</b> loop is "
             "easier to read - and easier to fix later."),
    ]


def part_functions():
    return [
        h1("14. Functions"),
        p("A function is a named piece of program you can run whenever you "
          "like. <b>cook</b> starts one and <b>spill</b> sends a value back:"),
        code(wpp("""
            cook greet(name):
                spill "Hello, " + name

            yap(greet("Ada"))
            yap(greet("Alan"))
        """)),
        p("The names in the brackets are <i>parameters</i> - stand-ins filled "
          "with whatever you pass in. A function without a <b>spill</b> "
          "simply does its work and hands back <b>npc</b>:"),
        code(wpp("""
            cook announce(text):
                yap("***", text, "***")

            result = announce("no spill here")
            yap("it gave back:", result)
        """)),
        h2("Several parameters, and defaults"),
        code(wpp("""
            cook power(base, exponent=2):
                spill base ** exponent

            yap(power(5))
            yap(power(5, 3))
            yap(power(exponent=3, base=2))
        """)),
        note("Naming your arguments as in <font face='%s'>power(base=2)</font> "
             "makes a call much easier to read when a function takes several "
             "things." % MONO),
        p("<b>spill</b> can hand back several values at once:"),
        code(wpp("""
            cook stats(numbers):
                spill min(numbers), max(numbers), sum(numbers) / bodycount(numbers)

            low, high, mean = stats(squad([4, 8, 15, 16]))
            yap(low, high, mean)
        """)),
        p("<b>spill</b> also ends the function on the spot, which is handy "
          "for dealing with awkward cases first:"),
        code(wpp("""
            cook safe_divide(a, b):
                bet b == 0:
                    spill npc
                spill a / b

            yap(safe_divide(10, 2))
            yap(safe_divide(10, 0))
        """)),
        h2("Taking any number of arguments"),
        code(wpp("""
            cook total(*numbers):
                spill sum(numbers)

            yap(total(1, 2), total(1, 2, 3, 4))

            cook describe(**details):
                spam key, value in details.items():
                    yap(key, "=", value)

            describe(name="Ada", score=91)
        """)),
        h2("Functions calling themselves"),
        p("A function may call itself. Always give it a case that stops:"),
        code(wpp("""
            cook factorial(n):
                bet n <= 1:
                    spill 1
                spill n * factorial(n - 1)

            yap(factorial(5))
            yap([factorial(n) spam n in range(1, 8)])
        """)),
        h2("Tiny throwaway functions"),
        p("<font face='%s'>lambda</font> makes a one-expression function "
          "without a name. It is mostly used to tell "
          "<font face='%s'>sorted</font> what to sort by:" % (MONO, MONO)),
        code(wpp("""
            double = lambda n: n * 2
            yap(double(21))

            people = squad([
                tea(name="Ada", score=91),
                tea(name="Alan", score=84),
                tea(name="Grace", score=99),
            ])

            ranked = sorted(people, key=lambda person: person["score"], reverse=nocap)
            spam person in ranked:
                yap(person["name"], person["score"])
        """)),
        h2("Explaining yourself"),
        p("A string on the first line of a function is a note for whoever "
          "reads it next - often you:"),
        code(wpp("""
            cook celsius_to_f(c):
                "Convert a Celsius temperature to Fahrenheit."
                spill c * 9 / 5 + 32

            yap(celsius_to_f(100))
            yap(celsius_to_f.__doc__)
        """)),

        h1("15b. Where names live"),
        p("A name made inside a function belongs to that function and "
          "disappears when it ends:"),
        code(wpp("""
            cook demo():
                inside = "local"
                yap("in the function:", inside)

            demo()
            yap("outside, asking for it:")
        """)),
        p("Reading an outer name is fine; <i>changing</i> one needs "
          "permission:"),
        code(wpp("""
            total = 0

            cook add_wrong(n):
                total = n

            cook add_right(n):
                global total
                total = total + n

            add_wrong(5)
            yap("after add_wrong:", total)

            add_right(5)
            add_right(3)
            yap("after add_right:", total)
        """)),
        p("A function inside a function can remember the outer one's values. "
          "<font face='%s'>nonlocal</font> lets it change them:" % MONO),
        code(wpp("""
            cook make_counter():
                count = 0
                cook step():
                    nonlocal count
                    count = count + 1
                    spill count
                spill step

            tick = make_counter()
            yap(tick(), tick(), tick())
        """)),
        note("Reach for <font face='%s'>global</font> sparingly. Passing "
             "values in and spilling results back is easier to follow." % MONO),
    ]


def part_classes():
    return [
        h1("16b. Your own kinds of thing"),
        p("A <font face='%s'>class</font> describes a kind of thing: the data "
          "each one carries and what it can do. <font face='%s'>class</font> "
          "itself has no nickname, but the methods inside it are made with "
          "<b>cook</b>:" % (MONO, MONO)),
        code(wpp("""
            class Dog:
                cook __init__(self, name):
                    self.name = name
                    self.tricks = squad()

                cook learn(self, trick):
                    self.tricks.append(trick)

                cook show_off(self):
                    bet not self.tricks:
                        spill f"{self.name} knows nothing yet"
                    spill f"{self.name} can " + ", ".join(self.tricks)

            rex = Dog("Rex")
            rex.learn("sit")
            rex.learn("roll over")
            yap(rex.show_off())

            fido = Dog("Fido")
            yap(fido.show_off())
        """)),
        bullets([
            "<font face='%s'>__init__</font> runs when you make a new one, "
            "and sets up its data." % MONO,
            "<font face='%s'>self</font> is the particular object being "
            "worked on. Every method takes it as the first parameter, and you "
            "never pass it yourself." % MONO,
            "<font face='%s'>self.name</font> is data belonging to that one "
            "object - <font face='%s'>rex</font> and "
            "<font face='%s'>fido</font> have their own." % (MONO, MONO, MONO),
        ]),
        h2("Printing your objects nicely"),
        p("Give a class <font face='%s'>__str__</font> and it decides what "
          "<b>yap</b> shows:" % MONO),
        code(wpp("""
            class Point:
                cook __init__(self, x, y):
                    self.x = x
                    self.y = y

                cook __str__(self):
                    spill f"({self.x}, {self.y})"

                cook __eq__(self, other):
                    spill self.x == other.x and self.y == other.y

            a = Point(1, 2)
            b = Point(1, 2)
            yap(a)
            yap(a == b, a is b)
        """)),
        h2("Building on another class"),
        code(wpp("""
            class Animal:
                cook __init__(self, name):
                    self.name = name

                cook speak(self):
                    spill "..."

                cook introduce(self):
                    spill f"{self.name} says {self.speak()}"

            class Cat(Animal):
                cook speak(self):
                    spill "meow"

            class LoudCat(Cat):
                cook speak(self):
                    spill super().speak().upper() + "!"

            spam pet in squad([Animal("Thing"), Cat("Tom"), LoudCat("Rex")]):
                yap(pet.introduce())
        """)),
        note("A method cannot be named after a W++ keyword - "
             "<font face='%s'>cook dip(self)</font> is refused, because "
             "<b>dip</b> is reserved. Data attributes are fine: "
             "<font face='%s'>self.cap = 10</font> works, because a name "
             "after a dot is never a keyword. Section 16 has the details." % (MONO, MONO)),
    ]


def part_generators():
    return [
        h1("17b. Producing values lazily"),
        p("A function that uses <font face='%s'>yield</font> instead of "
          "<b>spill</b> hands back values one at a time, only as they are "
          "asked for. It is how you work with something long - or endless - "
          "without building it all first:" % MONO),
        code(wpp("""
            cook countdown(n):
                grind n > 0:
                    yield n
                    n = n - 1

            spam value in countdown(4):
                yap(value)

            yap(squad(countdown(3)))
        """)),
        p("Because nothing is computed until it is needed, an endless "
          "generator is perfectly safe as long as you stop taking from it:"),
        code(wpp("""
            cook evens():
                n = 0
                grind nocap:
                    yield n
                    n = n + 2

            picked = squad()
            spam value in evens():
                bet bodycount(picked) == 5:
                    dip
                picked.append(value)
            yap(picked)
        """)),
        p("<font face='%s'>yield from</font> passes along everything another "
          "generator produces:" % MONO),
        code(wpp("""
            cook first_part():
                yield "a"
                yield "b"

            cook everything():
                yield from first_part()
                yield "c"

            yap(squad(everything()))
        """)),
    ]


def part_errors():
    rows = [[name, message] for name, message in SKILL_ISSUES.items()]
    return [
        h1("15. When things go wrong"),
        p("W++ replaces Python's tracebacks with its own messages, called the "
          "<b>Skill Issue Protocol</b>. Here is one:"),
        code(wpp("""
            yap("this line is fine")
            yap(undefined_name)
        """), expect_error=True),
        p("Read it from the top: <i>what</i> went wrong, <i>where</i>, the "
          "line itself, then Python's own description. The line number is the "
          "line in your file, so you can go straight to it."),
        note("In a real terminal each message is preceded by a siren emoji. "
             "It is left out of this guide only because the PDF fonts cannot "
             "draw it."),
        h2("The seven messages"),
        table(["When Python says", "W++ says"], rows,
              widths=[1.5 * inch, 4.7 * inch]),
        p("Anything outside this table is reported as <i>Unspecified skill "
          "issue</i> with the real name in brackets, so you are never left "
          "without a clue:"),
        code('t = tea(a=1)\nyap(t["missing"])', expect_error=True),
        h2("The mistakes you will actually make"),
        p("<b>A name that does not exist.</b> Usually a typo, or using "
          "something before you set it:"),
        code('total = 10\nyap(totl)', expect_error=True),
        p("<b>Mixing text and numbers.</b> Convert one of them:"),
        code('yap("Score: " + 10)', expect_error=True),
        p("<b>Reaching past the end of a list.</b> Five items means positions "
          "0 to 4:"),
        code('items = squad(["a", "b"])\nyap(items[5])', expect_error=True),
        p("<b>Dividing by zero.</b> Check the divisor first:"),
        code('yap(10 / 0)', expect_error=True),
        p("<b>Indentation that does not line up.</b> Keep to four spaces per "
          "level and never mix in tabs:"),
        code('cook f():\n    yap(1)\n        yap(2)', expect_error=True),
        h2("Handling errors instead of crashing"),
        p("Wrap the risky part in <font face='%s'>try</font> and say what to "
          "do when it fails. This is how you deal with a user typing "
          "nonsense:" % MONO),
        code(wpp("""
            cook read_number(text):
                try:
                    spill int(text)
                except ValueError:
                    yap("that was not a number:", text)
                    spill npc

            yap(read_number("42"))
            yap(read_number("banana"))
        """)),
        p("A fuller shape: <b>nah</b> runs when nothing went wrong, and "
          "<font face='%s'>finally</font> runs either way:" % MONO),
        code(wpp("""
            cook divide(a, b):
                try:
                    answer = a / b
                except ZeroDivisionError:
                    yap("cannot divide by zero")
                nah:
                    yap("got", answer)
                finally:
                    yap("done with", a, b)

            divide(10, 2)
            divide(10, 0)
        """)),
        p("Catch several kinds at once, and look at the problem itself:"),
        code(wpp("""
            cook attempt(items, index):
                try:
                    spill items[index]
                except (IndexError, TypeError) as problem:
                    spill f"failed: {problem}"

            data = squad(["a", "b"])
            yap(attempt(data, 0))
            yap(attempt(data, 9))
            yap(attempt(data, "x"))
        """)),
        p("You can raise problems yourself when your function is given "
          "something it cannot work with:"),
        code(wpp("""
            cook set_age(age):
                bet age < 0:
                    raise ValueError("age cannot be negative")
                spill age

            yap(set_age(30))
            try:
                set_age(-1)
            except ValueError as problem:
                yap("refused:", problem)
        """)),
        p("The loop that keeps asking until the input is valid is worth "
          "memorising - it combines almost everything so far:"),
        code(wpp("""
            grind nocap:
                raw = dm("Age: ")
                try:
                    age = int(raw)
                except ValueError:
                    yap("Please type digits.")
                    skrrt
                bet age < 0:
                    yap("Please type a positive number.")
                    skrrt
                dip

            yap("Thank you, age is", age)
        """), answers=["abc", "-3", "30"]),
    ]


def part_reserved():
    reserved = [(word, target) for word, target in KEYWORDS.items()]
    rows = [[w, t] for w, t in reserved]
    return [
        h1("16. Reserved words: the one real gotcha"),
        p("This is the only place W++ can surprise you, so it gets its own "
          "section. The nineteen keywords are <b>reserved</b>: you cannot use "
          "one as the name of your own variable, function, class or "
          "parameter."),
        p("The reason is simple once you have seen the pipeline in section 1. "
          "If you write a function called <b>dip</b>, the translator turns "
          "every <b>dip</b> into <font face='%s'>break</font> - both where "
          "you defined it and everywhere you called it. There is no way to "
          "tell the two apart. Python has the same rule about its own words: "
          "you cannot write <font face='%s'>def break()</font> either." % (MONO, MONO)),
        p("W++ tells you plainly when you try:"),
        code(wpp("""
            class Stack:
                cook dip(self):
                    spill "pop"
        """), expect_error=True),
        h2("What is fine"),
        p("Only the exact words are taken. Anything longer is yours:"),
        code(wpp("""
            cookie = "fine"
            capacity = 100
            recap = "also fine"
            bet_size = 5
            my_squad = squad([1, 2])
            spam_folder = squad()

            yap(cookie, capacity, recap, bet_size, my_squad, spam_folder)
        """)),
        p("Names after a dot are never keywords, so object data and methods "
          "can be called anything:"),
        code(wpp("""
            class Bottle:
                cook __init__(self):
                    self.cap = "on"
                    self.range = squad([1, 2])

            b = Bottle()
            yap(b.cap, b.range)
        """)),
        h2("If you want a name that is taken"),
        p("Add a word, or use a synonym. All of these are ordinary names:"),
        snippet(
            "  wanted        use instead\n"
            "  ------------  -----------------------------\n"
            "  dip           pop, remove, leave, exit_loop\n"
            "  cap           limit, maximum, lid\n"
            "  spill         give, emit, output\n"
            "  range         span, bounds, extent\n"
            "  squad         group, team, my_squad\n"
            "  tea           table, lookup, mapping\n"
            "  cult          unique, distinct"
        ),
        h2("The full reserved list"),
        table(["W++ word", "Becomes"], rows, widths=[1.6 * inch, 1.6 * inch]),
        note("Python's own keywords are also reserved, exactly as in Python: "
             "<font face='%s'>and, or, not, in, is, if, for, while, def, "
             "class, return, import, try, except, finally, with, as, lambda, "
             "global, nonlocal, yield, raise, assert, pass, del, None, True, "
             "False</font>. You write most of these as their W++ nicknames "
             "anyway." % MONO),
    ]


def part_python_side():
    return [
        h1("17. Everything Python brings with it"),
        p("Nineteen words got nicknames. Everything else in Python is "
          "untouched and available. This is what makes W++ able to build real "
          "things, and it is worth skimming so you know what you already "
          "have."),
        h2("Words that stay exactly as they are"),
        snippet(
            "  and    or     not    in     is     None-checks via npc\n"
            "  class  import from   as     pass   del\n"
            "  try    except finally raise  assert with\n"
            "  lambda yield  global nonlocal\n"
            "  match  case   async  await"
        ),
        h2("Built-in functions you will use"),
        table(["Function", "What it does"],
              [["int, float, str, bool", "convert between kinds of value"],
               ["sum, min, max", "add up, smallest, largest"],
               ["sorted, reversed", "ordered copy, reversed copy"],
               ["enumerate, zip", "count while looping, pair up two lists"],
               ["abs, round, divmod", "size, rounding, quotient and remainder"],
               ["any, all", "is one true, are they all true"],
               ["map, filter", "apply to each, keep some"],
               ["type, isinstance", "what kind of value is this"],
               ["input, print, len", "the plain names behind dm, yap, bodycount"]],
              widths=[2.0 * inch, 4.2 * inch]),
        note("The plain Python names still work. <font face='%s'>len(x)</font> "
             "and <font face='%s'>bodycount(x)</font> do the same thing, and "
             "<font face='%s'>list</font> and <b>squad</b> are the same "
             "function. Use the W++ words - they are the point - but nothing "
             "breaks if a plain one slips in." % (MONO, MONO, MONO)),
        h2("The standard library"),
        p("<font face='%s'>import</font> gives you Python's whole library. "
          "Nothing to install:" % MONO),
        code(wpp("""
            import math
            import random

            yap(math.sqrt(144), math.pi)
            yap(math.floor(3.7), math.ceil(3.2))

            random.seed(7)
            yap(random.randint(1, 6))
            yap(random.choice(squad(["rock", "paper", "scissors"])))
        """)),
        p("Other modules worth knowing early:"),
        code(wpp("""
            from collections import Counter
            import json

            words = "the cook will cook the meal".split()
            yap(Counter(words).most_common(2))

            data = tea(name="Ada", scores=squad([1, 2]))
            text = json.dumps(data)
            yap(text)
            yap(json.loads(text)["name"])
        """)),
        code(wpp("""
            import datetime

            day = datetime.date(2026, 1, 31)
            yap(day.year, day.month, day.day)
            yap(day.strftime("%d %B %Y"))
            yap(day + datetime.timedelta(days=1))
        """)),
        p("A short list to explore when you need it:"),
        table(["Module", "For"],
              [["math", "square roots, trigonometry, constants"],
               ["random", "dice, shuffling, random choices"],
               ["datetime", "dates, times, differences"],
               ["json", "saving and loading structured data"],
               ["collections", "Counter, defaultdict, deque"],
               ["itertools", "combinations, permutations, cycles"],
               ["re", "finding patterns in text"],
               ["os, pathlib", "files and folders"],
               ["statistics", "mean, median, standard deviation"],
               ["time", "timing things, pausing"]],
              widths=[1.5 * inch, 4.7 * inch]),
        h2("Reading and writing files"),
        p("Files work exactly as in Python. "
          "<font face='%s'>with</font> closes the file for you:" % MONO),
        snippet(
            'with open("notes.txt", "w") as handle:\n'
            '    handle.write("first line\\n")\n'
            '    handle.write("second line\\n")\n'
            '\n'
            'with open("notes.txt") as handle:\n'
            '    spam line in handle:\n'
            '        yap(line.strip())'
        ),
    ]


def part_tooling():
    return [
        h1("18. Tools that help"),
        h2("Seeing the Python behind your program"),
        p("This is the single most useful thing you can do when a program "
          "confuses you. <font face='%s'>--emit</font> prints the Python that "
          "your W++ turned into, without running it:" % MONO),
        # The Python shown here is produced by the real translator, not by
        # editing the source by hand.
        shell("python wpp.py --emit examples/vibe_check.wpp",
              translate(read_example("vibe_check.wpp")).rstrip()),
        p("If the Python looks right, the bug is in your logic. If the Python "
          "looks wrong, look for a keyword you used as a name."),
        h2("The dictionary, on demand"),
        shell("python wpp.py --keywords"),
        p("Prints the whole table from section 3 in your terminal."),
        h2("The error sound"),
        p("When a program fails, W++ plays "
          "<font face='%s'>audio/fah.mp3</font>. In the playground it plays "
          "whenever an error appears, and the speaker button in the output "
          "panel mutes it - your browser remembers the choice. In the "
          "terminal it plays only when you are running interactively, so "
          "piping output into a file stays quiet." % MONO),
        bullets([
            "<font face='%s'>--mute</font> turns it off for one run." % MONO,
            "<font face='%s'>--sound</font> forces it on even when output is "
            "piped." % MONO,
            "<font face='%s'>WPP_MUTE=1</font> in your environment mutes it "
            "everywhere." % MONO,
            "Replace <font face='%s'>audio/fah.mp3</font> with any MP3 to "
            "change it." % MONO,
        ]),
        note("If the file is missing, or your machine cannot play an MP3, the "
             "sound is skipped and the error is reported exactly as it would "
             "be otherwise. Nothing about your program depends on it."),
        h2("Everything the command offers"),
        table(["Command", "What it does"],
              [["python wpp.py FILE.wpp", "run a program"],
               ["python wpp.py --emit FILE.wpp", "show the generated Python"],
               ["python wpp.py --keywords", "print the keyword table"],
               ["python wpp.py --mute FILE.wpp", "run without the error sound"],
               ["python wpp.py --sound FILE.wpp", "force the error sound on"],
               ["python wpp.py --version", "print the W++ version"],
               ["python playground/server.py", "start the web playground"]],
              widths=[2.6 * inch, 3.6 * inch]),
        h2("Exit codes"),
        p("Useful if you ever run W++ from a script:"),
        table(["Code", "Meaning"],
              [["0", "the program finished normally"],
               ["1", "a skill issue stopped it"],
               ["2", "bad command line, or the file was not found"],
               ["130", "interrupted with Ctrl+C"]],
              widths=[0.9 * inch, 5.3 * inch]),
        h2("In the playground"),
        bullets([
            "<b>Run</b> or Ctrl+Enter runs what is in the editor.",
            "<b>Examples</b> loads a ready-made program.",
            "<b>Documentation</b> shows the keyword and error tables.",
            "<b>Stop</b> ends a program that is still going.",
            "<b>Copy</b> and <b>Reset</b> act on the editor.",
            "When a program calls <b>dm</b>, type your answer directly in the "
            "output panel and press Enter.",
            "A runaway loop is stopped after ten seconds of running - time "
            "spent waiting for you to type does not count.",
            "The speaker button mutes the sound that plays when a program "
            "fails.",
        ]),
    ]


def part_programs():
    return [
        h1("19. Complete programs"),
        p("Everything up to here, put to work. Each program is short enough "
          "to read in one go and does something real."),

        h2("Number guessing game"),
        p("Loops, input, decisions and a running count:"),
        code(wpp("""
            import random

            random.seed(3)
            secret = random.randint(1, 50)
            tries = 0

            yap("I picked a number between 1 and 50.")

            grind nocap:
                guess = int(dm("Your guess: "))
                tries = tries + 1

                bet guess < secret:
                    yap("Higher.")
                plotwist guess > secret:
                    yap("Lower.")
                nah:
                    yap(f"Got it in {tries} tries. It was {secret}.")
                    dip
        """), answers=["25", "12", "18", "15", "16"]),

        h2("Grade book"),
        p("A dictionary of lists, and a report built from it:"),
        code(wpp("""
            grades = tea()
            grades["Ada"] = squad([91, 88, 95])
            grades["Alan"] = squad([72, 80, 68])
            grades["Grace"] = squad([100, 98, 99])

            cook average(marks):
                spill sum(marks) / bodycount(marks)

            cook letter(mark):
                bet mark >= 90:
                    spill "A"
                plotwist mark >= 80:
                    spill "B"
                plotwist mark >= 70:
                    spill "C"
                nah:
                    spill "F"

            yap(f"{'Name':<8}{'Avg':>7}  Grade")
            yap("-" * 24)

            ranked = sorted(grades.items(), key=lambda entry: average(entry[1]), reverse=nocap)
            spam name, marks in ranked:
                mean = average(marks)
                yap(f"{name:<8}{mean:>7.1f}  {letter(mean)}")

            everyone = [mark spam marks in grades.values() spam mark in marks]
            yap("-" * 24)
            yap(f"class average: {average(everyone):.1f}")
            yap(f"best single mark: {max(everyone)}")
        """)),

        h2("Word frequency counter"),
        p("Text in, ranked counts out:"),
        code(wpp("""
            text = """ + '"""' + """
            the quick brown fox jumps over the lazy dog
            the dog barks and the fox runs
            """ + '"""' + """

            counts = tea()
            spam word in text.lower().split():
                clean = word.strip(".,!?")
                bet not clean:
                    skrrt
                counts[clean] = counts.get(clean, 0) + 1

            ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))

            yap(f"{bodycount(counts)} different words")
            spam word, n in ranked[:5]:
                bar = "#" * n
                yap(f"{word:<8}{n:>3} {bar}")
        """)),

        h2("To-do list"),
        p("A list of dictionaries, and functions that work on it:"),
        code(wpp("""
            tasks = squad()

            cook add(title, priority="normal"):
                tasks.append(tea(title=title, priority=priority, done=cap))

            cook finish(title):
                spam task in tasks:
                    bet task["title"] == title:
                        task["done"] = nocap
                        spill nocap
                spill cap

            cook show():
                bet not tasks:
                    yap("nothing to do")
                    spill
                order = tea(high=0, normal=1, low=2)
                spam task in sorted(tasks, key=lambda t: order[t["priority"]]):
                    mark = "x" bet task["done"] nah " "
                    yap(f"[{mark}] {task['title']} ({task['priority']})")

            add("write the guide", "high")
            add("water the plants", "low")
            add("review pull request")

            finish("water the plants")
            yap("found the task:", finish("not a real task"))

            show()
            left = bodycount([t spam t in tasks bet not t["done"]])
            yap(f"{left} still open")
        """)),

        h2("Bank account, as a class"),
        code(wpp("""
            class Account:
                cook __init__(self, owner, balance=0):
                    self.owner = owner
                    self.balance = balance
                    self.history = squad()

                cook deposit(self, amount):
                    bet amount <= 0:
                        raise ValueError("deposit must be positive")
                    self.balance = self.balance + amount
                    self.history.append(f"+{amount}")

                cook withdraw(self, amount):
                    bet amount > self.balance:
                        spill cap
                    self.balance = self.balance - amount
                    self.history.append(f"-{amount}")
                    spill nocap

                cook __str__(self):
                    spill f"{self.owner}: {self.balance}"

            account = Account("Ada", 100)
            account.deposit(50)

            yap(account)
            yap("withdraw 30:", account.withdraw(30))
            yap("withdraw 500:", account.withdraw(500))
            yap(account)
            yap("history:", ", ".join(account.history))

            try:
                account.deposit(-5)
            except ValueError as problem:
                yap("refused:", problem)
        """)),

        h2("FizzBuzz, three ways"),
        p("The classic, written normally, as a function, and squeezed into "
          "one line:"),
        code(wpp("""
            spam i in range(1, 16):
                bet i % 15 == 0:
                    yap("FizzBuzz")
                plotwist i % 3 == 0:
                    yap("Fizz")
                plotwist i % 5 == 0:
                    yap("Buzz")
                nah:
                    yap(i)
        """)),
        code(wpp("""
            cook fizzbuzz(n):
                bet n % 15 == 0:
                    spill "FizzBuzz"
                plotwist n % 3 == 0:
                    spill "Fizz"
                plotwist n % 5 == 0:
                    spill "Buzz"
                spill str(n)

            yap(" ".join([fizzbuzz(n) spam n in range(1, 16)]))
        """)),

        h2("Sorting, from scratch"),
        p("Recursion and comprehensions together:"),
        code(wpp("""
            cook quicksort(items):
                bet bodycount(items) <= 1:
                    spill items
                pivot = items[bodycount(items) // 2]
                smaller = [i spam i in items bet i < pivot]
                same = [i spam i in items bet i == pivot]
                bigger = [i spam i in items bet i > pivot]
                spill quicksort(smaller) + same + quicksort(bigger)

            yap(quicksort(squad([5, 3, 8, 1, 9, 2, 7, 3])))
        """)),

        h2("Prime numbers"),
        code(wpp("""
            cook primes_upto(limit):
                maybe = [nocap] * (limit + 1)
                maybe[0] = cap
                bet limit >= 1:
                    maybe[1] = cap

                n = 2
                grind n * n <= limit:
                    bet maybe[n]:
                        multiple = n * n
                        grind multiple <= limit:
                            maybe[multiple] = cap
                            multiple = multiple + n
                    n = n + 1

                spill [i spam i in range(limit + 1) bet maybe[i]]

            found = primes_upto(60)
            yap(f"{bodycount(found)} primes up to 60")
            yap(found)
        """)),

        h2("Finding a way through a graph"),
        p("Sets, lists as queues, and a search that ends when it should:"),
        code(wpp("""
            routes = tea()
            routes["home"] = squad(["shop", "park"])
            routes["shop"] = squad(["school"])
            routes["park"] = squad(["school", "lake"])
            routes["school"] = squad(["library"])
            routes["lake"] = squad([])
            routes["library"] = squad([])

            cook shortest(start, goal):
                queue = squad([squad([start])])
                seen = cult([start])

                grind bodycount(queue) > 0:
                    path = queue.pop(0)
                    here = path[-1]

                    bet here == goal:
                        spill path

                    spam nxt in routes.get(here, squad()):
                        bet nxt in seen:
                            skrrt
                        seen.add(nxt)
                        queue.append(path + squad([nxt]))

                spill npc

            yap(" -> ".join(shortest("home", "library")))
            yap("to the moon:", shortest("home", "moon"))
        """)),
    ]


def part_habits():
    return [
        h1("20. Habits worth picking up"),
        bullets([
            "<b>Four spaces per level of indentation.</b> Never mix tabs and "
            "spaces in one file.",
            "<b>Name things for what they hold.</b> "
            "<font face='%s'>player_score</font> beats "
            "<font face='%s'>ps</font>, and you will thank yourself in a "
            "week." % (MONO, MONO),
            "<b>Use lower_case_with_underscores</b> for variables and "
            "functions, and CapitalWords for classes. That is what Python "
            "programmers expect.",
            "<b>Leave comments for why, not what.</b> The code already says "
            "what it does.",
            "<b>Keep functions small.</b> If one does not fit on a screen, it "
            "is probably two functions.",
            "<b>Print things while you work.</b> A quick <b>yap</b> showing a "
            "value is the fastest way to find out where a program went wrong.",
            "<b>Reach for --emit when stuck.</b> Seeing the Python usually "
            "makes the problem obvious.",
            "<b>Read the error, all of it.</b> The message says what, the "
            "line says where, and the details say why.",
        ]),
        h2("Comments"),
        code(wpp("""
            # A full line comment.
            yap("code")  # or at the end of a line

            # Keywords inside comments are ignored:
            # cook spill yap bet nah
            yap("still fine")
        """)),
        h2("A note on speed"),
        p("W++ runs at Python's speed, because it <i>is</i> Python by the "
          "time it executes. The keyword swap happens once, before your "
          "program starts, and costs nothing measurable. Nothing in this "
          "guide is slower than the Python it becomes."),
    ]


def part_limits():
    return [
        h1("21. What W++ does not do"),
        p("An honest list, so nothing catches you out:"),
        bullets([
            "<b>Keywords are reserved.</b> Section 16 covers this. It is the "
            "one thing you will hit.",
            "<b>Only the nineteen words have nicknames.</b> "
            "<font face='%s'>and</font>, <font face='%s'>or</font>, "
            "<font face='%s'>not</font>, <font face='%s'>class</font>, "
            "<font face='%s'>import</font>, <font face='%s'>try</font> and "
            "the rest are written the Python way." % ((MONO,) * 6),
            "<b>One file per program.</b> You can import Python modules, but "
            "you cannot yet import another <font face='%s'>.wpp</font> "
            "file." % MONO,
            "<b>No interactive prompt.</b> There is no W++ REPL; use a file "
            "or the playground.",
            "<b>One error at a time.</b> The first failure stops the program, "
            "just as in Python.",
            "<b>Keywords are syntax, not a display layer.</b> "
            "<font face='%s'>yap(nocap)</font> prints "
            "<i>True</i>." % MONO,
            "<b>The playground is a local tool.</b> It runs code as you, with "
            "only a time limit, so keep it on your own machine.",
        ]),
        p("None of these limit what you can build. The standard library, "
          "classes, generators and the rest of Python are all available - so "
          "the ceiling on what you can make in W++ is your imagination, not "
          "the language."),
    ]


def two_columns(left, right, column=40, gap=3):
    """Lay two lists of lines side by side without hand-counted spaces."""
    widest = max((len(line) for line in left), default=0)
    if widest > column:
        PROBLEMS.append("cheat sheet: left column needs %d columns" % widest)
    lines = []
    for index in range(max(len(left), len(right))):
        one = left[index] if index < len(left) else ""
        two = right[index] if index < len(right) else ""
        lines.append((one.ljust(column) + " " * gap + two).rstrip())
    return "\n".join(lines)


def part_cheatsheet():
    left = [
        "OUTPUT AND INPUT",
        '  yap("hi")',
        '  yap(a, b, sep="-")',
        '  yap("no newline", end="")',
        '  name = dm("Who? ")',
        '  n = int(dm("Number: "))',
        "",
        "TRUTH",
        "  nocap   cap   npc",
        "  ==  !=  <  >  <=  >=",
        "  and  or  not  in  is",
        "",
        "COLLECTIONS",
        "  s = squad([1, 2, 3])",
        "  t = tea(a=1, b=2)",
        "  c = cult([1, 2, 2])",
        "  bodycount(s)",
        "  s[0]   s[-1]   s[1:3]",
        "  s.append(4)   s.pop()",
        '  t["a"]   t.get("z", 0)',
        "  t.items()   t.keys()",
        "  c.add(3)   c & c2   c | c2",
        "",
        "STRINGS",
        '  f"{name} has {n} items"',
        '  f"{value:.2f}"',
        '  "a,b".split(",")',
        '  "-".join(parts)',
        "  text.strip().upper()",
        '  text.replace("a", "b")',
        "  bodycount(text)",
        "",
        "RUNNING",
        "  python wpp.py prog.wpp",
        "  python wpp.py --emit prog.wpp",
        "  python wpp.py --keywords",
        "  python playground/server.py",
    ]
    right = [
        "DECISIONS",
        "  bet x > 10:",
        '      yap("big")',
        "  plotwist x > 5:",
        '      yap("medium")',
        "  nah:",
        '      yap("small")',
        "",
        '  label = "y" bet ok nah "n"',
        "",
        "LOOPS",
        "  spam i in range(5):",
        "      yap(i)",
        "",
        "  spam item in things:",
        "      yap(item)",
        "",
        "  grind n > 0:",
        "      n = n - 1",
        "",
        "  dip     leave the loop",
        "  skrrt   next round",
        "",
        "COMPREHENSIONS",
        "  [n * n spam n in range(5)]",
        "  [n spam n in xs bet n > 2]",
        "  {k: v spam k, v in pairs}",
        "",
        "FUNCTIONS",
        "  cook add(a, b=1):",
        "      spill a + b",
        "",
        "  cook many(*args, **kw):",
        "      spill args, kw",
        "",
        "  f = lambda n: n * 2",
    ]
    more_left = [
        "CLASSES",
        "  class Dog:",
        "      cook __init__(self, n):",
        "          self.name = n",
        "",
        "      cook speak(self):",
        '          spill "woof"',
        "",
        "  rex = Dog(\"Rex\")",
        "  yap(rex.speak())",
    ]
    more_right = [
        "ERRORS",
        "  try:",
        "      risky()",
        "  except ValueError as e:",
        '      yap("oops", e)',
        "  nah:",
        '      yap("fine")',
        "  finally:",
        '      yap("always")',
        "",
        '  raise ValueError("nope")',
    ]
    return [
        PageBreak(),
        h1("23. Cheat sheet"),
        snippet(two_columns(left, right)),
        snippet(two_columns(more_left, more_right)),
    ]


def part_next_steps():
    return [
        h1("22. Where to go next"),
        p("You now have the whole language. The fastest way to make it stick "
          "is not to read more - it is to break things on purpose."),
        bullets([
            "Open the playground, load an example, and change it until it "
            "stops working. Read the error, fix it, change it again. That "
            "loop is how programmers actually learn.",
            "Pick one program from section 19 and add a feature to it. Give "
            "the grade book a pass mark you can set. Let the to-do list save "
            "to a file with <font face='%s'>json</font>." % MONO,
            "When something confuses you, run "
            "<font face='%s'>--emit</font> and read the Python. It is the "
            "quickest way to see what your code really said." % MONO,
            "Write something you actually want. A dice roller, a quiz, a "
            "budget tracker, a text adventure. Everything in this guide was "
            "chosen because it turns up in real little programs.",
        ]),
        p("And remember the one rule that unlocks the rest: <b>if Python can "
          "do it, W++ can do it</b>. Anything you find in a Python tutorial "
          "works here, with nineteen words swapped."),
    ]


def build_content():
    parts = []
    parts += part_intro()
    parts += part_setup()
    parts += part_dictionary()
    parts += part_output_input()
    parts += part_values()
    parts += part_strings()
    parts += part_truth()
    parts += part_decisions()
    parts += part_loops()
    parts += part_collections()
    parts += part_comprehensions()
    parts += part_functions()
    parts += part_errors()
    parts += part_reserved()
    parts += part_python_side()
    parts += part_classes()
    parts += part_generators()
    parts += part_tooling()
    parts += part_programs()
    parts += part_habits()
    parts += part_limits()
    parts += part_next_steps()
    parts += part_cheatsheet()
    return parts


# --------------------------------------------------------------------- styling

def make_styles():
    sheet = getSampleStyleSheet()
    styles = {}

    styles["title"] = ParagraphStyle(
        "title", parent=sheet["Title"], fontName=BODY_BOLD, fontSize=34,
        leading=40, textColor=INK, alignment=TA_CENTER, spaceAfter=6)
    styles["subtitle"] = ParagraphStyle(
        "subtitle", parent=sheet["Normal"], fontName=BODY, fontSize=14,
        leading=20, textColor=MUTED, alignment=TA_CENTER)
    styles["cover_note"] = ParagraphStyle(
        "cover_note", parent=sheet["Normal"], fontName=BODY, fontSize=9.5,
        leading=15, textColor=FAINT, alignment=TA_CENTER)
    styles["h1"] = ParagraphStyle(
        "h1", parent=sheet["Heading1"], fontName=BODY_BOLD, fontSize=17,
        leading=22, textColor=INK, spaceBefore=20, spaceAfter=9,
        keepWithNext=1)
    styles["h2"] = ParagraphStyle(
        "h2", parent=sheet["Heading2"], fontName=BODY_BOLD, fontSize=12,
        leading=16, textColor=ACCENT, spaceBefore=14, spaceAfter=5,
        keepWithNext=1)
    styles["body"] = ParagraphStyle(
        "body", parent=sheet["BodyText"], fontName=BODY, fontSize=10,
        leading=15.5, textColor=INK, spaceAfter=8)
    styles["bullet"] = ParagraphStyle(
        "bullet", parent=styles["body"], leftIndent=16, bulletIndent=4,
        spaceAfter=5)
    styles["note"] = ParagraphStyle(
        "note", parent=styles["body"], fontSize=9.5, leading=14.5,
        leftIndent=9, textColor=colors.HexColor("#3d4854"), spaceBefore=2,
        spaceAfter=10)
    styles["code"] = ParagraphStyle(
        "code", parent=sheet["Code"], fontName=MONO, fontSize=8.6,
        leading=11.6, textColor=colors.HexColor("#12161b"), leftIndent=0,
        spaceAfter=0, spaceBefore=0)
    styles["caption"] = ParagraphStyle(
        "caption", parent=styles["body"], fontName=BODY_ITALIC, fontSize=9,
        leading=13, textColor=MUTED, spaceAfter=3)
    styles["toc_line"] = ParagraphStyle(
        "toc_line", parent=styles["body"], fontSize=10.5, leading=18,
        spaceAfter=0)
    return styles


def boxed(flowable, bg, edge):
    """Put a code or output block in a tinted box."""
    box = Table([[flowable]], colWidths=[6.35 * inch])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.6, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return box


def check_width(text, where):
    """Source I wrote must fit the box; over-wide lines are a mistake."""
    for line in text.splitlines():
        if len(line) > MAX_CODE_COLUMNS:
            PROBLEMS.append(
                "%s: line of %d columns will not fit (max %d): %r"
                % (where, len(line), MAX_CODE_COLUMNS, line[:60]))


def wrap_output(text):
    """Fold real program output to the box width, keeping it readable.

    Output is whatever the interpreter produced, so it cannot be rewritten to
    fit - a long line is folded with a hanging indent instead.
    """
    lines = []
    for line in text.splitlines():
        if len(line) <= MAX_CODE_COLUMNS:
            lines.append(line)
            continue
        indent = " " * (len(line) - len(line.lstrip()) + 2)
        pieces = textwrap.wrap(
            line, width=MAX_CODE_COLUMNS, subsequent_indent=indent,
            break_long_words=True, break_on_hyphens=False,
            drop_whitespace=False)
        lines.extend(pieces or [line])
    return "\n".join(lines)


def render(content, styles):
    """Turn the content list into reportlab flowables."""
    story = []

    for block in content:
        if not isinstance(block, tuple):
            story.append(block)  # already a flowable (PageBreak, Spacer)
            continue

        kind = block[0]

        if kind == "h1":
            story.append(Paragraph(block[1], styles["h1"]))
        elif kind == "h2":
            story.append(Paragraph(block[1], styles["h2"]))
        elif kind == "p":
            story.append(Paragraph(block[1], styles["body"]))
        elif kind == "note":
            story.append(boxed(
                Paragraph(block[1], styles["note"]),
                colors.HexColor("#f7f4ea"), colors.HexColor("#e3dcc4")))
            story.append(Spacer(1, 9))
        elif kind == "bullets":
            for item in block[1]:
                story.append(Paragraph(item, styles["bullet"],
                                       bulletText="\u2022"))
            story.append(Spacer(1, 4))
        elif kind == "table":
            _, headers, rows, widths = block
            story.append(build_table(headers, rows, widths))
            story.append(Spacer(1, 10))
        elif kind == "snippet":
            check_width(block[1], "snippet")
            story.append(boxed(Preformatted(block[1], styles["code"]),
                               CODE_BG, CODE_EDGE))
            story.append(Spacer(1, 10))
        elif kind == "shell":
            _, command, output = block
            check_width(command, "shell command")
            pieces = [boxed(Preformatted("$ " + command.replace("\n", "\n$ "),
                                         styles["code"]), CODE_BG, CODE_EDGE)]
            if output:
                pieces.append(Spacer(1, 3))
                pieces.append(boxed(
                    Preformatted(wrap_output(strip_unrenderable(output)),
                                 styles["code"]),
                    OUT_BG, OUT_EDGE))
            story.append(KeepTogether(pieces))
            story.append(Spacer(1, 10))
        elif kind == "code":
            story.append(code_block(block, styles))

    return story


def code_block(block, styles):
    _, source, answers, expect_error, caption, run_it = block
    label = source.splitlines()[0][:52]
    check_width(source, "example %r" % label)

    pieces = []
    if caption:
        pieces.append(Paragraph(caption, styles["caption"]))
    pieces.append(boxed(Preformatted(source, styles["code"]),
                        CODE_BG, CODE_EDGE))

    if run_it:
        output = run(source, answers=answers, expect_error=expect_error,
                     label=label)
        output = strip_unrenderable(output)
        if output.strip():
            output = wrap_output(output)
            pieces.append(Spacer(1, 3))
            bg, edge = (ERR_BG, ERR_EDGE) if expect_error else (OUT_BG, OUT_EDGE)
            pieces.append(boxed(Preformatted(output, styles["code"]), bg, edge))

    pieces.append(Spacer(1, 11))
    return KeepTogether(pieces)


def build_table(headers, rows, widths):
    data = [[Paragraph("<b>%s</b>" % h, _cell_style(True)) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), _cell_style(False)) for c in row])

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.35, colors.HexColor("#e8ecf1")),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


_CELL_CACHE = {}


def _cell_style(header):
    key = bool(header)
    if key not in _CELL_CACHE:
        _CELL_CACHE[key] = ParagraphStyle(
            "cell%s" % key, fontName=BODY_BOLD if header else BODY,
            fontSize=9, leading=13,
            textColor=INK if header else colors.HexColor("#2b333c"))
    return _CELL_CACHE[key]


# ------------------------------------------------------------------- the cover

def cover(styles):
    return [
        Spacer(1, 1.85 * inch),
        Paragraph("W++", styles["title"]),
        Spacer(1, 2),
        Paragraph("The Complete Guide", styles["subtitle"]),
        Spacer(1, 26),
        Paragraph(
            "A programming language that reads like group chat<br/>"
            "and runs like Python.", styles["subtitle"]),
        Spacer(1, 1.5 * inch),
        Paragraph(
            "Everything you need to go from your first line<br/>"
            "to building whatever you like.", styles["cover_note"]),
        Spacer(1, 30),
        Paragraph(
            "Version %s &nbsp;&middot;&nbsp; %s<br/>"
            "Every example in this guide was run by the W++ interpreter "
            "while the guide was being written." % (
                __version__, date.today().strftime("%d %B %Y")),
            styles["cover_note"]),
        NextPageTemplate("body"),
        PageBreak(),
    ]


def contents(styles):
    entries = [
        ("1", "What W++ is"), ("2", "Getting set up"),
        ("3", "The Official Dictionary"), ("4", "Printing with yap"),
        ("5", "Reading input with dm"), ("6", "Variables and values"),
        ("7", "Numbers and arithmetic"), ("8", "Text"),
        ("9", "Yes, no and nothing"), ("10", "Making decisions"),
        ("11", "Repeating things"), ("12", "Collections"),
        ("13", "Building collections in one line"), ("14", "Functions"),
        ("15", "When things go wrong"),
        ("16", "Reserved words: the one real gotcha"),
        ("17", "Everything Python brings with it"),
        ("18", "Tools that help"), ("19", "Complete programs"),
        ("20", "Habits worth picking up"), ("21", "What W++ does not do"),
        ("22", "Where to go next"), ("23", "Cheat sheet"),
    ]
    story = [Paragraph("Contents", styles["h1"]), Spacer(1, 6)]
    for number, title in entries:
        story.append(Paragraph(
            "%s.&nbsp;&nbsp;&nbsp;%s" % (number, title), styles["toc_line"]))
    story.append(PageBreak())
    return story


def decorate(canvas, doc):
    """Footer with a page number."""
    canvas.saveState()
    canvas.setFont(MONO, 8)
    canvas.setFillColor(FAINT)
    canvas.drawCentredString(LETTER[0] / 2.0, 0.5 * inch, str(doc.page))
    canvas.setFont(BODY, 8)
    canvas.drawString(0.75 * inch, 0.5 * inch, "W++ - The Complete Guide")
    canvas.restoreState()


def build(path):
    styles = make_styles()

    doc = BaseDocTemplate(
        path, pagesize=LETTER,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title="W++ - The Complete Guide",
        author="W++", subject="A complete guide to the W++ language",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame]),
        PageTemplate(id="body", frames=[frame], onPage=decorate),
    ])

    story = cover(styles) + contents(styles) + render(build_content(), styles)
    doc.build(story)


def main():
    output = os.path.join(HERE, "WPP_Guide.pdf")
    build(output)

    if PROBLEMS:
        print("The guide was NOT written correctly:")
        for problem in PROBLEMS:
            print("  - " + problem)
        return 1

    size = os.path.getsize(output)
    print("wrote %s (%.0f KB)" % (output, size / 1024.0))
    print("every example ran as the guide claims")
    return 0


if __name__ == "__main__":
    sys.exit(main())
