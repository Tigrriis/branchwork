"""Tempo, phases, review, ideas and git sync."""
import os
import re
import subprocess
from datetime import date, datetime, timedelta, timezone

from conftest import (
    copy_in, copy_prefix_in, login, make_branch, make_project, make_task, make_user,
    post_statuses, status_rows,
)
from copytext import tx
from gitsync import sync_project
from models import InboxItem, Task


def _age(project, days):
    project.last_activity_at = datetime.now(timezone.utc) - timedelta(days=days)


def test_due_when_past_cadence(db):
    user = make_user()
    p = make_project(user)
    p.phase, p.cadence_days = "building", 7
    _age(p, 3); db.session.commit()
    assert not p.is_due and p.overdue_days == -4
    _age(p, 9); db.session.commit()
    assert p.is_due and p.overdue_days == 2


def test_no_tempo_and_shelved_projects_are_never_due(db):
    user = make_user()
    p = make_project(user)
    p.cadence_days = 0; _age(p, 100); db.session.commit()
    assert p.overdue_days is None and not p.is_due
    p.cadence_days, p.phase = 7, "parked"; db.session.commit()
    assert not p.is_due


def test_points_change_records_event_and_touch(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    _age(p, 30); db.session.commit()
    task = make_task(make_branch(p), "T", points_max=2)
    client.post(f"/machinations/{task.id}/points", json={"delta": 1})
    db.session.refresh(p)
    assert p.days_since_touch == 0
    kinds = [(e.kind, e.delta) for e in p.events]
    assert ("points", 1) in kinds
    # a no-op change (already at max) records nothing
    client.post(f"/machinations/{task.id}/points", json={"delta": 1})
    client.post(f"/machinations/{task.id}/points", json={"delta": 1})
    assert sum(1 for e in p.events if e.kind == "points") == 2


def test_activity_strip_buckets_by_week(db):
    user = make_user()
    p = make_project(user)
    now = datetime.now(timezone.utc)
    p.record("touch", at=now)
    p.record("touch", at=now - timedelta(weeks=1))
    p.record("touch", at=now - timedelta(weeks=1, days=1))
    p.record("touch", at=now - timedelta(weeks=20))
    db.session.commit()
    strip = p.activity_strip()
    assert len(strip) == 12
    assert strip[-1] == 1 and sum(strip) == 3


def test_today_lists_due_and_missing_action(client, db):
    user = make_user()
    login(client)
    due = make_project(user); due.name, due.phase, due.cadence_days, due.next_action = "Stale one", "building", 7, "Ship it"
    _age(due, 20)
    fresh = make_project(user); fresh.name, fresh.phase, fresh.cadence_days = "Fresh one", "exploring", 30
    db.session.commit()
    html = client.get("/").data.decode()
    assert "Stale one" in html
    assert _count(html, "due") == 1 and _count(html, "noaction") == 1
    assert "Fresh one" in html


def test_wip_limit_on_building(client, db):
    user = make_user()
    user.status("building").wip_limit = 2
    db.session.commit()
    login(client)
    for i in range(2):
        p = make_project(user); p.phase = "building"
    db.session.commit()
    third = make_project(user)
    r = client.post(f"/plots/{third.id}/phase", data={"phase": "building"}, follow_redirects=True)
    assert copy_prefix_in(r.data, "board.status_full")
    db.session.refresh(third)
    assert third.phase == "idea"
    # moving within building (no-op) or elsewhere is fine
    r = client.post(f"/plots/{third.id}/phase", data={"phase": "exploring"}, follow_redirects=True)
    db.session.refresh(third)
    assert third.phase == "exploring"
    assert any(e.kind == "phase" and "Exploring" in e.note for e in third.events)


def test_park_and_resurface(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post(f"/plots/{p.id}/phase", data={"phase": "parked", "parked_until": yesterday})
    db.session.refresh(p)
    assert p.phase == "parked" and p.parked_expired
    html = client.get("/").data.decode()
    assert copy_in(html, "today.shelf_heading")
    client.post(f"/plots/{p.id}/phase", data={"phase": "exploring"})
    db.session.refresh(p)
    assert p.phase == "exploring" and p.parked_until is None


def test_the_loose_inbox_is_gone(client, db):
    """Ideas live under a plot's tree now; Today has no inbox to capture into."""
    user = make_user()
    login(client)
    db.session.add(InboxItem(user=user, text="Left over from the old inbox")); db.session.commit()
    assert client.post("/inbox", data={"text": "Anything"}).status_code == 404
    assert InboxItem.query.count() == 1
    assert b"Left over from the old inbox" not in client.get("/").data

# ── Per-project ideas ───────────────────────────────────────────────────────

def _promote(client, item_id, branch_id, tier):
    return client.post(f"/ideas/{item_id}/promote", json={"branch_id": branch_id, "tier": tier})


def test_project_ideas_live_under_their_tree(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.name, p.phase = "Fit-out", "building"
    db.session.commit()
    client.post(f"/plots/{p.id}/ideas", data={"text": "Ask about the fire damper"})

    idea = InboxItem.query.filter_by(text="Ask about the fire damper").one()
    assert idea.project_id == p.id and idea.status == "open"
    assert "Ask about the fire damper" in client.get(f"/plots/{p.id}").data.decode()
    assert "Ask about the fire damper" not in client.get("/").data.decode()


def test_dropping_an_idea_on_a_tier_makes_it_a_task(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    branch = make_branch(p, "Design")
    make_task(branch, "Existing", tier=1)
    client.post(f"/plots/{p.id}/ideas", data={"text": "Check the ceiling heights\nwith the architect"})
    idea = InboxItem.query.one()

    r = _promote(client, idea.id, branch.id, 1)
    assert r.status_code == 200
    body = r.get_json()
    assert body["branch"] == "Design" and body["tier"] == 1
    assert body["title"] == "Check the ceiling heights"
    # Both fragments come back, since the idea leaves one list for the other.
    assert "Check the ceiling heights" in body["tree"]
    assert "Check the ceiling heights" not in body["ideas"]
    assert body["points_max"] == 2                      # header has to move too

    db.session.refresh(idea)
    assert idea.status == "filed" and idea.task_id is not None
    task = db.session.get(Task, idea.task_id)
    assert task.branch_id == branch.id and task.tier == 1 and task.points_max == 1
    # The rest of a multi-line idea is kept as the task's notes.
    assert task.notes.endswith("with the architect")
    assert any(e.kind == "task" and "From ideas" in (e.note or "") for e in p.events)


def test_an_idea_can_open_a_new_tier(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    branch = make_branch(p)
    make_task(branch, "First", tier=1)
    client.post(f"/plots/{p.id}/ideas", data={"text": "Later thing"})
    idea = InboxItem.query.one()
    _promote(client, idea.id, branch.id, 2)
    db.session.refresh(branch)
    assert sorted(t.tier for t in branch.tasks) == [1, 2]


def test_an_idea_cannot_be_promoted_twice(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    branch = make_branch(p)
    client.post(f"/plots/{p.id}/ideas", data={"text": "Once only"})
    idea = InboxItem.query.one()
    assert _promote(client, idea.id, branch.id, 1).status_code == 200
    r = _promote(client, idea.id, branch.id, 1)
    assert r.status_code == 409
    assert Task.query.count() == 1


def test_promote_is_owner_only(client, db):
    owner = make_user("owner@example.com")
    p = make_project(owner)
    branch = make_branch(p)
    db.session.add(InboxItem(user=owner, project=p, text="Theirs")); db.session.commit()
    idea = InboxItem.query.one()
    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert _promote(client, idea.id, branch.id, 1).status_code == 404
    assert Task.query.count() == 0


def test_finishing_an_idea_leaves_the_tree_alone(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    make_branch(p)
    client.post(f"/plots/{p.id}/ideas", data={"text": "Never mind"})
    idea = InboxItem.query.one()
    client.post(f"/ideas/{idea.id}/done")
    db.session.refresh(idea)
    assert idea.status == "done" and Task.query.count() == 0
    assert "Never mind" not in client.get(f"/plots/{p.id}").data.decode()


# ── Focus vs backburner ─────────────────────────────────────────────────────

def _count(html, key):
    """Read a header count out of its <span data-count-KEY>N</span>."""
    m = re.search(r'data-count-%s[^>]*>\s*(\d+)' % key, html)
    assert m, f"no data-count-{key} in the page"
    return int(m.group(1))


def _lane(html, name):
    """The slice of Today between one lane heading and the next."""
    start = html.index('data-focus-zone="%s"' % ("1" if name == "focus" else "0"))
    rest = html[start:]
    end = rest.find('data-focus-zone="0"') if name == "focus" else -1
    return rest[:end] if end > 0 else rest


def test_new_projects_start_in_focus(client, db):
    user = make_user()
    login(client)
    # The new-plot form asks only for a name and a template; focus is on.
    assert b'name="focused"' not in client.get("/plots/new").data
    client.post("/plots/new", data={"name": "Fresh", "starter": "blank"})
    assert user.projects[0].focused is True


def test_unticking_focus_on_the_form_is_respected(client, db):
    """An unchecked box sends nothing, which has to mean backburner."""
    user = make_user()
    login(client)
    p = make_project(user); p.focused = True
    db.session.commit()
    client.post(f"/plots/{p.id}/edit", data={"name": p.name, "cadence_days": "14",
                                                "phase": "building", "gate_points": "3"})
    db.session.refresh(p)
    assert p.focused is False


def test_today_splits_focus_from_backburner(client, db):
    user = make_user()
    login(client)
    a = make_project(user); a.name, a.phase, a.focused = "Doing it", "building", True
    b = make_project(user); b.name, b.phase, b.focused = "Not now", "exploring", False
    db.session.commit()

    html = client.get("/").data.decode()
    assert _count(html, "focus") == 1 and _count(html, "back") == 1
    assert "Doing it" in _lane(html, "focus") and "Not now" not in _lane(html, "focus")
    assert "Not now" in _lane(html, "back")


def test_backburner_projects_do_not_nag(client, db):
    """Going quiet is the whole point of the backburner, so it is not counted."""
    user = make_user()
    login(client)
    quiet = make_project(user); quiet.name, quiet.phase, quiet.cadence_days = "Shelved", "building", 7
    quiet.focused, quiet.next_action = False, None
    _age(quiet, 90)
    db.session.commit()
    html = client.get("/").data.decode()
    assert _count(html, "due") == 0 and _count(html, "noaction") == 0
    assert "Shelved" in html                      # still visible, just not shouting
    # The cadence itself is untouched, so Review and the board still see it.
    assert quiet.is_due


def test_dragging_a_project_between_lanes(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.name, p.phase = "Swing", "building"
    db.session.commit()

    r = client.post(f"/plots/{p.id}/focus", json={"focused": "0"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["focused"] is False and body["name"] == "Swing"
    db.session.refresh(p)
    assert p.focused is False
    # The response carries both lanes re-rendered, with the project in the
    # backburner half.
    assert "Swing" in _lane(body["lists"], "back")

    r = client.post(f"/plots/{p.id}/focus", json={"focused": "1"})
    db.session.refresh(p)
    assert p.focused is True
    assert "Swing" in _lane(r.get_json()["lists"], "focus")


def test_focus_buttons_work_without_javascript(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.phase = "building"
    db.session.commit()
    client.post(f"/plots/{p.id}/focus", data={"focused": "0"})
    db.session.refresh(p)
    assert p.focused is False
    client.post(f"/plots/{p.id}/focus", data={"focused": "1"})
    db.session.refresh(p)
    assert p.focused is True


def test_focus_is_owner_only(client, db):
    owner = make_user("owner@example.com")
    p = make_project(owner); p.focused = True
    db.session.commit()
    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert client.post(f"/plots/{p.id}/focus", json={"focused": "0"}).status_code == 404
    db.session.refresh(p)
    assert p.focused is True


def test_focus_is_independent_of_phase(client, db):
    """A shelved project never shows in focus, whatever the flag says."""
    user = make_user()
    login(client)
    p = make_project(user); p.name, p.phase, p.focused = "Parked but flagged", "parked", True
    db.session.commit()
    html = client.get("/").data.decode()
    assert "Parked but flagged" not in _lane(html, "focus")
    assert _count(html, "focus") == 0 and _count(html, "back") == 0


# ── Custom project templates ────────────────────────────────────────────────

def test_copying_a_builtin_gives_an_editable_template(client, db):
    from models import Template
    user = make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "lifecycle"})
    t = Template.query.one()
    assert t.name == tx("starter.lifecycle.label") and t.user_id == user.id
    assert [(b.name, b.hue, b.waits) for b in t.branches] == [
        ("Idea", "violet", True), ("Prototype", "blue", True), ("Build", "green", True),
        ("Launch", "amber", True), ("Maintain", "teal", True)]
    # It shows on the new-project form, marked as the user's own.
    html = client.get("/plots/new").data.decode()
    assert f'value="custom:{t.id}"' in html and copy_in(html, "plot.yours_tag")


def test_copying_an_unchained_builtin_leaves_nothing_waiting(client, db):
    from models import Template
    make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "simple"})
    t = Template.query.one()
    assert [(b.name, b.waits) for b in t.branches] == [
        ("First steps", False), ("Main work", False), ("Finishing", False)]
    assert all(b.tasks() == [] for b in t.branches)


def test_a_copy_gets_a_distinct_name(client, db):
    from models import Template
    make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "simple"})
    client.post("/settings/templates/new", data={"copy": "simple"})
    label = tx("starter.simple.label")
    assert sorted(t.name for t in Template.query.all()) == sorted([label, label + " 2"])


def test_editing_a_template_renames_reorders_and_deletes(client, db):
    from models import Template, TemplateBranch
    make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "simple"})
    t = Template.query.one()

    # Four rows posted: rename the first, blank the second (delete), rename
    # the third, and add a fourth. Only row 3 is ticked as waiting.
    client.post(f"/settings/templates/{t.id}", data={
        "name": "Arete job", "hint": "How we actually run one",
        "branch_name": ["Concept", "", "Construction", "Handover"],
        "branch_hue": ["violet", "blue", "red", "teal"],
        "branch_waits_3": "1",
        "branch_tasks": ["Site visit | 2\nBrief signed", "", "", ""],
    })
    db.session.expire_all()
    t = Template.query.one()
    assert t.name == "Arete job" and t.hint == "How we actually run one"
    assert [(b.name, b.hue, b.waits, b.position) for b in t.branches] == [
        ("Concept", "violet", False, 0),
        ("Construction", "red", False, 1),
        ("Handover", "teal", True, 2)]
    assert t.branches[0].tasks() == [("Site visit", 2), ("Brief signed", 1)]
    assert TemplateBranch.query.count() == 3


def test_a_custom_template_builds_a_project(client, db):
    from models import Template
    user = make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "lifecycle"})
    t = Template.query.one()
    client.post(f"/settings/templates/{t.id}", data={
        "name": "Two step",
        "branch_name": ["Plan", "Do"],
        "branch_hue": ["blue", "green"],
        "branch_waits_1": "1",
        "branch_tasks": ["Write it down | 3", "Ship it"],
    })
    client.post("/plots/new", data={"name": "Real one", "starter": f"custom:{t.id}",
                                       "cadence_days": "14", "phase": "building",
                                       "gate_points": "3", "focused": "1"})
    p = [x for x in user.projects if x.name == "Real one"][0]
    assert [b.name for b in p.branches] == ["Plan", "Do"]
    assert p.branches[1].requires is p.branches[0]
    assert p.branches[1].is_locked          # chained, and Plan is unfinished
    assert [(t2.title, t2.points_max, t2.tier) for t2 in p.branches[0].tasks] == [("Write it down", 3, 1)]


def test_templates_are_private(client, db):
    from models import Template
    owner = make_user("owner@example.com")
    login(client, email="owner@example.com")
    client.post("/settings/templates/new", data={"copy": "simple"})
    t = Template.query.one()
    client.post("/logout")

    other = make_user("other@example.com")
    login(client, email="other@example.com")
    assert client.get(f"/settings/templates/{t.id}").status_code == 404
    assert client.post(f"/settings/templates/{t.id}/delete").status_code == 404
    assert f"custom:{t.id}" not in client.get("/plots/new").data.decode()
    # ...and naming it on a project create simply yields no branches.
    client.post("/plots/new", data={"name": "Sneaky", "starter": f"custom:{t.id}",
                                       "cadence_days": "14", "phase": "idea", "gate_points": "3"})
    assert other.projects[0].branches == []


def test_deleting_a_template_leaves_its_projects_alone(client, db):
    from models import Template
    user = make_user()
    login(client)
    client.post("/settings/templates/new", data={"copy": "simple"})
    t = Template.query.one()
    client.post("/plots/new", data={"name": "Built from it", "starter": f"custom:{t.id}",
                                       "cadence_days": "14", "phase": "idea", "gate_points": "3"})
    client.post(f"/settings/templates/{t.id}/delete")
    db.session.expire_all()
    assert Template.query.count() == 0
    assert len([b.name for b in user.projects[0].branches]) == 3
