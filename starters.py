"""Starter templates: the branches a new project begins with.

Two sources, offered side by side on the new-project form:

* the built-ins below, which are code and the same for everyone;
* ``Template`` rows, which belong to one user and are edited in settings.

A built-in can be duplicated into an editable copy, which is the usual way
someone ends up with their own: start from Engineering job, rename a couple
of branches, keep it.
"""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import HUES, Branch, Project, Task, Template, TemplateBranch

starters_bp = Blueprint("starters", __name__)

STARTERS: dict[str, dict] = {
    # Names and descriptions live in the copy catalogue under [starter.<key>].
    "blank": {"branches": [], "chain": False},
    "lifecycle": {
        "branches": [("Idea", "violet"), ("Prototype", "blue"), ("Build", "green"),
                     ("Launch", "amber"), ("Maintain", "teal")],
        "chain": True,
    },
    "engineering": {
        "branches": [("Design", "green"), ("Approvals", "blue"), ("Construction", "red")],
        "chain": "last",
    },
    "software": {
        "branches": [("Spec", "violet"), ("Build", "green"), ("Ship", "amber"), ("Maintain", "teal")],
        "chain": "last",
    },
    # For a business that already runs and needs systemising rather than
    # building. Nothing is chained on purpose: an operating business cannot
    # put Finance on hold until Sales is "finished", and a locked column would
    # grey out work that is actually happening. The sequence lives in the
    # tiers instead, one ladder per area, so each area keeps its own tempo and
    # the board shows at a glance which one you have stopped touching.
    "business": {
        "branches": [("Sales & marketing", "amber"), ("Delivery", "green"),
                     ("Finance & admin", "blue"), ("People", "violet"),
                     ("Systems & tools", "teal")],
        "chain": False,
        # Worth 3 points each, which is the default gate: finish the map and
        # tier 2 opens by itself. Deliberately one task per area, not a
        # pre-filled backlog of guesses about someone else's business.
        "tasks": {
            "Sales & marketing": [("Map how work is won today", "chart", 3)],
            "Delivery": [("Map how a job runs start to finish", "truck", 3)],
            "Finance & admin": [("Map the money in and out", "cash", 3)],
            "People": [("Map who does what, and what only you can do", "users", 3)],
            "Systems & tools": [("List every tool in use and what it is for", "gear", 3)],
        },
    },
}
DEFAULT_STARTER = "lifecycle"
MAX_TEMPLATES = 30
MAX_TEMPLATE_BRANCHES = 12


# ── Applying one to a new project ───────────────────────────────────────────

def _make(project: Project, name: str, hue: str, position: int,
          previous: Branch | None, waits: bool,
          tasks: list[tuple[str, str, int]]) -> Branch:
    branch = Branch(project=project, name=name, hue=hue if hue in HUES else "green",
                    position=position)
    if waits and previous is not None:
        branch.requires = previous
    for index, (title, icon, points) in enumerate(tasks):
        Task(branch=branch, tier=1, position=index, title=title, icon=icon,
             points_max=points, points_done=0)
    return branch


def apply_starter(project: Project, key: str) -> list[Branch]:
    """Create the chosen starter's branches, and any seeded tasks, on ``project``.

    Nothing is added to the session here; the caller adds the returned
    branches and the ``save-update`` cascade carries the tasks with them.
    """
    if key.startswith("custom:"):
        return _apply_custom(project, key.split(":", 1)[1])

    spec = STARTERS.get(key) or STARTERS["blank"]
    seeded = spec.get("tasks") or {}
    made: list[Branch] = []
    last = len(spec["branches"]) - 1
    for pos, (name, hue) in enumerate(spec["branches"]):
        waits = spec["chain"] is True or (spec["chain"] == "last" and pos == last)
        made.append(_make(project, name, hue, pos, made[-1] if made else None, waits,
                          seeded.get(name, [])))
    return made


def _apply_custom(project: Project, raw_id: str) -> list[Branch]:
    if not raw_id.isdigit():
        return []
    template = db.session.get(Template, int(raw_id))
    # Someone else's template is simply not found, same as a missing one.
    if template is None or template.user_id != project.owner_id:
        return []
    made: list[Branch] = []
    for pos, spec in enumerate(template.branches):
        tasks = [(title, "check", points) for title, points in spec.tasks()]
        made.append(_make(project, spec.name, spec.hue, pos,
                          made[-1] if made else None, spec.waits, tasks))
    return made


def builtin_choices() -> list[dict]:
    """The built-ins with their words, which live in the copy catalogue."""
    return [{"key": key, "label": tx(f"starter.{key}.label"), "hint": tx(f"starter.{key}.hint")}
            for key in STARTERS]


