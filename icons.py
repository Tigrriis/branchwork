"""Machination icons: SVG files in static/branchwork/img/machination_icons/.

Each file is one icon, named by its filename (``bomb.svg`` is ``bomb``), and
that name is what ``Task.icon`` and ``Routine.icon`` store. Adding an icon is
dropping a file into the folder: the pickers list whatever is there, and a
new or changed file is picked up without a restart.

Icons are drawn inline rather than as ``<img>`` so they take the colour of
wherever they sit. Anything drawn in white (``#fff`` or ``white``) becomes
``currentColor``, which is how a tile's icon still dims before it has points;
any other colour is kept as drawn.
"""
import os
import re
import time

from markupsafe import Markup

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "static", "branchwork", "img", "machination_icons")
DEFAULT_ICON = "bomb"

# Names fit Task.icon (String(30)) and are safe in ids and attributes.
_NAME = re.compile(r"[a-z0-9_-]{1,30}")
_WHITE = re.compile(r"((?:fill|stroke)\s*(?::\s*|=\s*[\"']))(#fff(?:fff)?|white)\b", re.I)
# The files are ours, but they go straight into every page, so anything that
# could run is refused rather than trusted.
_UNSAFE = re.compile(r"<\s*(?:script|foreignObject)\b|\son\w+\s*=|javascript:", re.I)

_cache: dict = {"checked": 0.0, "signature": None, "icons": {}}


def _signature() -> tuple:
    try:
        return tuple(sorted((e.name, e.stat().st_mtime_ns) for e in os.scandir(ICON_DIR)
                            if e.is_file() and e.name.lower().endswith(".svg")))
    except FileNotFoundError:
        return ()


def _parse(name: str, text: str):
    """``(viewBox, root style, inner markup)``, or None if the file won't do."""
    if _UNSAFE.search(text):
        return None
    start = text.find("<svg")
    end = text.find(">", start) if start >= 0 else -1
    close = text.rfind("</svg>")
    if start < 0 or end < 0 or close < end:
        return None
    root = text[start:end]
    view_box = re.search(r'viewBox\s*=\s*"([^"]+)"', root)
    if not view_box:
        return None
    style = re.search(r'\sstyle\s*=\s*"([^"]*)"', root)
    body = _WHITE.sub(lambda m: m.group(1) + "currentColor", text[end + 1:close])
    # The icon's name goes in front of every id, so two icons on one page
    # never answer to each other's gradients or clip paths.
    prefix = f"mi-{name}-"
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', body)
    body = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{prefix}{m.group(1)})", body)
    body = re.sub(r'((?:xlink:)?href)="#([^"]+)"', lambda m: f'{m.group(1)}="#{prefix}{m.group(2)}"', body)
    return view_box.group(1), (style.group(1) if style else ""), body


def _icons() -> dict:
    """The current set, re-read at most once a second and only if the folder changed."""
    now = time.monotonic()
    if now - _cache["checked"] < 1.0:
        return _cache["icons"]
    _cache["checked"] = now
    signature = _signature()
    if signature != _cache["signature"]:
        icons = {}
        for filename, _mtime in signature:
            name = filename[:-4].lower()
            if not _NAME.fullmatch(name):
                continue
            with open(os.path.join(ICON_DIR, filename), encoding="utf-8") as handle:
                parsed = _parse(name, handle.read())
            if parsed is not None:
                icons[name] = parsed
        _cache.update(signature=signature, icons=icons)
    return _cache["icons"]


def refresh() -> None:
    """Forget the cached set, so the next call reads the folder again."""
    _cache.update(checked=0.0, signature=None, icons={})


def icon_names() -> list[str]:
    """Every icon, in filename order: the order the pickers show them."""
    return list(_icons())


def has_icon(name: str | None) -> bool:
    return bool(name) and name in _icons()


def default_icon() -> str | None:
    icons = _icons()
    return DEFAULT_ICON if DEFAULT_ICON in icons else next(iter(icons), None)


def clean_icon(name: str | None) -> str:
    """A name worth storing: the one given if it exists, else the default."""
    return name if has_icon(name) else (default_icon() or DEFAULT_ICON)


def icon_svg(name: str | None, size: int = 32, cls: str = "") -> Markup:
    """Inline SVG for an icon name. An unknown name draws the default icon,
    so a task saved under a retired name still shows something."""
    icons = _icons()
    entry = icons.get(name or "") or icons.get(default_icon() or "")
    if entry is None:
        return Markup("")
    view_box, style, body = entry
    klass = f"micon {cls}".strip()
    style_attr = f' style="{style}"' if style else ""
    return Markup(
        f'<svg class="{klass}" width="{size}" height="{size}" viewBox="{view_box}" fill="none"'
        f'{style_attr} aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">'
        f"{body}</svg>")
