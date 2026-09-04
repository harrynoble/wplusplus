"""Build docs/WPP_Documentation.pdf - the project's technical documentation.

Deliberately short: what W++ is, how the compiler is built, how errors work,
how the playground runs in two places, how we know any of it works, and what it
does not do.  The learning guide (docs/WPP_Guide.pdf) teaches the language;
this document describes the engineering.

Every number in it - test count, line counts, the keyword and error tables, the
commit history - is read from the repository while the PDF is written, so the
document cannot drift from the code.

    python docs/build_documentation.py
"""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle,
)

from wpplang import KEYWORDS, SKILL_ISSUES, __version__  # noqa: E402

TARGET = os.path.join(HERE, "WPP_Documentation.pdf")
MAX_PAGES = 10

# ------------------------------------------------------------------- theme

INK = colors.HexColor("#16181c")
BODY_GREY = colors.HexColor("#3f4650")
MUTED = colors.HexColor("#767f8b")
HAIRLINE = colors.HexColor("#dcdfe4")
ACCENT = colors.HexColor("#2563eb")
CODE_BG = colors.HexColor("#f6f7f9")


def register_fonts():
    windows = r"C:\Windows\Fonts"
    wanted = {
        "Doc": "segoeui.ttf", "Doc-Bold": "segoeuib.ttf",
        "Doc-Italic": "segoeuii.ttf", "DocMono": "consola.ttf",
    }
    try:
        for name, filename in wanted.items():
            path = os.path.join(windows, filename)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            pdfmetrics.registerFont(TTFont(name, path))
        return "Doc", "Doc-Bold", "Doc-Italic", "DocMono"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


BODY, BOLD, ITALIC, MONO = register_fonts()

STYLES = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=30, leading=34,
                            textColor=INK),
    "subtitle": ParagraphStyle("subtitle", fontName=BODY, fontSize=12.5,
                               leading=18, textColor=MUTED),
    "cover_meta": ParagraphStyle("cover_meta", fontName=MONO, fontSize=8.5,
                                 leading=14, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=14, leading=18,
                         textColor=INK, spaceBefore=2, spaceAfter=7,
                         keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=10, leading=14,
                         textColor=ACCENT, spaceBefore=11, spaceAfter=3,
                         keepWithNext=1),
    "body": ParagraphStyle("body", fontName=BODY, fontSize=9.5, leading=15,
                           textColor=BODY_GREY, spaceAfter=7),
    "lead": ParagraphStyle("lead", fontName=BODY, fontSize=10.5, leading=17,
                           textColor=INK, spaceAfter=9),
    "bullet": ParagraphStyle("bullet", fontName=BODY, fontSize=9.5, leading=14.5,
                             textColor=BODY_GREY, leftIndent=11, bulletIndent=1,
                             spaceAfter=4),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=7.8, leading=10.6,
                           textColor=INK),
    "caption": ParagraphStyle("caption", fontName=ITALIC, fontSize=8.5,
                              leading=12.5, textColor=MUTED, spaceBefore=3,
                              spaceAfter=8),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.5, leading=12,
                           textColor=BODY_GREY),
    "cell_head": ParagraphStyle("cell_head", fontName=BOLD, fontSize=8,
                                leading=11, textColor=MUTED),
    "cell_mono": ParagraphStyle("cell_mono", fontName=MONO, fontSize=8,
                                leading=12, textColor=INK),
}


# --------------------------------------------------------------- ingredients

def facts():
    """Read the numbers out of the repository."""
    def lines(paths):
        total = 0
        for path in paths:
            with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
                total += sum(1 for _ in handle)
        return total

    def listing(folder, suffix):
        base = os.path.join(ROOT, folder)
        return [os.path.join(folder, name) for name in sorted(os.listdir(base))
                if name.endswith(suffix)]

    tests = unittest.TestLoader().discover(
        os.path.join(ROOT, "tests"), top_level_dir=ROOT).countTestCases()

    history = []
    try:
        raw = subprocess.run(
            ["git", "log", "--reverse", "--format=%s"], cwd=ROOT,
            capture_output=True, text=True, timeout=20).stdout
        history = [line for line in raw.splitlines() if line.strip()]
    except Exception:
        pass

    return {
        "version": __version__,
        "keywords": len(KEYWORDS),
        "tests": tests,
        "compiler_lines": lines(listing("wpplang/compiler", ".py")),
        "language_lines": lines(listing("wpplang", ".py") + ["wpp.py"]),
        "test_lines": lines(listing("tests", ".py")),
        "examples": len(listing("examples", ".wpp")),
        "history": history,
    }


