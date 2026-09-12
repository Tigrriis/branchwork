"""
Branchwork: plan large, multi-stranded projects as a skill tree.

  /                      Today: projects due for a touch, the inbox
  /board                 every project by phase (Idea → Maintaining, shelves)
  /review                the weekly review: keep / advance / park / drop
  /projects/<id>         the tree (branches as columns, tasks in tiers)
  /projects/<id>/list    the same tasks as a table
  /login, /register, /account

Module-level ``app`` rather than a factory, matching the other Arete Flask
services, so ``gunicorn app:app`` works unchanged. Tests build their own app
via ``create_app()``.
"""
import hashlib
import os
import threading

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from auth import auth_bp
from dashboard import dashboard_bp
from demo import demo_bp
from gitsync import gitsync_bp
from extensions import csrf, db, login_manager, migrate
from icons import ICONS, icon_svg
from models import CADENCES, HUES, PHASES
from projects import projects_bp


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config.Config)
    if overrides:
        app.config.update(overrides)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(demo_bp)
    app.register_blueprint(gitsync_bp)

    _register_asset_versioning(app)
    _register_template_helpers(app)
    _register_routes(app)
    _register_error_handlers(app)
    return app


# Content hash per static file, computed once per process.
_ASSET_VERSIONS: dict[str, str] = {}


def _asset_version(app: Flask, filename: str) -> str | None:
    if not app.debug and filename in _ASSET_VERSIONS:
        return _ASSET_VERSIONS[filename]
    try:
        with open(os.path.join(app.static_folder, filename), "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()[:8]
    except OSError:
        return None
    _ASSET_VERSIONS[filename] = digest
    return digest


def _register_asset_versioning(app: Flask) -> None:
    @app.url_defaults
    def _add_version(endpoint, values):
        if endpoint == "static" and "filename" in values:
            version = _asset_version(app, values["filename"])
            if version:
                values["v"] = version


def _register_template_helpers(app: Flask) -> None:
    @app.template_filter("to_date")
    def _to_date(ordinal: int) -> str:
        from datetime import date
        return date.fromordinal(int(ordinal)).isoformat()

    @app.context_processor
    def _inject():
        return {
            "SITE_NAME": config.SITE_NAME,
            "HUES": HUES,
            "PHASES": PHASES,
            "CADENCES": CADENCES,
            "ICON_NAMES": list(ICONS),
            "icon": icon_svg,
        }


def _register_routes(app: Flask) -> None:
    @app.route("/healthz")
    def healthz():
        return {"ok": True}


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def _not_found(_e):
        return render_template("error.html", code=404,
                               message="That page does not exist, or is not yours."), 404

    @app.errorhandler(CSRFError)
    def _csrf(e):
        if request.is_json:
            return {"error": "csrf", "message": e.description}, 400
        return render_template("error.html", code=400, message=e.description), 400

    @app.errorhandler(500)
    def _server_error(_e):
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500


app = create_app()

# Apply migrations once per process on first request, so a plain code deploy
# self-heals even if the start command was not updated (see bootstrap_db.py).
_migrated = threading.Event()


@app.before_request
def _ensure_schema():
    if _migrated.is_set() or app.config.get("TESTING"):
        return
    with _migration_lock:
        if not _migrated.is_set():
            from bootstrap_db import run_migrations
            run_migrations()
            _migrated.set()


_migration_lock = threading.Lock()
