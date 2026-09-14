"""Routines: the things a plot needs doing on a tempo, shown as abilities.

Each routine is a cooldown. Doing it empties the icon, which refills over
``every_days`` until it is ready again. A plot's page shows all of its
routines as a bar above its schemes; Today gathers the ready ones from every
live plot.

Marking one done counts as work on the plot, so it moves "last touched" the
same way points do. Correcting the last-done date on the form does not: that
is bookkeeping, not progress.
"""
from datetime import date, datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from icons import ICONS
from models import Project, Routine, _aware

routines_bp = Blueprint("routines", __name__)

DEFAULT_ROUTINE_ICON = "refresh"


# ── Where routines show up ──────────────────────────────────────────────────

def _live_routines(user) -> list[Routine]:
    """Routines on plots still in play. Parked, done and dropped plots are
    left out: a routine on something you have put down is not due."""
    return [r for p in user.projects if p.is_active for r in p.routines]


def ready_routines(user) -> list[Routine]:
    """Ready routines across the user's live plots, longest overdue first."""
    ready = [r for r in _live_routines(user) if r.is_ready]
    ready.sort(key=lambda r: (-r.overdue_days, r.project.name.lower(), r.position, r.id))
    return ready


def next_routine(user) -> Routine | None:
    """The live routine that comes ready soonest, for when none are ready."""
    cooling = [r for r in _live_routines(user) if not r.is_ready]
    return min(cooling, key=lambda r: r.ready_at, default=None)


# ── Lookups ─────────────────────────────────────────────────────────────────

def _project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        abort(404)
    return project


def _routine(routine_id: int) -> Routine:
    routine = db.session.get(Routine, routine_id)
    if routine is None or routine.project.owner_id != current_user.id:
        abort(404)
    return routine


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


def _back(project: Project):
    nxt = request.referrer or ""
    host = request.host_url
    if nxt.startswith(host):
        return redirect("/" + nxt[len(host):])
    return redirect(url_for("projects.tree", project_id=project.id))


# ── Form ────────────────────────────────────────────────────────────────────

def _on_day(day: date) -> datetime:
    """A last-done date from the form as a moment: that day, at the current
    time of day, so "three days ago" means exactly three days of cooldown.
    Today or later is simply now."""
    now = datetime.now(timezone.utc)
    if day >= now.date():
        return now
    return datetime.combine(day, now.timetz())


def _read_form(routine: Routine) -> bool:
    title = (request.form.get("title") or "").strip()[:120]
    if not title:
        flash(tx("routine.title_required"), "error")
        return False
    icon = request.form.get("icon") or DEFAULT_ROUTINE_ICON
    routine.title = title
    routine.icon = icon if icon in ICONS else DEFAULT_ROUTINE_ICON
    routine.every_days = _int(request.form.get("every_days"), routine.every_days or 7, 1, 365)

    raw = (request.form.get("last_done") or "").strip()
    if not raw:
        routine.last_done_at = None          # never done: it starts ready
        return True
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return True                          # a garbled date changes nothing
    current = _aware(routine.last_done_at)
    # Saving the form without touching the date must not nudge the timestamp.
    if current is None or current.date() != day:
        routine.last_done_at = _on_day(day)
    return True


# ── Routes ──────────────────────────────────────────────────────────────────

@routines_bp.route("/projects/<int:project_id>/routines/new", methods=["GET", "POST"])
@login_required
def new_routine(project_id: int):
    project = _project(project_id)
    if len(project.routines) >= current_app.config["MAX_ROUTINES_PER_PROJECT"]:
        flash(tx("routine.limit"), "error")
        return redirect(url_for("projects.tree", project_id=project.id))
    # Not attached to the project until the form is valid, as with the other
    # forms, so an autoflush cannot insert a half-built row.
    routine = Routine(project_id=project.id, icon=DEFAULT_ROUTINE_ICON, every_days=7,
                      position=len(project.routines))
    if request.method == "POST" and _read_form(routine):
        routine.project = project
        db.session.add(routine)
        db.session.commit()
        flash(tx("routine.added", title=routine.title), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("routine_form.html", project=project, routine=routine, is_new=True)


@routines_bp.route("/routines/<int:routine_id>/edit", methods=["GET", "POST"])
@login_required
def edit_routine(routine_id: int):
    routine = _routine(routine_id)
    project = routine.project
    if request.method == "POST" and _read_form(routine):
        db.session.commit()
        flash(tx("routine.saved"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("routine_form.html", project=project, routine=routine, is_new=False)


@routines_bp.route("/routines/<int:routine_id>/delete", methods=["POST"])
@login_required
def delete_routine(routine_id: int):
    routine = _routine(routine_id)
    project = routine.project
    db.session.delete(routine)
    db.session.commit()
    flash(tx("routine.deleted"), "info")
    return redirect(url_for("projects.tree", project_id=project.id))


@routines_bp.route("/routines/<int:routine_id>/done", methods=["POST"])
@login_required
def routine_done(routine_id: int):
    """Use the ability: mark the routine done and start its cooldown.

    A plain form post redirects back. The page script posts JSON instead,
    with ``where`` naming the bar it clicked in (``tree`` or ``today``), and
    gets that bar back re-rendered to swap in place.
    """
    routine = _routine(routine_id)
    project = routine.project
    routine.mark_done()
    db.session.commit()

    payload = request.get_json(silent=True)
    if payload is None:
        flash(tx("routine.done", title=routine.title, n=routine.every_days), "success")
        return _back(project)
    if payload.get("where") == "today":
        html = render_template("_ready_bar.html",
                               ready_routines=ready_routines(current_user),
                               next_routine=next_routine(current_user))
    else:
        html = render_template("_routine_bar.html", project=project)
    return jsonify({"html": html, "title": routine.title, "every_days": routine.every_days})
