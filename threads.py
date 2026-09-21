"""Threads: sequence links between machinations, drawn as curved arrows.

A thread says one machination comes after another, usually in a different
scheme, so a plot can carry a sequence that the columns alone cannot show.
It is a statement about order, not a gate: nothing is locked by a thread,
because tier gates and scheme locks already do that job and a hidden third
rule would be one too many.

Threads are made by dragging a tile's handle onto another tile, or from the
"comes after" picker on the machination form, and removed by clicking the
arrow or from the same form.
"""
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import Project, Task, Thread

threads_bp = Blueprint("threads", __name__)


# ── Lookups ─────────────────────────────────────────────────────────────────

def _task(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None or task.branch.project.owner_id != current_user.id:
        abort(404)
    return task


def _thread(thread_id: int) -> Thread:
    thread = db.session.get(Thread, thread_id)
    if thread is None or thread.project.owner_id != current_user.id:
        abort(404)
    return thread


# ── The rule ────────────────────────────────────────────────────────────────

def _loops(project: Project, source: Task, target: Task) -> bool:
    """Would threading source → target close a loop? True if target already
    leads back to source, following the threads that exist."""
    onward: dict[int, list[int]] = {}
    for thread in project.threads:
        onward.setdefault(thread.from_task_id, []).append(thread.to_task_id)
    seen, stack = set(), [target.id]
    while stack:
        node = stack.pop()
        if node == source.id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(onward.get(node, ()))
    return False


def thread_tasks(project: Project, source_id, target: Task) -> str | None:
    """Thread source → target, adding it to the session. Returns a copy key
    naming the refusal, or None once it is made."""
    source_id = str(source_id or "")
    source = db.session.get(Task, int(source_id)) if source_id.isdigit() else None
    if source is None or source.branch.project_id != project.id:
        return "thread.not_in_plot"
    if source.id == target.id:
        return "thread.same"
    if len(project.threads) >= current_app.config["MAX_THREADS_PER_PROJECT"]:
        return "thread.limit"
    if any(t.from_task_id == source.id and t.to_task_id == target.id for t in project.threads):
        return "thread.exists"
    if _loops(project, source, target):
        return "thread.loop"
    db.session.add(Thread(project=project, source=source, target=target))
    return None


# ── Routes ──────────────────────────────────────────────────────────────────

def _tree(project: Project):
    return jsonify({"html": render_template("_tree.html", project=project)})


@threads_bp.route("/tasks/<int:task_id>/threads", methods=["POST"])
@login_required
def add_thread(task_id: int):
    """Thread this machination to another: ``{"to": id}``. The tile drag posts
    JSON and gets the re-rendered tree back, the way points do."""
    source = _task(task_id)
    project = source.branch.project
    payload = request.get_json(silent=True) or {}
    raw = payload.get("to", request.form.get("to"))
    target = db.session.get(Task, int(raw)) if str(raw or "").isdigit() else None
    if target is None or target.branch.project_id != project.id:
        message = tx("thread.not_in_plot")
        if request.get_json(silent=True) is None:
            flash(message, "error")
            return redirect(url_for("projects.tree", project_id=project.id))
        return jsonify({"error": "not_in_plot", "message": message}), 409

    error = thread_tasks(project, source.id, target)
    if error:
        message = tx(error)
        if request.get_json(silent=True) is None:
            flash(message, "error")
            return redirect(url_for("projects.tree", project_id=project.id))
        return jsonify({"error": "refused", "message": message}), 409
    db.session.commit()
    if request.get_json(silent=True) is None:
        flash(tx("thread.added", **{"from": source.title, "to": target.title}), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return _tree(project)


@threads_bp.route("/threads/<int:thread_id>/delete", methods=["POST"])
@login_required
def delete_thread(thread_id: int):
    thread = _thread(thread_id)
    project = thread.project
    db.session.delete(thread)
    db.session.commit()
    if request.get_json(silent=True) is None:
        flash(tx("thread.removed"), "info")
        return redirect(request.form.get("next") or url_for("projects.tree", project_id=project.id))
    return _tree(project)
