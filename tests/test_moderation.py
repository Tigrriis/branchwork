"""The moderation page, who may open it, the command that makes a moderator,
and the migration that made Roobs the first one."""
import os
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade

import moderation
from app import create_app
from conftest import copy_in, login, make_user
from extensions import db
from models import User

MIGRATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "migrations")


def _at(day, hour=12):
    return datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc)


@pytest.fixture
def mod(client):
    """A signed-in moderator, and a few other accounts in different states.
    Signing in stamps the moderator's last sign-in as now."""
    roobs = make_user("roobs@example.com")
    roobs.display_name = "Roobs"
    roobs.is_moderator = True
    roobs.created_at = _at(1)
    roobs.email_verified_at = _at(1, 13)
    waiting = make_user("waiting@example.com")
    waiting.created_at, waiting.verification_sent_at, waiting.last_login_at = _at(5), _at(5), _at(5)
    old = make_user("old@example.com")
    old.created_at = _at(2)
    db.session.commit()
    login(client, email="roobs@example.com")
    return roobs


def _rows(html: str) -> list[str]:
    """The emails in the table, top to bottom."""
    body = html.split("<tbody>", 1)[1]
    return [chunk.split("</span>", 1)[0] for chunk in body.split('mod-account__email">')[1:]]


# --- who can see it ---------------------------------------------------------

def test_signed_out_is_sent_to_sign_in(client):
    r = client.get("/moderation")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_anyone_but_a_moderator_gets_a_404(client):
    make_user()
    login(client)
    assert client.get("/moderation").status_code == 404
    assert not copy_in(client.get("/account").data, "account.moderation_heading")
    assert "/moderation" not in client.get("/account").data.decode()


def test_a_moderator_is_shown_the_way_in(client, mod):
    page = client.get("/account").data.decode()
    assert copy_in(page, "account.moderation_heading") and 'href="/moderation"' in page


# --- what it shows ----------------------------------------------------------

def test_every_account_with_its_dates_and_confirmation(client, mod):
    r = client.get("/moderation")
    assert r.status_code == 200
    html = r.data.decode()
    # Newest first by default.
    assert _rows(html) == ["waiting@example.com", "old@example.com", "roobs@example.com"]
    assert copy_in(html, "moderation.moderator_tag") and "Roobs" in html
    # Created and last sign-in, as UTC for the browser to put in local time.
    assert '<time datetime="2026-10-01T12:00:00Z" data-local-time>' in html
    assert '<time datetime="2026-10-05T12:00:00Z" data-local-time>' in html
    # One of each confirmation state, and the account with no sign-in on record.
    assert copy_in(html, "moderation.status_verified")
    assert copy_in(html, "moderation.status_pending")
    assert copy_in(html, "moderation.status_unsent") and copy_in(html, "moderation.no_link_sent")
    assert copy_in(html, "moderation.not_recorded")
    assert copy_in(html, "moderation.no_name")


def test_filter_by_confirmation(client, mod):
    html = client.get("/moderation?status=verified").data.decode()
    assert _rows(html) == ["roobs@example.com"]
    html = client.get("/moderation?status=unverified").data.decode()
    assert _rows(html) == ["waiting@example.com", "old@example.com"]
    # An unknown filter shows everyone rather than nobody.
    assert len(_rows(client.get("/moderation?status=nonsense").data.decode())) == 3


def test_search_by_email_or_name(client, mod):
    assert _rows(client.get("/moderation?q=WAIT").data.decode()) == ["waiting@example.com"]
    assert _rows(client.get("/moderation?q=roobs").data.decode()) == ["roobs@example.com"]
    html = client.get("/moderation?q=nobody-here").data.decode()
    assert _rows(html) == [] and copy_in(html, "moderation.none")


