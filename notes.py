"""Notes: an Obsidian-style notebook for each plot.

The folders are the plot's own shape: the plot is the root, each scheme is a
folder in it, and each machination a folder inside its scheme. A note can sit
at any of the three levels. The page is a file explorer down the left and the
open note on the right, written in markdown and read rendered.

Unlike the tree, the page does its rendering in the browser, because the
server cannot: a note's title and body are sealed in the browser with the
owner's notes key before they are sent, and stored and returned that way
(see ``vault.py``). Markdown is turned into HTML by
``static/branchwork/notes.js``, which also decrypts, sorts and searches the
titles in the explorer. Until an account has chosen a master password the
page asks for one and saves nothing.

  GET  /plots/<id>/notes              the explorer, no note open
  GET  /plots/<id>/notes/<note>       a note open
  GET  /plots/<id>/notes/new          a draft, saved on the first keystroke;
                                      ?scheme= / ?machination= say where.
                                      A title to start with rides in the
                                      #fragment, which never reaches here.
  POST /plots/<id>/notes              create (JSON)
  POST /notes/<note>                  save a title, body or folder (JSON)
  POST /notes/<note>/delete           delete (form)

Every route is owner-only, the way the tree's are.
"""
from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import Branch, Note, Project, Task
from vault import is_sealed, sealed_body, sealed_title

notes_bp = Blueprint("notes", __name__)


# ── Lookups ─────────────────────────────────────────────────────────────────

def _project(project_id: int) -> Project:
    project = db.session.get(Project, project_id)
    if project is None or project.owner_id != current_user.id:
        abort(404)
    return project


def _note(note_id: int) -> Note:
    note = db.session.get(Note, note_id)
    if note is None or note.project.owner_id != current_user.id:
        abort(404)
    return note


_NOWHERE = object()


def _place(project: Project, folder) -> Branch | Task | None:
    """A folder name from the page (``plot``, ``scheme:<id>``,
    ``machination:<id>``) as the scheme or machination it means, None for
    the root, or ``_NOWHERE`` if it is not a folder of this plot."""
    kind, _, raw = str(folder or "plot").partition(":")
    if kind == "plot" and not raw:
        return None
    if not raw.isdigit():
        return _NOWHERE
    if kind == "scheme":
        branch = db.session.get(Branch, int(raw))
        return branch if branch is not None and branch.project_id == project.id else _NOWHERE
    if kind == "machination":
        task = db.session.get(Task, int(raw))
        return task if task is not None and task.branch.project_id == project.id else _NOWHERE
    return _NOWHERE


def _folder_of(place: Branch | Task | None) -> str:
    if isinstance(place, Task):
        return f"machination:{place.id}"
    if isinstance(place, Branch):
        return f"scheme:{place.id}"
    return "plot"


def _filed(project: Project) -> dict[str, list[Note]]:
    """Every note of the plot by folder, each folder's notes by title."""
    by_folder: dict[str, list[Note]] = {}
    for note in project.notes:
        by_folder.setdefault(note.folder, []).append(note)
    for notes in by_folder.values():
        notes.sort(key=lambda n: (n.title.casefold(), n.id))
    return by_folder


def _shelves(project: Project, folder: str) -> dict:
    """The explorer's contents: the root's own notes, then a folder per
    scheme holding a folder per machination. ``count`` takes in every note
    below a folder, and the folders on the way to ``folder`` start open."""
    filed = _filed(project)
    schemes = []
    for branch in project.branches:
        key = f"scheme:{branch.id}"
        machinations = [{"task": task, "key": f"machination:{task.id}",
                         "notes": filed.get(f"machination:{task.id}", []),
                         "open": folder == f"machination:{task.id}"}
                        for task in branch.tasks]
        notes = filed.get(key, [])
        schemes.append({
            "branch": branch, "key": key, "notes": notes, "machinations": machinations,
            "count": len(notes) + sum(len(m["notes"]) for m in machinations),
            "open": folder == key or any(m["open"] for m in machinations),
        })
    return {"notes": filed.get("plot", []), "schemes": schemes, "count": len(project.notes)}


def _explorer(project: Project, note: Note | None, folder: str) -> str:
    return render_template("_notes_explorer.html", project=project, note=note,
                           shelves=_shelves(project, folder))


def _page(project: Project, note: Note | None = None, *, draft: dict | None = None):
    folder = note.folder if note is not None else (draft or {}).get("folder", "plot")
    return render_template("notes.html", project=project, note=note, draft=draft,
                           folder=folder, shelves=_shelves(project, folder))


