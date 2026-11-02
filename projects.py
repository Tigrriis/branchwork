"""Projects, branches and tasks: the tree itself.

Every route here is owner-only. ``_project``/``_branch``/``_task`` look an
object up and 404 unless the signed-in user owns the project it belongs to,
so a guessed id reads the same as a missing one.

Points change through one endpoint, ``POST /machinations/<id>/points``, which the
tree page calls with fetch() and which answers with the re-rendered tree
fragment. One template renders the tree in both cases, so the page never has
to reproduce the gate logic in JavaScript.
"""
from datetime import datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from icons import DEFAULT_ICON, clean_icon
from models import CADENCES, HUES, Branch, InboxItem, Project, Task
from starters import DEFAULT_STARTER, apply_starter, choices_for
from threads import find_target, thread_tasks

projects_bp = Blueprint("projects", __name__)


# ── Lookups ─────────────────────────────────────────────────────────────────

def _project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        abort(404)
    return project


def _branch(branch_id: int) -> Branch:
    branch = db.session.get(Branch, branch_id)
    if branch is None or branch.project.owner_id != current_user.id:
        abort(404)
    return branch


def _task(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None or task.branch.project.owner_id != current_user.id:
        abort(404)
    return task


def _idea(item_id: int) -> InboxItem:
    """An inbox item this user owns. Ownership is on the item, not the project:
    an idea can sit in the loose inbox with no project at all."""
    item = db.session.get(InboxItem, item_id)
    if item is None or item.user_id != current_user.id:
        abort(404)
    return item


def _project_ideas(project: Project) -> list[InboxItem]:
    """Open ideas parked under this project's tree, oldest first."""
    items = [i for i in current_user.inbox_items
             if i.project_id == project.id and i.status == "open"]
    items.sort(key=lambda i: i.id)
    return items


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


# ── Projects ────────────────────────────────────────────────────────────────

def _read_project_form(project: Project) -> bool:
    name = (request.form.get("name") or "").strip()[:120]
    if not name:
        flash(tx("plot.name_required"), "error")
        return False
    project.name = name
    project.code = (request.form.get("code") or "").strip()[:40] or None
    project.description = (request.form.get("description") or "").strip() or None
    project.gate_points = _int(request.form.get("gate_points"),
                               current_app.config["DEFAULT_GATE_POINTS"], 1, 99)
    cadence = _int(request.form.get("cadence_days"), 14, 0, 365)
    project.cadence_days = cadence if cadence in CADENCES else 14
    project.focused = bool(request.form.get("focused"))
    project.objective = (request.form.get("objective") or "").strip()[:300] or None
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    project.repo_path = (request.form.get("repo_path") or "").strip()[:400] or None
    status = current_user.status(request.form.get("phase") or project.phase)
    if status is not None and status.key != project.phase:
        if project.id is None:
            project.phase = status.key          # new, so nothing to shelve from
        else:
            project.change_phase(status, park_until=project.parked_until, record=False)
    return True


@projects_bp.route("/plots/new", methods=["GET", "POST"])
@login_required
def new_project():
    if len(current_user.projects) >= current_app.config["MAX_PROJECTS_PER_USER"]:
        flash(tx("plot.limit"), "error")
        return redirect(url_for("dashboard.today"))
    # Not attached to current_user until the form is valid: appending to the
    # relationship would let an autoflush insert a half-built row.
    # focused=True so the form renders with the box ticked: creating a project
    # is an act of attention, and unticking it is one click.
    project = Project(owner_id=current_user.id, gate_points=current_app.config["DEFAULT_GATE_POINTS"],
                      phase=current_user.default_status.key, cadence_days=14, focused=True)
    if request.method == "POST" and _read_project_form(project):
        db.session.add(project)
        for branch in apply_starter(project, request.form.get("starter") or "blank"):
            db.session.add(branch)
        project.record("touch", note="Project created")
        db.session.commit()
        flash(tx("plot.created") if project.branches else tx("plot.created_add_scheme"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("project_form.html", project=project, is_new=True,
                           starters=choices_for(current_user), default_starter=DEFAULT_STARTER)


@projects_bp.route("/plots/<int:project_id>")
@login_required
def tree(project_id: int):
    project = _project(project_id)
    return render_template("project_tree.html", project=project,
                           ideas=_project_ideas(project))


@projects_bp.route("/plots/<int:project_id>/tree")
@login_required
def tree_fragment(project_id: int):
    project = _project(project_id)
    return render_template("_tree.html", project=project)


@projects_bp.route("/plots/<int:project_id>/list")
@login_required
def task_list(project_id: int):
    project = _project(project_id)
    return render_template("project_list.html", project=project)


@projects_bp.route("/plots/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id: int):
    project = _project(project_id)
    if request.method == "POST" and _read_project_form(project):
        db.session.commit()
        flash(tx("plot.saved"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("project_form.html", project=project, is_new=False)


@projects_bp.route("/plots/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id: int):
    project = _project(project_id)
    db.session.delete(project)
    db.session.commit()
    flash(tx("plot.deleted"), "info")
    return redirect(url_for("dashboard.today"))


# ── Branches ────────────────────────────────────────────────────────────────

def _would_cycle(branch: Branch, requires: Branch | None) -> bool:
    """True if making ``branch`` require ``requires`` closes a loop."""
    seen = set()
    node = requires
    while node is not None:
        if node.id == branch.id or node.id in seen:
            return True
        seen.add(node.id)
        node = node.requires
    return False


def _read_branch_form(branch: Branch, project: Project) -> bool:
    name = (request.form.get("name") or "").strip()[:80]
    if not name:
        flash(tx("scheme.name_required"), "error")
        return False
    hue = request.form.get("hue") or "green"
    if hue not in HUES:
        hue = "green"
    requires_id = request.form.get("requires_branch_id") or ""
    requires = None
    if requires_id:
        requires = db.session.get(Branch, int(requires_id)) if requires_id.isdigit() else None
        if requires is None or requires.project_id != project.id:
            flash(tx("scheme.not_in_plot"), "error")
            return False
        if branch.id is not None and _would_cycle(branch, requires):
            flash(tx("scheme.cycle"), "error")
            return False
    branch.name, branch.hue, branch.requires = name, hue, requires
    return True


@projects_bp.route("/plots/<int:project_id>/schemes/new", methods=["GET", "POST"])
@login_required
def new_branch(project_id: int):
    project = _project(project_id)
    if len(project.branches) >= current_app.config["MAX_BRANCHES_PER_PROJECT"]:
        flash(tx("scheme.limit"), "error")
        return redirect(url_for("projects.tree", project_id=project.id))
    # Rotate through the hues so consecutive branches differ by default.
    hues = list(HUES)
    branch = Branch(project_id=project.id, position=len(project.branches),
                    hue=hues[len(project.branches) % len(hues)])
    if request.method == "POST" and _read_branch_form(branch, project):
        branch.project = project
        db.session.add(branch)
        db.session.commit()
        flash(tx("scheme.added", name=branch.name), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("branch_form.html", project=project, branch=branch, is_new=True)


@projects_bp.route("/schemes/<int:branch_id>/edit", methods=["GET", "POST"])
@login_required
def edit_branch(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    if request.method == "POST" and _read_branch_form(branch, project):
        db.session.commit()
        flash(tx("scheme.saved"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    threads, locks = _crossing_links(branch)
    move_targets = sorted((p for p in current_user.projects if p.id != project.id),
                          key=lambda p: p.name.lower())
    return render_template("branch_form.html", project=project, branch=branch, is_new=False,
                           move_targets=move_targets, move_cuts=len(threads) + len(locks))


@projects_bp.route("/schemes/<int:branch_id>/move", methods=["POST"])
@login_required
def move_branch(branch_id: int):
    """Swap a branch with its neighbour (direction=left|right)."""
    branch = _branch(branch_id)
    project = branch.project
    order = list(project.branches)
    i = order.index(branch)
    j = i - 1 if request.form.get("direction") == "left" else i + 1
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]
        for pos, b in enumerate(order):
            b.position = pos
        db.session.commit()
    return redirect(url_for("projects.tree", project_id=project.id))


@projects_bp.route("/schemes/<int:branch_id>/reorder", methods=["POST"])
@login_required
def reorder_branch(branch_id: int):
    """Put a scheme just before another of its plot's schemes, or last: the
    drop handler for dragging a column by its name. Body: JSON
    ``{"before": scheme id or null}``. Answers with the re-rendered tree."""
    branch = _branch(branch_id)
    project = branch.project
    payload = request.get_json(silent=True) or {}
    current = list(project.branches)
    others = [b for b in current if b is not branch]
    before = _int(payload.get("before"), 0, 0, 2**31 - 1)
    at = next((i for i, b in enumerate(others) if b.id == before), len(others))
    order = others[:at] + [branch] + others[at:]
    moved = order != current
    if moved:
        for position, b in enumerate(order):
            b.position = position
        db.session.commit()
    return jsonify({"moved": moved, "html": render_template("_tree.html", project=project)})


def _crossing_links(branch: Branch) -> tuple[list, list[Branch]]:
    """What ties a scheme to the rest of its plot: threads with one end in
    the scheme and the other outside it, and the schemes on either side of
    its "opens after" lock. Neither can cross to another plot."""
    task_ids = {t.id for t in branch.tasks}
    ultimate_id = branch.ultimate.id if branch.ultimate else None
    threads = []
    for thread in branch.project.threads:
        starts_inside = thread.from_task_id in task_ids
        ends_inside = (thread.to_task_id in task_ids if thread.to_task_id is not None
                       else ultimate_id is not None and thread.to_ultimate_id == ultimate_id)
        if starts_inside != ends_inside:
            threads.append(thread)
    locks = [b for b in branch.project.branches
             if b is not branch and b.requires_branch_id == branch.id]
    if branch.requires is not None:
        locks.append(branch)
    return threads, locks


def _move_to_plot(branch: Branch, target: Project) -> int:
    """Move a scheme, with its machinations, ultimate, threads within it and
    notes, to the end of another plot. Links that would cross plots are cut,
    and how many is returned."""
    source = branch.project
    task_ids = {t.id for t in branch.tasks}
    crossing, locks = _crossing_links(branch)
    for thread in crossing:
        db.session.delete(thread)
    for b in locks:
        b.requires = None
    # Threads wholly inside the scheme travel with it.
    for thread in list(source.threads):
        if thread.from_task_id in task_ids and thread not in crossing:
            thread.project = target
    # Its folder in the notebook, and every machination folder inside it.
    # Notes are sealed with the owner's key, not the plot's, so they read
    # the same wherever they are filed.
    for note in list(source.notes):
        if note.branch_id == branch.id or note.task_id in task_ids:
            note.project = target
            if note.task_id in task_ids:
                note.branch = branch
    # Ideas that became these machinations belong to the new plot's list now.
    for item in current_user.inbox_items:
        if item.task_id in task_ids:
            item.project = target
    position = len(target.branches)
    branch.project = target
    branch.position = position
    for pos, b in enumerate(b for b in source.branches if b is not branch):
        b.position = pos
    source.record("touch", note=f"Scheme moved out: {branch.name}"[:200])
    target.record("touch", note=f"Scheme moved in: {branch.name}"[:200])
    return len(crossing) + len(locks)


@projects_bp.route("/schemes/<int:branch_id>/move-to", methods=["POST"])
@login_required
def move_branch_to_plot(branch_id: int):
    branch = _branch(branch_id)
    source = branch.project
    raw = request.form.get("project_id") or ""
    target = db.session.get(Project, int(raw)) if raw.isdigit() else None
    if target is None or target.owner_id != current_user.id or target.id == source.id:
        flash(tx("scheme.move_pick"), "error")
        return redirect(url_for("projects.edit_branch", branch_id=branch.id))
    if len(target.branches) >= current_app.config["MAX_BRANCHES_PER_PROJECT"]:
        flash(tx("scheme.move_full", plot=target.name), "error")
        return redirect(url_for("projects.edit_branch", branch_id=branch.id))
    cut = _move_to_plot(branch, target)
    db.session.commit()
    flash(tx("scheme.moved", name=branch.name, plot=target.name), "success")
    if cut:
        flash(tx("scheme.moved_cut", n=cut), "info")
    return redirect(url_for("projects.tree", project_id=target.id))


@projects_bp.route("/schemes/<int:branch_id>/delete", methods=["POST"])
@login_required
def delete_branch(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    for other in project.branches:
        if other.requires_branch_id == branch.id:
            other.requires = None
    db.session.delete(branch)
    db.session.commit()
    flash(tx("scheme.deleted"), "info")
    return redirect(url_for("projects.tree", project_id=project.id))


# ── Tasks ───────────────────────────────────────────────────────────────────

def _read_task_form(task: Task, project: Project, default_branch: Branch | None = None) -> bool:
    title = (request.form.get("title") or "").strip()[:120]
    if not title:
        flash(tx("machination.title_required"), "error")
        return False
    branch_id = request.form.get("branch_id")
    if branch_id and branch_id.isdigit():
        target = db.session.get(Branch, int(branch_id))
        if target is None or target.project_id != project.id:
            flash(tx("scheme.not_in_plot"), "error")
            return False
        if task.branch is not target:
            task.branch = target
            task.position = len([t for t in target.tasks if t.tier == task.tier])
            # Its notes go with it, so they still fall back to the right
            # scheme if the machination is deleted later.
            for note in task.filed_notes:
                note.file_under(task)
    elif task.branch is None and default_branch is not None:
        task.branch = default_branch
    task.title = title
    task.icon = clean_icon(request.form.get("icon"))
    task.tier = _int(request.form.get("tier"), task.tier or 1, 1, 50)
    task.points_max = _int(request.form.get("points_max"), 1, 1,
                           current_app.config["MAX_POINTS_PER_TASK"])
    task.set_points(_int(request.form.get("points_done"), task.points_done or 0, 0, task.points_max))
    return True


def _thread_from_form(project: Project, task: Task) -> None:
    """The form's "comes after" and "leads to" pickers, applied once the
    machination has an id. A refusal is flashed and the rest of the save
    still stands."""
    follows = (request.form.get("follows") or "").strip()
    if follows:
        error = thread_tasks(project, follows, task)
        if error:
            flash(tx(error), "error")
        else:
            db.session.commit()
    leads_to = (request.form.get("leads_to") or "").strip()
    if leads_to:
        ultimate = find_target(project, ultimate_id=leads_to)
        error = "thread.not_in_plot" if ultimate is None else thread_tasks(project, task.id, ultimate)
        if error:
            flash(tx(error), "error")
        else:
            db.session.commit()


@projects_bp.route("/schemes/<int:branch_id>/machinations/new", methods=["GET", "POST"])
@login_required
def new_task(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    if len(branch.tasks) >= current_app.config["MAX_TASKS_PER_BRANCH"]:
        flash(tx("machination.limit"), "error")
        return redirect(url_for("projects.tree", project_id=project.id))
    tier = _int(request.args.get("tier"), branch.next_tier, 1, 50)
    task = Task(branch_id=branch.id, tier=tier, icon=DEFAULT_ICON, points_max=1, points_done=0,
                position=len([t for t in branch.tasks if t.tier == tier]))
    if request.method == "POST" and _read_task_form(task, project, default_branch=branch):
        db.session.add(task)
        db.session.flush()
        project.record("task", task=task, note=f"Added {task.title}")
        db.session.commit()
        _thread_from_form(project, task)
        flash(tx("machination.added", title=task.title), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("task_form.html", project=project, task=task, branch=branch, is_new=True)


@projects_bp.route("/machinations/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id: int):
    task = _task(task_id)
    project = task.branch.project
    if request.method == "POST" and _read_task_form(task, project):
        db.session.commit()
        _thread_from_form(project, task)
        flash(tx("machination.saved"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("task_form.html", project=project, task=task, branch=task.branch, is_new=False)


@projects_bp.route("/machinations/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    task = _task(task_id)
    project = task.branch.project
    db.session.delete(task)
    db.session.commit()
    flash(tx("machination.deleted"), "info")
    return redirect(url_for("projects.tree", project_id=project.id))


@projects_bp.route("/machinations/<int:task_id>/points", methods=["POST"])
@login_required
def task_points(task_id: int):
    """Adjust a task's points. Body: JSON ``{"delta": ±1}`` or ``{"set": n}``.

    Answers with the re-rendered tree fragment (HTML) plus a JSON header of
    the project totals, so the page swaps the tree in one go.
    """
    task = _task(task_id)
    project = task.branch.project
    payload = request.get_json(silent=True) or {}
    if not task.editable:
        return jsonify({"error": "locked",
                        "message": tx("machination.locked")}), 409
    before = task.points_done
    if "set" in payload:
        task.set_points(_int(payload.get("set"), task.points_done, 0, task.points_max))
    else:
        task.adjust(_int(payload.get("delta"), 1, -task.points_max, task.points_max))
    if task.points_done != before:
        project.record("points", task=task, delta=task.points_done - before, note=task.title)
    db.session.commit()
    html = render_template("_tree.html", project=project)
    return jsonify({
        "html": html,
        "points_done": project.points_done,
        "points_max": project.points_max,
        "percent": project.percent,
        "counts": {s: project.count_state(s) for s in ("full", "part", "empty")},
    })


@projects_bp.route("/machinations/<int:task_id>/move", methods=["POST"])
@login_required
def move_task(task_id: int):
    """Move a machination within its tier, or to another tier or scheme of
    its plot: the drop handler for dragging a tile. Body: JSON
    ``{"branch_id": n, "tier": n, "before": task id or null}``.

    It lands just before ``before`` when that machination is in the tier,
    and at the end of the tier otherwise. It keeps its points: moving is
    planning, so a finished machination dropped behind a closed gate stays
    finished. Its notes follow it to the new scheme's folder. Answers like
    the points endpoint, with the re-rendered tree and the plot's totals.
    """
    task = _task(task_id)
    project = task.branch.project
    payload = request.get_json(silent=True) or {}
    target = db.session.get(Branch, _int(payload.get("branch_id"), 0, 0, 2**31 - 1))
    if target is None or target.project_id != project.id:
        return jsonify({"error": "not_in_plot", "message": tx("scheme.not_in_plot")}), 404
    tier = _int(payload.get("tier"), task.tier, 1, 50)
    changes_place = target is not task.branch or tier != task.tier
    if changes_place and target is not task.branch \
            and len(target.tasks) >= current_app.config["MAX_TASKS_PER_BRANCH"]:
        return jsonify({"error": "full", "message": tx("machination.limit")}), 409

    # The tier as it stands, then as it will be with this one dropped in.
    current = [t for t in target.tasks if t.tier == tier]
    others = [t for t in current if t is not task]
    before = _int(payload.get("before"), 0, 0, 2**31 - 1)
    at = next((i for i, t in enumerate(others) if t.id == before), len(others))
    order = others[:at] + [task] + others[at:]
    moved = changes_place or order != current
    if moved:
        if changes_place:
            task.branch, task.tier = target, tier
            # Its notes go with it, as when the form moves it.
            for note in task.filed_notes:
                note.file_under(task)
        for position, t in enumerate(order):
            t.position = position
        verb = "Moved" if changes_place else "Reordered"
        project.record("task", task=task, note=f"{verb} {task.title}"[:200])
        db.session.commit()
    return jsonify({
        "moved": moved,
        "html": render_template("_tree.html", project=project),
        "points_done": project.points_done,
        "points_max": project.points_max,
        "percent": project.percent,
        "counts": {s: project.count_state(s) for s in ("full", "part", "empty")},
    })


# ── Project ideas ───────────────────────────────────────────────────────────
# A per-project inbox for thoughts that are not tasks yet: no tier, no points,
# no bearing on progress. Dragging one onto a tier is what turns it into a
# task, which is the moment you decide where it actually belongs.

@projects_bp.route("/plots/<int:project_id>/ideas", methods=["POST"])
@login_required
def add_idea(project_id: int):
    project = _project(project_id)
    text = (request.form.get("text") or "").strip()
    if not text:
        flash(tx("ideas.text_required"), "error")
    elif len([i for i in current_user.inbox_items if i.status != "done"]) >= current_app.config["MAX_INBOX_ITEMS"]:
        flash(tx("ideas.full"), "error")
    else:
        db.session.add(InboxItem(user=current_user, project=project, text=text[:2000]))
        db.session.commit()
    return redirect(url_for("projects.tree", project_id=project.id))


@projects_bp.route("/ideas/<int:item_id>/promote", methods=["POST"])
@login_required
def promote_idea(item_id: int):
    """Turn an idea into a task on a branch and tier — the drop handler.

    Body: JSON ``{"branch_id": n, "tier": n}``. Answers with both re-rendered
    fragments, since the idea leaves one list and appears in the other.
    """
    item = _idea(item_id)
    payload = request.get_json(silent=True) or {}
    branch = db.session.get(Branch, payload.get("branch_id") or 0)
    if branch is None or branch.project.owner_id != current_user.id:
        return jsonify({"error": "no_branch", "message": tx("ideas.scheme_gone")}), 404
    project = branch.project
    if item.status != "open":
        return jsonify({"error": "not_open", "message": tx("ideas.not_open")}), 409
    if len(branch.tasks) >= current_app.config["MAX_TASKS_PER_BRANCH"]:
        return jsonify({"error": "full", "message": tx("ideas.scheme_full")}), 409

    tier = _int(payload.get("tier"), branch.next_tier, 1, 50)
    title = item.text.strip().splitlines()[0][:120]
    task = Task(branch=branch, tier=tier, title=title, icon=DEFAULT_ICON,
                points_max=1, points_done=0,
                notes=item.text if len(item.text) > len(title) else None,
                position=len([t for t in branch.tasks if t.tier == tier]))
    db.session.add(task)
    db.session.flush()
    # Both, so the item reads as filed and still points at where it went.
    item.project, item.task_id = project, task.id
    project.record("task", task=task, note=f"From ideas: {title}")
    db.session.commit()
    return jsonify({
        "tree": render_template("_tree.html", project=project),
        "ideas": render_template("_ideas.html", project=project, ideas=_project_ideas(project)),
        "title": title,
        "branch": branch.name,
        "tier": tier,
        # A new task adds to the denominator and the "not started" count, so
        # the header has to move too.
        "points_done": project.points_done,
        "points_max": project.points_max,
        "percent": project.percent,
        "counts": {s: project.count_state(s) for s in ("full", "part", "empty")},
    })


@projects_bp.route("/ideas/<int:item_id>/done", methods=["POST"])
@login_required
def finish_idea(item_id: int):
    item = _idea(item_id)
    project_id = item.project_id
    item.done_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("projects.tree", project_id=project_id) if project_id
                    else url_for("dashboard.today"))


@projects_bp.route("/ideas/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_idea(item_id: int):
    item = _idea(item_id)
    project_id = item.project_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("projects.tree", project_id=project_id) if project_id
                    else url_for("dashboard.today"))
