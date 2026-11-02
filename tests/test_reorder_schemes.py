"""Dragging a scheme's column by its name bar to reorder a plot's schemes."""
from conftest import copy_in, login, make_branch, make_project, make_user


def _reorder(client, branch, before):
    return client.post(f"/schemes/{branch.id}/reorder",
                       json={"before": before.id if before else None})


def _names(project):
    return [b.name for b in project.branches]


def test_a_scheme_moves_before_another_or_to_the_end(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    a, b, c = (make_branch(project, name) for name in "ABC")

    body = _reorder(client, c, a).get_json()
    assert body["moved"] and f'data-branch="{c.id}"' in body["html"]
    db.session.expire_all()
    assert _names(project) == ["C", "A", "B"]
    assert [s.position for s in project.branches] == [0, 1, 2]

    _reorder(client, c, None)
    db.session.expire_all()
    assert _names(project) == ["A", "B", "C"]


def test_dropping_a_scheme_back_where_it_was_changes_nothing(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    a, b, c = (make_branch(project, name) for name in "ABC")
    assert _reorder(client, b, c).get_json()["moved"] is False
    assert _reorder(client, c, None).get_json()["moved"] is False
    db.session.expire_all()
    assert _names(project) == ["A", "B", "C"]


def test_a_scheme_from_another_plot_counts_as_the_end(client, db):
    user = make_user()
    login(client)
    home, away = make_project(user), make_project(user)
    a, b = make_branch(home, "A"), make_branch(home, "B")
    elsewhere = make_branch(away, "Elsewhere")
    _reorder(client, a, elsewhere)
    db.session.expire_all()
    assert _names(home) == ["B", "A"] and elsewhere.project_id == away.id


def test_someone_elses_scheme_cannot_be_reordered(client, db):
    make_user()
    login(client)
    theirs = make_branch(make_project(make_user("someone@example.com")), "Theirs")
    assert _reorder(client, theirs, None).status_code == 404


def test_a_schemes_name_bar_is_what_you_drag(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    make_branch(project, "A")
    html = client.get(f"/plots/{project.id}").data.decode()
    assert '<div class="col__foot" draggable="true"' in html
    assert copy_in(html, "tree.drag_scheme_title")
