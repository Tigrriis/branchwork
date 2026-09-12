"""Tempo, phases, inbox, review and git sync."""
import os
import subprocess
from datetime import date, datetime, timedelta, timezone

from conftest import login, make_branch, make_project, make_task, make_user
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
    client.post(f"/tasks/{task.id}/points", json={"delta": 1})
    db.session.refresh(p)
    assert p.days_since_touch == 0
    kinds = [(e.kind, e.delta) for e in p.events]
    assert ("points", 1) in kinds
    # a no-op change (already at max) records nothing
    client.post(f"/tasks/{task.id}/points", json={"delta": 1})
    client.post(f"/tasks/{task.id}/points", json={"delta": 1})
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
    assert "Stale one" in html and "1 due for a touch" in html
    assert "1 without a next action" in html
    assert "Fresh one" in html


def test_wip_limit_on_building(client, db, app):
    app.config["WIP_BUILDING_LIMIT"] = 2
    user = make_user()
    login(client)
    for i in range(2):
        p = make_project(user); p.phase = "building"
    db.session.commit()
    third = make_project(user)
    r = client.post(f"/projects/{third.id}/phase", data={"phase": "building"}, follow_redirects=True)
    assert b"Building is full" in r.data
    db.session.refresh(third)
    assert third.phase == "idea"
    # moving within building (no-op) or elsewhere is fine
    r = client.post(f"/projects/{third.id}/phase", data={"phase": "exploring"}, follow_redirects=True)
    db.session.refresh(third)
    assert third.phase == "exploring"
    assert any(e.kind == "phase" and "Exploring" in e.note for e in third.events)


