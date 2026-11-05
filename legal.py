"""The privacy policy and terms of use, open to everyone signed in or not.

The words are in the copy file under [privacy] and [terms]; the contact
address under [legal] is the one inbox both pages point people to.
"""
from flask import Blueprint, render_template
from markupsafe import Markup, escape

from copytext import tx

legal_bp = Blueprint("legal", __name__)


def _contact_link() -> Markup:
    email = escape(tx("legal.contact_email"))
    return Markup(f'<a href="mailto:{email}">{email}</a>')


@legal_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", contact=_contact_link())


@legal_bp.route("/terms")
def terms():
    return render_template("terms.html", contact=_contact_link())
