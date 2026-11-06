"""Threads: sequence links between machinations, and the rules that hold."""
from conftest import copy_in, login, make_branch, make_project, make_task, make_ultimate, make_user
from models import Task, Thread, Ultimate


def _thread(client, source, target):
    return client.post(f"/machinations/{source.id}/threads", json={"to": target.id})


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
    assert thread.project_id == project.id
    assert not thread.started and not thread.done

    # The answer carries the re-rendered tree, with the arrow in it.
    html = res.get_json()["html"]
    assert f'data-from="{brief.id}" data-to="{dig.id}"' in html
    assert "thread--started" not in html and "thread--done" not in html

    # Part way through the near end is not a start: the arrow stays grey.
    brief.set_points(1)
    db.session.commit()
    assert not Thread.query.one().started
    assert "thread--started" not in client.get(f"/plots/{project.id}").data.decode()

    # Finishing the near end starts the sequence, but one end alone is not
    # the whole of it: orange.
    brief.set_points(2)
    db.session.commit()
    thread = Thread.query.one()
    assert thread.started and not thread.done
    html = client.get(f"/plots/{project.id}").data.decode()
    assert "thread--started" in html and "thread--done" not in html

    # Both ends finished turns it green.
    dig.set_points(dig.points_max)
    db.session.commit()
    assert Thread.query.one().done
    assert "thread--done" in client.get(f"/plots/{project.id}").data.decode()


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
    client.post(f"/machinations/{second.id}/delete")
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


