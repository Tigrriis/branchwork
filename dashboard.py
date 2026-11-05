"""The portfolio layer: one home page and the weekly review (switched off).

The home page answers "what am I neglecting": plots in focus as tiles with
their tree in miniature, the backburner beneath, and parked plots whose date
has come. Each tile carries its status, which is what the board used to be
for, and the parked and closed plots sit on shelves underneath.
Review is a mode of the same page that flips every live tile to one decision:
keep, advance, park or drop. It is off unless ``WEEKLY_REVIEW`` is set.
"""
from collections import Counter
from datetime import date, timedelta

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from landing import demo_plot, glyph
from models import Project
from routines import next_routine, ready_routines

dashboard_bp = Blueprint("dashboard", __name__)


def _project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        abort(404)
    return project


def _review_enabled() -> bool:
    return bool(current_app.config.get("WEEKLY_REVIEW"))


def _parse_date(value: str | None, default_days: int = 30) -> date:
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return date.today() + timedelta(days=default_days)


def _back():
    nxt = request.form.get("next") or request.referrer or ""
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(url_for("dashboard.today"))


# ── Today ───────────────────────────────────────────────────────────────────

def _focus_split(projects: list[Project]) -> tuple[list[Project], list[Project]]:
    """(focus, backburner), each worst-neglected first.

    Shelved projects are never in focus regardless of the flag: a dropped
    project sitting at the top of the page would be nonsense.
    """
    # A plot whose status has somehow gone stays on a tile, where its pill
    # offers the real statuses, rather than vanishing from the page.
    live = [p for p in projects if p.is_active or p.status is None]
    def order(p):
        return (p.overdue_days if p.overdue_days is not None else -9999, p.days_since_touch)
    focus = sorted((p for p in live if p.focused), key=order, reverse=True)
    backburner = sorted((p for p in live if not p.focused), key=order, reverse=True)
    return focus, backburner


def _shelves(projects: list[Project]) -> list[tuple]:
    """(status, plots) for every parked or closed status, in the account's order."""
    return [(s, [p for p in projects if p.phase == s.key])
            for s in current_user.statuses if not s.is_active]


def _today_context(reviewing: bool = False, done: str = ""):
    projects = list(current_user.projects)
    focus, backburner = _focus_split(projects)
    resurfaced = [p for p in projects if p.parked_expired]
    return {
        "focus": focus,
        "backburner": backburner,
        "resurfaced": resurfaced,
        # The nagging counts are about what you said you are working on. A
        # backburner project going quiet is the point of the backburner.
        "due": [p for p in focus if p.is_due],
        "no_action": [p for p in focus if not p.next_action],
        "active_projects": [p for p in projects if p.is_active],
        "today": date.today(),
        # Every tile's status pill offers every status, with the caps.
        "statuses": list(current_user.statuses),
        "status_counts": Counter(p.phase for p in projects),
        "shelves": _shelves(projects),
        # The bar across the top: routines ready on any live plot.
        "ready_routines": ready_routines(current_user),
        "next_routine": next_routine(current_user),
        "review_enabled": _review_enabled(),
        **_review_state(reviewing, focus + backburner + resurfaced, done),
    }


def _review_state(reviewing: bool, under_review: list[Project], done: str) -> dict:
    """Review mode's bookkeeping. ``done`` carries the plots decided this
    pass, so a decided one stays on the page, marked, instead of vanishing."""
    ids = {p.id for p in under_review}
    reviewed_ids = {int(x) for x in done.split(",") if x.isdigit()} & ids if reviewing else set()
    return {
        "reviewing": reviewing,
        "reviewed_ids": reviewed_ids,
        "reviewed": len(reviewed_ids),
        "total": len(under_review),
        "done_param": ",".join(str(i) for i in sorted(reviewed_ids)),
    }


@dashboard_bp.route("/")
def today():
    # Signed out, the same address is the front door: the pitch and a sign-up box.
    if not current_user.is_authenticated:
        return render_template("landing.html", demo=demo_plot(), glyph=glyph)
    return render_template("today.html", **_today_context(
        reviewing=_review_enabled() and request.args.get("review") == "1",
        done=request.args.get("done", "")))


