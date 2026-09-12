"""Projects, branches and tasks: the tree itself.

Every route here is owner-only. ``_project``/``_branch``/``_task`` look an
object up and 404 unless the signed-in user owns the project it belongs to,
so a guessed id reads the same as a missing one.

Points change through one endpoint, ``POST /tasks/<id>/points``, which the
tree page calls with fetch() and which answers with the re-rendered tree
fragment. One template renders the tree in both cases, so the page never has
to reproduce the gate logic in JavaScript.
"""
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from extensions import db
from icons import DEFAULT_ICON, ICONS
from models import CADENCES, HUES, PHASES, Branch, Project, Task
from starters import DEFAULT_STARTER, STARTERS, apply_starter

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
        flash("Give the project a name.", "error")
        return False
    project.name = name
    project.code = (request.form.get("code") or "").strip()[:40] or None
    project.description = (request.form.get("description") or "").strip() or None
    project.gate_points = _int(request.form.get("gate_points"),
                               current_app.config["DEFAULT_GATE_POINTS"], 1, 99)
    cadence = _int(request.form.get("cadence_days"), 14, 0, 365)
    project.cadence_days = cadence if cadence in CADENCES else 14
    project.objective = (request.form.get("objective") or "").strip()[:300] or None
    project.next_action = (request.form.get("next_action") or "").strip()[:200] or None
    project.repo_path = (request.form.get("repo_path") or "").strip()[:400] or None
    phase = request.form.get("phase") or project.phase or "idea"
    if phase in PHASES and phase != project.phase:
        project.phase = phase
    return True


@projects_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    if len(current_user.projects) >= current_app.config["MAX_PROJECTS_PER_USER"]:
        flash("You have reached the project limit.", "error")
        return redirect(url_for("dashboard.board"))
    # Not attached to current_user until the form is valid: appending to the
    # relationship would let an autoflush insert a half-built row.
    project = Project(owner_id=current_user.id, gate_points=current_app.config["DEFAULT_GATE_POINTS"],
                      phase="idea", cadence_days=14)
    if request.method == "POST" and _read_project_form(project):
        db.session.add(project)
        for branch in apply_starter(project, request.form.get("starter") or "blank"):
            db.session.add(branch)
        project.record("touch", note="Project created")
        db.session.commit()
        flash("Project created." + (" Add a branch to start the tree." if not project.branches else ""), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("project_form.html", project=project, is_new=True,
                           starters=STARTERS, default_starter=DEFAULT_STARTER)


@projects_bp.route("/projects/<int:project_id>")
@login_required
def tree(project_id: int):
    project = _project(project_id)
    return render_template("project_tree.html", project=project)


@projects_bp.route("/projects/<int:project_id>/tree")
@login_required
def tree_fragment(project_id: int):
    project = _project(project_id)
    return render_template("_tree.html", project=project)


@projects_bp.route("/projects/<int:project_id>/list")
@login_required
def task_list(project_id: int):
    project = _project(project_id)
    return render_template("project_list.html", project=project)


@projects_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id: int):
    project = _project(project_id)
    if request.method == "POST" and _read_project_form(project):
        db.session.commit()
        flash("Project saved.", "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("project_form.html", project=project, is_new=False)


@projects_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id: int):
    project = _project(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "info")
    return redirect(url_for("dashboard.board"))


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
        flash("Give the branch a name.", "error")
        return False
    hue = request.form.get("hue") or "green"
    if hue not in HUES:
        hue = "green"
    requires_id = request.form.get("requires_branch_id") or ""
    requires = None
    if requires_id:
        requires = db.session.get(Branch, int(requires_id)) if requires_id.isdigit() else None
        if requires is None or requires.project_id != project.id:
            flash("That branch is not in this project.", "error")
            return False
        if branch.id is not None and _would_cycle(branch, requires):
            flash("That would make the branches wait on each other.", "error")
            return False
    branch.name, branch.hue, branch.requires = name, hue, requires
    return True


