"""Build the line-drawn machination icons from the landing page's glyphs.

    python design/gen_machination_icons.py

Each icon is the bomb's rounded frame with a 24px line glyph scaled inside
it, drawn in white so icons.py can recolour it. Re-run after changing a
glyph; the output is committed under static/branchwork/img/machination_icons/.
bomb.svg is drawn by hand in Affinity and is left alone.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from landing import GLYPHS  # noqa: E402

OUT = os.path.join(ROOT, "static", "branchwork", "img", "machination_icons")

# Extra glyphs the landing page does not draw, on the same 24px grid.
EXTRA = {
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16"/><path d="M8 3v4"/><path d="M16 3v4"/>',
    "chat": '<path d="M4 5h16v11H10l-5 4v-4H4z"/><path d="M8 10h8"/>',
    "rocket": ('<path d="M12 3c3 2.2 4.5 5.5 4.5 9.5L15 16H9l-1.5-3.5C7.5 8.5 9 5.2 12 3z"/>'
               '<circle cx="12" cy="10" r="1.8"/><path d="M9.5 16L8 20l2.5-1.5"/><path d="M14.5 16L16 20l-2.5-1.5"/>'),
}

FRAME = ('<path d="M15.84,5.04l0,7.2c0,1.987 -1.613,3.6 -3.6,3.6l-7.2,0c-1.987,0 -3.6,-1.613 -3.6,-3.6l-0,-7.2'
         'c0,-1.987 1.613,-3.6 3.6,-3.6l7.2,-0c1.987,0 3.6,1.613 3.6,3.6Z" fill="none" stroke="#fff" stroke-width="1"/>')
SKIP = {"bomb", "lock"}


def main() -> None:
    glyphs = {k: v for k, v in GLYPHS.items() if k not in SKIP} | EXTRA
    for name, body in sorted(glyphs.items()):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18">'
               f"{FRAME}"
               '<g transform="translate(3.84 3.84) scale(0.4)" fill="none" stroke="#fff" '
               f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>\n')
        with open(os.path.join(OUT, f"{name}.svg"), "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(name)


if __name__ == "__main__":
    main()
