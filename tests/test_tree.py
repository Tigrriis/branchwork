"""Gate and lock rules, and the points endpoint that enforces them."""
from conftest import login, make_branch, make_project, make_task, make_user


def _points(client, task_id, delta=1):
    return client.post(f"/tasks/{task_id}/points", json={"delta": delta})


def test_tier_two_opens_at_gate(db):
    user = make_user()
    project = make_project(user, gate_points=3)
    branch = make_branch(project)
    a = make_task(branch, "A", tier=1, points_max=2)
    b = make_task(branch, "B", tier=1, points_max=2)
    c = make_task(branch, "C", tier=2)

    rows = branch.tiers()
    assert [r["tier"] for r in rows] == [1, 2]
    assert rows[0]["open"] and not rows[1]["open"]
    assert "Needs 3 points" in rows[1]["reason"]
    assert not c.editable

    a.set_points(2); b.set_points(1); db.session.commit()
    assert branch.tiers()[1]["open"]
    assert c.editable


def test_tier_three_waits_on_tier_two_even_when_full(db):
    user = make_user()
    project = make_project(user, gate_points=3)
    branch = make_branch(project)
    make_task(branch, "A", tier=1, points_max=3, points_done=3)
    make_task(branch, "B", tier=2, points_max=1, points_done=0)
    make_task(branch, "C", tier=3, points_max=1)
    rows = branch.tiers()
    assert rows[1]["open"] and not rows[2]["open"]


def test_branch_locked_until_required_branch_complete(db):
    user = make_user()
    project = make_project(user)
    approvals = make_branch(project, "Approvals", "blue")
    construction = make_branch(project, "Construction", "red", requires=approvals)
    permit = make_task(approvals, "Permit", points_max=2)
    tender = make_task(construction, "Tender")

    assert construction.is_locked
    assert construction.lock_reason == "Opens when Approvals is complete"
    assert not tender.editable
    permit.set_points(2); db.session.commit()
    assert approvals.is_complete and not construction.is_locked
    assert tender.editable


def test_empty_required_branch_is_not_complete(db):
    user = make_user()
    project = make_project(user)
    empty = make_branch(project, "Empty")
    other = make_branch(project, "Other", requires=empty)
    assert other.is_locked


def test_requirement_cycle_degrades_to_locked(db):
    user = make_user()
    project = make_project(user)
    a = make_branch(project, "A")
    b = make_branch(project, "B", requires=a)
    a.requires = b; db.session.commit()
    assert a.is_locked and b.is_locked   # no infinite loop


def test_points_endpoint_updates_and_clamps(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    task = make_task(branch, "Only", points_max=2)

    r = _points(client, task.id, +1)
    assert r.status_code == 200
    body = r.get_json()
    assert body["points_done"] == 1 and body["points_max"] == 2
    assert 'data-task="%d"' % task.id in body["html"]
    assert body["counts"] == {"full": 0, "part": 1, "empty": 0}

    _points(client, task.id, +5)
    db.session.refresh(task)
    assert task.points_done == 2 and task.completed_at is not None

    _points(client, task.id, -1)
    db.session.refresh(task)
    assert task.points_done == 1 and task.completed_at is None


def test_points_endpoint_refuses_locked_tier(client, db):
    user = make_user()
    login(client)
    project = make_project(user, gate_points=3)
    branch = make_branch(project)
    make_task(branch, "A", tier=1, points_max=1)
    gated = make_task(branch, "B", tier=2)
    r = _points(client, gated.id, +1)
    assert r.status_code == 409
    db.session.refresh(gated)
    assert gated.points_done == 0


def test_points_endpoint_is_owner_only(client):
    owner = make_user("owner@example.com")
    project = make_project(owner)
    task = make_task(make_branch(project), "Secret")
    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert _points(client, task.id).status_code == 404


def test_branch_form_rejects_cycle(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    a = make_branch(project, "A")
    b = make_branch(project, "B", requires=a)
    r = client.post(f"/branches/{a.id}/edit", data={"name": "A", "hue": "green",
                                                    "requires_branch_id": str(b.id)},
                    follow_redirects=True)
    assert b"wait on each other" in r.data
    db.session.refresh(a)
    assert a.requires_branch_id is None


def test_deleting_required_branch_unlocks_dependants(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    a = make_branch(project, "A")
    b = make_branch(project, "B", requires=a)
    client.post(f"/branches/{a.id}/delete")
    db.session.refresh(b)
    assert b.requires_branch_id is None and not b.is_locked


def test_new_task_defaults_to_next_tier(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    make_task(branch, "A", tier=1)
    r = client.get(f"/branches/{branch.id}/tasks/new")
    assert b'name="tier" min="1" max="50" value="2"' in r.data
    client.post(f"/branches/{branch.id}/tasks/new?tier=2",
                data={"title": "B", "icon": "hammer", "tier": "2", "points_max": "3", "points_done": "0"})
    db.session.refresh(branch)
    assert [t.tier for t in branch.tasks] == [1, 2]
    assert branch.tasks[1].icon == "hammer" and branch.tasks[1].points_max == 3


def test_tree_page_renders_tiles_and_locks(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    build = make_branch(project, "Build", "red", requires=design)
    make_task(design, "Brief", points_max=2, points_done=1)
    make_task(build, "Dig")
    r = client.get(f"/projects/{project.id}")
    html = r.data.decode()
    assert "tile--part" in html and "1/2" in html
    assert "col--locked" in html and "Opens when Design is complete" in html
    assert "col--red" in html


def test_new_forms_render_without_inserting(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    assert client.get("/projects/new").status_code == 200
    assert client.get(f"/projects/{project.id}/branches/new").status_code == 200
    assert client.get(f"/branches/{branch.id}/tasks/new").status_code == 200
    db.session.rollback()
    assert len(user.projects) == 1 and len(project.branches) == 1 and branch.tasks == []