def test_park_and_resurface(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post(f"/projects/{p.id}/phase", data={"phase": "parked", "parked_until": yesterday})
    db.session.refresh(p)
    assert p.phase == "parked" and p.parked_expired
    html = client.get("/").data.decode()
    assert "Back from the shelf" in html
    client.post(f"/projects/{p.id}/phase", data={"phase": "exploring"})
    db.session.refresh(p)
    assert p.phase == "exploring" and p.parked_until is None


def test_inbox_add_file_park_done(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    client.post("/inbox", data={"text": "Try the new router\nwith notes"})
    item = InboxItem.query.one()
    assert item.status == "open"

    # filing into a project with no branches creates a Backlog branch + task
    client.post(f"/inbox/{item.id}/file", data={"project_id": str(p.id)})
    db.session.refresh(item); db.session.refresh(p)
    assert item.status == "filed"
    assert p.branches[0].name == "Backlog"
    task = Task.query.one()
    assert task.title == "Try the new router" and task.notes.startswith("Try the new router")
    assert any(e.kind == "task" for e in p.events)

    client.post("/inbox", data={"text": "Later idea"})
    later = InboxItem.query.filter_by(text="Later idea").one()
    client.post(f"/inbox/{later.id}/park", data={"revisit_on": (date.today() + timedelta(days=10)).isoformat()})
    db.session.refresh(later)
    assert later.status == "parked" and not later.resurfaced
    later.revisit_on = date.today() - timedelta(days=1); db.session.commit()
    assert later.status == "open" and later.resurfaced

    client.post(f"/inbox/{later.id}/done")
    db.session.refresh(later)
    assert later.status == "done"


def test_inbox_is_per_user(client, db):
    owner = make_user("a@example.com")
    db.session.add(InboxItem(user=owner, text="mine")); db.session.commit()
    item = InboxItem.query.one()
    make_user("b@example.com")
    login(client, email="b@example.com")
    assert client.post(f"/inbox/{item.id}/done").status_code == 404
    assert b"mine" not in client.get("/").data


def test_review_shows_every_project_at_once_and_marks_decided(client, db):
    user = make_user()
    login(client)
    a = make_project(user); a.name, a.phase = "Alpha", "idea"
    b = make_project(user); b.name, b.phase = "Beta", "building"
    db.session.commit()

    html = client.get("/review").data.decode()
    assert "0 of 2 decided" in html
    # The whole scope is on the page, not one project at a time.
    assert "Alpha" in html and "Beta" in html
    assert html.count('class="review-card ') == 2
    assert "is-decided" not in html

    r = client.post(f"/review/{a.id}", data={"decision": "advance",
                                             "objective": "Prove the idea is worth building",
                                             "next_action": "Write the spec", "done": ""})
    # Redirects back to the same page, anchored to the card just decided.
    assert r.status_code == 302
    assert f"done={a.id}" in r.headers["Location"] and f"#p{a.id}" in r.headers["Location"]
    db.session.refresh(a)
    assert a.phase == "exploring" and a.next_action == "Write the spec"
    assert a.objective == "Prove the idea is worth building"
    assert any(e.kind == "review" for e in a.events)

    # Alpha stays on the page, now marked, and Beta is still there undecided.
    html = client.get(f"/review?done={a.id}").data.decode()
    assert "1 of 2 decided" in html
    assert "Alpha" in html and "Beta" in html
    assert html.count("is-decided") == 1

    client.post(f"/review/{b.id}", data={"decision": "drop", "done": str(a.id)})
    db.session.refresh(b)
    assert b.phase == "dropped"
    # Dropped, so no longer active: one project left under review, and it is
    # decided, so the banner shows.
    html = client.get(f"/review?done={a.id},{b.id}").data.decode()
    assert "1 of 1 decided" in html
    assert "Every project has a decision" in html


def test_review_ignores_stale_done_ids(client, db):
    """A done list naming projects that are gone must not skew the count."""
    user = make_user()
    login(client)
    p = make_project(user); p.phase = "building"
    db.session.commit()
    html = client.get(f"/review?done={p.id},9999").data.decode()
    assert "1 of 1 decided" in html


def test_objective_saves_from_the_project_form(client, db):
    user = make_user()
    login(client)
    client.post("/projects/new", data={"name": "Arete", "starter": "blank", "cadence_days": "14",
                                       "phase": "building", "gate_points": "3",
                                       "objective": "Fewer hours per job, same fee",
                                       "next_action": "Time three jobs end to end"})
    p = user.projects[0]
    assert p.objective == "Fewer hours per job, same fee"
    html = client.get(f"/projects/{p.id}/edit").data.decode()
    assert "Fewer hours per job, same fee" in html


def test_new_project_starter_creates_chained_branches(client, db):
    user = make_user()
    login(client)
    client.post("/projects/new", data={"name": "Rocket", "starter": "lifecycle", "cadence_days": "7",
                                       "phase": "idea", "gate_points": "3"})
    p = user.projects[0]
    names = [b.name for b in p.branches]
    assert names == ["Idea", "Prototype", "Build", "Launch", "Maintain"]
    assert p.branches[1].requires is p.branches[0] and p.branches[0].requires is None
    assert p.branches[1].is_locked and not p.branches[0].is_locked
    assert p.cadence_days == 7 and any(e.kind == "touch" for e in p.events)


def test_sync_git_records_commits_once(db, tmp_path):
    user = make_user()
    p = make_project(user)
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    for i in range(2):
        (repo / f"f{i}.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, env=env)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", f"commit {i}"], check=True, env=env)
    p.repo_path = str(repo); _age(p, 40); db.session.commit()
    assert sync_project(p) == 2
    db.session.commit()
    assert p.days_since_touch == 0
    assert sync_project(p) == 0
    assert sorted(e.note.split(" ", 1)[1] for e in p.events if e.kind == "git") == ["commit 0", "commit 1"]


def test_business_starter_seeds_unchained_areas_with_mapping_tasks(client, db):
    user = make_user()
    login(client)
    client.post("/projects/new", data={"name": "Arete", "starter": "business",
                                       "cadence_days": "7", "phase": "maintaining",
                                       "gate_points": "3"})
    p = user.projects[0]
    assert [b.name for b in p.branches] == [
        "Sales & marketing", "Delivery", "Finance & admin", "People", "Systems & tools"]

    # An operating business cannot have a whole area locked behind another.
    assert all(b.requires is None and not b.is_locked for b in p.branches)

    # One mapping task per area, seeded through the cascade rather than a
    # direct session.add, so this also guards that wiring.
    assert Task.query.count() == 5
    for branch in p.branches:
        assert [(t.tier, t.points_max, t.points_done) for t in branch.tasks] == [(1, 3, 0)]
        assert branch.tasks[0].title.startswith(("Map", "List"))

    # The mapping task is worth exactly the gate, so finishing it opens tier 2.
    sales = p.branches[0]
    assert sales.tier_open(1) and not sales.tier_open(2)
    sales.tasks[0].set_points(3)
    db.session.commit()
    assert sales.tier_open(2)
    # ...and only for the area you actually mapped.
    assert not p.branches[1].tier_open(2)


def test_starters_are_internally_consistent():
    """Every seeded task names a real branch and a real icon."""
    from icons import ICONS
    from models import HUES
    from starters import STARTERS

    for key, spec in STARTERS.items():
        names = {name for name, _ in spec["branches"]}
        assert all(hue in HUES for _, hue in spec["branches"]), key
        for branch_name, tasks in (spec.get("tasks") or {}).items():
            assert branch_name in names, f"{key}: no branch {branch_name!r}"
            for title, icon, points in tasks:
                assert icon in ICONS, f"{key}: unknown icon {icon!r}"
                assert 1 <= points <= 20 and title
