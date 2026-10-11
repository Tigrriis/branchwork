"""The notes vault: notes encrypted in the browser under a master password.

The server never sees a master password, a key, or a note's words. What it
keeps, per account, is what a browser needs to unlock the notes again:

* ``vault_salt`` and ``vault_rounds``: the browser stretches the master
  password with PBKDF2-SHA256 using these into a key-encrypting key.
* ``vault_key``: a random AES-256 notes key, sealed with that key.

Every note's title and body is sealed with the notes key (AES-256-GCM, a
fresh nonce each time) before it leaves the browser, and arrives back the
same way; ``static/branchwork/vault.js`` does all of it. Changing the master
password re-seals only the notes key, so no note has to be touched.

A wrong master password is found out in the browser, when the notes key
fails to unseal, so there is nothing here to check it against and nothing
to guess it from. The cost is that a forgotten master password cannot be
recovered: ``reset`` deletes the notes so the account can start again.

Sealed values travel as ``v1.<nonce>.<ciphertext>`` in unpadded base64url.
The server cannot tell a good one from a forged one, but it does refuse
anything not in that shape, so a note is never stored in the clear by
mistake.

Notes written before the vault existed are plain text until their owner
first opens Notes and chooses a master password: ``plain`` hands them to the
browser once, and ``setup`` swaps them for their sealed versions in the same
transaction that stores the key.

Text can also arrive in the clear afterwards, from where the server writes
it: a machination's ``notes`` column holds what the machination form's old
notes box held and the rest of an idea filed onto the tree. ``pending``
hands that to an unlocked browser, which seals each into a note in the
machination's folder and sends it back, and the column is emptied.
"""
import hashlib
import re
from datetime import datetime, timezone

from flask import (
    Blueprint, current_app, flash, jsonify, redirect, request, url_for,
)
from flask_login import current_user, login_required

from copytext import tx
from extensions import db
from models import Branch, Note, Project, Task

vault_bp = Blueprint("vault", __name__)

SEALED = re.compile(r"^v1\.[A-Za-z0-9_-]{16}\.[A-Za-z0-9_-]{22,}$")
SALT = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
MIN_ROUNDS, MAX_ROUNDS = 100_000, 10_000_000

# Sealed text is longer than what it seals: up to four bytes a character in
# UTF-8, a third more again in base64, and a nonce and tag besides.
SEALED_GROWTH = 6
MAX_TITLE_CHARS = 200


def is_sealed(value) -> bool:
    return isinstance(value, str) and SEALED.match(value) is not None


def sealed_title(value) -> bool:
    return is_sealed(value) and len(value) <= MAX_TITLE_CHARS * SEALED_GROWTH + 64


def sealed_body(value) -> bool:
    return is_sealed(value) and len(value) <= current_app.config["MAX_NOTE_CHARS"] * SEALED_GROWTH + 64


def _refuse(key: str, status: int):
    return jsonify({"error": key.rsplit(".", 1)[-1], "message": tx(key)}), status


def _read_key(payload: dict) -> tuple[str, int, str] | None:
    salt, key = payload.get("salt"), payload.get("key")
    try:
        rounds = int(payload.get("rounds"))
    except (TypeError, ValueError):
        return None
    if not (isinstance(salt, str) and SALT.match(salt)) or not is_sealed(key) or len(key) > 200:
        return None
    if not MIN_ROUNDS <= rounds <= MAX_ROUNDS:
        return None
    return salt, rounds, key


def _owned_notes() -> list[Note]:
    return Note.query.join(Project).filter(Project.owner_id == current_user.id).all()


@vault_bp.route("/notes/vault/plain")
@login_required
def plain():
    """The account's notes as they were stored before there was a vault,
    for the browser to seal. Gone for good once the vault exists."""
    if current_user.has_vault:
        return _refuse("vault.exists", 409)
    return jsonify({"notes": [{"id": n.id, "title": n.title, "body": n.body}
                              for n in _owned_notes()]})