def test_sort_by_column(client, mod):
    by_login = _rows(client.get("/moderation?sort=login").data.decode())
    # Most recent sign-in first; never recorded goes last.
    assert by_login == ["roobs@example.com", "waiting@example.com", "old@example.com"]
    by_login_up = _rows(client.get("/moderation?sort=login&dir=asc").data.decode())
    assert by_login_up == ["waiting@example.com", "roobs@example.com", "old@example.com"]
    by_email = _rows(client.get("/moderation?sort=email").data.decode())
    assert by_email == ["old@example.com", "roobs@example.com", "waiting@example.com"]
    # Something that is not a column is ignored, not an error.
    assert client.get("/moderation?sort=password_hash").status_code == 200


def test_pages(client, mod, monkeypatch):
    monkeypatch.setattr(moderation, "PER_PAGE", 2)
    first = client.get("/moderation").data.decode()
    assert len(_rows(first)) == 2 and copy_in(first, "moderation.page_of", n=1, total=2)
    second = client.get("/moderation?page=2").data.decode()
    assert _rows(second) == ["roobs@example.com"]


# --- making a moderator -----------------------------------------------------

def test_set_moderator_command(app):
    make_user("someone@example.com")
    runner = app.test_cli_runner()
    result = runner.invoke(args=["set-moderator", "Someone@Example.com"])
    assert result.exit_code == 0, result.output
    assert User.query.filter_by(email="someone@example.com").one().is_moderator
    result = runner.invoke(args=["set-moderator", "someone@example.com", "--off"])
    assert result.exit_code == 0
    assert not User.query.filter_by(email="someone@example.com").one().is_moderator
    result = runner.invoke(args=["set-moderator", "nobody@example.com"])
    assert result.exit_code != 0 and "no account" in result.output


def test_nothing_in_the_app_can_make_a_moderator(client):
    """The account form ignores a field it does not expect."""
    make_user()
    login(client)
    client.post("/account", data={"display_name": "Roobs", "is_moderator": "1"})
    user = User.query.one()
    assert user.display_name == "Roobs" and not user.is_moderator
    assert client.get("/moderation").status_code == 404


# --- the migration that picked the first moderator --------------------------

def _migrate_with(tmp_path, accounts):
    """Build the schema as it was before this change, add accounts, then run
    the migration. Returns {email: is_moderator}."""
    app = create_app({"TESTING": True, "SECRET_KEY": "test",
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'm.db'}"})
    with app.app_context():
        upgrade(directory=MIGRATIONS, revision="7a1e5c9b3d82")
        with db.engine.begin() as conn:
            for email, name, created in accounts:
                conn.execute(sa.text(
                    "INSERT INTO users (email, password_hash, display_name, created_at) "
                    "VALUES (:e, 'x', :n, :c)"), {"e": email, "n": name, "c": created})
        upgrade(directory=MIGRATIONS, revision="754451bd2ef3")
        with db.engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT email, is_moderator FROM users")).all()
        db.engine.dispose()
    return {email: bool(flag) for email, flag in rows}


def test_migration_makes_the_oldest_roobs_the_moderator(tmp_path):
    flags = _migrate_with(tmp_path, [
        ("copycat@example.com", "Roobs", "2026-10-02 00:00:00"),
        ("real@example.com", " roobs ", "2026-09-12 00:00:00"),
        ("other@example.com", "Someone", "2026-09-01 00:00:00"),
    ])
    assert flags == {"copycat@example.com": False, "real@example.com": True,
                     "other@example.com": False}


def test_migration_falls_back_to_a_roobs_email(tmp_path):
    flags = _migrate_with(tmp_path, [
        ("roobs@example.com", None, "2026-09-12 00:00:00"),
        ("other@example.com", "Someone", "2026-09-01 00:00:00"),
    ])
    assert flags == {"roobs@example.com": True, "other@example.com": False}


def test_migration_with_no_roobs_makes_no_moderator(tmp_path):
    flags = _migrate_with(tmp_path, [("other@example.com", "Someone", "2026-09-01 00:00:00")])
    assert flags == {"other@example.com": False}
