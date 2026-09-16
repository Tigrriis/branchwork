"""Routines: the cooldown maths, the done endpoint, and where they show up."""
from datetime import datetime, timedelta, timezone

from conftest import copy_in, login, make_project, make_user
from models import Routine


def _ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _routine(db, project, title="Send invoices", every_days=7, done_days_ago=None):
    routine = Routine(project=project, title=title, every_days=every_days,
                      position=len(project.routines))
    if done_days_ago is not None:
        routine.last_done_at = _ago(done_days_ago)
    db.session.add(routine)
    db.session.commit()
    return routine


def test_a_new_routine_starts_ready(db):
    r = _routine(db, make_project(make_user()))
    assert r.charge == 1.0 and r.is_ready
    assert r.days_left == 0 and r.overdue_days == 0


def test_cooldown_refills_over_the_tempo(db):
    r = _routine(db, make_project(make_user()), every_days=7, done_days_ago=3)
    assert 0.42 < r.charge < 0.44 and not r.is_ready
    assert r.days_left == 4 and r.overdue_days == 0

    r.last_done_at = _ago(9)
    db.session.commit()
    assert r.charge == 1.0 and r.is_ready
    assert r.days_left == 0 and r.overdue_days == 2


def test_marking_done_empties_it_and_counts_as_a_touch(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    p.phase, p.last_activity_at = "building", _ago(30)
    r = _routine(db, p, done_days_ago=10)

    res = client.post(f"/routines/{r.id}/done", json={"where": "tree"})
    assert res.status_code == 200
    body = res.get_json()
    assert f'data-routine="{r.id}"' in body["html"] and body["title"] == "Send invoices"

    db.session.refresh(r)
    db.session.refresh(p)
    assert r.charge < 0.01 and not r.is_ready and r.days_left == 7
    assert p.days_since_touch == 0
    assert [e.note for e in p.events if e.kind == "routine"] == ["Send invoices"]


def test_marking_done_without_the_script_redirects_with_a_message(client, db):
    user = make_user()
    login(client)
    r = _routine(db, make_project(user), every_days=14)
    res = client.post(f"/routines/{r.id}/done", follow_redirects=True)
    assert res.status_code == 200
    assert copy_in(res.data, "routine.done", title="Send invoices", n=14)


def test_routines_are_owner_only(client, db):
    owner = make_user("owner@example.com")
    r = _routine(db, make_project(owner))
    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert client.post(f"/routines/{r.id}/done", json={}).status_code == 404
    assert client.get(f"/routines/{r.id}/edit").status_code == 404
    assert client.post(f"/routines/{r.id}/delete").status_code == 404
    db.session.refresh(r)
    assert r.last_done_at is None


def test_today_bar_gathers_ready_routines_from_live_plots(client, db):
    user = make_user()
    login(client)
    live = make_project(user)
    live.name, live.phase = "Consultancy", "building"
    quiet = make_project(user)
    quiet.name, quiet.phase, quiet.focused = "Side thing", "maintaining", False
    shelved = make_project(user)
    shelved.name, shelved.phase = "Old site", "parked"
    db.session.commit()
    invoices = _routine(db, live, "Send invoices", done_days_ago=8)
    _routine(db, quiet, "Check backups", every_days=7, done_days_ago=5)
    _routine(db, shelved, "Renew domain")

    html = client.get("/").data.decode()
    assert "Send invoices" in html
    assert "Check backups" not in html      # still cooling
    assert "Renew domain" not in html       # ready, but its plot is parked

    body = client.post(f"/routines/{invoices.id}/done", json={"where": "today"}).get_json()
    # Nothing is ready now, so the bar says what comes up next instead.
    assert "data-routine" not in body["html"]
    assert copy_in(body["html"], "ready.none_next", title="Check backups", name="Side thing", n=2)


def test_today_bar_includes_backburner_plots(client, db):
    """A routine is a tempo the user set on purpose, so the backburner does
    not silence it the way it silences the general "needs a touch" nag."""
    user = make_user()
    login(client)
    p = make_project(user)
    p.phase, p.focused = "maintaining", False
    db.session.commit()
    _routine(db, p, "Water the plants")
    assert "Water the plants" in client.get("/").data.decode()


def test_routine_form_creates_edits_and_deletes(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    assert client.get(f"/projects/{p.id}/routines/new").status_code == 200
    db.session.rollback()
    assert p.routines == []                 # rendering the form inserts nothing

    client.post(f"/projects/{p.id}/routines/new",
                data={"title": "Site walk", "every_days": "14", "icon": "bomb", "last_done": ""})
    r = Routine.query.one()
    assert (r.title, r.every_days, r.icon, r.last_done_at) == ("Site walk", 14, "bomb", None)

    three_days_ago = _ago(3).date().isoformat()
    client.post(f"/routines/{r.id}/edit",
                data={"title": "Site walk", "every_days": "14", "icon": "nonsense",
                      "last_done": three_days_ago})
    db.session.refresh(r)
    assert r.icon == "bomb" and r.days_left == 11
    # Correcting the date is bookkeeping, not work on the plot.
    assert not any(e.kind == "routine" for e in p.events)

    html = client.get(f"/projects/{p.id}").data.decode()
    assert f'data-routine="{r.id}"' in html and "Site walk" in html

    client.post(f"/routines/{r.id}/delete")
    assert Routine.query.count() == 0


def test_deleting_a_plot_deletes_its_routines(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    _routine(db, p)
    client.post(f"/projects/{p.id}/delete")
    assert Routine.query.count() == 0
