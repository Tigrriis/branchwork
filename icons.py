"""Task icons: a small stroke set on a 24px grid, rendered inline as SVG.

Keyed by a short name stored on ``Task.icon``. Adding one is a matter of
adding an entry here; the task form lists them all as a picker.
"""
from markupsafe import Markup

ICONS: dict[str, str] = {
    "check": '<path d="M5 12.5l4.5 4.5L19 7"></path>',
    "doc": '<path d="M6 3h8l5 5v13H6z"></path><path d="M14 3v5h5M9 13h7M9 17h7"></path>',
    "layout": '<rect x="3" y="3" width="18" height="18" rx="1"></rect><path d="M3 10h18M10 10v11"></path>',
    "pencil": '<path d="M4 20l4-1L19 8l-3-3L5 16z"></path><path d="M13 7l3 3"></path>',
    "ruler": '<rect x="2" y="9" width="20" height="7" rx="1"></rect><path d="M6 9v3M10 9v3M14 9v3M18 9v3"></path>',
    "sign": '<path d="M3 17c3-7 6-7 7 0s4 6 7-3"></path><path d="M3 21h18"></path>',
    "flag": '<path d="M5 21V4M5 4h13l-3 4 3 4H5"></path>',
    "wrench": '<path d="M14 6a4 4 0 0 0-5 5l-5 5 4 4 5-5a4 4 0 0 0 5-5l-3 3-2-2z"></path>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"></path>',
    "key": '<circle cx="8" cy="12" r="4"></circle><path d="M12 12h9M18 12v3M15 12v2"></path>',
    "seal": '<circle cx="12" cy="9" r="5"></circle><path d="M8 13l-1 8 5-3 5 3-1-8"></path>',
    "fire": '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-6 1 1 2 2 3 1z"></path>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="1"></rect><path d="M3 10h18M8 3v4M16 3v4"></path>',
    "hardhat": '<path d="M4 15a8 8 0 0 1 16 0"></path><path d="M2 15h20M12 7v3"></path>',
    "home": '<path d="M3 11l9-7 9 7M6 10v10h12V10"></path>',
    "users": '<circle cx="9" cy="8" r="3"></circle><path d="M3 20a6 6 0 0 1 12 0M16 4a3 3 0 0 1 0 6M21 20a6 6 0 0 0-5-5.9"></path>',
    "trophy": '<path d="M7 4h10v5a5 5 0 0 1-10 0z"></path><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M12 14v4M8 21h8"></path>',
    "hammer": '<path d="M14 4l6 6-3 3-6-6z"></path><path d="M11 7l-7 7 3 3 7-7"></path>',
    "truck": '<path d="M3 17V7h11v10M14 11h4l3 3v3"></path><circle cx="7" cy="18" r="2"></circle><circle cx="17" cy="18" r="2"></circle>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="1"></rect><path d="M3 7l9 6 9-6"></path>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"></path>',
    "cash": '<rect x="2" y="6" width="20" height="12" rx="1"></rect><circle cx="12" cy="12" r="3"></circle><path d="M6 12h.01M18 12h.01"></path>',
    "chart": '<path d="M3 21h18M6 17V10M11 17V5M16 17v-7M21 17V8"></path>',
    "gear": '<circle cx="12" cy="12" r="3"></circle><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"></path>',
    "box": '<path d="M12 2l9 5v10l-9 5-9-5V7z"></path><path d="M3 7l9 5 9-5M12 12v10"></path>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"></path>',
    "shield": '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"></path><path d="M9 12l2 2 4-4"></path>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3v12H4z"></path><circle cx="12" cy="13" r="3.5"></circle>',
    "globe": '<circle cx="12" cy="12" r="9"></circle><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"></path>',
    "star": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-2.9L6.5 20l1-6.2L3 9.6l6.2-.9z"></path>',
}

DEFAULT_ICON = "check"


def icon_svg(name: str, size: int = 32, stroke_width: float = 1.7, cls: str = "") -> Markup:
    """Inline SVG for an icon name; unknown names fall back to a tick."""
    body = ICONS.get(name) or ICONS[DEFAULT_ICON]
    klass = f' class="{cls}"' if cls else ""
    return Markup(
        f'<svg{klass} width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{body}</svg>')
