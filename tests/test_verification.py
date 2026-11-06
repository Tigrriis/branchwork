"""Email confirmation: the link sent at sign-up, following it, asking for
another, the banner, and the mailer underneath. Also sign-in times, which
the moderation page shows beside confirmation."""
import io
import json
import re
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest
from flask import g

import mailer
import verification
from conftest import copy_in, login, make_user
from extensions import db
from models import User
from ratelimit import VERIFY_SEND_PER_USER


@pytest.fixture
def outbox(app):
    return app.extensions.setdefault("mail_outbox", [])


def _link(message) -> str:
    return re.search(r"https?://\S+/verify/\S+", message["text"]).group(0)


def _path(link: str) -> str:
    return "/verify/" + link.rsplit("/verify/", 1)[1]


def _register(client, email="new@example.com", **extra):
    return client.post("/register", data={"email": email, "password": "longenough1", **extra},
                       follow_redirects=True)


# --- sign-up sends a link ---------------------------------------------------

def test_sign_up_sends_one_confirmation_email(client, outbox):
    r = _register(client, display_name="Newt")
    assert len(outbox) == 1
    message = outbox[0]
    assert message["to"] == ["new@example.com"]
    assert "Newt" in message["text"] and "Newt" in message["html"]
    link = _link(message)
    assert link in message["html"]
    # Told on arrival, and the banner keeps saying so until it is done.
    assert copy_in(r.data, "verify.sent", email="new@example.com")
    assert copy_in(r.data, "verify.banner_sent", email="new@example.com")
    user = User.query.filter_by(email="new@example.com").one()
    assert user.verification_sent_at is not None and not user.is_verified


def test_following_the_link_confirms_and_the_banner_goes(client, outbox):
    _register(client)
    r = client.get(_path(_link(outbox[0])), follow_redirects=True)
    assert copy_in(r.data, "verify.done")
    assert not copy_in(r.data, "verify.banner_sent", email="new@example.com")
    assert User.query.filter_by(email="new@example.com").one().is_verified


def test_a_link_followed_twice_does_no_harm(client, outbox):
    _register(client)
    path = _path(_link(outbox[0]))
    client.get(path)
    when = User.query.filter_by(email="new@example.com").one().email_verified_at
    r = client.get(path, follow_redirects=True)
    assert copy_in(r.data, "verify.already")
    assert User.query.filter_by(email="new@example.com").one().email_verified_at == when


def test_the_link_works_signed_out_and_lands_on_sign_in(client, outbox):
    _register(client)
    client.post("/logout")
    r = client.get(_path(_link(outbox[0])))
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    assert User.query.filter_by(email="new@example.com").one().is_verified


def test_a_forged_link_confirms_nothing(client, outbox):
    _register(client)
    token = _path(_link(outbox[0])).rsplit("/", 1)[1]
    r = client.get("/verify/" + token[:-3] + "abc", follow_redirects=True)
    assert copy_in(r.data, "verify.bad_link")
    assert not User.query.filter_by(email="new@example.com").one().is_verified


def test_an_expired_link_confirms_nothing(app, client, outbox):
    _register(client)
    app.config["VERIFY_LINK_MAX_AGE"] = -1
    r = client.get(_path(_link(outbox[0])), follow_redirects=True)
    assert copy_in(r.data, "verify.bad_link")
    assert not User.query.filter_by(email="new@example.com").one().is_verified


def test_a_link_only_confirms_the_address_it_was_sent_to(client, outbox):
    _register(client)
    user = User.query.filter_by(email="new@example.com").one()
    user.email = "changed@example.com"
    db.session.commit()
    r = client.get(_path(_link(outbox[0])), follow_redirects=True)
    assert copy_in(r.data, "verify.bad_link")
    assert not db.session.get(User, user.id).is_verified


def test_links_use_the_public_url_when_set(app, client, outbox):
    app.config["PUBLIC_URL"] = "https://villainy.example"
    _register(client)
    assert _link(outbox[0]).startswith("https://villainy.example/verify/")


def test_a_failed_send_still_makes_the_account(client, monkeypatch):
    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    r = _register(client)
    assert r.status_code == 200
    user = User.query.filter_by(email="new@example.com").one()
    assert user.verification_sent_at is None
    # No "we sent it" claim; the banner offers to send one instead.
    assert not copy_in(r.data, "verify.sent", email="new@example.com")
    assert copy_in(r.data, "verify.banner_unsent")


# --- asking for another -----------------------------------------------------

def test_older_accounts_are_offered_a_link(client, outbox):
    make_user()
    r = login(client)
    assert copy_in(r.data, "verify.banner_unsent") and copy_in(r.data, "verify.send_first")
    r = client.post("/verify/send", data={"next": "/account"}, follow_redirects=True)
    assert copy_in(r.data, "verify.sent", email="ruben@example.com")
    assert len(outbox) == 1 and outbox[0]["to"] == ["ruben@example.com"]
    assert copy_in(r.data, "verify.send_again")


