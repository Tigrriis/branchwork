"""Notes: a notebook per plot, foldered by scheme and machination.

Titles and bodies are sealed in the browser, so these tests send stand-ins
in the sealed shape (``conftest.sealed``); the server never looks inside.
"""
from conftest import copy_in, login, make_branch, make_project, make_task, make_user, make_vault, sealed
from models import ActivityEvent, Note


def make_user_with_vault(*args):
    user = make_user(*args)
    make_vault(user)
    return user


def _create(client, project, **payload):
    for field in ("title", "body"):
        if field in payload and not payload[field].startswith("v1."):
            payload[field] = sealed(payload[field])
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
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    brief = make_task(design, "Brief")

    root = _create(client, project, title="Plan", body="# Big plan", folder="plot").get_json()
    assert root["folder"] == "plot"
    scheme = _create(client, project, title="Design notes", body="", folder=f"scheme:{design.id}").get_json()
    assert scheme["folder"] == f"scheme:{design.id}"
    body = sealed("Ask about the lifts")
    res = _create(client, project, title="Lifts", body=body, folder=f"machination:{brief.id}")
    assert res.status_code == 200
    made = res.get_json()
    assert made["folder"] == f"machination:{brief.id}"
    assert made["url"] == f"/plots/{project.id}/notes/{made['id']}"
    # The explorer comes back with the new note in its folder.
    assert f'data-note="{made["id"]}"' in made["explorer"]

    note = db.session.get(Note, made["id"])
    assert (note.task_id, note.branch_id, note.body) == (brief.id, design.id, body)

    # Opened, the sealed note is on the page for the browser to open.
    page = client.get(made["url"]).data.decode()
    assert body in page
    assert 'aria-current="page"' in page

    # Starting a note counts as work on the plot, and keeps its words out of the log.
    events = ActivityEvent.query.filter_by(kind="note").all()
    assert len(events) == 3 and all(e.note is None for e in events)


def test_saving_renaming_and_moving(client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    design = make_branch(project, "Design")
    brief = make_task(design, "Brief")
    made = _create(client, project, title="Plan", body="one", folder="plot").get_json()

    two = sealed("two")
    res = client.post(made["save_url"], json={"body": two})
    assert res.status_code == 200
    # Nothing moved, so no explorer to swap.
    assert "explorer" not in res.get_json()
    assert db.session.get(Note, made["id"]).body == two

    title = sealed("The plan")
    assert client.post(made["save_url"], json={"title": title}).status_code == 200
    moved = client.post(made["save_url"], json={"folder": f"machination:{brief.id}"}).get_json()
    assert moved["folder"] == f"machination:{brief.id}" and "explorer" in moved
    back = client.post(made["save_url"], json={"folder": "plot"}).get_json()
    assert back["folder"] == "plot"
    note = db.session.get(Note, made["id"])
    assert (note.title, note.branch_id, note.task_id) == (title, None, None)


def test_a_folder_must_belong_to_the_plot(client, db):
    user = make_user_with_vault()
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
    user = make_user_with_vault()
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
    owner = make_user_with_vault("owner@example.com")
    project = make_project(owner)
    note = Note(project=project, title=sealed("Secret"), body=sealed("the plan"))
    db.session.add(note)
    db.session.commit()

    intruder = make_user_with_vault("intruder@example.com")
    login(client, "intruder@example.com")
    assert client.get(f"/plots/{project.id}/notes").status_code == 404
    assert client.get(f"/plots/{project.id}/notes/{note.id}").status_code == 404
    assert _create(client, project, title="Mine", body="", folder="plot").status_code == 404
    assert client.post(f"/notes/{note.id}", json={"body": sealed("gone")}).status_code == 404
    assert client.post(f"/notes/{note.id}/delete").status_code == 404
    assert db.session.get(Note, note.id).body == note.body

    # A note only opens under its own plot's address.
    other = make_project(intruder)
    assert client.get(f"/plots/{other.id}/notes/{note.id}").status_code == 404


def test_deleting_a_note(client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    made = _create(client, project, title="Plan", body="", folder="plot").get_json()
    res = client.post(made["delete_url"], follow_redirects=True)
    assert copy_in(res.data, "notes.deleted")
    assert Note.query.count() == 0


def test_limits(app, client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    # The browser holds the real limit, on the words; the server can only
    # bound the sealed text, which runs up to six times longer.
    app.config["MAX_NOTE_CHARS"] = 10
    res = _create(client, project, title="Plan", body="x" * 100, folder="plot")
    assert res.status_code == 413 and copy_in(res.get_json()["message"], "notes.too_long")
    made = _create(client, project, title="Plan", body="x" * 10, folder="plot").get_json()
    assert client.post(made["save_url"], json={"body": sealed("y" * 100)}).status_code == 413

    app.config["MAX_NOTES_PER_PROJECT"] = 1
    res = _create(client, project, title="Another", body="", folder="plot")
    assert res.status_code == 409 and copy_in(res.get_json()["message"], "notes.limit")


def _note_on(db, task, title="Note"):
    note = Note(project=task.branch.project, title=sealed(title), body=sealed("words"))
    db.session.add(note)
    note.file_under(task)
    db.session.commit()
    return note


def test_a_tile_counts_its_notes(client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    bare, one, two, waiting = (make_task(branch, name) for name in ("Bare", "One", "Two", "Waiting"))
    only = _note_on(db, one)
    _note_on(db, two), _note_on(db, two)
    waiting.notes = "From the old notes box"
    db.session.commit()

    html = client.get(f"/plots/{project.id}").data.decode()
    assert html.count('class="tile__notes"') == 3
    # One note opens it; more, or text still to become a note, open the folder.
    assert f'href="/plots/{project.id}/notes/{only.id}"' in html
    assert f'href="/plots/{project.id}/notes?machination={two.id}"' in html
    assert f'href="/plots/{project.id}/notes?machination={waiting.id}"' in html
    assert copy_in(html, "tree.notes_count", n=2)
    # The old text is not shown on the tree, not even in a tooltip.
    assert "From the old notes box" not in html


def test_the_notes_page_opens_on_a_machinations_folder(client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    task = make_task(make_branch(project), "Brief")
    html = client.get(f"/plots/{project.id}/notes?machination={task.id}").data.decode()
    assert f'data-folder="machination:{task.id}" open' in html
    elsewhere = make_task(make_branch(make_project(user)), "Far away")
    assert client.get(f"/plots/{project.id}/notes?machination={elsewhere.id}").status_code == 404


def test_the_machination_form_lists_its_notes_in_place_of_the_box(client, db):
    user = make_user_with_vault()
    login(client)
    project = make_project(user)
    task = make_task(make_branch(project), "Brief")
    note = _note_on(db, task)
    task.notes = "Old words"
    db.session.commit()

    html = client.get(f"/machinations/{task.id}/edit").data.decode()
    assert 'name="notes"' not in html
    assert note.title in html and f"/plots/{project.id}/notes/{note.id}" in html
    assert f"/plots/{project.id}/notes/new?machination={task.id}" in html
    assert copy_in(html, "machination.notes_waiting") and "tasknotes.js" in html

    # Saving the form leaves the waiting text alone for the browser to seal.
    client.post(f"/machinations/{task.id}/edit", data={
        "title": "Brief", "branch_id": task.branch_id, "tier": 1, "points_max": 1, "points_done": 0})
    db.session.expire_all()
    assert db.session.get(type(task), task.id).notes == "Old words"

    # A new machination has nowhere to file a note yet.
    html = client.get(f"/schemes/{task.branch_id}/machinations/new").data.decode()
    assert copy_in(html, "machination.notes_after_save")
