"""The portfolio layer: Today, the phase board, the inbox and the weekly review.

Today answers "what am I neglecting": projects past their cadence, parked
projects whose date has come, projects with no next action, and the inbox.
The board is every project by phase, with a WIP limit on Building. Review
walks the active projects one by one and asks: keep, advance, park or drop.
"""
from datetime import date, datetime, timedelta, timezone

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    url_for,
)
from flask_login import current_user, login_required

from extensions import db
from models import (
    ACTIVE_PHASES, CADENCES, PHASES, Branch, InboxItem, Project, Task,
)

dashboard_bp = Blueprint("dashboard", __name__)


def _project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        abort(404)
    return project


def _inbox_item(item_id: int) -> InboxItem:
    item = db.session.get(InboxItem, item_id)
    if item is None or item.user_id != current_user.id:
        abort(404)
    return item


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

@dashboard_bp.route("/")
def today():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    projects = list(current_user.projects)
    due = sorted((p for p in projects if p.is_due), key=lambda p: p.overdue_days, reverse=True)
    resurfaced = [p for p in projects if p.parked_expired]
    no_action = [p for p in projects if p.is_active and not p.next_action]
    on_track = sorted((p for p in projects if p.is_active and not p.is_due and p.next_action),
                      key=lambda p: p.days_since_touch, reverse=True)
    # Only loose ideas belong here; ones attached to a project live under that
    # project's tree instead.
    inbox = [i for i in current_user.inbox_items if i.is_loose]
    inbox.sort(key=lambda i: (not i.resurfaced, i.created_at or datetime.min.replace(tzinfo=timezone.utc)))
    parked_items = [i for i in current_user.inbox_items
                    if i.status == "parked" and i.project_id is None]
    return render_template(
        "today.html", due=due, resurfaced=resurfaced, no_action=no_action,
        on_track=on_track, inbox=inbox, parked_items=parked_items,
        active_projects=[p for p in projects if p.is_active],
        today=date.today())


# ── Board ───────────────────────────────────────────────────────────────────

@dashboard_bp.route("/board")
@login_required
def board():
    projects = list(current_user.projects)
    columns = [(key, PHASES[key], sorted((p for p in projects if p.phase == key),
                                          key=lambda p: p.days_since_touch))
               for key in ACTIVE_PHASES]
    shelves = [(key, PHASES[key], [p for p in projects if p.phase == key])
               for key in ("parked", "done", "dropped")]
    return render_template("board.html", columns=columns, shelves=shelves,
                           wip_limit=current_user.wip_building_limit)


def _building_count(exclude: Project) -> int:
    return sum(1 for p in current_user.projects if p.phase == "building" and p.id != exclude.id)


def _set_phase(project: Project, phase: str, *, park_until: date | None = None,
               kind: str = "phase") -> bool:
    """Move a project; enforce the WIP limit; record the event. False if refused."""
    if phase not in PHASES:
        return False
    # 0 means the user has turned the cap off on their account page.
    limit = current_user.wip_building_limit
    if limit and phase == "building" and project.phase != "building" and _building_count(project) >= limit:
        names = ", ".join(p.name for p in current_user.projects if p.phase == "building")
        flash(f"Building is full ({limit}): {names}. Ship or park one first, "
              f"or raise the cap on your account page.", "error")
        return False
    old = project.phase
    project.phase = phase
    project.parked_until = park_until if phase == "parked" else None
    if old != phase:
        project.record(kind, note=f"{PHASES.get(old, old)} → {PHASES[phase]}")
    return True


@dashboard_bp.route("/projects/<int:project_id>/phase", methods=["POST"])
@login_required
def set_phase(project_id: int):
    project = _project(project_id)
    phase = request.form.get("phase") or ""
    until = _parse_date(request.form.get("parked_until")) if phase == "parked" else None
    if _set_phase(project, phase, park_until=until):
        db.session.commit()
        flash(f"{project.name} → {project.phase_label}.", "success")
    return _back()


@dashboard_bp.route("/projects/<int:project_id>/next-action", methods=["POST"])
@login_required
def set_next_action(project_id: int):
    project = _project(project_id)
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    db.session.commit()
    return _back()


@dashboard_bp.route("/projects/<int:project_id>/touch", methods=["POST"])
@login_required
def touch(project_id: int):
    """Log activity that happened outside the app."""
    project = _project(project_id)
    project.record("touch", note=(request.form.get("note") or "").strip()[:200] or None)
    db.session.commit()
    flash(f"Logged a touch on {project.name}.", "success")
    return _back()