def flow(*items):
    return [item for item in items if item is not None]


def para(text, style="body"):
    return Paragraph(text, STYLES[style])


def bullets(items):
    return [Paragraph(item, STYLES["bullet"], bulletText="\u2013")
            for item in items]


def code(text, width=170 * mm):
    block = Table([[Preformatted(text, STYLES["code"])]], colWidths=[width])
    block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return block


def table(headers, rows, widths, mono_columns=()):
    data = [[Paragraph(h, STYLES["cell_head"]) for h in headers]]
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            style = "cell_mono" if index in mono_columns else "cell"
            cells.append(Paragraph(str(value), STYLES[style]))
        data.append(cells)

    block = Table(data, colWidths=widths, repeatRows=1)
    block.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, HAIRLINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.HexColor("#eceef1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    return block


def history_table(subjects):
    """The commit history, two abreast so it stays on one page."""
    numbered = [(index + 1, subject) for index, subject in enumerate(subjects)]
    half = (len(numbered) + 1) // 2
    left, right = numbered[:half], numbered[half:]

    rows = []
    for index in range(half):
        first = left[index]
        second = right[index] if index < len(right) else ("", "")
        rows.append([first[0], first[1], second[0], second[1]])

    # Wide enough for two digits; at 6mm the numbers wrapped.
    return table(["", "Commit", "", "Commit"], rows,
                 widths=[9 * mm, 75 * mm, 9 * mm, 75 * mm])


def rule(space_before=0, space_after=8):
    return HRFlowable(width="100%", thickness=0.6, color=HAIRLINE,
                      spaceBefore=space_before, spaceAfter=space_after)


def section(number, title):
    return flow(
        Spacer(1, 4),
        rule(space_after=6),
        para("<font color='#767f8b'>%s</font>&nbsp;&nbsp;%s" % (number, title), "h1"),
    )


# ----------------------------------------------------------------- content

def cover(data):
    return flow(
        Spacer(1, 52 * mm),
        para("W++", "title"),
        Spacer(1, 4),
        rule(space_after=10),
        para("A programming language with its own compiler frontend, "
             "targeting Python.<br/>Technical documentation.", "subtitle"),
        Spacer(1, 26),
        para(
            "version %s &nbsp;|&nbsp; %s keywords &nbsp;|&nbsp; %s tests<br/>"
            "github.com/harrynoble/wplusplus<br/>"
            "wplusplus.vercel.app"
            % (data["version"], data["keywords"], data["tests"]),
            "cover_meta"),
        NextPageTemplate("body"),
        PageBreak(),
    )


def overview(data):
    return flow(
        *section("01", "What W++ is"),
        para("W++ is a small programming language whose nineteen keywords are "
             "Gen Z slang: <font name='%s'>cook</font> declares a function, "
             "<font name='%s'>yap</font> prints, "
             "<font name='%s'>bet</font> is <font name='%s'>if</font>. "
             "It is dynamically typed and built on Python semantics."
             % (MONO, MONO, MONO, MONO), "lead"),
        para("What makes it a language implementation rather than a text "
             "substitution is the frontend. W++ source is tokenized, parsed "
             "into a W++ syntax tree, checked against W++'s own rules, and "
             "only then translated into Python by a separate backend. Python "
             "is the execution target. W++ has no runtime of its own and does "
             "not compile to machine code."),
        para("It runs two ways from one codebase: from the command line, and "
             "in a browser playground that can be deployed as static files "
             "because the compiler itself runs client-side under Pyodide."),

        para("At a glance", "h2"),
        table(
            ["", "", ""],
            [
                ["Compiler frontend", "%s lines" % data["compiler_lines"],
                 "lexer, parser, AST, semantic pass, code generator"],
                ["Language and CLI", "%s lines" % data["language_lines"],
                 "keyword table, runner, error protocol, entry point"],
                ["Tests", "%s tests" % data["tests"],
                 "%s lines, standard library unittest" % data["test_lines"]],
                ["Dependencies", "none",
                 "for the language; Pyodide and Monaco in the browser only"],
                ["Examples", "%s programs" % data["examples"],
                 "including the two from the language specification"],
            ],
            widths=[38 * mm, 24 * mm, 108 * mm]),
    )


def architecture():
    diagram = os.path.join(HERE, "images", "architecture.png")
    picture = None
    if os.path.isfile(diagram):
        # Sized from the file, and kept narrow enough to sit on the same page
        # as the text above it rather than pushing itself onto the next one.
        try:
            from PIL import Image as _Probe
            with _Probe.open(diagram) as probe:
                aspect = probe.height / float(probe.width)
        except Exception:
            aspect = 796 / 900.0
        width = 124 * mm
        picture = Image(diagram, width=width, height=width * aspect)
        picture.hAlign = "LEFT"

    return flow(
        *section("02", "Architecture"),
        para("Each stage has one responsibility and hands a single kind of "
             "thing to the next. No stage rewrites W++ text into Python text; "
             "the two vocabularies meet in exactly one place, the keyword "
             "table, which the code generator consults as it walks the tree."),
        picture,
        para("The stages marked in blue are the compiler proper. Everything "
             "else - the CLI, the playground, the execution layer - was "
             "already there and did not change when the compiler replaced the "
             "original text translator.", "caption"),
    )


def compiler_stages():
    example = """cook check_vibe(name):
    bet name == "Claude":
        spill "W AI"
    nah:
        spill "Mid\""""

    tree = """Program  @1:0
  body:
    FunctionDeclaration  name='check_vibe' keyword='cook' @1:0
      params:
        Parameter  name='name' kind='normal' @1:16
      body:
        IfStatement  @2:4
          branches:
            (
              ComparisonExpression  operators=['=='] @2:8
                left:
                  Identifier  name='name' @2:8
                comparators:
                  Literal  raw='"Claude"' kind='string' @2:16
              ReturnStatement  keyword='spill' @3:8
            )
          orelse:
            ReturnStatement  keyword='spill' @5:8"""[:]

    return flow(
        *section("03", "Inside the compiler"),

        para("Lexer", "h2"),
        para("Produces W++ tokens carrying a line and a column. W++ and Python "
             "are lexically identical - same numbers, strings, operators and "
             "indentation rules - and differ only in which bare words are "
             "keywords, which is a parser question. So character scanning is "
             "delegated to Python's keyword-agnostic "
             "<font name='%s'>tokenize</font>, and this stage adds what is "
             "W++'s own: classifying the nineteen keywords, collapsing "
             "f-strings so their replacement fields can be parsed separately "
             "from their text, and reporting a scanning failure as a W++ "
             "error." % MONO),
        para("One consequence is structural rather than cosmetic. A keyword "
             "inside a string can never be translated, because the scanner "
             "returns the whole literal as one token - nothing downstream ever "
             "looks inside it."),

        para("Parser and AST", "h2"),
        para("Recursive descent for statements, one method per construct; "
             "precedence climbing for expressions, so the precedence table is "
             "written once. The tree describes W++ constructs and records "
             "which W++ keyword opened each one. Nothing in it holds "
             "half-translated text."),
        KeepTogether(flow(code(example, width=170 * mm), Spacer(1, 4),
                          code(tree, width=170 * mm))),
        para("The same program before and after parsing. Printed by "
             "<font name='%s'>python wpp.py --ast</font>; the tree for the two "
             "lines after the function continues past what is shown."
             % MONO, "caption"),

        para("Semantic pass", "h2"),
        para("The questions that need a view of the whole tree: is "
             "<font name='%s'>dip</font> inside a loop, is "
             "<font name='%s'>spill</font> inside a "
             "<font name='%s'>cook</font>, is a parameter repeated, is a "
             "keyword being used where only a name can go. Deliberately small "
             "- W++ is dynamically typed, so there is no type checking to do "
             "and inventing some would change the language."
             % (MONO, MONO, MONO)),

        para("Code generator", "h2"),
        para("Walks the tree and emits Python, lining each statement up with "
             "the W++ line it came from and recording the mapping. That map is "
             "what lets a Python exception be reported against the author's "
             "source."),
    )


def errors():
    rows = [[name, message] for name, message in SKILL_ISSUES.items()]
    report = """Math ain't mathing: Bro tried to divide by zero (ZeroDivisionError)
   where: average.wpp, line 5
      5 | spill total / bodycount(marks)
   details: division by zero"""

    return flow(
        *section("04", "Errors: the Skill Issue Protocol"),
        para("Python exceptions are intercepted and re-presented in W++'s own "
             "wording, with the W++ line that caused them, the source line "
             "itself, and Python's original description underneath."),
        code(report, width=170 * mm),
        Spacer(1, 8),
        table(["Python exception", "W++ message"], rows,
              widths=[38 * mm, 132 * mm], mono_columns=(0,)),
        Spacer(1, 6),
        para("Anything outside this table is reported as <i>Unspecified skill "
             "issue</i> with the real exception name, so a raw traceback never "
             "reaches the user. Errors the frontend finds - a keyword used as "
             "a name, <font name='%s'>dip</font> outside a loop - travel the "
             "same path, and name the offending word." % MONO),
        para("Reporting the author's line is the practical reason the AST "
             "exists. A runtime failure knows only the generated Python line; "
             "the source map turns it back into the W++ line, so the message "
             "never refers to code nobody wrote."),
    )


def playground():
    return flow(
        *section("05", "The playground, and how it deploys"),
        para("One interface, two execution engines. Which one is used is "
             "decided at load time by asking whether a backend answers, and "
             "the interface cannot tell them apart because both emit the same "
             "records."),
        table(
            ["Engine", "Where W++ runs", "Used when"],
            [["Server", "playground/server.py, one child process per program",
              "running locally"],
             ["Browser", "the same wpplang package under Pyodide, in a Worker",
              "no backend answers"]],
            widths=[24 * mm, 88 * mm, 58 * mm]),
        Spacer(1, 8),
        para("Because the browser engine needs no backend, the site is static "
             "files with no build step: the compiler's Python sources are "
             "committed as a JSON bundle and fetched at load. That is also "
             "what makes it safe to host publicly - there is no server "
             "executing anyone's code. The local server, which does execute "
             "code with only a timeout and no sandbox, binds to 127.0.0.1 "
             "deliberately and is not what gets deployed."),

        para("Behaviour shared by both engines", "h2"),
        *bullets([
            "Programs stop after ten seconds of <i>running</i>. Time spent "
            "waiting for input does not count, so answering slowly is fine "
            "while a runaway loop is still stopped.",
            "A program that calls <font name='%s'>dm()</font> prints its "
            "prompt into the output panel and takes the answer typed straight "
            "after it, as a terminal would." % MONO,
            "Errors appear with the W++ line, the source line, and the "
            "failing line marked in the editor.",
        ]),
        para("The browser engine differs in two ways, both deliberate. "
             "Interactive input works by replay - a worker cannot pause "
             "synchronous Python for the user without cross-origin isolation "
             "headers, so the program is run again from the start with each "
             "new answer and the transcript rebuilt; each attempt takes "
             "milliseconds. And a runaway loop is stopped by discarding the "
             "worker, which is the only way to interrupt synchronous Python in "
             "a browser."),
    )


def verification(data):
    return flow(
        *section("06", "How we know it works"),
        para("%s tests, standard library only." % data["tests"], "lead"),
        table(
            ["Suite", "Covers"],
            [["test_compiler.py", "each stage on its own: lexer, parser and "
              "AST shape, semantic rules, code generation, source mapping"],
             ["test_compiler_equivalence.py",
              "the refactor itself - see below"],
             ["test_programs.py", "whole programs with exact expected output, "
              "including quicksort, a sieve, BFS, and diagnostics for errors "
              "raised inside comprehensions, generators and decorated "
              "functions"],
             ["test_translator.py", "keyword mapping, word boundaries, "
              "literal safety, line numbering"],
             ["test_errors.py", "every Skill Issue message and its context"],
             ["test_playground.py", "the API, interactive prompts, the compute "
              "budget, Stop, runaway output, worker cleanup"],
             ["test_web_bundle.py", "the browser bundle still matches the "
              "package, including by importing the compiler from the bundled "
              "text alone"],
             ["test_cli.py, test_sound.py, test_guide.py",
              "the command line, the error sound, and every example in the "
              "learning guide"]],
            widths=[52 * mm, 118 * mm], mono_columns=(0,)),

        para("The equivalence check", "h2"),
        para("W++ was originally implemented as a single regular-expression "
             "pass over the source. When that was replaced by the compiler, "
             "the old translator was kept as a test oracle - on no execution "
             "path, with a test asserting nothing in the package imports it."),
        para("Both target Python, so for any program the two both accept, "
             "they must generate Python that <i>parses to the same tree</i>. "
             "Comparing parsed trees rather than text ignores layout and "
             "redundant brackets, which are the generator's business, and "
             "catches anything that would change behaviour. The check runs on "
             "every shipped example and on a program for every construct the "
             "language supports, and they agree on all of them. The only "
             "disagreement anywhere is a program the compiler now deliberately "
             "rejects - see section 07."),
        para("That check is what made the refactor safe to do at all, and it "
             "found the two real bugs in it: a "
             "<font name='%s'>nah</font> attached to a loop being claimed by "
             "an inner <font name='%s'>bet</font> - which silently changed "
             "what programs meant - and nested f-strings failing to lex."
             % (MONO, MONO)),
    )


def decisions():
    return flow(
        *section("07", "Decisions worth recording"),
        para("Keywords are reserved words", "h2"),
        para("You cannot name a function, class, parameter or keyword argument "
             "after one, for the same reason Python will not let you write "
             "<font name='%s'>def break()</font>: "
             "<font name='%s'>cook dip(self)</font> would become "
             "<font name='%s'>def break(self)</font>, and a call written "
             "<font name='%s'>dip()</font> would become "
             "<font name='%s'>break()</font> anyway. The compiler says which "
             "word is the problem and on which line, rather than letting "
             "Python complain about generated code. Names that merely contain "
             "a keyword are fine, and so are attributes - a name after a dot "
             "is never a keyword." % ((MONO,) * 5)),

        para("Two changes from the original implementation", "h2"),
        para("Both narrow invalid programs only, and both are documented:"),
        *bullets([
            "The parser needs whole statements. "
            "<font name='%s'>cook squad(x):</font> with no body is refused; "
            "the regular-expression version accepted it because it never "
            "parsed anything." % MONO,
            "A keyword used where a name is required is refused up front. "
            "<font name='%s'>f(bet=1)</font> previously became "
            "<font name='%s'>f(if=1)</font> and failed confusingly."
            % (MONO, MONO),
        ]),

        para("Kept, not rewritten", "h2"),
        para("The CLI, the execution layer, the playground and its API "
             "contract were already working and were left alone. The compiler "
             "was slotted in behind the same "
             "<font name='%s'>translate()</font> entry point, which is why "
             "nothing above it had to change." % MONO),
    )


def limitations(data):
    return flow(
        *section("08", "What it does not do"),
        *bullets([
            "Only the nineteen keywords have slang names. "
            "<font name='%s'>and</font>, <font name='%s'>class</font>, "
            "<font name='%s'>import</font>, <font name='%s'>try</font> and the "
            "rest are written the Python way." % ((MONO,) * 4),
            "One file per program. Python modules can be imported; another "
            "<font name='%s'>.wpp</font> file cannot." % MONO,
            "No REPL, and errors stop at the first failure, as in Python.",
            "Keywords are source syntax, not a display layer: "
            "<font name='%s'>yap(nocap)</font> prints "
            "<font name='%s'>True</font>." % (MONO, MONO),
            "<font name='%s'>case</font> patterns are carried through as "
            "written, since W++ adds nothing to Python's pattern syntax and a "
            "name there means bind rather than read." % MONO,
            "The browser engine downloads Pyodide on first load - tens of "
            "megabytes, a few seconds - and its replay approach to input can "
            "differ for a program whose output depends on randomness or the "
            "clock.",
            "The local server executes the code it is given with only a "
            "timeout. It is a development tool, not a sandbox.",
        ]),

        # Kept whole: a table split across a page break reads badly, and this
        # one closes the document.
        KeepTogether(flow(
            para("How it was built", "h2"),
            para("In order, from the repository history:"),
            history_table(data["history"]),
            Spacer(1, 6),
            para("The language and its tests came first; the playground, the "
                 "guide and the compiler refactor followed. The refactor is "
                 "the only change that touched the core, and the equivalence "
                 "check in section 06 is why it could be done without risking "
                 "the working demo.", "caption"),
        )),
    )


def build_story(data):
    return (cover(data) + overview(data) + architecture() + compiler_stages()
            + errors() + playground() + verification(data) + decisions()
            + limitations(data))


# ------------------------------------------------------------------- output

def decorate(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.6)
    canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
    canvas.setFont(MONO, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm, "W++ technical documentation")
    canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, str(doc.page))
    canvas.restoreState()


def build():
    data = facts()
    doc = BaseDocTemplate(
        TARGET, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title="W++ - technical documentation", author="W++",
        subject="How the W++ compiler and playground are built")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame]),
        PageTemplate(id="body", frames=[frame], onPage=decorate),
    ])
    doc.build(build_story(data))
    return data


def main():
    build()
    from pypdf import PdfReader
    pages = len(PdfReader(TARGET).pages)
    size = os.path.getsize(TARGET) / 1024.0
    print("wrote %s" % TARGET)
    print("  %d pages, %.0f KB" % (pages, size))
    if pages > MAX_PAGES:
        print("  TOO LONG: %d pages, the limit is %d" % (pages, MAX_PAGES))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