@projects_bp.route("/projects/<int:project_id>/branches/new", methods=["GET", "POST"])
@login_required
def new_branch(project_id: int):
    project = _project(project_id)
    if len(project.branches) >= current_app.config["MAX_BRANCHES_PER_PROJECT"]:
        flash("This project has reached the branch limit.", "error")
        return redirect(url_for("projects.tree", project_id=project.id))
    # Rotate through the hues so consecutive branches differ by default.
    hues = list(HUES)
    branch = Branch(project_id=project.id, position=len(project.branches),
                    hue=hues[len(project.branches) % len(hues)])
    if request.method == "POST" and _read_branch_form(branch, project):
        branch.project = project
        db.session.add(branch)
        db.session.commit()
        flash(f"Branch “{branch.name}” added.", "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("branch_form.html", project=project, branch=branch, is_new=True)


@projects_bp.route("/branches/<int:branch_id>/edit", methods=["GET", "POST"])
@login_required
def edit_branch(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    if request.method == "POST" and _read_branch_form(branch, project):
        db.session.commit()
        flash("Branch saved.", "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("branch_form.html", project=project, branch=branch, is_new=False)


@projects_bp.route("/branches/<int:branch_id>/move", methods=["POST"])
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


@projects_bp.route("/branches/<int:branch_id>/delete", methods=["POST"])
@login_required
def delete_branch(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    for other in project.branches:
        if other.requires_branch_id == branch.id:
            other.requires = None
    db.session.delete(branch)
    db.session.commit()
    flash("Branch deleted.", "info")
    return redirect(url_for("projects.tree", project_id=project.id))


# ── Tasks ───────────────────────────────────────────────────────────────────

def _read_task_form(task: Task, project: Project, default_branch: Branch | None = None) -> bool:
    title = (request.form.get("title") or "").strip()[:120]
    if not title:
        flash("Give the task a title.", "error")
        return False
    branch_id = request.form.get("branch_id")
    if branch_id and branch_id.isdigit():
        target = db.session.get(Branch, int(branch_id))
        if target is None or target.project_id != project.id:
            flash("That branch is not in this project.", "error")
            return False
        if task.branch is not target:
            task.branch = target
            task.position = len([t for t in target.tasks if t.tier == task.tier])
    elif task.branch is None and default_branch is not None:
        task.branch = default_branch
    icon = request.form.get("icon") or DEFAULT_ICON
    task.title = title
    task.icon = icon if icon in ICONS else DEFAULT_ICON
    task.tier = _int(request.form.get("tier"), task.tier or 1, 1, 50)
    task.points_max = _int(request.form.get("points_max"), 1, 1,
                           current_app.config["MAX_POINTS_PER_TASK"])
    task.notes = (request.form.get("notes") or "").strip() or None
    task.set_points(_int(request.form.get("points_done"), task.points_done or 0, 0, task.points_max))
    return True


@projects_bp.route("/branches/<int:branch_id>/tasks/new", methods=["GET", "POST"])
@login_required
def new_task(branch_id: int):
    branch = _branch(branch_id)
    project = branch.project
    if len(branch.tasks) >= current_app.config["MAX_TASKS_PER_BRANCH"]:
        flash("This branch has reached the task limit.", "error")
        return redirect(url_for("projects.tree", project_id=project.id))
    tier = _int(request.args.get("tier"), branch.next_tier, 1, 50)
    task = Task(branch_id=branch.id, tier=tier, icon=DEFAULT_ICON, points_max=1, points_done=0,
                position=len([t for t in branch.tasks if t.tier == tier]))
    if request.method == "POST" and _read_task_form(task, project, default_branch=branch):
        db.session.add(task)
        db.session.flush()
        project.record("task", task=task, note=f"Added {task.title}")
        db.session.commit()
        flash(f"Task “{task.title}” added.", "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("task_form.html", project=project, task=task, branch=branch, is_new=True)


@projects_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id: int):
    task = _task(task_id)
    project = task.branch.project
    if request.method == "POST" and _read_task_form(task, project):
        db.session.commit()
        flash("Task saved.", "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("task_form.html", project=project, task=task, branch=task.branch, is_new=False)


@projects_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    task = _task(task_id)
    project = task.branch.project
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("projects.tree", project_id=project.id))


@projects_bp.route("/tasks/<int:task_id>/points", methods=["POST"])
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
                        "message": "This task is on a locked tier."}), 409
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