def _refuse(key: str, status: int):
    return jsonify({"error": key.rsplit(".", 1)[-1], "message": tx(key)}), status


# ── Pages ───────────────────────────────────────────────────────────────────

@notes_bp.route("/plots/<int:project_id>/notes")
@login_required
def index(project_id: int):
    return _page(_project(project_id))


@notes_bp.route("/plots/<int:project_id>/notes/<int:note_id>")
@login_required
def show(project_id: int, note_id: int):
    project = _project(project_id)
    note = _note(note_id)
    if note.project_id != project.id:
        abort(404)
    return _page(project, note)


@notes_bp.route("/plots/<int:project_id>/notes/new")
@login_required
def new_note(project_id: int):
    """A blank note in the folder asked for, not yet saved. Nothing is
    written until there is something to write, so following a pencil and
    changing your mind leaves no "Untitled" behind."""
    project = _project(project_id)
    if request.args.get("machination"):
        place = _place(project, f"machination:{request.args['machination']}")
    elif request.args.get("scheme"):
        place = _place(project, f"scheme:{request.args['scheme']}")
    else:
        place = None
    if place is _NOWHERE:
        abort(404)
    return _page(project, draft={"folder": _folder_of(place)})


# ── Saving ──────────────────────────────────────────────────────────────────

@notes_bp.route("/plots/<int:project_id>/notes", methods=["POST"])
@login_required
def create(project_id: int):
    """Body: JSON ``{"title", "body", "folder"}``. Answers with where the note
    now lives and the explorer re-rendered with it in."""
    project = _project(project_id)
    payload = request.get_json(silent=True) or {}
    if not current_user.has_vault:
        return _refuse("vault.missing", 409)
    if len(project.notes) >= current_app.config["MAX_NOTES_PER_PROJECT"]:
        return _refuse("notes.limit", 409)
    refused = _unsealed(payload, ("title", "body"))
    if refused:
        return refused
    place = _place(project, payload.get("folder"))
    if place is _NOWHERE:
        return _refuse("notes.not_in_plot", 404)
    note = Note(project=project, title=payload["title"], body=payload["body"])
    note.file_under(place)
    db.session.add(note)
    db.session.flush()
    # Nothing of the note in the log: the server has nothing of it to put there.
    project.record("note")
    db.session.commit()
    return jsonify(_answer(note, explorer=True))


@notes_bp.route("/notes/<int:note_id>", methods=["POST"])
@login_required
def save(note_id: int):
    """Body: JSON with any of ``title``, ``body`` and ``folder``. The explorer
    comes back only when the note moved, since a title the page can relabel
    in place and a body changes nothing in it."""
    note = _note(note_id)
    payload = request.get_json(silent=True) or {}
    if not current_user.has_vault:
        return _refuse("vault.missing", 409)
    refused = _unsealed(payload, [k for k in ("title", "body") if k in payload])
    if refused:
        return refused
    if "body" in payload:
        note.body = payload["body"]
    if "title" in payload:
        note.title = payload["title"]
    moved = False
    if "folder" in payload:
        place = _place(note.project, payload.get("folder"))
        if place is _NOWHERE:
            return _refuse("notes.not_in_plot", 404)
        moved = _folder_of(place) != note.folder
        note.file_under(place)
    note.touch()
    db.session.commit()
    return jsonify(_answer(note, explorer=moved))


def _unsealed(payload: dict, fields) -> tuple | None:
    """A refusal if any of ``fields`` is missing, unsealed or too long. The
    browser holds the real limits; these only bound what is stored."""
    for field in fields:
        value = payload.get(field)
        if not is_sealed(value):
            return _refuse("vault.not_sealed", 400)
        if not (sealed_title if field == "title" else sealed_body)(value):
            return _refuse("notes.too_long", 413)
    return None


def _answer(note: Note, *, explorer: bool) -> dict:
    out = {
        "id": note.id,
        "folder": note.folder,
        "url": url_for("notes.show", project_id=note.project_id, note_id=note.id),
        "save_url": url_for("notes.save", note_id=note.id),
        "delete_url": url_for("notes.delete", note_id=note.id),
    }
    if explorer:
        # Rendered as the page would be after a reload with this note open,
        # which is what the page has just become.
        out["explorer"] = _explorer(note.project, note, note.folder)
    return out


@notes_bp.route("/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete(note_id: int):
    note = _note(note_id)
    project_id = note.project_id
    db.session.delete(note)
    db.session.commit()
    flash(tx("notes.deleted"), "info")
    return redirect(url_for("notes.index", project_id=project_id))
