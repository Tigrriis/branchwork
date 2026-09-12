"""Configuration.

Driven by environment variables so the same code runs locally (SQLite) and on
Render (Postgres). Nothing here is a secret; secrets arrive from the environment.
"""
import os

try:
    from dotenv import load_dotenv  # optional: load a local .env in dev
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _database_url() -> str:
    """Return a SQLAlchemy URL, normalising Render's Postgres scheme."""
    url = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "branchwork.db"))
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PREFERRED_URL_SCHEME = "https"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # Static URLs carry a content hash (see app._register_asset_versioning), so
    # a long cache lifetime is safe: a changed file is a different URL.
    SEND_FILE_MAX_AGE_DEFAULT = 31_536_000

    # Default number of points a tier must hold before the next tier opens.
    # Each project can override it.
    DEFAULT_GATE_POINTS = 3

    # Kanban-style work-in-progress cap on the Building phase. The point of
    # the cap is to force a finish-or-park decision before a fourth build.
    WIP_BUILDING_LIMIT = int(os.environ.get("WIP_BUILDING_LIMIT", "3"))
    MAX_INBOX_ITEMS = 200

    MAX_PROJECTS_PER_USER = 50
    MAX_BRANCHES_PER_PROJECT = 12
    MAX_TASKS_PER_BRANCH = 200
    MAX_POINTS_PER_TASK = 20


SITE_NAME = os.environ.get("SITE_NAME", "Branchwork")
