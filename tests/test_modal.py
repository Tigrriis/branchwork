"""Forms in the pop-up: fetched bare, and a save answered as JSON."""
from conftest import copy_in, login, make_branch, make_project, make_task, make_user
from models import Task

MODAL = {"X-Requested-With": "modal"}


def test_a_form_asked_for_by_the_popup_comes_bare(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    task = make_task(make_branch(project), "Brief")

    page = client.get(f"/machinations/{task.id}/edit").data.decode()
    bare = client.get(f"/machinations/{task.id}/edit", headers=MODAL).data.decode()
    assert "<html" in page and 'class="topbar"' in page and "data-modal-body" not in page
    assert "<html" not in bare and 'class="topbar"' not in bare
    assert 'data-modal-body' in bare and copy_in(bare, "machination.title_edit")
    assert 'value="Brief"' in bare
    # The links that open it say so.
    tree = client.get(f"/plots/{project.id}").data.decode()
    assert f'href="/machinations/{task.id}/edit" data-modal' in tree


def test_a_save_from_the_popup_answers_json_with_its_messages(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    task = make_task(branch, "Brief")
    data = {"title": "Brief and survey", "icon": "bomb", "tier": "1", "points_max": "2", "points_done": "1"}

    res = client.post(f"/machinations/{task.id}/edit", data=data, headers=MODAL)
    assert res.status_code == 200 and res.is_json
    body = res.get_json()
    assert body["redirect"].endswith(f"/plots/{project.id}")
    assert body["flashes"] == [["success", str(__import__("copytext").tx("machination.saved"))]]
    assert db.session.get(Task, task.id).title == "Brief and survey"
    # Read once, the messages do not show again on the next page.
    assert not copy_in(client.get(f"/plots/{project.id}").data, "machination.saved")

    # A bad save comes back as the form, bare, with what was wrong at its top.
    res = client.post(f"/machinations/{task.id}/edit", data={**data, "title": ""}, headers=MODAL)
    assert res.status_code == 200 and not res.is_json
    html = res.data.decode()
    assert "data-modal-body" in html and copy_in(html, "machination.title_required")

    # Without the header a save redirects as it always did.
    res = client.post(f"/machinations/{task.id}/edit", data=data)
    assert res.status_code == 302


def test_the_plot_page_refreshes_in_place_after_a_popup_save(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    make_task(branch, "Brief", points_max=2, points_done=1)
    res = client.get(f"/plots/{project.id}/refresh")
    assert res.status_code == 200
    body = res.get_json()
    assert f'data-branch="{branch.id}"' in body["html"]
    assert copy_in(body["routines"], "routines.empty") and body["has_routines"] is False
    assert (body["points_done"], body["points_max"], body["percent"]) == (1, 2, 50)
    assert body["counts"] == {"full": 0, "part": 1, "empty": 0}

    make_user("other@example.com")
    client.post("/logout")
    login(client, email="other@example.com")
    assert client.get(f"/plots/{project.id}/refresh").status_code == 404