def test_either_end_of_a_thread_moves_to_another_tile(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief, survey = make_task(design, "Brief"), make_task(design, "Survey")
    dig = make_task(build, "Dig")
    keys = make_ultimate(build, "Keys handed over")
    _thread(client, brief, dig)
    thread = Thread.query.one()

    # A moved thread is a fresh row, so it is looked up again after each move.
    def move(**payload):
        return client.post(f"/threads/{Thread.query.one().id}/move", json=payload)

    # The far end onto another tile, and the tree comes back redrawn.
    res = move(end="to", to=survey.id)
    assert res.status_code == 200 and res.get_json()["moved"]
    assert f'data-from="{brief.id}" data-to="{survey.id}"' in res.get_json()["html"]
    # The near end too.
    assert move(end="from", to=dig.id).status_code == 200
    thread = Thread.query.one()
    assert (thread.from_task_id, thread.to_task_id) == (dig.id, survey.id)
    # The far end can land on an ultimate; the near end cannot.
    assert move(end="to", to_ultimate=keys.id).status_code == 200
    assert Thread.query.one().target is keys
    assert move(end="from", to_ultimate=keys.id).status_code == 409
    assert Thread.query.one().from_task_id == dig.id
    # Back where it was is a no-op, not a refusal.
    res = move(end="to", to_ultimate=keys.id)
    assert res.status_code == 200 and not res.get_json()["moved"]
    assert Thread.query.count() == 1


def test_moving_an_end_keeps_the_rules(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    a, b, c = (make_task(branch, name) for name in ("A", "B", "C"))
    elsewhere = make_task(make_branch(make_project(user)), "Far away")
    _thread(client, a, b)
    _thread(client, b, c)

    # The thread leading from a task, found afresh: a move makes a new row.
    def move(source, **payload):
        thread = Thread.query.filter_by(from_task_id=source.id).one()
        return client.post(f"/threads/{thread.id}/move", json=payload)

    assert copy_in(move(a, end="to", to=a.id).get_json()["message"], "thread.same")
    assert copy_in(move(a, end="to", to=elsewhere.id).get_json()["message"], "thread.not_in_plot")
    # b → c swung onto a would loop back through a → b.
    assert copy_in(move(b, end="to", to=a.id).get_json()["message"], "thread.loop")
    # a → b moved to a → c duplicates nothing, and then b → c's near end
    # onto a would be a second a → c.
    assert move(a, end="to", to=c.id).status_code == 200
    assert copy_in(move(b, end="from", to=a.id).get_json()["message"], "thread.exists")
    # Its own old line never counts against it: a → c can swing straight
    # back to a → b.
    assert move(a, end="to", to=b.id).status_code == 200
    assert Thread.query.count() == 2

    # Someone else's thread is not found.
    make_user("intruder@example.com")
    client.post("/logout")
    login(client, email="intruder@example.com")
    assert move(a, end="to", to=c.id).status_code == 404


def test_the_machination_form_no_longer_edits_threads(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief, dig = make_task(design, "Brief"), make_task(build, "Dig")
    _thread(client, brief, dig)
    form = client.get(f"/machinations/{dig.id}/edit").data.decode()
    assert not copy_in(form, "thread.follows") and "unthread-" not in form
    # A stray "follows" field in a post is ignored.
    client.post(f"/machinations/{dig.id}/edit", data={"title": "Dig", "icon": "bomb", "tier": "1",
                                               "points_max": "1", "points_done": "0",
                                               "follows": str(brief.id)})
    assert Thread.query.count() == 1


def _thread_into(client, source, ultimate):
    return client.post(f"/machinations/{source.id}/threads", json={"to_ultimate": ultimate.id})


def test_a_machination_threads_into_an_ultimate(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief", points_max=2)
    dig = make_task(build, "Dig", points_max=3)
    keys = make_ultimate(build, "Keys handed over")

    res = _thread_into(client, brief, keys)
    assert res.status_code == 200
    thread = Thread.query.one()
    assert (thread.from_task_id, thread.to_task_id, thread.to_ultimate_id) == (brief.id, None, keys.id)
    assert thread.target is keys and keys.threads_in == [thread]
    assert not thread.started and not thread.done
    html = res.get_json()["html"]
    assert f'data-from="{brief.id}" data-to-ultimate="{keys.id}"' in html
    assert "data-to=" not in html

    # Repeats and other plots are refused like any thread; an ultimate never
    # leads on, so it cannot close a loop.
    assert copy_in(_thread_into(client, brief, keys).get_json()["message"], "thread.exists")
    far = make_ultimate(make_branch(make_project(user)), "Far away")
    assert copy_in(_thread_into(client, brief, far).get_json()["message"], "thread.not_in_plot")
    assert _thread(client, dig, brief).status_code == 200
    assert Thread.query.count() == 2

    # Under way once the near end is done, green once the ultimate is claimed.
    brief.set_points(2); db.session.commit()
    thread = db.session.get(Thread, thread.id)
    assert thread.started and not thread.done
    dig.set_points(3); keys.set_achieved(True); db.session.commit()
    assert db.session.get(Thread, thread.id).done
    assert "thread--done" in client.get(f"/plots/{project.id}").data.decode()

    # The ultimate takes its threads with it; the other thread stays.
    client.post(f"/ultimates/{keys.id}/delete")
    assert Thread.query.count() == 1 and Thread.query.one().to_task_id == brief.id


def test_the_ultimate_form_threads_into_it(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    design, build = make_branch(project, "Design"), make_branch(project, "Build", "red")
    brief = make_task(design, "Brief")
    dig = make_task(build, "Dig")
    keys = make_ultimate(build, "Keys handed over")
    _thread_into(client, brief, keys)
    thread = Thread.query.one()

    # "Comes after" on the ultimate form, which also lists and removes.
    form = client.get(f"/schemes/{build.id}/ultimate").data.decode()
    assert copy_in(form, "thread.follows") and f'id="unthread-{thread.id}"' in form
    client.post(f"/schemes/{build.id}/ultimate",
                data={"title": "Keys handed over", "icon": "bomb", "follows": str(dig.id)})
    assert Thread.query.count() == 2
    assert {t.from_task_id for t in keys.threads_in} == {brief.id, dig.id}
    client.post(f"/threads/{thread.id}/delete", data={"next": f"/schemes/{build.id}/ultimate"},
                follow_redirects=True)
    assert Thread.query.count() == 1

    # A refusal from the ultimate form is flashed and the save still stands.
    r = client.post(f"/schemes/{build.id}/ultimate",
                    data={"title": "Handover", "icon": "bomb", "follows": str(dig.id)},
                    follow_redirects=True)
    assert copy_in(r.data, "thread.exists") and Ultimate.query.one().title == "Handover"
