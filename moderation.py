"""Moderation: every account on one page, for moderators only.

  /moderation    each account's name, email, when it was created, when it
                 last signed in, and whether its email is confirmed. Filter
                 by confirmation, search by name or email, sort by column.

Anyone who is not a moderator gets the same 404 as any page that is not
theirs, so the page does not admit to existing. Who is a moderator is the
``users.is_moderator`` column, set from the command line and never from the
app, so no form can make someone one:

    flask --app app set-moderator someone@example.com
    flask --app app set-moderator someone@example.com --off
"""
from __future__ import annotations

from functools import wraps

import click
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from extensions import db
from models import User

moderation_bp = Blueprint("moderation", __name__, cli_group=None)

PER_PAGE = 100

# ?sort= value -> column. Accounts with no value (no sign-in recorded yet)
# go last whichever way the column is sorted.
SORTS = {
    "created": User.created_at,
    "login": User.last_login_at,
    "email": User.email,
}
STATUSES = ("all", "verified", "unverified")


def moderator_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_moderator:
            abort(404)
        return view(*args, **kwargs)
    return wrapped


@moderation_bp.route("/moderation")
@moderator_required
def index():
    sort = request.args.get("sort") if request.args.get("sort") in SORTS else "created"
    # Text sorts A to Z first; dates newest first.
    default_dir = "asc" if sort == "email" else "desc"
    direction = request.args.get("dir") if request.args.get("dir") in ("asc", "desc") else default_dir
    status = request.args.get("status") if request.args.get("status") in STATUSES else "all"
    q = (request.args.get("q") or "").strip()[:100]

    query = db.select(User)
    if status == "verified":
        query = query.where(User.email_verified_at.isnot(None))
    elif status == "unverified":
        query = query.where(User.email_verified_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(User.email).like(like),
                                func.lower(User.display_name).like(like)))
    column = SORTS[sort]
    ordered = column.asc() if direction == "asc" else column.desc()
    query = query.order_by(column.is_(None), ordered, User.id.desc())
    page = db.paginate(query, page=request.args.get("page", 1, type=int),
                       per_page=PER_PAGE, error_out=False)

    total = db.session.scalar(db.select(func.count(User.id)))
    verified = db.session.scalar(
        db.select(func.count(User.id)).where(User.email_verified_at.isnot(None)))
    return render_template(
        "moderation.html", page=page, sort=sort, direction=direction, status=status, q=q,
        totals={"all": total, "verified": verified, "unverified": total - verified})


@moderation_bp.cli.command("set-moderator")
@click.argument("email")
@click.option("--off", is_flag=True, help="Take moderation away instead.")
def set_moderator(email: str, off: bool):
    """Make the account with this email a moderator, or stop it being one."""
    user = User.query.filter_by(email=email.strip().lower()).first()
    if user is None:
        raise click.ClickException(f"no account with the email {email}")
    user.is_moderator = not off
    db.session.commit()
    click.echo(f"{user.email} is {'no longer' if off else 'now'} a moderator")
    others = User.query.filter(User.is_moderator.is_(True), User.id != user.id).all()
    if others:
        click.echo("other moderators: " + ", ".join(u.email for u in others))
