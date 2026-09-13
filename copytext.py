"""The words the app shows, read from ``copy/villainy.toml``.

Every user-facing string lives in that one file so it can be edited without
reading templates. Two ways to get a string out:

* ``tx(key, **values)`` -> plain ``str``, for Python: flash messages, JSON
  error messages, labels. Jinja escapes it when it reaches a template.
* ``t(key, **values)`` -> ``Markup``, for templates. The catalogue text is
  escaped, the ``{placeholders}`` are filled in, and a value that is already
  ``Markup`` (a link, a ``<span data-count>``) goes in unescaped. That is how
  a sentence keeps its link without the catalogue holding any HTML.

The file is re-read when it changes on disk (checked at most once a second),
so an edit shows on the next page load in development.

A missing key or placeholder is loud under ``STRICT`` (the test suite sets
it) and quiet otherwise: production shows ``[key]`` rather than a 500, since
one mistyped key in a hand-edited file should not take a page down.
"""
from __future__ import annotations

import os
import threading
import time
import tomllib

from markupsafe import Markup, escape

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "copy", "villainy.toml")

STRICT = False

_lock = threading.Lock()
_state = {"mtime": None, "checked": 0.0, "flat": {}, "screens": []}


def _flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, path + "."))
        elif isinstance(value, str):
            out[path] = value
    return out


def catalogue() -> dict[str, str]:
    """Every key -> text, underscore-prefixed editor labels excluded."""
    now = time.monotonic()
    if now - _state["checked"] < 1.0 and _state["mtime"] is not None:
        return _state["flat"]
    mtime = os.path.getmtime(PATH)
    if mtime != _state["mtime"]:
        with _lock:
            if mtime != _state["mtime"]:
                with open(PATH, "rb") as handle:
                    data = tomllib.load(handle)
                _state["flat"] = {k: v for k, v in _flatten(data).items()
                                  if not k.rsplit(".", 1)[-1].startswith("_")}
                _state["mtime"] = mtime
    _state["checked"] = now
    return _state["flat"]


class _Values(dict):
    """format_map helper: a missing placeholder stays visible as {name}."""

    def __missing__(self, key):
        if STRICT:
            raise KeyError(f"copy placeholder {{{key}}} was not supplied")
        return "{" + key + "}"


def _lookup(key: str) -> str | None:
    text = catalogue().get(key)
    if text is None and STRICT:
        raise KeyError(f"no copy for {key!r} in {os.path.basename(PATH)}")
    return text


def tx(key: str, **values) -> str:
    text = _lookup(key)
    if text is None:
        return f"[{key}]"
    return text.format_map(_Values(values)) if values or "{" in text else text


def t(key: str, **values) -> Markup:
    text = _lookup(key)
    if text is None:
        return Markup(escape(f"[{key}]"))
    return Markup(escape(text)).format_map(_Values(values))


def js_copy() -> dict[str, str]:
    """The ``[js]`` table, for pop-ups the browser raises without a reload."""
    return {k[3:]: v for k, v in catalogue().items() if k.startswith("js.")}
