"""Authentication: register, login, logout, account settings.

Sessions are Flask-Login's; passwords are hashed by Werkzeug. There is no
password-reset flow yet because the app sends no email; see README.
"""
from urllib.parse import urlparse

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LEN = 8


def _int(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(n, hi))


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
            flash("Enter a valid email address.", "error")
        elif len(password) < MIN_PASSWORD_LEN:
            flash(f"Password must be at least {MIN_PASSWORD_LEN} characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered. Sign in instead.", "error")
        else:
            user = User(email=email, display_name=display_name or None,
                        wip_building_limit=current_app.config["DEFAULT_WIP_BUILDING_LIMIT"])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome. Start by creating a project.", "success")
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
        flash("Invalid email or password.", "error")
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
        current_user.wip_building_limit = _int(
            request.form.get("wip_building_limit"), current_user.wip_building_limit,
            0, current_app.config["MAX_WIP_BUILDING_LIMIT"])

        current_pw = request.form.get("current_password") or ""
        new_pw = request.form.get("new_password") or ""
        if new_pw:
            if not current_user.check_password(current_pw):
                flash("Current password is wrong.", "error")
                return render_template("account.html")
            if len(new_pw) < MIN_PASSWORD_LEN:
                flash(f"New password must be at least {MIN_PASSWORD_LEN} characters.", "error")
                return render_template("account.html")
            current_user.set_password(new_pw)
        db.session.commit()
        flash("Account updated.", "success")
        return redirect(url_for("auth.account"))
    return render_template("account.html")
