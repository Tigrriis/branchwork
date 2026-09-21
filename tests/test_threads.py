"""Threads: sequence links between machinations, and the rules that hold."""
from conftest import copy_in, login, make_branch, make_project, make_task, make_user
from models import Task, Thread


def _thread(client, source, target):
    return client.post(f"/tasks/{source.id}/threads", json={"to": target.id})


def test_threading_two_machinations_across_schemes(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief", points_max=2)
    dig = make_task(build, "Dig")

    res = _thread(client, brief, dig)
    assert res.status_code == 200
    thread = Thread.query.one()
    assert (thread.from_task_id, thread.to_task_id) == (brief.id, dig.id)
    assert thread.project_id == project.id and not thread.done

    # The answer carries the re-rendered tree, with the arrow in it.
    html = res.get_json()["html"]
    assert f'data-from="{brief.id}" data-to="{dig.id}"' in html
    assert "thread--done" not in html

    # One end finished is still an unfinished sequence: the arrow stays orange.
    brief.set_points(2)
    db.session.commit()
    assert not Thread.query.one().done
    assert "thread--done" not in client.get(f"/projects/{project.id}").data.decode()

    # Both ends finished turns it green.
    dig.set_points(dig.points_max)
    db.session.commit()
    assert Thread.query.one().done
    assert "thread--done" in client.get(f"/projects/{project.id}").data.decode()


def test_a_thread_refuses_itself_a_loop_a_repeat_and_another_plot(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    a, b, c = (make_task(branch, name) for name in ("A", "B", "C"))
    elsewhere = make_task(make_branch(make_project(user)), "Far away")

    assert _thread(client, a, a).status_code == 409
    assert copy_in(_thread(client, a, a).get_json()["message"], "thread.same")
    assert copy_in(_thread(client, a, elsewhere).get_json()["message"], "thread.not_in_plot")

    assert _thread(client, a, b).status_code == 200
    assert copy_in(_thread(client, a, b).get_json()["message"], "thread.exists")
    assert _thread(client, b, c).status_code == 200
    # c already leads back to a through b, so a would close the loop.
    assert copy_in(_thread(client, c, a).get_json()["message"], "thread.loop")
    assert Thread.query.count() == 2


def test_threads_are_owner_only_and_go_when_a_machination_does(client, db):
    owner = make_user("owner@example.com")
    project = make_project(owner)
    branch = make_branch(project)
    first, second = make_task(branch, "First"), make_task(branch, "Second")
    db.session.add(Thread(project=project, source=first, target=second))
    db.session.commit()

    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert _thread(client, first, second).status_code == 404
    assert client.post(f"/threads/{Thread.query.one().id}/delete").status_code == 404

    client.post("/logout")                   # signing in again while signed in is a no-op
    login(client, email="owner@example.com")
    client.post(f"/tasks/{second.id}/delete")
    assert Thread.query.count() == 0 and Task.query.count() == 1


def test_a_thread_is_removed_by_its_own_endpoint(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    first, second = make_task(branch, "First"), make_task(branch, "Second")
    _thread(client, first, second)
    thread_id = Thread.query.one().id

    res = client.post(f"/threads/{thread_id}/delete", json={})
    assert res.status_code == 200 and "data-from" not in res.get_json()["html"]
    assert Thread.query.count() == 0


def test_the_machination_form_threads_and_unthreads(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief")
    dig = make_task(build, "Dig")

    # "Comes after" on the form is the route without a mouse.
    form = client.get(f"/tasks/{dig.id}/edit").data.decode()
    assert copy_in(form, "thread.follows") and f'value="{brief.id}"' in form
    client.post(f"/tasks/{dig.id}/edit", data={"title": "Dig", "icon": "bomb", "tier": "1",
                                               "points_max": "1", "points_done": "0",
                                               "follows": str(brief.id)})
    thread = Thread.query.one()
    assert (thread.from_task_id, thread.to_task_id) == (brief.id, dig.id)

    # Both ends list it, and the form posts the removal.
    for task_id in (brief.id, dig.id):
        assert f'id="unthread-{thread.id}"' in client.get(f"/tasks/{task_id}/edit").data.decode()
    client.post(f"/threads/{thread.id}/delete", data={"next": f"/tasks/{dig.id}/edit"},
                follow_redirects=True)
    assert Thread.query.count() == 0


def test_a_refused_thread_from_the_form_says_so(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    only = make_task(branch, "Only")
    r = client.post(f"/tasks/{only.id}/edit", data={"title": "Only", "icon": "bomb", "tier": "1",
                                                   "points_max": "1", "points_done": "0",
                                                   "follows": str(only.id)},
                    follow_redirects=True)
    assert copy_in(r.data, "thread.same")
    assert Thread.query.count() == 0
