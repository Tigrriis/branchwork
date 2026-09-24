"""Threads: sequence links between machinations, drawn as curved arrows.

A thread says one machination comes after another, usually in a different
scheme, so a plot can carry a sequence that the columns alone cannot show.
It is a statement about order, not a gate: nothing is locked by a thread,
because tier gates and scheme locks already do that job and a hidden third
rule would be one too many.

Threads are made by dragging a tile's handle onto another tile or onto a
scheme's ultimate, or from the pickers on the machination and ultimate
forms, and removed from those forms. An ultimate only ever ends a thread.
"""
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import Project, Task, Thread, Ultimate

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

def _loops(project: Project, source: Task, target: Task | Ultimate) -> bool:
    """Would threading source → target close a loop? True if target already
    leads back to source, following the threads that exist. Nothing leads
    on from an ultimate, so a thread into one never loops."""
    if isinstance(target, Ultimate):
        return False
    onward: dict[int, list[int]] = {}
    for thread in project.threads:
        if thread.to_task_id is not None:
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


def find_target(project: Project, task_id=None, ultimate_id=None) -> Task | Ultimate | None:
    """The machination or ultimate a thread is to end at, if it is in this
    plot. One id or the other; anything else is nothing."""
    task_id, ultimate_id = str(task_id or ""), str(ultimate_id or "")
    if ultimate_id.isdigit():
        ultimate = db.session.get(Ultimate, int(ultimate_id))
        return ultimate if ultimate and ultimate.branch.project_id == project.id else None
    if task_id.isdigit():
        task = db.session.get(Task, int(task_id))
        return task if task and task.branch.project_id == project.id else None
    return None


def thread_tasks(project: Project, source_id, target: Task | Ultimate) -> str | None:
    """Thread source → target, adding it to the session. Returns a copy key
    naming the refusal, or None once it is made."""
    source_id = str(source_id or "")
    source = db.session.get(Task, int(source_id)) if source_id.isdigit() else None
    if source is None or source.branch.project_id != project.id:
        return "thread.not_in_plot"
    if source is target:
        return "thread.same"
    if len(project.threads) >= current_app.config["MAX_THREADS_PER_PROJECT"]:
        return "thread.limit"
    if any(t.from_task_id == source.id and t.target is target for t in project.threads):
        return "thread.exists"
    if _loops(project, source, target):
        return "thread.loop"
    db.session.add(Thread(project=project, source=source, target=target))
    return None


# ── Routes ──────────────────────────────────────────────────────────────────

def _tree(project: Project):
    return jsonify({"html": render_template("_tree.html", project=project)})


@threads_bp.route("/machinations/<int:task_id>/threads", methods=["POST"])
@login_required
def add_thread(task_id: int):
    """Thread this machination to another, ``{"to": id}``, or into a scheme's
    ultimate, ``{"to_ultimate": id}``. The tile drag posts JSON and gets the
    re-rendered tree back, the way points do."""
    source = _task(task_id)
    project = source.branch.project
    payload = request.get_json(silent=True) or {}
    target = find_target(project, task_id=payload.get("to", request.form.get("to")),
                         ultimate_id=payload.get("to_ultimate", request.form.get("to_ultimate")))
    if target is None:
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