@dashboard_bp.route("/plots/<int:project_id>/focus", methods=["POST"])
@login_required
def set_focus(project_id: int):
    """Move a project between focus and the backburner.

    Answers with the re-rendered lists for a dropped card, or redirects for
    the plain button, so both interactions go through one rule.
    """
    project = _project(project_id)
    payload = request.get_json(silent=True)
    raw = (payload or {}).get("focused", request.form.get("focused"))
    project.focused = str(raw).lower() in ("1", "true", "yes", "on")
    db.session.commit()
    if payload is not None:
        context = _today_context()
        return jsonify({
            "lists": render_template("_focus_lists.html", **context),
            "name": project.name,
            "focused": project.focused,
            # The header sits outside the re-rendered region, so it has to be
            # told, or it contradicts the lists underneath it.
            "counts": {key: len(context[key])
                       for key in ("focus", "backburner", "due", "no_action")},
        })
    return _back()


# ── Statuses ────────────────────────────────────────────────────────────────

@dashboard_bp.route("/board")
@login_required
def board():
    """The board was folded into the home page. Old links still land."""
    return redirect(url_for("dashboard.today"))


def _set_phase(project: Project, key: str, *, park_until: date | None = None,
               kind: str = "phase") -> bool:
    """Move a plot to one of the user's statuses, enforcing that status's cap
    and recording the event. False if refused."""
    status = current_user.status(key)
    if status is None:
        return False
    limit = status.wip_limit if status.is_active else 0      # 0 means no cap
    if limit and project.phase != key:
        already = [p for p in current_user.projects if p.phase == key and p.id != project.id]
        if len(already) >= limit:
            flash(tx("board.status_full", status=status.name, limit=limit,
                     names=", ".join(p.name for p in already)), "error")
            return False
    project.change_phase(status, park_until=park_until, kind=kind)
    return True


@dashboard_bp.route("/plots/<int:project_id>/phase", methods=["POST"])
@login_required
def set_phase(project_id: int):
    project = _project(project_id)
    phase = request.form.get("phase") or ""
    status = current_user.status(phase)
    parking = status is not None and status.is_parked
    until = _parse_date(request.form.get("parked_until")) if parking else None
    if _set_phase(project, phase, park_until=until):
        db.session.commit()
        flash(tx("board.phase_moved", name=project.name, phase=project.phase_label), "success")
    return _back()


@dashboard_bp.route("/plots/<int:project_id>/next-action", methods=["POST"])
@login_required
def set_next_action(project_id: int):
    project = _project(project_id)
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    db.session.commit()
    return _back()


# ── Review ──────────────────────────────────────────────────────────────────

@dashboard_bp.route("/review")
@login_required
def review():
    """Review became a mode of the home page. Old links, ticks and all, land there."""
    if not _review_enabled():
        return redirect(url_for("dashboard.today"))
    return redirect(url_for("dashboard.today", review=1, done=request.args.get("done") or None))


@dashboard_bp.route("/review/<int:project_id>", methods=["POST"])
@login_required
def review_decide(project_id: int):
    if not _review_enabled():
        abort(404)
    project = _project(project_id)
    decision = request.form.get("decision") or "keep"
    project.objective = (request.form.get("objective") or "").strip()[:300] or None
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    ok = True
    parking = current_user.parked_status
    if decision == "advance" and project.next_status is not None:
        ok = _set_phase(project, project.next_status.key, kind="review")
    elif decision == "park" and parking is not None:
        ok = _set_phase(project, parking.key, park_until=_parse_date(request.form.get("parked_until")),
                        kind="review")
    elif decision.startswith("close:"):
        # Only onto a closed status: the buttons offer nothing else.
        target = current_user.status(decision.split(":", 1)[1])
        ok = target is not None and target.is_closed and _set_phase(project, target.key, kind="review")
    elif decision == "unpark":
        ok = _set_phase(project, project.resume_phase, kind="review")
    else:
        project.record("review", note="Reviewed, kept as is")
    if ok:
        db.session.commit()
    done = request.form.get("done") or ""
    ids = [x for x in done.split(",") if x.isdigit()] + [str(project.id)]
    # Anchor back to the tile just decided, so a long page does not jump to
    # the top after every decision.
    return redirect(url_for("dashboard.today", review=1, done=",".join(ids)) + f"#p{project.id}")
