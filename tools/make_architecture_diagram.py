"""Draw the W++ compiler pipeline as docs/images/architecture.png.

Used by the README. Regenerate with:

    python tools/make_architecture_diagram.py

Needs Pillow, and only for this - W++ itself has no dependencies.
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "docs", "images", "architecture.png")

# The playground's palette, so the diagram belongs with the project.
BG = (11, 14, 19)
CARD = (18, 22, 29)
EDGE = (43, 52, 63)
ACCENT = (59, 130, 246)
TEXT = (222, 227, 234)
MUTED = (138, 149, 163)
FAINT = (98, 109, 123)

SCALE = 2            # drawn double size and shrunk, for clean edges
WIDTH = 900
PAD = 40
BOX_W = 470
BOX_H = 66
GAP = 30

STAGES = [
    ("W++ source", "your_program.wpp", None),
    ("Lexer", "W++ tokens, each with a line and column", "wpplang/compiler/lexer.py"),
    ("Parser", "recursive descent + precedence climbing", "wpplang/compiler/parser.py"),
    ("W++ AST", "FunctionDeclaration, IfStatement, ForStatement, ...",
     "wpplang/compiler/nodes.py"),
    ("Semantic validation", "is `dip` in a loop? is `spill` in a `cook`?",
     "wpplang/compiler/semantic.py"),
    ("Python code generator", "walks the tree, emits Python + a W++ line map",
     "wpplang/compiler/codegen.py"),
    ("Python runtime", "output, or a Skill Issue on your W++ line",
     "wpplang/runner.py"),
]


def font(names, size):
    """First font that loads, else Pillow's built-in."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build():
    title_font = font(["segoeuib.ttf", "arialbd.ttf"], 30 * SCALE)
    label_font = font(["segoeuib.ttf", "arialbd.ttf"], 17 * SCALE)
    body_font = font(["segoeui.ttf", "arial.ttf"], 14 * SCALE)
    mono_font = font(["consola.ttf", "cour.ttf"], 12 * SCALE)

    height = PAD * 2 + 74 + len(STAGES) * BOX_H + (len(STAGES) - 1) * GAP
    image = Image.new("RGB", (WIDTH * SCALE, height * SCALE), BG)
    pen = ImageDraw.Draw(image)

    pen.text((PAD * SCALE, PAD * SCALE), "W++ compiler pipeline",
             font=title_font, fill=TEXT)
    pen.text((PAD * SCALE, (PAD + 40) * SCALE),
             "W++ is parsed into its own AST; Python is the execution target.",
             font=body_font, fill=MUTED)

    top = PAD + 74
    left = PAD
    for index, (name, detail, module) in enumerate(STAGES):
        box = [left * SCALE, top * SCALE,
               (left + BOX_W) * SCALE, (top + BOX_H) * SCALE]
        pen.rounded_rectangle(box, radius=8 * SCALE, fill=CARD, outline=EDGE,
                              width=1 * SCALE)
        # A bar marking the stages that are the compiler proper.
        if module and module.startswith("wpplang/compiler"):
            pen.rounded_rectangle(
                [left * SCALE, (top + 10) * SCALE,
                 (left + 3) * SCALE, (top + BOX_H - 10) * SCALE],
                radius=2 * SCALE, fill=ACCENT)

        pen.text(((left + 18) * SCALE, (top + 13) * SCALE), name,
                 font=label_font, fill=TEXT)
        pen.text(((left + 18) * SCALE, (top + 38) * SCALE), detail,
                 font=body_font, fill=MUTED)
        if module:
            pen.text(((left + BOX_W + 22) * SCALE, (top + 24) * SCALE), module,
                     font=mono_font, fill=FAINT)

        if index < len(STAGES) - 1:
            centre = (left + 30) * SCALE
            start = (top + BOX_H) * SCALE
            end = (top + BOX_H + GAP) * SCALE
            pen.line([centre, start, centre, end], fill=EDGE, width=2 * SCALE)
            pen.polygon(
                [(centre - 5 * SCALE, end - 7 * SCALE),
                 (centre + 5 * SCALE, end - 7 * SCALE),
                 (centre, end)], fill=EDGE)
        top += BOX_H + GAP

    return image.resize((WIDTH, height), Image.LANCZOS)


def main():
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    build().save(TARGET, optimize=True)
    print("wrote %s (%.0f KB)" % (TARGET, os.path.getsize(TARGET) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
