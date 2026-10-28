"""The page a signed-out visitor sees at ``/``: the pitch, a sign-up box, and
an example plot drawn as its skill tree.

The example is a picture, not data: it is built here rather than read from
the database, so the page needs no account and runs no query. Its points are
real sums all the same, so the tier fills, the gates, the ultimate and the
totals always agree with one another when someone edits the tiles below.
"""
from markupsafe import Markup

from copytext import tx

# The default gate: tier N opens once tier N-1 holds this many points.
GATE = 3

# 24px stroke glyphs for the example's tiles, drawn in currentColor.
GLYPHS = {
    "doc": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M10 12h5"/><path d="M10 16h5"/>',
    "doc_tick": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M9 14l2 2 4-4"/>',
    "hall": '<path d="M4 21h16"/><path d="M6 21V9l6-5 6 5v12"/><path d="M10 21v-5h4v5"/><path d="M9.5 11h5"/>',
    "crown": '<path d="M4 18h16"/><path d="M4 15L3 7l5 4 4-6 4 6 5-4-1 8z"/>',
    "ballot": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l3 3 5-6"/>',
    "bank": '<path d="M4 21h16"/><path d="M5 21V10h14v11"/><path d="M3 10l9-6 9 6"/><path d="M9 14v4"/><path d="M15 14v4"/>',
    "coin": ('<circle cx="12" cy="12" r="8"/><path d="M12 7v10"/>'
             '<path d="M15 9.5c-.6-.9-1.7-1.5-3-1.5-1.7 0-3 .9-3 2s1.3 2 3 2 3 .9 3 2-1.3 2-3 2c-1.3 0-2.4-.6-3-1.5"/>'),
    "key": '<circle cx="8" cy="12" r="3.5"/><path d="M11.5 12H21"/><path d="M17.5 12v3"/><path d="M20.5 12v2.5"/>',
    "inbox": '<path d="M3 13l2.5-8h13L21 13v6H3z"/><path d="M3 13h5l1.5 2.5h5L16 13h5"/>',
    "volcano": '<path d="M3 20l6-10h6l6 10z"/><path d="M10 6c0-1 1-2 2-2s2 1 2 2"/>',
    "crew": ('<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/>'
             '<path d="M16 5a3 3 0 0 1 0 6"/><path d="M18 14c1.8.7 3 2.5 3 4.5"/>'),
    "bomb": ('<circle cx="10" cy="14" r="6"/><path d="M14.5 9.5L17 7"/><path d="M18 3v2"/>'
             '<path d="M21 6h-2"/><path d="M20.2 3.8l-1.4 1.4"/>'),
    "flask": '<path d="M9 3h6"/><path d="M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M7.5 15h9"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
}


def glyph(name: str, size: int = 24, weight: float = 1.75) -> Markup:
    return Markup(
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="{weight}" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{GLYPHS[name]}</svg>')


def _state(done: int, most: int) -> str:
    return "full" if done >= most else "part" if done else "empty"


def _scheme(hue: str, name: str, mark: str, tiers: list[list[tuple[str, int, int]]],
            *, ultimate: str | None = None, waits_on: str | None = None) -> dict:
    """One column. ``tiers`` holds ``(glyph, done, max)`` per tile; a scheme
    that ``waits_on`` another is locked, so none of its tiers fill."""
    rows, have_above = [], None
    for tiles in tiers:
        have = sum(done for _, done, _ in tiles)
        shut = bool(waits_on) or (have_above is not None and have_above < GATE)
        if waits_on and have_above is None:
            note = tx("gate.opens_when", name=waits_on)
        elif shut and have_above is not None:
            note = tx("gate.needs_points", gate=GATE, have=have_above)
        else:
            note = None
        rows.append({
            "tiles": [{"glyph": g, "done": d, "max": m, "state": _state(d, m)} for g, d, m in tiles],
            "fill": 0 if shut else round(100 * min(have, GATE) / GATE),
            "shut": shut,
            "note": note,
        })
        have_above = have
    done = sum(t["done"] for row in rows for t in row["tiles"])
    most = sum(t["max"] for row in rows for t in row["tiles"])
    return {
        "hue": hue, "name": name, "mark": mark, "tiers": rows,
        "done": done, "max": most, "pct": round(100 * done / most) if most else 0,
        "ultimate": ultimate,
        # Reached once the last tier holds enough points to open another.
        "ultimate_reached": bool(ultimate) and not waits_on and have_above is not None and have_above >= GATE,
    }


def demo_plot() -> dict:
    funding = tx("landing.demo_scheme_2")
    schemes = [
        _scheme("green", tx("landing.demo_scheme_1"), "crown", [
            [("doc", 3, 3), ("hall", 2, 2), ("crown", 2, 4)],
            [("doc_tick", 1, 1), ("ballot", 2, 2)],
        ], ultimate=tx("landing.demo_ultimate")),
        _scheme("blue", funding, "coin", [
            [("bank", 1, 1), ("coin", 2, 3)],
            [("key", 1, 2), ("inbox", 0, 1)],
        ]),
        _scheme("red", tx("landing.demo_scheme_3"), "bomb", [
            [("volcano", 0, 3), ("crew", 0, 2), ("bomb", 0, 5)],
            [("flask", 0, 2)],
        ], waits_on=funding),
    ]
    done = sum(s["done"] for s in schemes)
    most = sum(s["max"] for s in schemes)
    return {
        "name": tx("landing.demo_plot"),
        "schemes": schemes,
        "done": done, "max": most, "pct": round(100 * done / most),
    }
