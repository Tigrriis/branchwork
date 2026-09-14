"""The plot switcher: on every signed-in page, grouped, marking where you are."""
import re
from datetime import datetime, timedelta, timezone

from conftest import copy_in, login, make_project, make_user
from models import Routine
from switcher import initials


def _rail(html):
    return html[html.index('id="rail"'):html.index("</aside>")]


def _plot(db, user, name, phase="building", focused=True):
    p = make_project(user)
    p.name, p.phase, p.focused = name, phase, focused
    db.session.commit()
    return p


def test_signed_out_pages_have_no_switcher(client):
    assert 'id="rail"' not in client.get("/login").data.decode()


def test_every_signed_in_page_has_the_switcher(client, db):
    user = make_user()
    login(client)
    p = _plot(db, user, "Moon laser")
    for url in ("/", "/board", "/review", "/account", "/settings/statuses", "/settings/templates",
                "/projects/new", f"/projects/{p.id}", f"/projects/{p.id}/list", f"/projects/{p.id}/edit"):
        html = client.get(url).data.decode()
        assert f'href="/projects/{p.id}"' in _rail(html), url


def test_focus_comes_before_the_backburner_and_shelved_plots_stay_out(client, db):
    user = make_user()
    login(client)
    _plot(db, user, "Zeppelin fleet")
    _plot(db, user, "Aardvark army", phase="exploring", focused=False)
    _plot(db, user, "Old lair", phase="parked")
    rail = _rail(client.get("/").data.decode())
    # Grouped first, alphabetical within a group.
    assert rail.index("Zeppelin fleet") < rail.index("Aardvark army")
    assert copy_in(rail, "rail.focus") and copy_in(rail, "rail.backburner")
    assert "Old lair" not in rail
    assert 'aria-current="page"' not in rail


def test_the_plot_being_viewed_is_marked_even_when_shelved(client, db):
    user = make_user()
    login(client)
    live = _plot(db, user, "Shark tank")
    shelved = _plot(db, user, "Old lair", phase="parked")

    rail = _rail(client.get(f"/projects/{live.id}").data.decode())
    assert re.search(rf'href="/projects/{live.id}"[^>]*aria-current="page"', rail)

    # A shelved plot appears only on its own page, under its status's name.
    rail = _rail(client.get(f"/projects/{shelved.id}").data.decode())
    assert re.search(rf'href="/projects/{shelved.id}"[^>]*aria-current="page"', rail)
    assert shelved.phase_label in rail


def test_due_plots_and_ready_routines_are_flagged(client, db):
    user = make_user()
    login(client)
    p = _plot(db, user, "Doomsday clock")
    p.cadence_days = 7
    p.last_activity_at = datetime.now(timezone.utc) - timedelta(days=20)
    for title in ("Oil the gears", "Feed the sharks"):
        db.session.add(Routine(project=p, title=title, every_days=7))
    db.session.commit()
    rail = _rail(client.get("/board").data.decode())
    assert 'class="rail__due"' in rail
    assert copy_in(rail, "rail.ready_title", n=2)


def test_initials():
    assert initials("Office fit-out, Level 3") == "OF"
    assert initials("lair") == "La"
    assert initials("   ") == "?"