def choices_for(user) -> list[dict]:
    """Everything offerable on the new-project form, built-ins first."""
    out = [dict(spec, custom=False) for spec in builtin_choices()]
    out += [{"key": t.key, "label": t.name, "hint": t.hint or t.summary, "custom": True}
            for t in sorted(user.templates, key=lambda t: t.name.lower())]
    return out


# ── Managing your own ───────────────────────────────────────────────────────

def _template(template_id: int) -> Template:
    template = db.session.get(Template, template_id)
    if template is None or template.user_id != current_user.id:
        abort(404)
    return template


def _unique_name(base: str) -> str:
    taken = {t.name for t in current_user.templates}
    if base not in taken:
        return base
    for n in range(2, 50):
        candidate = f"{base} {n}"
        if candidate not in taken:
            return candidate
    return base


@starters_bp.route("/settings/templates")
@login_required
def template_list():
    return render_template("templates_list.html",
                           templates=sorted(current_user.templates, key=lambda t: t.name.lower()),
                           builtins=builtin_choices(), limit=MAX_TEMPLATES)


@starters_bp.route("/settings/templates/new", methods=["POST"])
@login_required
def new_template():
    """Blank, or a copy of a built-in to edit. Copying is the usual route."""
    if len(current_user.templates) >= MAX_TEMPLATES:
        flash(tx("templates.limit"), "error")
        return redirect(url_for("starters.template_list"))

    source = request.form.get("copy") or ""
    spec = STARTERS.get(source)
    if spec is not None:
        template = Template(user=current_user, name=_unique_name(tx(f"starter.{source}.label")),
                            hint=tx(f"starter.{source}.hint"))
        seeded = spec.get("tasks") or {}
        last = len(spec["branches"]) - 1
        for pos, (name, hue) in enumerate(spec["branches"]):
            lines = "\n".join(f"{title} | {points}" for title, _icon, points in seeded.get(name, []))
            db.session.add(TemplateBranch(
                template=template, name=name, hue=hue, position=pos,
                waits=spec["chain"] is True or (spec["chain"] == "last" and pos == last),
                tasks_text=lines or None))
    else:
        template = Template(user=current_user, name=_unique_name(tx("templates.default_name")))
        db.session.add(TemplateBranch(template=template, name=tx("templates.first_scheme"), hue="green", position=0))
    db.session.add(template)
    db.session.commit()
    flash(tx("templates.created", name=template.name), "success")
    return redirect(url_for("starters.edit_template", template_id=template.id))


@starters_bp.route("/settings/templates/<int:template_id>", methods=["GET", "POST"])
@login_required
def edit_template(template_id: int):
    template = _template(template_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        if not name:
            flash(tx("templates.name_required"), "error")
            return render_template("template_form.html", template=template)
        template.name = name
        template.hint = (request.form.get("hint") or "").strip()[:300] or None

        # The form posts parallel arrays, one entry per row. A row with no
        # name is how a branch is deleted: blank it and save. The rows are
        # rewritten onto the existing records in order, so a snapshot is
        # taken first -- creating a branch appends to template.branches, and
        # slicing a collection that is growing under you loses rows.
        existing = list(template.branches)
        names = request.form.getlist("branch_name")
        hues = request.form.getlist("branch_hue")
        tasks = request.form.getlist("branch_tasks")
        kept: list[TemplateBranch] = []
        for index, raw_name in enumerate(names[:MAX_TEMPLATE_BRANCHES]):
            clean = raw_name.strip()[:80]
            if not clean:
                continue
            if len(kept) < len(existing):
                branch = existing[len(kept)]
            else:
                branch = TemplateBranch(template=template)
                db.session.add(branch)
            branch.name = clean
            branch.hue = hues[index] if index < len(hues) and hues[index] in HUES else "green"
            # Indexed rather than a parallel list: an unchecked box posts
            # nothing at all, so a list would silently shift every row after
            # the first unticked one.
            branch.waits = request.form.get(f"branch_waits_{index}") == "1"
            branch.tasks_text = (tasks[index].strip() if index < len(tasks) else "") or None
            branch.position = len(kept)
            kept.append(branch)
        for leftover in existing[len(kept):]:
            db.session.delete(leftover)
        db.session.commit()
        flash(tx("templates.saved"), "success")
        return redirect(url_for("starters.template_list"))
    return render_template("template_form.html", template=template)


@starters_bp.route("/settings/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def delete_template(template_id: int):
    template = _template(template_id)
    db.session.delete(template)
    db.session.commit()
    flash(tx("templates.deleted"), "info")
    return redirect(url_for("starters.template_list"))
