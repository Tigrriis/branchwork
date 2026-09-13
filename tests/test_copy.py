"""The copy catalogue and the code that reads it must agree.

A mistyped key renders as [key] in production, so these catch it here: every
key the code asks for exists, and every key in the file is actually used, so
the copy editor never offers a line that changes nothing.
"""
import glob
import os
import re

import copytext

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Families looked up by a computed key, e.g. tx(f"phase.{key}").
DYNAMIC = ("phase.", "cadence.", "hue.", "starter.", "state.")


def _read(pattern):
    return "\n".join(open(p, encoding="utf-8").read()
                     for p in glob.glob(os.path.join(ROOT, pattern)))


def _referenced():
    templates = _read("templates/*.html")
    python = _read("*.py")
    js = _read("static/branchwork/app.js")
    keys = set(re.findall(r"\bt\('([a-z_0-9.]+)'", templates))
    keys |= set(re.findall(r'\btx\("([a-z_0-9.]+)"', python))
    keys |= {k for k in copytext.catalogue() if k.startswith("js.") and f'"{k[3:]}"' in js}
    # t('state.' ~ task.state) captures as "state.": a computed prefix, not a key.
    return {k for k in keys if not k.endswith(".")}


def test_every_referenced_key_exists():
    missing = sorted(k for k in _referenced() if k not in copytext.catalogue())
    assert not missing, f"keys used in code but missing from the catalogue: {missing}"


def test_every_catalogue_key_is_used():
    used = _referenced()
    unused = sorted(k for k in copytext.catalogue()
                    if k not in used and not k.startswith(DYNAMIC))
    assert not unused, f"catalogue keys nothing reads: {unused}"


def test_markup_values_survive_and_text_is_escaped():
    out = copytext.t("focus.empty", link=copytext.Markup('<a href="/x">go</a>'))
    assert '<a href="/x">go</a>' in out
    assert "&lt;b&gt;" in copytext.t("today.subhead", date="<b>", focus=1, back=2)