# ── Inbox ───────────────────────────────────────────────────────────────────

@dashboard_bp.route("/inbox", methods=["POST"])
@login_required
def inbox_add():
    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Write something first.", "error")
    elif len([i for i in current_user.inbox_items if i.status != "done"]) >= current_app.config["MAX_INBOX_ITEMS"]:
        flash("The inbox is full. Triage it before adding more.", "error")
    else:
        db.session.add(InboxItem(user=current_user, text=text[:2000]))
        db.session.commit()
    return _back()


@dashboard_bp.route("/inbox/<int:item_id>/file", methods=["POST"])
@login_required
def inbox_file(item_id: int):
    """Turn an inbox item into a task on a project (first branch, tier 1)."""
    item = _inbox_item(item_id)
    project_id = request.form.get("project_id") or ""
    project = _project(int(project_id)) if project_id.isdigit() else None
    if project is None:
        flash("Pick a project to file it into.", "error")
        return _back()
    branch = project.branches[0] if project.branches else None
    if branch is None:
        branch = Branch(project=project, name="Backlog", hue="violet", position=0)
        db.session.add(branch)
        db.session.flush()
    title = item.text.strip().splitlines()[0][:120]
    task = Task(branch=branch, tier=1, title=title, icon="check", points_max=1, points_done=0,
                notes=item.text if len(item.text) > len(title) else None,
                position=len([t for t in branch.tasks if t.tier == 1]))
    db.session.add(task)
    db.session.flush()
    item.project, item.task_id = project, task.id
    project.record("task", task=task, note=f"Filed from inbox: {title}")
    db.session.commit()
    flash(f"Filed into {project.name} › {branch.name}.", "success")
    return _back()


@dashboard_bp.route("/inbox/<int:item_id>/park", methods=["POST"])
@login_required
def inbox_park(item_id: int):
    item = _inbox_item(item_id)
    item.revisit_on = _parse_date(request.form.get("revisit_on"))
    db.session.commit()
    return _back()


@dashboard_bp.route("/inbox/<int:item_id>/done", methods=["POST"])
@login_required
def inbox_done(item_id: int):
    item = _inbox_item(item_id)
    item.done_at = datetime.now(timezone.utc)
    db.session.commit()
    return _back()


@dashboard_bp.route("/inbox/<int:item_id>/delete", methods=["POST"])
@login_required
def inbox_delete(item_id: int):
    item = _inbox_item(item_id)
    db.session.delete(item)
    db.session.commit()
    return _back()


# ── Review ──────────────────────────────────────────────────────────────────

@dashboard_bp.route("/review")
@login_required
def review():
    """Every project under review on one scrolling page.

    Deciding one does not remove it: the point of the page is to see the
    whole scope at once, so a decided project stays put and is marked.
    ``done`` carries which ones have been decided this pass.
    """
    projects = [p for p in current_user.projects if p.is_active or p.parked_expired]
    projects.sort(key=lambda p: (p.overdue_days if p.overdue_days is not None else -999), reverse=True)
    ids = {p.id for p in projects}
    reviewed_ids = {int(x) for x in request.args.get("done", "").split(",") if x.isdigit()} & ids
    return render_template("review.html", projects=projects, reviewed_ids=reviewed_ids,
                           reviewed=len(reviewed_ids), total=len(projects),
                           done_param=",".join(str(i) for i in sorted(reviewed_ids)),
                           today=date.today())


@dashboard_bp.route("/review/<int:project_id>", methods=["POST"])
@login_required
def review_decide(project_id: int):
    project = _project(project_id)
    decision = request.form.get("decision") or "keep"
    project.objective = (request.form.get("objective") or "").strip()[:300] or None
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    ok = True
    if decision == "advance" and project.next_phase:
        ok = _set_phase(project, project.next_phase, kind="review")
    elif decision == "park":
        ok = _set_phase(project, "parked", park_until=_parse_date(request.form.get("parked_until")), kind="review")
    elif decision == "drop":
        ok = _set_phase(project, "dropped", kind="review")
    elif decision == "unpark":
        ok = _set_phase(project, "exploring", kind="review")
    else:
        project.record("review", note="Reviewed, kept as is")
    if ok:
        db.session.commit()
    done = request.form.get("done") or ""
    ids = [x for x in done.split(",") if x.isdigit()] + [str(project.id)]
    # Anchor back to the card just decided, so a long page does not jump to
    # the top after every decision.
    return redirect(url_for("dashboard.review", done=",".join(ids)) + f"#p{project.id}")
