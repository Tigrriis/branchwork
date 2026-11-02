"""Moving a scheme to another plot, from the scheme's edit page."""
from conftest import (copy_in, login, make_branch, make_project, make_task, make_ultimate,
                      make_user, sealed)
from models import InboxItem, Note, Project, Thread


def _plot(user, name):
    p = make_project(user)
    p.name = name
    return p


def test_a_scheme_moves_with_its_machinations_ultimate_threads_and_notes(client, db):
    user = make_user()
    login(client)
    home, away = _plot(user, "Home"), _plot(user, "Away")
    stay = make_branch(home, "Stay")
    go = make_branch(home, "Go")
    after = make_branch(home, "After")
    make_branch(away, "Already there")
    a = make_task(go, "First", points_done=1)
    b = make_task(go, "Second", tier=2)
    goal = make_ultimate(go)
    inside = Thread(project=home, source=a, target_task=b)
    into_goal = Thread(project=home, source=b, target_ultimate=goal)
    scheme_note = Note(project=home, branch=go, title=sealed("t"), body=sealed("b"))
    task_note = Note(project=home, branch=go, task=a, title=sealed("t"), body=sealed("b"))
    root_note = Note(project=home, title=sealed("t"), body=sealed("b"))
    db.session.add_all([inside, into_goal, scheme_note, task_note, root_note])
    db.session.commit()
    idea = InboxItem(user=user, text="Was an idea", project=home, task_id=a.id)
    db.session.add(idea)
    db.session.commit()

    r = client.post(f"/schemes/{go.id}/move-to", data={"project_id": str(away.id)},
                    follow_redirects=True)
    assert copy_in(r.data, "scheme.moved", name="Go", plot="Away")
    assert not copy_in(r.data, "scheme.moved_cut", n=0)

    db.session.expire_all()
    assert go.project_id == away.id
    # It lands at the end of its new plot, and the old one closes the gap.
    assert [s.name for s in away.branches] == ["Already there", "Go"]
    assert [(s.name, s.position) for s in home.branches] == [("Stay", 0), ("After", 1)]
    assert [t.title for t in go.tasks] == ["First", "Second"] and go.ultimate.id == goal.id
    # Threads wholly inside the scheme go with it.
    assert {t.id for t in away.threads} == {inside.id, into_goal.id}
    assert home.threads == []
    # So do its notebook folder and the notes in its machinations' folders.
    assert {n.id for n in away.notes} == {scheme_note.id, task_note.id}
    assert [n.id for n in home.notes] == [root_note.id]
    assert db.session.get(Note, task_note.id).folder == f"machination:{a.id}"
    # The idea that became a machination follows it.
    assert db.session.get(InboxItem, idea.id).project_id == away.id
    # Both plots count the move as a touch.
    assert home.events[-1].kind == "touch" and away.events[-1].kind == "touch"
    assert stay.project_id == home.id and after.project_id == home.id


def test_links_that_would_cross_plots_are_cut(client, db):
    user = make_user()
    login(client)
    home, away = _plot(user, "Home"), _plot(user, "Away")
    first = make_branch(home, "First")
    go = make_branch(home, "Go", requires=first)
    later = make_branch(home, "Later", requires=go)
    x = make_task(first, "Outside")
    y = make_task(go, "Inside")
    z = make_task(later, "Also outside")
    later_goal = make_ultimate(later)
    db.session.add_all([
        Thread(project=home, source=x, target_task=y),
        Thread(project=home, source=y, target_task=z),
        Thread(project=home, source=y, target_ultimate=later_goal),
    ])
    db.session.commit()

    # The edit page warns before cutting: three threads and two locks.
    page = client.get(f"/schemes/{go.id}/edit").data
    assert copy_in(page, "scheme.move_confirm", n=5)

    r = client.post(f"/schemes/{go.id}/move-to", data={"project_id": str(away.id)},
                    follow_redirects=True)
    assert copy_in(r.data, "scheme.moved_cut", n=5)
    db.session.expire_all()
    assert db.session.query(Thread).count() == 0
    assert go.requires_branch_id is None and later.requires_branch_id is None
    assert not later.is_locked


def test_a_move_is_refused_to_a_plot_that_is_not_yours_or_is_full(client, app, db):
    user = make_user()
    other = make_user("someone@example.com")
    login(client)
    home, mine = _plot(user, "Home"), _plot(user, "Mine")
    theirs = _plot(other, "Theirs")
    go = make_branch(home, "Go")

    for target in (theirs.id, home.id, 999999, "nope"):
        r = client.post(f"/schemes/{go.id}/move-to", data={"project_id": str(target)},
                        follow_redirects=True)
        assert copy_in(r.data, "scheme.move_pick")
    for i in range(app.config["MAX_BRANCHES_PER_PROJECT"]):
        make_branch(mine, f"S{i}")
    r = client.post(f"/schemes/{go.id}/move-to", data={"project_id": str(mine.id)},
                    follow_redirects=True)
    assert copy_in(r.data, "scheme.move_full", plot="Mine")
    db.session.expire_all()
    assert go.project_id == home.id


def test_someone_elses_scheme_cannot_be_moved(client, db):
    owner = make_user("someone@example.com")
    make_user()
    login(client)
    theirs = _plot(owner, "Theirs")
    go = make_branch(theirs, "Go")
    mine = _plot(make_user("me2@example.com"), "Mine")
    r = client.post(f"/schemes/{go.id}/move-to", data={"project_id": str(mine.id)})
    assert r.status_code == 404


def test_the_edit_page_offers_your_other_plots(client, db):
    user = make_user()
    login(client)
    home = _plot(user, "Home")
    go = make_branch(home, "Go")
    html = client.get(f"/schemes/{go.id}/edit").data.decode()
    assert copy_in(html, "scheme.move_none")
    assert "move-to" not in html

    _plot(user, "Zebra")
    _plot(user, "Apple")
    _plot(make_user("someone@example.com"), "Theirs")
    html = client.get(f"/schemes/{go.id}/edit").data.decode()
    assert f'action="/schemes/{go.id}/move-to"' in html
    # Your other plots by name; not this one, not anyone else's, and no
    # warning when nothing would be cut.
    picker = html[html.index('id="move_project_id"'):]
    picker = picker[:picker.index("</select>")]
    assert picker.index(">Apple<") < picker.index(">Zebra<")
    assert ">Home<" not in picker and ">Theirs<" not in picker
    assert "data-confirm=\"Moving" not in html
    assert db.session.query(Project).count() == 4
