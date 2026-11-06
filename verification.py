"""Email confirmation: the signed link a new account is sent, and reading it.

A link carries the account's id and a fingerprint of its email address,
signed with SECRET_KEY (itsdangerous) and good for VERIFY_LINK_MAX_AGE.
Nothing is stored for it, so there is no table of tokens to clean up. Because
the address is inside the signature, a link only confirms the address it was
sent to; it is a fingerprint rather than the address itself so the address
never shows in a URL or a server log. Following a link a second time does no
harm: the account just stays confirmed.

The routes that use this live in auth.py: /verify/<token> to follow a link,
and /verify/send to ask for another.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from flask import current_app, render_template, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

import mailer
from copytext import tx
from extensions import db
from models import User

_SALT = "verify-email"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _fingerprint(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()[:16]


def make_token(user: User) -> str:
    return _serializer().dumps({"u": user.id, "e": _fingerprint(user.email)})


def read_token(token: str) -> User | None:
    """The account a link is for, or None if it is forged, expired or stale."""
    try:
        data = _serializer().loads(token, max_age=current_app.config["VERIFY_LINK_MAX_AGE"])
    except BadSignature:  # SignatureExpired is one of these
        return None
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get("u")) if isinstance(data.get("u"), int) else None
    if user is None or not hmac.compare_digest(_fingerprint(user.email), str(data.get("e"))):
        return None
    return user


def link_for(user: User) -> str:
    token = make_token(user)
    base = current_app.config.get("PUBLIC_URL")
    if base:
        return base + url_for("auth.verify_email", token=token)
    return url_for("auth.verify_email", token=token, _external=True)


def send_link(user: User) -> bool:
    """Email the account a confirmation link. True once it is on its way.

    Records when it went, which the banner and the moderation page show.
    The caller commits.
    """
    link = link_for(user)
    site = tx("brand.name")
    days = max(1, current_app.config["VERIFY_LINK_MAX_AGE"] // 86400)
    subject = tx("email.verify_subject", site=site)
    text = "\n\n".join([
        tx("email.verify_greeting", name=user.public_name),
        tx("email.verify_body", site=site),
        link,
        tx("email.verify_expiry", days=days),
        tx("email.verify_ignore"),
    ]) + "\n"
    html = render_template("email_verify.html", user=user, link=link, site=site, days=days)
    sent = mailer.send(user.email, subject, text, html)
    if sent:
        user.verification_sent_at = datetime.now(timezone.utc)
    return sent


def confirm(user: User) -> bool:
    """Mark the account's address confirmed. False if it already was."""
    if user.is_verified:
        return False
    user.email_verified_at = datetime.now(timezone.utc)
    return True
