"""Dragging a machination's tile to another tier or scheme of its plot."""
from conftest import (copy_in, login, make_branch, make_project, make_task, make_user,
                      sealed)
import copytext
from models import Note


def _move(client, task, branch, tier):
    return client.post(f"/machinations/{task.id}/move",
                       json={"branch_id": branch.id, "tier": tier})


def test_a_tile_moves_to_another_scheme_at_the_end_of_the_tier(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    build = make_branch(project, "Build")
    sketch = make_task(design, "Sketch", points_max=2, points_done=2)
    make_task(build, "Weld")
    make_task(build, "Paint")
    note = Note(project=project, branch=design, task=sketch, title=sealed("t"), body=sealed("b"))
    db.session.add(note)
    db.session.commit()

    r = _move(client, sketch, build, 1)
    assert r.status_code == 200
    body = r.get_json()
    assert body["moved"] and f'data-task="{sketch.id}"' in body["html"]
    assert body["points_done"] == 2 and body["points_max"] == 4

    db.session.expire_all()
    assert sketch.branch_id == build.id and sketch.tier == 1
    # Last in its new tier, with its points kept.
    assert [t.title for t in build.tasks] == ["Weld", "Paint", "Sketch"]
    assert sketch.points_done == 2
    # Its note follows it to the new scheme's folder.
    assert db.session.get(Note, note.id).branch_id == build.id
    assert project.events[-1].kind == "task"


def test_a_tile_moves_between_tiers_and_onto_a_new_one(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    a = make_task(design, "A")
    make_task(design, "B", tier=2)

    assert _move(client, a, design, 2).get_json()["moved"]
    db.session.expire_all()
    assert a.tier == 2 and [t.title for t in design.tasks] == ["B", "A"]

    # The "+ New tier" space carries the scheme's next tier.
    assert _move(client, a, design, design.next_tier).get_json()["moved"]
    db.session.expire_all()
    assert a.tier == 3


def test_dropping_a_tile_where_it_already_is_changes_nothing(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    a = make_task(design, "A")
    events = len(project.events)
    body = _move(client, a, design, 1).get_json()
    assert body["moved"] is False
    db.session.expire_all()
    assert len(project.events) == events


def test_a_tile_cannot_move_to_another_plot_or_someone_elses(client, db):
    user = make_user()
    login(client)
    home, away = make_project(user), make_project(user)
    design = make_branch(home, "Design")
    elsewhere = make_branch(away, "Elsewhere")
    a = make_task(design, "A")

    r = _move(client, a, elsewhere, 1)
    assert r.status_code == 404 and r.get_json()["message"] == copytext.tx("scheme.not_in_plot")
    r = client.post(f"/machinations/{a.id}/move", json={"branch_id": "nope", "tier": 1})
    assert r.status_code == 404

    theirs = make_task(make_branch(make_project(make_user("someone@example.com")), "X"), "Theirs")
    assert _move(client, theirs, design, 1).status_code == 404
    db.session.expire_all()
    assert a.branch_id == design.id


def test_a_full_scheme_refuses_another_tile(client, app, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build")
    a = make_task(design, "A")
    for i in range(app.config["MAX_TASKS_PER_BRANCH"]):
        make_task(build, f"T{i}")
    r = _move(client, a, build, 1)
    assert r.status_code == 409 and r.get_json()["error"] == "full"


def test_tiles_are_draggable_and_tiers_say_where_they_are(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    a = make_task(design, "A")
    html = client.get(f"/plots/{project.id}").data.decode()
    assert f'data-task="{a.id}" draggable="true"' in html
    assert f'data-branch="{design.id}" data-tier="1"' in html
    assert f'data-branch="{design.id}" data-tier="2"' in html   # its "+ New tier"
    assert copy_in(html, "tree.click_hint")
