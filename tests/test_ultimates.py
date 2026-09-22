"""Ultimates: a scheme's end goal below its tiers, and the rules that hold."""
from conftest import (
    copy_in, login, make_branch, make_project, make_task, make_ultimate, make_user,
)
from copytext import tx
from models import ActivityEvent, Ultimate


def _claim(client, ultimate, achieved=True):
    return client.post(f"/ultimates/{ultimate.id}/achieve", json={"achieved": achieved})


def test_ultimate_opens_by_the_tier_rule(db):
    user = make_user()
    project = make_project(user, gate_points=3)
    branch = make_branch(project)
    ultimate = make_ultimate(branch)

    # Nothing to climb yet.
    assert not ultimate.open and ultimate.reason == tx("ultimate.needs_machinations")

    a = make_task(branch, "A", tier=1, points_max=2)
    b = make_task(branch, "B", tier=1, points_max=2)
    assert not ultimate.open
    assert ultimate.reason == tx("gate.needs_points", gate=3, have=0)
    assert ultimate.state == "closed"

    # Enough in the last tier to open another: the ultimate is that next step.
    a.set_points(2); b.set_points(1); db.session.commit()
    assert ultimate.open and ultimate.state == "open"

    # A new tier slides in above it and becomes the one that has to fill.
    make_task(branch, "C", tier=2)
    assert not ultimate.open
    assert ultimate.reason == tx("gate.needs_points", gate=3, have=0)


def test_ultimate_stays_closed_while_the_scheme_is_locked(db):
    user = make_user()
    project = make_project(user)
    first = make_branch(project, "Approvals")
    make_task(first, "Permit")
    second = make_branch(project, "Build", "red", requires=first)
    ultimate = make_ultimate(second)
    make_task(second, "Dig", points_max=3, points_done=3)

    assert not ultimate.open and ultimate.reason == second.lock_reason


def test_a_scheme_with_an_ultimate_is_complete_only_once_it_is_claimed(db):
    user = make_user()
    project = make_project(user)
    first = make_branch(project, "Approvals")
    make_task(first, "Permit", points_max=3, points_done=3)
    second = make_branch(project, "Build", "red", requires=first)
    assert first.is_complete and not second.is_locked

    ultimate = make_ultimate(first)
    assert not first.is_complete and second.is_locked

    ultimate.set_achieved(True); db.session.commit()
    assert first.is_complete and not second.is_locked


