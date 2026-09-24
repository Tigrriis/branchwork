"""Old /projects/, /branches/ and /tasks/ links redirect to the renamed paths."""
from conftest import login, make_branch, make_project, make_task, make_user


def test_old_paths_redirect_permanently(client):
    for old, new in (("/projects/5", "/plots/5"),
                     ("/projects/5/list?sort=points", "/plots/5/list?sort=points"),
                     ("/branches/3/tasks/new", "/schemes/3/machinations/new"),
                     ("/tasks/9/threads", "/machinations/9/threads")):
        r = client.get(old)
        assert r.status_code == 308, old
        assert r.headers["Location"] == new, old


def test_old_page_link_lands_on_the_plot(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    r = client.get(f"/projects/{project.id}", follow_redirects=True)
    assert r.status_code == 200
    assert r.request.path == f"/plots/{project.id}"


def test_post_from_a_stale_page_keeps_its_body(client, db):
    user = make_user()
    login(client)
    task = make_task(make_branch(make_project(user)), "A", tier=1, points_max=2)
    r = client.post(f"/tasks/{task.id}/points", json={"delta": 1}, follow_redirects=True)
    assert r.status_code == 200
    db.session.refresh(task)
    assert task.points_done == 1
