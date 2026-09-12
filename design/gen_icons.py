"""Rasterise the Branchwork mark into the icon files browsers ask for.

    .venv\\Scripts\\python design\\gen_icons.py

Writes into ``static/branchwork/img/``. The outputs are committed, so this
only needs re-running when the mark changes; Pillow is a dev dependency
(requirements-dev.txt) and is never imported by the app.

The geometry here is the same 32-unit grid as ``favicon.svg`` — the bold
version of the mark, not ``logo.svg``, because thin bars disappear at 16px.
Keep the two in step by hand: there is no SVG renderer in the loop, since
pulling in cairo to redraw three rectangles is a poor trade.
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "static", "branchwork", "img")

GRID = 32                      # the viewBox of favicon.svg
RADIUS = 2.5
BARS = [  # x, y, w, h, fill — green, blue, red, as in theme.css
    (2, 3, 8, 26, "#3fcf63"),
    (12, 3, 8, 26, "#5b8def"),
    (22, 3, 8, 26, "#f0684e"),
]
# iOS ignores transparency and composites its own rounded mask over the
# square, so the touch icon gets the app background painted in.
APP_BG = "#15181d"
SUPERSAMPLE = 8


def render(size: int, background: str | None = None, mark: float = 1.0) -> Image.Image:
    """Square icon ``size`` px wide, the mark filling ``mark`` of the width."""
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    span = canvas * mark
    offset = (canvas - span) / 2
    unit = span / GRID
    for x, y, w, h, fill in BARS:
        draw.rounded_rectangle(
            [offset + x * unit, offset + y * unit,
             offset + (x + w) * unit, offset + (y + h) * unit],
            radius=RADIUS * unit, fill=fill)
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    for size in (16, 32):
        path = os.path.join(OUT, f"favicon-{size}.png")
        render(size).save(path)
        print("wrote", os.path.relpath(path, os.path.dirname(OUT)))

    # One .ico carrying three sizes, for browsers and Windows pinned sites
    # that still ignore the SVG.
    ico = os.path.join(OUT, "favicon.ico")
    render(64).save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote", os.path.relpath(ico, os.path.dirname(OUT)))

    # 0.66 leaves the breathing room iOS home screens expect; flattened to
    # RGB because a transparent touch icon renders black on some versions.
    touch = os.path.join(OUT, "apple-touch-icon.png")
    render(180, background=APP_BG, mark=0.66).convert("RGB").save(touch)
    print("wrote", os.path.relpath(touch, os.path.dirname(OUT)))


if __name__ == "__main__":
    main()
