"""Plot statuses: the columns and shelves a plot moves through, per account.

One settings page edits the whole list as rows. Each row is matched to its
status by id, never by position, because a status's key is what plots
store: renaming, recolouring or reordering must leave every plot where it
is. Clearing a row's name deletes that status, and its plots move to the
first remaining status of the same kind, or else the first active one.
"""
import re

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import STATUS_HUES, STATUS_KINDS, Status

statuses_bp = Blueprint("statuses", __name__)

MAX_STATUSES = 12
BLANK_ROWS = 3
FIELDS = ("status_id", "status_name", "status_hue", "status_kind", "status_cap")


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def _key_for(name: str, taken: set[str]) -> str:
    """A key from the first name a status is given, unique within the account
    and short enough for ``Project.phase``. It never changes afterwards."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:16] or "status"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


@statuses_bp.route("/settings/statuses", methods=["GET", "POST"])
@login_required
def edit_statuses():
    if request.method == "POST" and _save():
        # Back to the same page, so a move arrow keeps you where you were.
        return redirect(url_for("statuses.edit_statuses"))
    counts: dict[str, int] = {}
    for project in current_user.projects:
        counts[project.phase] = counts.get(project.phase, 0) + 1
    statuses = list(current_user.statuses)
    return render_template("statuses_form.html", statuses=statuses, counts=counts,
                           blanks=max(0, min(BLANK_ROWS, MAX_STATUSES - len(statuses))),
                           max_cap=current_app.config["MAX_WIP_BUILDING_LIMIT"])


def _save() -> bool:
    """Apply the posted rows. False, with nothing changed, if refused."""
    ids, names, hues, kinds, caps = (request.form.getlist(field) for field in FIELDS)
    mine = {s.id: s for s in current_user.statuses}
    max_cap = current_app.config["MAX_WIP_BUILDING_LIMIT"]

    def at(values, i):
        return values[i] if i < len(values) else ""

    # Read everything before touching anything, so a refusal leaves no trace.
    rows, removed, seen = [], [], set()
    for i, raw in enumerate(names):
        sid = at(ids, i)
        # Only this account's ids count; anything else is read as a new row.
        status = mine.get(int(sid)) if sid.isdigit() else None
        if status is not None:
            if status.id in seen:
                continue
            seen.add(status.id)
        name = raw.strip()[:40]
        if not name:
            if status is not None:
                removed.append(status)
            continue
        if status is None and len(rows) >= MAX_STATUSES:
            continue
        rows.append({
            "index": i, "status": status, "name": name,
            "hue": at(hues, i) if at(hues, i) in STATUS_HUES else "grey",
            "kind": at(kinds, i) if at(kinds, i) in STATUS_KINDS else "active",
            "cap": _int(at(caps, i), status.wip_limit if status else 0, 0, max_cap),
        })
    # A status the form did not mention at all is left as it was, at the end.
    for status in current_user.statuses:
        if status.id not in seen:
            rows.append({"index": None, "status": status, "name": status.name,
                         "hue": status.hue, "kind": status.kind, "cap": status.wip_limit})

    if not any(row["kind"] == "active" for row in rows):
        flash(tx("statuses.need_active"), "error")
        return False

    move = re.fullmatch(r"(\d+):(up|down)", request.form.get("move") or "")
    if move:
        here = next((n for n, row in enumerate(rows) if row["index"] == int(move.group(1))), None)
        if here is not None:
            there = here - 1 if move.group(2) == "up" else here + 1
            if 0 <= there < len(rows):
                rows[here], rows[there] = rows[there], rows[here]

    # Keys of statuses being deleted stay taken for this save, so a new status
    # named like a removed one cannot collide with it before the delete lands.
    taken = {s.key for s in current_user.statuses}
    kept: list[Status] = []
    for position, row in enumerate(rows):
        status = row["status"]
        if status is None:
            status = Status(key=_key_for(row["name"], taken))
            taken.add(status.key)
            current_user.statuses.append(status)
        status.name, status.hue, status.kind = row["name"], row["hue"], row["kind"]
        status.wip_limit, status.position = row["cap"], position
        kept.append(status)

    for status in removed:
        home = (next((s for s in kept if s.kind == status.kind), None)
                or next(s for s in kept if s.is_active))
        moved = [p for p in current_user.projects if p.phase == status.key]
        for project in moved:
            project.phase = home.key
            if not home.is_parked:
                project.parked_until = None
        if moved:
            flash(tx("statuses.moved", n=len(moved), name=home.name), "info")
        current_user.statuses.remove(status)      # delete-orphan removes the row
    db.session.commit()
    flash(tx("statuses.saved"), "success")
    return True
