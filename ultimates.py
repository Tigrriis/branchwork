"""Ultimates: a scheme's end goal, drawn below every tier.

One per scheme. It opens by the tier rule, so it is always the step after
the last tier wherever that ends up, and a new tier slides in above it. It
is claimed with a click rather than pointed, and a scheme with one is not
complete until it is claimed.

Every route is owner-only, the way the tree's are: a guessed id reads the
same as a missing one.
"""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from icons import DEFAULT_ICON, clean_icon
from models import Branch, Ultimate
from threads import thread_tasks

ultimates_bp = Blueprint("ultimates", __name__)


# ── Lookups ─────────────────────────────────────────────────────────────────

def _branch(branch_id: int) -> Branch:
    branch = db.session.get(Branch, branch_id)
    if branch is None or branch.project.owner_id != current_user.id:
        abort(404)
    return branch


def _ultimate(ultimate_id: int) -> Ultimate:
    ultimate = db.session.get(Ultimate, ultimate_id)
    if ultimate is None or ultimate.branch.project.owner_id != current_user.id:
        abort(404)
    return ultimate


def _read_form(ultimate: Ultimate) -> bool:
    title = (request.form.get("title") or "").strip()[:120]
    if not title:
        flash(tx("ultimate.title_required"), "error")
        return False
    ultimate.title = title
    ultimate.icon = clean_icon(request.form.get("icon"))
    ultimate.notes = (request.form.get("notes") or "").strip() or None
    return True


def _thread_from_form(project, ultimate: Ultimate) -> None:
    """The form's "comes after" picker: a machination that leads into this
    ultimate. A refusal is flashed and the save still stands."""
    follows = (request.form.get("follows") or "").strip()
    if not follows:
        return
    error = thread_tasks(project, follows, ultimate)
    if error:
        flash(tx(error), "error")
    else:
        db.session.commit()


# ── Routes ──────────────────────────────────────────────────────────────────

@ultimates_bp.route("/schemes/<int:branch_id>/ultimate", methods=["GET", "POST"])
@login_required
def edit_ultimate(branch_id: int):
    """One form both sets and edits, since a scheme has at most one."""
    branch = _branch(branch_id)
    project = branch.project
    is_new = branch.ultimate is None
    # By id rather than relationship while it is only a form: attaching it to
    # the scheme would put the empty row in the session before it has a title.
    ultimate = branch.ultimate or Ultimate(branch_id=branch.id, icon=DEFAULT_ICON)
    if request.method == "POST" and _read_form(ultimate):
        if is_new:
            ultimate.branch = branch
            db.session.add(ultimate)
        db.session.commit()
        _thread_from_form(project, ultimate)
        flash(tx("ultimate.added" if is_new else "ultimate.saved"), "success")
        return redirect(url_for("projects.tree", project_id=project.id))
    return render_template("ultimate_form.html", project=project, branch=branch,
                           ultimate=ultimate, is_new=is_new)


@ultimates_bp.route("/ultimates/<int:ultimate_id>/delete", methods=["POST"])
@login_required
def delete_ultimate(ultimate_id: int):
    ultimate = _ultimate(ultimate_id)
    project = ultimate.branch.project
    db.session.delete(ultimate)
    db.session.commit()
    flash(tx("ultimate.deleted"), "info")
    return redirect(url_for("projects.tree", project_id=project.id))


@ultimates_bp.route("/ultimates/<int:ultimate_id>/achieve", methods=["POST"])
@login_required
def achieve_ultimate(ultimate_id: int):
    """Claim an ultimate, or take the claim back. Body: JSON
    ``{"achieved": true|false}``, true when absent.

    Claiming needs the ultimate open, which the tree already shows; taking
    it back is always allowed, the way points can always come off. Answers
    with the re-rendered tree fragment, like the points endpoint.
    """
    ultimate = _ultimate(ultimate_id)
    project = ultimate.branch.project
    payload = request.get_json(silent=True) or {}
    want = bool(payload.get("achieved", True))
    if want and not ultimate.achieved and not ultimate.open:
        return jsonify({"error": "closed", "message": tx("ultimate.closed")}), 409
    was = ultimate.achieved
    ultimate.set_achieved(want)
    if ultimate.achieved != was:
        project.record("ultimate", delta=1 if ultimate.achieved else -1, note=ultimate.title)
    db.session.commit()
    return jsonify({"html": render_template("_tree.html", project=project)})