def test_sending_again_is_limited(client, outbox):
    make_user()
    login(client)
    limit = VERIFY_SEND_PER_USER[0]
    for _ in range(limit):
        client.post("/verify/send")
    r = client.post("/verify/send", follow_redirects=True)
    assert copy_in(r.data, "auth.slow_down")
    assert len(outbox) == limit


def test_a_confirmed_account_is_not_sent_another(client, outbox):
    user = make_user()
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    r = login(client)
    assert not copy_in(r.data, "verify.banner_unsent")
    r = client.post("/verify/send", follow_redirects=True)
    assert copy_in(r.data, "verify.already") and outbox == []


def test_send_returns_to_the_page_it_came_from_but_never_offsite(client, outbox):
    make_user()
    login(client)
    r = client.post("/verify/send", data={"next": "/settings/statuses"})
    assert r.headers["Location"].endswith("/settings/statuses")
    r = client.post("/verify/send", data={"next": "//evil.example/"})
    assert r.headers["Location"].endswith("/account")


def test_sending_needs_a_sign_in(client):
    r = client.post("/verify/send")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_account_page_shows_whether_the_email_is_confirmed(client):
    user = make_user()
    login(client)
    assert copy_in(client.get("/account").data, "account.email_unverified")
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    assert copy_in(client.get("/account").data, "account.email_verified")


# --- sign-in times ----------------------------------------------------------

def test_sign_up_and_sign_in_record_the_time(client):
    _register(client)
    user = User.query.filter_by(email="new@example.com").one()
    assert user.last_login_at is not None
    user.last_login_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.session.commit()
    client.post("/logout")
    client.post("/login", data={"email": "new@example.com", "password": "longenough1"})
    seen = db.session.get(User, user.id).last_login_at.replace(tzinfo=timezone.utc)
    assert seen > datetime.now(timezone.utc) - timedelta(minutes=1)


def test_a_failed_sign_in_records_nothing(client):
    make_user()
    login(client, password="wrong")
    assert User.query.one().last_login_at is None


def test_being_signed_back_in_by_keep_me_signed_in_counts(app, client):
    make_user()
    client.post("/login", data={"email": "ruben@example.com", "password": "hunter2hunter2",
                                "remember": "1"})
    user = User.query.one()
    user.last_login_at = None
    db.session.commit()
    # A new browser session: the session cookie is gone, the remember cookie
    # stays. The fixture's app context outlives each request, so forget the
    # user Flask-Login cached on it, as a new process would never have it.
    g.pop("_login_user", None)
    remember = client.get_cookie("remember_token")
    fresh = app.test_client()
    fresh.set_cookie("remember_token", remember.value)
    assert fresh.get("/account").status_code == 200
    assert db.session.get(User, user.id).last_login_at is not None


# --- the mailer -------------------------------------------------------------

class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def live_mailer(app):
    """The mailer as production runs it: not under test, with a key."""
    app.config.update(TESTING=False, RESEND_API_KEY="re_test_key",
                      MAIL_FROM="Villainy <noreply@villainy.example>")
    yield app
    app.config["TESTING"] = True


def test_mailer_posts_to_resend(live_mailer, monkeypatch):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(request)
        return _Response(b'{"id": "abc"}')

    monkeypatch.setattr(mailer.urllib.request, "urlopen", fake_urlopen)
    assert mailer.send("to@example.com", "Subject", "Text body", "<p>Html</p>") is True
    request = sent[0]
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer re_test_key"
    body = json.loads(request.data)
    assert body["from"] == "Villainy <noreply@villainy.example>"
    assert body["to"] == ["to@example.com"]
    assert body["subject"] == "Subject" and body["text"] == "Text body"
    assert body["html"] == "<p>Html</p>" and body["reply_to"]


def test_mailer_reports_a_refusal_without_raising(live_mailer, monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {},
                                     io.BytesIO(b'{"message": "domain not verified"}'))

    monkeypatch.setattr(mailer.urllib.request, "urlopen", refuse)
    assert mailer.send("to@example.com", "S", "T", "<p>H</p>") is False


def test_mailer_reports_an_outage_without_raising(live_mailer, monkeypatch):
    def down(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(mailer.urllib.request, "urlopen", down)
    assert mailer.send("to@example.com", "S", "T", "<p>H</p>") is False


def test_mailer_without_a_key_sends_nothing(live_mailer, monkeypatch):
    live_mailer.config["RESEND_API_KEY"] = ""

    def should_not_run(*a, **k):
        raise AssertionError("tried to reach Resend with no key")

    monkeypatch.setattr(mailer.urllib.request, "urlopen", should_not_run)
    assert mailer.send("to@example.com", "S", "T", "<p>H</p>") is False


def test_tokens_name_the_account_and_address(app):
    user = make_user()
    assert verification.read_token(verification.make_token(user)) == user
    assert verification.read_token("not-a-token") is None


def test_the_link_does_not_carry_the_address(client, outbox):
    """It ends up in server logs and browser history, so only a fingerprint."""
    import base64
    _register(client)
    payload = _link(outbox[0]).rsplit("/verify/", 1)[1].split(".")[0]
    decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    assert b"new@example.com" not in decoded and b"example" not in decoded
