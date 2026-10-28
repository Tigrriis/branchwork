"""The landing page: what a signed-out visitor sees at the home address."""
from conftest import copy_in, login, make_user

from landing import GATE, demo_plot


def test_signed_out_visitors_get_the_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode()
    assert copy_in(html, "landing.heading") and copy_in(html, "landing.form_heading")
    # The sign-up box posts to the real sign-up, with the fields it reads.
    assert 'action="/register"' in html
    assert 'name="email"' in html and 'name="password"' in html
    assert 'href="/login"' in html
    # The example plot is drawn, and described for screen readers.
    assert html.count('class="lcol col--') == 3
    assert copy_in(html, "landing.demo_caption")


def test_signing_up_from_the_landing_page_lands_on_today(client):
    r = client.post("/register", data={"email": "new@example.com", "password": "longenough1"},
                    follow_redirects=True)
    assert copy_in(r.data, "today.heading")
    assert not copy_in(r.data, "landing.heading")


def test_signed_in_visitors_still_get_today(client):
    make_user()
    login(client)
    html = client.get("/").data.decode()
    assert copy_in(html, "today.heading")
    assert not copy_in(html, "landing.heading")


def test_the_example_plot_adds_up():
    plot = demo_plot()
    infiltration, funding, device = plot["schemes"]
    assert plot["done"] == sum(s["done"] for s in plot["schemes"])
    assert plot["max"] == sum(s["max"] for s in plot["schemes"])
    # Full tiers fill all the way; a part-filled tier fills by its share of the gate.
    assert [t["fill"] for t in infiltration["tiers"]] == [100, 100]
    have = sum(tile["done"] for tile in funding["tiers"][1]["tiles"])
    assert funding["tiers"][1]["fill"] == round(100 * have / GATE)
    # The last tier holds enough to open another, so the ultimate is reached.
    assert infiltration["ultimate_reached"]
    # The Device waits on Funding: every tier shut, nothing filled, both say why.
    assert all(t["shut"] and t["fill"] == 0 and t["note"] for t in device["tiers"])
