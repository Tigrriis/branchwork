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
    """Return a SQLAlchemy URL, normalising Render's Postgres scheme.

    The driver is named outright: a bare ``postgresql://`` means psycopg2 to
    SQLAlchemy 2.0 but psycopg 3 to 2.1, and psycopg2 is what is installed.
    """
    url = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "branchwork.db"))
    for bare in ("postgres://", "postgresql://"):
        if url.startswith(bare):
            url = "postgresql+psycopg2://" + url[len(bare):]
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

    # Analytics (Plausible: cookieless, so no consent banner). Off unless
    # PLAUSIBLE_SCRIPT is set to the script URL from the site's Plausible
    # settings. PLAUSIBLE_DOMAIN is only for the older script.js snippet,
    # which reads the site from a data-domain attribute.
    PLAUSIBLE_SCRIPT = os.environ.get("PLAUSIBLE_SCRIPT", "")
    PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN", "")

    # Limits on sign-in and sign-up attempts (ratelimit.py).
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "1") == "1"

    # Email goes out through Resend (mailer.py). With no RESEND_API_KEY
    # nothing is sent: the message, link included, goes to the log instead,
    # which is what a local run wants. MAIL_FROM must be on a domain verified
    # in Resend. Replies go to the contact address in the copy file.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "Villainy <noreply@villainy.win>")

    # Where links in emails point, e.g. https://villainy.win. Unset, they use
    # the address the request came in on. Setting it means a forged Host
    # header can never put someone else's site into a confirmation email.
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")

    # How long an email confirmation link works, in seconds.
    VERIFY_LINK_MAX_AGE = 3 * 24 * 60 * 60

    # Default number of points a tier must hold before the next tier opens.
    # Each project can override it.
    DEFAULT_GATE_POINTS = 3

    # The cap on the Building status a new account starts with, which forces a
    # finish-or-park decision before a fourth build. Each account then edits
    # its own statuses and caps in settings, so changing this moves no one
    # who has already signed up. MAX_WIP_BUILDING_LIMIT bounds any cap.
    DEFAULT_WIP_BUILDING_LIMIT = int(os.environ.get("WIP_BUILDING_LIMIT", "3"))
    MAX_WIP_BUILDING_LIMIT = 20
    MAX_OPEN_IDEAS = 200

    # The weekly review (Today's ?review=1 mode) is switched off. Set
    # WEEKLY_REVIEW=1 to bring it back; the code and copy are kept for that.
    WEEKLY_REVIEW = os.environ.get("WEEKLY_REVIEW", "0") == "1"

    MAX_PROJECTS_PER_USER = 50
    MAX_BRANCHES_PER_PROJECT = 12
    MAX_TASKS_PER_BRANCH = 200
    MAX_POINTS_PER_TASK = 20
    MAX_ROUTINES_PER_PROJECT = 12
    MAX_THREADS_PER_PROJECT = 60
    MAX_NOTES_PER_PROJECT = 500
    MAX_NOTE_CHARS = 200_000

