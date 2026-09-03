"""Draw playground/static/favicon.ico from the same mark as favicon.svg.

Modern browsers use the SVG.  The .ico is there for the ones that do not, and
because a browser asks for /favicon.ico whether you offer one or not.

    python playground/make_favicon.py

Needs Pillow, and only to regenerate the icon - the playground itself still
runs with nothing but the standard library.
"""

import io
import os
import struct
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "static", "favicon.ico")

ACCENT = (59, 130, 246, 255)   # #3b82f6, the Run button's blue
GLYPH = (255, 255, 255, 255)

# The W as a polyline on a 32x32 grid, matching favicon.svg exactly.
GRID = 32.0
STROKE = 3.0
CORNER = 7.0
POINTS = [(6.2, 10.0), (11.3, 22.0), (16.0, 12.6), (20.7, 22.0), (25.8, 10.0)]

SIZES = [16, 32, 48, 64, 256]

# Drawn large and shrunk down, which is what gives clean edges.
SUPERSAMPLE = 8


def draw(size):
    """Render the mark at one size."""
    big = size * SUPERSAMPLE
    scale = big / GRID

    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)

    pen.rounded_rectangle(
        [(0, 0), (big - 1, big - 1)], radius=CORNER * scale, fill=ACCENT)

    # A hair more weight at small sizes, or the W thins out to nothing.
    weight = STROKE * scale * (1.2 if size <= 16 else 1.0)
    pen.line(
        [(x * scale, y * scale) for x, y in POINTS],
        fill=GLYPH, width=int(round(weight)), joint="curve")

    # Round caps: the joints are curved above, but the two open ends are not.
    radius = weight / 2.0
    for x, y in (POINTS[0], POINTS[-1]):
        cx, cy = x * scale, y * scale
        pen.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                    fill=GLYPH)

    return image.resize((size, size), Image.LANCZOS)


def build_ico(frames):
    """Assemble an .ico from one PNG per size.

    Pillow's own ICO writer resizes the single image it is given and quietly
    drops any size larger than it, so the container is written here instead:
    that way every frame is exactly the one drawn for that size, including the
    slightly heavier stroke used at 16 pixels.
    """
    payloads = []
    for image in frames:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        payloads.append(buffer.getvalue())

    count = len(payloads)
    header = struct.pack("<HHH", 0, 1, count)          # reserved, type 1, count
    directory_size = 16 * count
    offset = len(header) + directory_size

    directory = b""
    for image, payload in zip(frames, payloads):
        width, height = image.size
        directory += struct.pack(
            "<BBBBHHII",
            0 if width >= 256 else width,   # 0 stands for 256
            0 if height >= 256 else height,
            0,                              # palette size: 0 for true colour
            0,                              # reserved
            1,                              # colour planes
            32,                             # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)

    return header + directory + b"".join(payloads)


def main():
    frames = [draw(size) for size in SIZES]
    with open(TARGET, "wb") as handle:
        handle.write(build_ico(frames))
    print("wrote %s (%d bytes, sizes %s)"
          % (TARGET, os.path.getsize(TARGET),
             ", ".join(str(s) for s in SIZES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
