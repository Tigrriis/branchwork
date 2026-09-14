"""Authentication: register, login, logout, account settings.

Sessions are Flask-Login's; passwords are hashed by Werkzeug. There is no
password-reset flow yet because the app sends no email; see README.
"""
from urllib.parse import urlparse

from flask import (
    Blueprint, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from copytext import tx
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LEN = 8


def _safe_next(target: str | None) -> bool:
    """Only allow same-site relative redirects (guards against open redirect)."""
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and target.startswith("/") and not target.startswith("//")


def _after_login():
    nxt = request.args.get("next")
    return redirect(nxt if _safe_next(nxt) else url_for("dashboard.today"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.today"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        display_name = (request.form.get("display_name") or "").strip()[:80]
        if not email or "@" not in email:
            flash(tx("auth.invalid_email"), "error")
        elif len(password) < MIN_PASSWORD_LEN:
            flash(tx("auth.password_short", min=MIN_PASSWORD_LEN), "error")
        elif User.query.filter_by(email=email).first():
            flash(tx("auth.email_taken"), "error")
        else:
            user = User(email=email, display_name=display_name or None)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(tx("auth.welcome"), "success")
            return _after_login()
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.today"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            return _after_login()
        flash(tx("auth.bad_login"), "error")
    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()[:80]
        current_user.display_name = display_name or None

        current_pw = request.form.get("current_password") or ""
        new_pw = request.form.get("new_password") or ""
        if new_pw:
            if not current_user.check_password(current_pw):
                flash(tx("auth.wrong_password"), "error")
                return render_template("account.html")
            if len(new_pw) < MIN_PASSWORD_LEN:
                flash(tx("auth.new_password_short", min=MIN_PASSWORD_LEN), "error")
                return render_template("account.html")
            current_user.set_password(new_pw)
        db.session.commit()
        flash(tx("auth.account_updated"), "success")
        return redirect(url_for("auth.account"))
    return render_template("account.html")