def test_claiming_needs_it_open_and_taking_back_does_not(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    task = make_task(branch, "A", points_max=3)
    ultimate = make_ultimate(branch, "Keys handed over")

    res = _claim(client, ultimate)
    assert res.status_code == 409
    assert res.get_json()["message"] == tx("ultimate.closed")
    assert not Ultimate.query.one().achieved

    task.set_points(3); db.session.commit()
    res = _claim(client, ultimate)
    assert res.status_code == 200
    ultimate = Ultimate.query.one()
    assert ultimate.achieved and ultimate.achieved_at is not None
    html = res.get_json()["html"]
    assert f'data-ultimate="{ultimate.id}"' in html and "ultimate--achieved" in html
    assert 'aria-pressed="true"' in html
    event = ActivityEvent.query.filter_by(kind="ultimate").one()
    assert event.delta == 1 and event.note == "Keys handed over"

    # Claimed, it stays lit even if the tier above loses a point.
    task.set_points(2); db.session.commit()
    assert Ultimate.query.one().state == "achieved"
    assert "ultimate--achieved" in client.get(f"/projects/{project.id}").data.decode()

    # Taking it back is always allowed, and is its own event.
    res = _claim(client, ultimate, achieved=False)
    assert res.status_code == 200
    assert not Ultimate.query.one().achieved
    assert "ultimate--closed" in res.get_json()["html"]
    assert ActivityEvent.query.filter_by(kind="ultimate").count() == 2


def test_ultimate_routes_are_owner_only(client, db):
    owner = make_user()
    project = make_project(owner)
    branch = make_branch(project)
    make_task(branch, "A", points_max=3, points_done=3)
    ultimate = make_ultimate(branch)

    make_user("other@example.com")
    login(client, "other@example.com")
    assert _claim(client, ultimate).status_code == 404
    assert client.get(f"/branches/{branch.id}/ultimate").status_code == 404
    assert client.post(f"/ultimates/{ultimate.id}/delete").status_code == 404
    assert not Ultimate.query.one().achieved


def test_form_sets_edits_and_removes_the_ultimate(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    make_task(branch, "A")

    # The tree offers to set one, and the empty form inserts nothing.
    html = client.get(f"/projects/{project.id}").data.decode()
    assert copy_in(html, "tree.set_ultimate") and 'class="ultimate ' not in html
    assert client.get(f"/branches/{branch.id}/ultimate").status_code == 200
    assert Ultimate.query.count() == 0

    res = client.post(f"/branches/{branch.id}/ultimate",
                      data={"title": "  Keys handed over ", "icon": "bomb", "notes": ""},
                      follow_redirects=True)
    assert res.status_code == 200
    ultimate = Ultimate.query.one()
    assert (ultimate.branch_id, ultimate.title, ultimate.notes) == (branch.id, "Keys handed over", None)
    html = res.data.decode()
    assert copy_in(html, "ultimate.added")
    assert "ultimate--closed" in html and "Keys handed over" in html
    assert not copy_in(html, "tree.set_ultimate")

    # A blank title is refused and changes nothing.
    res = client.post(f"/branches/{branch.id}/ultimate", data={"title": "   "})
    assert res.status_code == 200 and copy_in(res.data.decode(), "ultimate.title_required")
    assert Ultimate.query.one().title == "Keys handed over"

    # The same form edits the one that exists rather than adding a second.
    res = client.post(f"/branches/{branch.id}/ultimate",
                      data={"title": "Handover", "icon": "nope", "notes": "With the manuals"},
                      follow_redirects=True)
    assert copy_in(res.data.decode(), "ultimate.saved")
    ultimate = Ultimate.query.one()
    assert (ultimate.title, ultimate.icon, ultimate.notes) == ("Handover", "bomb", "With the manuals")

    res = client.post(f"/ultimates/{ultimate.id}/delete", follow_redirects=True)
    assert copy_in(res.data.decode(), "ultimate.deleted")
    assert Ultimate.query.count() == 0


def test_deleting_a_scheme_takes_its_ultimate(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    make_task(branch, "A")
    make_ultimate(branch)

    client.post(f"/branches/{branch.id}/delete", follow_redirects=True)
    assert Ultimate.query.count() == 0


def test_tree_shows_the_lock_reason_on_a_closed_ultimate(client, db):
    user = make_user()
    login(client)
    project = make_project(user, gate_points=3)
    branch = make_branch(project)
    make_task(branch, "A", points_max=3, points_done=1)
    make_ultimate(branch)

    html = client.get(f"/projects/{project.id}").data.decode()
    assert "ultimate--closed" in html
    assert tx("gate.needs_points", gate=3, have=1) in html
    assert "<button type=\"button\" class=\"ultimate__box\" disabled" in html


def test_claiming_seals_the_look_but_leftovers_still_tick(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    make_task(branch, "A", points_max=3, points_done=3)
    b = make_task(branch, "B", points_max=2, points_done=1)
    ultimate = make_ultimate(branch)
    assert ultimate.open and not branch.is_sealed

    html = client.get(f"/projects/{project.id}").data.decode()
    assert "ultimate--open" in html and "col--sealed" not in html

    # Sealed is a look: the note and the class, with the tiles still live.
    _claim(client, ultimate)
    assert branch.is_sealed and b.editable
    html = client.get(f"/projects/{project.id}").data.decode()
    assert "col--sealed" in html and tx("gate.sealed") in html
    assert html.count("tile--live") == 2 and 'class="tile__box" disabled' not in html
    assert client.post(f"/tasks/{b.id}/points", json={"delta": 1}).status_code == 200
    assert b.points_done == 2

    _claim(client, ultimate, achieved=False)
    assert not branch.is_sealed
    assert "col--sealed" not in client.get(f"/projects/{project.id}").data.decode()
