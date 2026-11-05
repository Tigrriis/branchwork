"""What a launch needs: the legal pages, analytics, and limits on sign-in."""
import pytest

from app import create_app
from conftest import copy_in, login, make_user
from extensions import db as _db
from models import User
from ratelimit import LOGIN_FAILS_PER_EMAIL, LOGIN_PER_IP, REGISTER_PER_IP


def _register(client, email, ip="1.2.3.4", **extra):
    data = {"email": email, "password": "hunter2hunter2", **extra}
    return client.post("/register", data=data, headers={"X-Forwarded-For": ip})


# --- legal pages ---------------------------------------------------------

@pytest.mark.parametrize("path, key", [("/privacy", "privacy.heading"), ("/terms", "terms.heading")])
def test_legal_pages_open_signed_out(client, path, key):
    page = client.get(path)
    assert page.status_code == 200
    assert copy_in(page.data, key)
    assert copy_in(page.data, "legal.contact_email")


def test_sign_up_forms_link_the_legal_pages(client):
    for path in ("/", "/register"):
        html = client.get(path).data.decode()
        assert 'href="/terms"' in html and 'href="/privacy"' in html


# --- analytics -----------------------------------------------------------

def test_no_analytics_unless_configured(client):
    assert b"plausible" not in client.get("/").data


@pytest.fixture
def tracked_client():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://",
                      "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test-key",
                      "PLAUSIBLE_SCRIPT": "https://plausible.io/js/pa-test.js"})
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_analytics_script_and_signup_event_once(tracked_client):
    landing = tracked_client.get("/").data.decode()
    assert "https://plausible.io/js/pa-test.js" in landing
    assert 'plausible("Signup")' not in landing

    after = _register(tracked_client, "new@example.com")
    first = tracked_client.get(after.headers["Location"]).data.decode()
    assert 'plausible("Signup")' in first
    assert 'plausible("Signup")' not in tracked_client.get("/").data.decode()


# --- bot trap ------------------------------------------------------------

def test_honeypot_makes_no_account(client):
    _register(client, "bot@example.com", hp_website="http://spam.example")
    assert User.query.filter_by(email="bot@example.com").first() is None


def test_people_leave_the_honeypot_empty(client):
    _register(client, "person@example.com", hp_website="")
    assert User.query.filter_by(email="person@example.com").first() is not None


# --- rate limits ---------------------------------------------------------

def test_failed_logins_lock_the_email_from_any_ip(client):
    make_user()
    limit, _ = LOGIN_FAILS_PER_EMAIL
    for i in range(limit):
        client.post("/login", data={"email": "ruben@example.com", "password": "wrong"},
                    headers={"X-Forwarded-For": f"10.0.0.{i}"})
    # Even the right password, from a fresh address, is refused for now.
    page = client.post("/login", data={"email": "ruben@example.com", "password": "hunter2hunter2"},
                       headers={"X-Forwarded-For": "10.9.9.9"})
    assert page.status_code == 429
    assert copy_in(page.data, "auth.slow_down")


def test_a_good_login_resets_the_failures(client):
    make_user()
    limit, _ = LOGIN_FAILS_PER_EMAIL
    for _ in range(limit - 1):
        client.post("/login", data={"email": "ruben@example.com", "password": "wrong"})
    assert login(client).status_code == 200
    client.post("/logout")
    for _ in range(limit - 1):
        client.post("/login", data={"email": "ruben@example.com", "password": "wrong"})
    assert login(client).status_code == 200


def test_login_attempts_per_ip(client):
    limit, _ = LOGIN_PER_IP
    for i in range(limit):
        client.post("/login", data={"email": f"x{i}@example.com", "password": "nope"},
                    headers={"X-Forwarded-For": "5.5.5.5"})
    assert client.post("/login", data={"email": "y@example.com", "password": "nope"},
                       headers={"X-Forwarded-For": "5.5.5.5"}).status_code == 429
    assert client.post("/login", data={"email": "y@example.com", "password": "nope"},
                       headers={"X-Forwarded-For": "6.6.6.6"}).status_code == 200


def test_signups_per_ip(client):
    limit, _ = REGISTER_PER_IP
    for i in range(limit):
        _register(client, f"u{i}@example.com", ip="7.7.7.7")
        client.post("/logout")
    page = _register(client, "late@example.com", ip="7.7.7.7")
    assert page.status_code == 429
    assert User.query.filter_by(email="late@example.com").first() is None
    _register(client, "other@example.com", ip="8.8.8.8")
    assert User.query.filter_by(email="other@example.com").first() is not None


# --- the example plot ----------------------------------------------------

def test_new_accounts_start_with_the_example_plot(client):
    from landing import demo_plot
    _register(client, "fresh@example.com")
    user = User.query.filter_by(email="fresh@example.com").one()
    assert len(user.projects) == 1
    plot = user.projects[0]
    # The same picture as the landing page: names, points and the lock.
    demo = demo_plot()
    assert plot.name == demo["name"] and plot.focused
    assert [b.name for b in plot.branches] == [s["name"] for s in demo["schemes"]]
    assert [(b.points_done, b.points_max) for b in plot.branches] == \
        [(s["done"], s["max"]) for s in demo["schemes"]]
    assert plot.branches[2].is_locked and not plot.branches[1].is_locked
    assert plot.branches[0].ultimate.state == "open"
