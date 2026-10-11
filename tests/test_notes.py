"""Notes: a notebook per plot, foldered by scheme and machination."""
from conftest import copy_in, login, make_branch, make_project, make_task, make_user
from models import ActivityEvent, Note


def _create(client, project, **payload):
    return client.post(f"/plots/{project.id}/notes", json=payload)


def test_the_notes_tab_replaces_the_list_tab(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    html = client.get(f"/plots/{project.id}").data.decode()
    assert f'href="/plots/{project.id}/notes"' in html
    assert f'href="/plots/{project.id}/list"' not in html
    assert copy_in(html, "tree.tab_notes")


def test_every_machination_has_a_pencil_into_its_folder(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    task = make_task(make_branch(project), "Brief")
    html = client.get(f"/plots/{project.id}").data.decode()
    assert f'href="/plots/{project.id}/notes/new?machination={task.id}"' in html

    # Following it opens a draft filed there, and saves nothing yet.
    page = client.get(f"/plots/{project.id}/notes/new?machination={task.id}").data.decode()
    assert f'"folder": "machination:{task.id}"' in page
    assert f'<option value="machination:{task.id}" selected>' in page
    assert Note.query.count() == 0


def test_the_explorer_mirrors_the_plot(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief")
    html = client.get(f"/plots/{project.id}/notes").data.decode()
    for folder in (f"scheme:{design.id}", f"scheme:{build.id}", f"machination:{brief.id}"):
        assert f'data-drop-folder="{folder}"' in html
    assert 'data-drop-folder="plot"' in html
    assert copy_in(html, "notes.empty")


def test_creating_a_note_at_each_level(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    brief = make_task(design, "Brief")

    root = _create(client, project, title="Plan", body="# Big plan", folder="plot").get_json()
    assert root["folder"] == "plot"
    scheme = _create(client, project, title="Design notes", body="", folder=f"scheme:{design.id}").get_json()
    assert scheme["folder"] == f"scheme:{design.id}"
    res = _create(client, project, title="", body="Ask about the lifts", folder=f"machination:{brief.id}")
    assert res.status_code == 200
    made = res.get_json()
    assert made["folder"] == f"machination:{brief.id}"
    assert copy_in(made["title"], "notes.untitled")
    assert made["url"] == f"/plots/{project.id}/notes/{made['id']}"
    # The explorer comes back with the new note in its folder.
    assert f'data-note="{made["id"]}"' in made["explorer"]

    note = db.session.get(Note, made["id"])
    assert (note.task_id, note.branch_id, note.body) == (brief.id, design.id, "Ask about the lifts")

    # Opened, the note's words are on the page for the editor.
    page = client.get(made["url"]).data.decode()
    assert "Ask about the lifts" in page
    assert 'aria-current="page"' in page

    # Starting a note counts as work on the plot, and keeps its words out of the log.
    events = ActivityEvent.query.filter_by(kind="note").all()
    assert len(events) == 3 and all(e.note is None for e in events)


def test_saving_renaming_and_moving(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    brief = make_task(design, "Brief")
    made = _create(client, project, title="Plan", body="one", folder="plot").get_json()

    res = client.post(made["save_url"], json={"body": "two"})
    assert res.status_code == 200
    # Nothing moved, so no explorer to swap.
    assert "explorer" not in res.get_json()
    assert db.session.get(Note, made["id"]).body == "two"

    assert client.post(made["save_url"], json={"title": "  The   plan "}).get_json()["title"] == "The plan"
    moved = client.post(made["save_url"], json={"folder": f"machination:{brief.id}"}).get_json()
    assert moved["folder"] == f"machination:{brief.id}" and "explorer" in moved
    back = client.post(made["save_url"], json={"folder": "plot"}).get_json()
    assert back["folder"] == "plot"
    note = db.session.get(Note, made["id"])
    assert (note.title, note.branch_id, note.task_id) == ("The plan", None, None)


def test_a_folder_must_belong_to_the_plot(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    elsewhere = make_task(make_branch(make_project(user)), "Far away")
    for folder in (f"machination:{elsewhere.id}", f"scheme:{elsewhere.branch_id}", "scheme:x", "attic"):
        res = _create(client, project, title="Plan", body="", folder=folder)
        assert res.status_code == 404
        assert copy_in(res.get_json()["message"], "notes.not_in_plot")
    made = _create(client, project, title="Plan", body="", folder="plot").get_json()
    assert client.post(made["save_url"], json={"folder": f"machination:{elsewhere.id}"}).status_code == 404
    assert client.get(f"/plots/{project.id}/notes/new?machination={elsewhere.id}").status_code == 404
    assert Note.query.one().folder == "plot"


def test_notes_fall_back_a_folder_rather_than_vanish(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief")
    made = _create(client, project, title="Plan", body="", folder=f"machination:{brief.id}").get_json()

    # A machination moving scheme takes its notes with it...
    client.post(f"/machinations/{brief.id}/edit", data={
        "title": "Brief", "branch_id": build.id, "tier": 1, "points_max": 1, "points_done": 0})
    note = db.session.get(Note, made["id"])
    assert (note.task_id, note.branch_id) == (brief.id, build.id)

    # ...deleting it leaves them in its scheme...
    client.post(f"/machinations/{brief.id}/delete")
    db.session.expire_all()
    note = db.session.get(Note, made["id"])
    assert note.folder == f"scheme:{build.id}"

    # ...and deleting the scheme leaves them at the root.
    client.post(f"/schemes/{build.id}/delete")
    db.session.expire_all()
    assert db.session.get(Note, made["id"]).folder == "plot"

    # Only deleting the plot takes them.
    client.post(f"/plots/{project.id}/delete")
    assert Note.query.count() == 0


def test_notes_are_owner_only(client, db):
    owner = make_user("owner@example.com")
    project = make_project(owner)
    note = Note(project=project, title="Secret", body="the plan")
    db.session.add(note)
    db.session.commit()

    intruder = make_user("intruder@example.com")
    login(client, "intruder@example.com")
    assert client.get(f"/plots/{project.id}/notes").status_code == 404
    assert client.get(f"/plots/{project.id}/notes/{note.id}").status_code == 404
    assert _create(client, project, title="Mine", body="", folder="plot").status_code == 404
    assert client.post(f"/notes/{note.id}", json={"body": "gone"}).status_code == 404
    assert client.post(f"/notes/{note.id}/delete").status_code == 404
    assert db.session.get(Note, note.id).body == "the plan"

    # A note only opens under its own plot's address.
    other = make_project(intruder)
    assert client.get(f"/plots/{other.id}/notes/{note.id}").status_code == 404


def test_deleting_a_note(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    made = _create(client, project, title="Plan", body="", folder="plot").get_json()
    res = client.post(made["delete_url"], follow_redirects=True)
    assert copy_in(res.data, "notes.deleted")
    assert Note.query.count() == 0


def test_limits(app, client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    app.config["MAX_NOTE_CHARS"] = 10
    res = _create(client, project, title="Plan", body="x" * 11, folder="plot")
    assert res.status_code == 413 and copy_in(res.get_json()["message"], "notes.too_long")
    made = _create(client, project, title="Plan", body="x" * 10, folder="plot").get_json()
    assert client.post(made["save_url"], json={"body": "y" * 11}).status_code == 413

    app.config["MAX_NOTES_PER_PROJECT"] = 1
    res = _create(client, project, title="Another", body="", folder="plot")
    assert res.status_code == 409 and copy_in(res.get_json()["message"], "notes.limit")
