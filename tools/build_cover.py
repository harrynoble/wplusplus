"""Draw the 1280x640 cover image.

The palette is the playground's own (playground/static/app.css) and the code
on the card is highlighted with the real keyword table, so the cover cannot
drift from the language it advertises.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from wpplang.keywords import KEYWORDS  # noqa: E402

OUT = os.path.join(ROOT, "docs", "cover.png")
W, H = 1280, 640

# playground/static/app.css
BG = "#0b0e13"
SURFACE = "#141920"
BORDER = "#1f262f"
TEXT = "#dee3ea"
MUTED = "#8a95a3"
FAINT = "#626d7b"
ACCENT = "#3b82f6"
KEYWORD = "#b48ead"
FUNCTION = "#7fa8d4"
STRING = "#97b982"
NUMBER = "#d0a67d"

FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


UI_BOLD = "segoeuib.ttf"
UI = "segoeui.ttf"
UI_LIGHT = "segoeuil.ttf"
MONO = "consola.ttf"
MONO_BOLD = "consolab.ttf"

CODE = [
    "cook greet(name):",
    '    yap("gm, " + name)',
    "",
    'crew = squad(["world", "chat"])',
    'yap("crew size:", bodycount(crew))',
    "",
    "spam name in crew:",
    "    greet(name)",
    '    bet name == "chat":',
    "        dip",
]

BUILTINS = {"greet"}


def classify(word, following):
    """Colour for one identifier-ish word."""
    if word in KEYWORDS:
        return KEYWORD
    if word.isdigit():
        return NUMBER
    if following.startswith("("):
        return FUNCTION
    return TEXT


def draw_code(pen, lines, x, y, face, leading):
    """Draw highlighted W++ - strings whole, then words, then punctuation."""
    import re
    pattern = re.compile(r'("(?:[^"\\]|\\.)*"|[A-Za-z_]\w*|\d+)')
    for row, line in enumerate(lines):
        cursor = x
        top = y + row * leading
        pos = 0
        for match in pattern.finditer(line):
            gap = line[pos:match.start()]
            if gap:
                pen.text((cursor, top), gap, font=face, fill=TEXT)
                cursor += pen.textlength(gap, font=face)
            token = match.group(0)
            if token.startswith('"'):
                colour = STRING
            else:
                colour = classify(token, line[match.end():])
            pen.text((cursor, top), token, font=face, fill=colour)
            cursor += pen.textlength(token, font=face)
            pos = match.end()
        rest = line[pos:]
        if rest:
            pen.text((cursor, top), rest, font=face, fill=TEXT)


def check_snippet():
    """The code on the cover must be code that actually compiles."""
    from wpplang.translator import translate
    try:
        translate(chr(10).join(CODE))
    except Exception as error:
        print("the cover snippet does not compile: %s: %s"
              % (type(error).__name__, error))
        return False
    return True


def main():
    if not check_snippet():
        return 1

    image = Image.new("RGB", (W, H), BG)
    pen = ImageDraw.Draw(image)

    # ---- right: a code card, echoing the playground editor ----
    card = (688, 96, 1216, 544)
    pen.rounded_rectangle(card, radius=12, fill=SURFACE, outline=BORDER, width=1)

    tab = font(UI_BOLD, 13)
    pen.text((card[0] + 28, card[1] + 22), "MAIN.WPP", font=tab, fill=FAINT)
    pen.line([(card[0] + 1, card[1] + 56), (card[2] - 1, card[1] + 56)],
             fill=BORDER, width=1)

    draw_code(pen, CODE, card[0] + 28, card[1] + 86, font(MONO, 19), 34)

    # ---- left: wordmark and pitch ----
    # Positions hang off the wordmark's measured ink box, so the gaps stay
    # honest if the mark is ever resized.
    mark = font(UI_BOLD, 132)
    pen.text((72, 110), "W++", font=mark, fill=TEXT)
    base = pen.textbbox((72, 110), "W++", font=mark)[3]

    tag = font(UI_LIGHT, 30)
    pen.text((78, base + 46), "A Gen-Z programming language", font=tag, fill=TEXT)
    pen.text((78, base + 88), "that compiles to Python.", font=tag, fill=MUTED)

    # keyword sample, in the colour the editor gives them
    sample = font(MONO, 17)
    cursor, row = 80, base + 168
    words = ["cook", "yap", "bet", "spam", "grind", "dip"]
    for index, word in enumerate(words):
        pen.text((cursor, row), word, font=sample, fill=KEYWORD)
        cursor += pen.textlength(word, font=sample)
        if index < len(words) - 1:
            pen.text((cursor, row), "  ·  ", font=sample, fill=FAINT)
            cursor += pen.textlength("  ·  ", font=sample)

    link = font(MONO, 19)
    pen.text((80, base + 232), "wplusplus.vercel.app", font=link, fill=ACCENT)

    image.save(OUT, "PNG", optimize=True)
    size = os.path.getsize(OUT)
    print("wrote %s  %dx%d  %.1f KB" % (OUT, image.width, image.height, size / 1024.0))
    if image.size != (W, H):
        print("WRONG SIZE")
        return 1
    if size > 2 * 1024 * 1024:
        print("OVER 2 MB")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
