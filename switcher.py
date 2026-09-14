"""The plot switcher: the sidebar of plots on every signed-in page.

base.html calls ``plot_switcher`` itself, so the work happens once per full
page and never for the fragments the tree and Today re-render.

Plots are listed by name, not by neglect as Today orders them: a switcher is
used from memory, and a list that reshuffles every time something is touched
defeats that.
"""
import re

from flask_login import current_user

from copytext import tx


def initials(name: str) -> str:
    """Two letters for a plot's chip: the first letter of each of the first
    two words, or the first two letters of a one-word name."""
    words = [w for w in re.split(r"\W+", name or "") if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].capitalize()
    return (words[0][0] + words[1][0]).upper()


def _row(project, current_id):
    return {
        "project": project,
        "initials": initials(project.name),
        "ready": sum(1 for r in project.routines if r.is_ready),
        "current": project.id == current_id,
    }


def plot_switcher(current_id=None) -> list[dict]:
    """Groups for the sidebar, each ``{"key", "label", "rows"}``, empty ones
    left out. Live plots only, in Focus then Backburner. A shelved plot shows
    in a group of its own only while you are on its page, so the switcher can
    still say where you are."""
    if not current_user.is_authenticated:
        return []
    plots = sorted(current_user.projects, key=lambda p: p.name.lower())
    live = [p for p in plots if p.is_active]
    groups = [
        {"key": "focus", "label": tx("rail.focus"),
         "rows": [_row(p, current_id) for p in live if p.focused]},
        {"key": "backburner", "label": tx("rail.backburner"),
         "rows": [_row(p, current_id) for p in live if not p.focused]},
    ]
    shelved = next((p for p in plots if p.id == current_id and not p.is_active), None)
    if shelved is not None:
        groups.append({"key": "shelved", "label": shelved.phase_label,
                       "rows": [_row(shelved, current_id)]})
    return [g for g in groups if g["rows"]]