@vault_bp.route("/notes/vault", methods=["POST"])
@login_required
def setup():
    """Body: JSON ``{"salt", "rounds", "key", "notes": [{"id", "title",
    "body"}]}``, ``notes`` sealing every note the account has. All of it
    lands in one transaction, or none of it does."""
    if current_user.has_vault:
        return _refuse("vault.exists", 409)
    payload = request.get_json(silent=True) or {}
    parts = _read_key(payload)
    if parts is None:
        return _refuse("vault.bad_key", 400)
    sealed = payload.get("notes") or []
    if not isinstance(sealed, list):
        return _refuse("vault.bad_key", 400)
    by_id = {}
    for item in sealed:
        if not isinstance(item, dict) or not sealed_title(item.get("title")) \
                or not sealed_body(item.get("body")):
            return _refuse("vault.not_sealed", 400)
        by_id[item.get("id")] = item
    notes = _owned_notes()
    # A note written in another tab meanwhile would be left in the clear.
    if set(by_id) != {n.id for n in notes} or len(by_id) != len(sealed):
        return _refuse("vault.notes_changed", 409)
    for note in notes:
        note.title, note.body = by_id[note.id]["title"], by_id[note.id]["body"]
    current_user.vault_salt, current_user.vault_rounds, current_user.vault_key = parts
    current_user.vault_set_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"ok": True, "sealed": len(notes)})


@vault_bp.route("/notes/vault/key", methods=["POST"])
@login_required
def rekey():
    """A new master password: the same notes key, sealed under the new one.
    Body: JSON ``{"salt", "rounds", "key", "was"}``, ``was`` being the
    sealed key the browser unsealed to do it, so two tabs changing it at
    once cannot leave one of them holding a key that no longer exists."""
    if not current_user.has_vault:
        return _refuse("vault.missing", 409)
    payload = request.get_json(silent=True) or {}
    parts = _read_key(payload)
    if parts is None:
        return _refuse("vault.bad_key", 400)
    if payload.get("was") != current_user.vault_key:
        return _refuse("vault.key_changed", 409)
    current_user.vault_salt, current_user.vault_rounds, current_user.vault_key = parts
    current_user.vault_set_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"ok": True})


@vault_bp.route("/notes/vault/reset", methods=["POST"])
@login_required
def reset():
    """For a forgotten master password: delete every note and the vault, so
    Notes can be started again. Guarded by the sign-in password, since it
    cannot be undone."""
    if not current_user.check_password(request.form.get("password") or ""):
        flash(tx("auth.wrong_password"), "error")
        return redirect(url_for("auth.account"))
    for note in _owned_notes():
        db.session.delete(note)
    current_user.vault_salt = current_user.vault_rounds = current_user.vault_key = None
    current_user.vault_set_at = None
    db.session.commit()
    flash(tx("vault.reset_done"), "info")
    return redirect(url_for("auth.account"))


def _pending_tasks() -> list[Task]:
    return (Task.query.join(Branch).join(Project)
            .filter(Project.owner_id == current_user.id, Task.notes.isnot(None), Task.notes != "")
            .order_by(Task.id).all())


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@vault_bp.route("/notes/vault/pending")
@login_required
def pending():
    """Text in the clear waiting to become notes, for an unlocked browser to
    seal. ``title`` is the machination's, which the note takes."""
    if not current_user.has_vault:
        return _refuse("vault.missing", 409)
    return jsonify({"pending": [{"task_id": t.id, "title": t.title, "text": t.notes}
                                for t in _pending_tasks()]})


@vault_bp.route("/notes/vault/pending", methods=["POST"])
@login_required
def absorb():
    """Body: JSON ``{"notes": [{"task_id", "title", "body", "digest"}]}``,
    each sealing one machination's waiting text, ``digest`` being the
    SHA-256 of the text that was sealed. A machination whose text changed
    in the meantime is left for next time, so nothing is cleared unsealed."""
    if not current_user.has_vault:
        return _refuse("vault.missing", 409)
    waiting = {t.id: t for t in _pending_tasks()}
    created = 0
    for item in (request.get_json(silent=True) or {}).get("notes") or []:
        if not isinstance(item, dict):
            continue
        task = waiting.get(item.get("task_id"))
        if task is None or item.get("digest") != _digest(task.notes):
            continue
        if not sealed_title(item.get("title")) or not sealed_body(item.get("body")):
            return _refuse("vault.not_sealed", 400)
        note = Note(project=task.branch.project, title=item["title"], body=item["body"])
        db.session.add(note)
        note.file_under(task)
        task.notes = None
        created += 1
    db.session.commit()
    return jsonify({"created": created})
