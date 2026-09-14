"""Plot statuses: each account's own columns and shelves, edited in settings."""
from conftest import (
    copy_in, copy_prefix_in, login, make_project, make_user, post_statuses, status_rows,
)
from copytext import tx


def test_a_new_account_starts_with_the_default_statuses(db):
    user = make_user()
    assert [s.key for s in user.statuses] == [
        "idea", "exploring", "building", "maintaining", "done", "parked", "dropped"]
    assert [s.name for s in user.statuses[:2]] == [tx("phase.idea"), tx("phase.exploring")]
    assert [s.kind for s in user.statuses] == ["active"] * 4 + ["closed", "parked", "closed"]
    assert user.default_status.key == "idea" and user.parked_status.key == "parked"
    assert user.status("building").wip_limit == 3


def test_the_statuses_page_lists_them(client, db):
    user = make_user()
    login(client)
    html = client.get("/settings/statuses").data.decode()
    assert copy_in(html, "statuses.heading")
    assert all(f'value="{s.id}"' in html for s in user.statuses)


def test_renaming_a_status_keeps_its_plots(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    p.phase = "building"
    db.session.commit()
    rows = status_rows(user)
    rows[2][1], rows[2][2] = "Scheming", "red"
    r = post_statuses(client, rows)
    assert copy_in(r.data, "statuses.saved")
    db.session.expire_all()
    assert p.phase == "building" and p.phase_label == "Scheming" and p.phase_hue == "red"
    board = client.get("/board").data.decode()
    assert "Scheming" in board and "hue--red" in board


def test_an_added_active_status_is_a_column_that_advance_walks_through(client, db):
    user = make_user()
    login(client)
    rows = status_rows(user)
    rows.insert(2, ["", "Testing", "amber", "active", "0"])
    post_statuses(client, rows)
    db.session.expire_all()
    assert [s.key for s in user.statuses][:4] == ["idea", "exploring", "testing", "building"]
    p = make_project(user)
    p.phase = "exploring"
    db.session.commit()
    assert p.next_status.key == "testing"
    assert "Testing" in client.get("/board").data.decode()


def test_a_new_status_gets_a_key_of_its_own(client, db):
    user = make_user()
    login(client)
    post_statuses(client, status_rows(user) + [["", "Idea", "grey", "closed", "0"]])
    db.session.expire_all()
    newest = user.statuses[-1]
    assert (newest.key, newest.name, newest.kind) == ("idea-2", "Idea", "closed")


def test_deleting_a_status_moves_its_plots_to_one_of_the_same_kind(client, db):
    user = make_user()
    login(client)
    dropped = make_project(user)
    dropped.phase = "dropped"
    exploring = make_project(user)
    exploring.phase = "exploring"
    db.session.commit()
    rows = status_rows(user)
    for row in rows:
        if row[1] in (tx("phase.dropped"), tx("phase.exploring")):
            row[1] = ""
    r = post_statuses(client, rows)
    assert copy_in(r.data, "statuses.moved", n=1, name=tx("phase.done"))
    db.session.expire_all()
    assert dropped.phase == "done"          # a closed status's plots go to another closed one
    assert exploring.phase == "idea"        # an active status's plots go to the first active one
    assert [s.key for s in user.statuses] == ["idea", "building", "maintaining", "done", "parked"]


def test_the_board_always_keeps_one_active_status(client, db):
    user = make_user()
    login(client)
    rows = status_rows(user)
    for row in rows:
        row[3] = "closed"
    r = post_statuses(client, rows)
    assert copy_in(r.data, "statuses.need_active")
    db.session.expire_all()
    assert user.status("idea").kind == "active"


def test_moving_a_status_changes_the_advance_order(client, db):
    user = make_user()
    login(client)
    post_statuses(client, status_rows(user), move="2:up")     # Building above Exploring
    db.session.expire_all()
    assert [s.key for s in user.statuses][:3] == ["idea", "building", "exploring"]
    p = make_project(user)
    p.phase = "idea"
    db.session.commit()
    assert p.next_status.key == "building"


def test_any_active_status_can_carry_a_cap(client, db):
    user = make_user()
    login(client)
    rows = status_rows(user)
    rows[1][4] = "1"                                            # Exploring
    post_statuses(client, rows)
    first, second = make_project(user), make_project(user)
    client.post(f"/projects/{first.id}/phase", data={"phase": "exploring"})
    r = client.post(f"/projects/{second.id}/phase", data={"phase": "exploring"}, follow_redirects=True)
    assert copy_prefix_in(r.data, "board.status_full")
    db.session.expire_all()
    assert first.phase == "exploring" and second.phase == "idea"


def test_another_accounts_status_ids_are_ignored(client, db):
    other = make_user("other@example.com")
    theirs = other.statuses[0]
    user = make_user()
    login(client)
    post_statuses(client, status_rows(user) + [[str(theirs.id), "Hijacked", "red", "active", "0"]])
    db.session.expire_all()
    assert theirs.name == tx("phase.idea") and theirs.user_id == other.id
    assert user.statuses[-1].name == "Hijacked" and user.statuses[-1].user_id == user.id


def test_picking_a_plot_back_up_returns_it_where_it_was(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    p.phase = "building"
    db.session.commit()
    client.post(f"/review/{p.id}", data={"decision": "park", "done": "", "parked_until": "2030-01-01"})
    db.session.expire_all()
    assert p.phase == "parked" and p.shelved_from == "building"
    client.post(f"/review/{p.id}", data={"decision": "unpark", "done": ""})
    db.session.expire_all()
    assert p.phase == "building" and p.shelved_from is None


def test_review_closes_only_onto_closed_statuses(client, db):
    user = make_user()
    login(client)
    p = make_project(user)
    p.name, p.phase = "Doomsday device", "exploring"
    db.session.commit()
    html = client.get("/review").data.decode()
    assert 'value="close:done"' in html and 'value="close:dropped"' in html
    client.post(f"/review/{p.id}", data={"decision": "close:building", "done": ""})
    db.session.expire_all()
    assert p.phase == "exploring"
    client.post(f"/review/{p.id}", data={"decision": "close:done", "done": ""})
    db.session.expire_all()
    assert p.phase == "done"
