"""The notes vault: what the server keeps, and what it refuses.

The cryptography itself runs in the browser (static/branchwork/vault.js) and
is exercised there; here the server's side of the bargain is checked: it
stores only sealed notes, swaps the notes from before the vault in one go,
and never takes a note in the clear.
"""
from conftest import copy_in, login, make_branch, make_project, make_task, make_user, make_vault, sealed
from models import Note, User

KEY = {"salt": "AAAAAAAAAAAAAAAAAAAAAA", "rounds": 600_000}


def _key(**extra):
    return {**KEY, "key": sealed("k" * 32), **extra}


def test_notes_wait_for_a_master_password(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    page = client.get(f"/plots/{project.id}/notes").data.decode()
    assert "data-vault-setup" in page and '"vault": null' in page
    res = client.post(f"/plots/{project.id}/notes",
                      json={"title": sealed("Plan"), "body": sealed(""), "folder": "plot"})
    assert res.status_code == 409 and copy_in(res.get_json()["message"], "vault.missing")
    assert Note.query.count() == 0


def test_a_note_in_the_clear_is_refused(client, db):
    user = make_vault(make_user())
    login(client)
    project = make_project(user)
    url = f"/plots/{project.id}/notes"
    for title, body in (("Plan", sealed("x")), (sealed("Plan"), "the words"),
                        (sealed("Plan"), "v1.short.x"), (None, sealed("x"))):
        res = client.post(url, json={"title": title, "body": body, "folder": "plot"})
        assert res.status_code == 400 and copy_in(res.get_json()["message"], "vault.not_sealed")
    made = client.post(url, json={"title": sealed("Plan"), "body": sealed("x"), "folder": "plot"}).get_json()
    assert client.post(made["save_url"], json={"body": "in the clear"}).status_code == 400
    assert Note.query.one().body.startswith("v1.")


def test_the_page_carries_no_words_of_a_note(client, db):
    user = make_vault(make_user())
    login(client)
    project = make_project(user)
    task = make_task(make_branch(project), "Brief")
    title, body = sealed("Secret title"), sealed("Secret body")
    note = Note(project=project, title=title, body=body)
    db.session.add(note)
    note.file_under(task)
    db.session.commit()
    page = client.get(f"/plots/{project.id}/notes/{note.id}").data.decode()
    assert title in page and body in page
    # The vault data is the sealed key and how to stretch the password: no key.
    assert user.vault_key in page and '"rounds": 600000' in page


def test_setting_up_seals_the_notes_from_before(client, db):
    user = make_user()
    login(client)
    project = make_project(user)
    old = [Note(project=project, title="Plan", body="the words"),
           Note(project=project, title="Budget", body="")]
    db.session.add_all(old)
    db.session.commit()
    other = make_user("other@example.com")
    db.session.add(Note(project=make_project(other), title="Not yours", body="x"))
    db.session.commit()

    plain = client.get("/notes/vault/plain").get_json()["notes"]
    assert {(n["title"], n["body"]) for n in plain} == {("Plan", "the words"), ("Budget", "")}

    # Leaving one out would leave it in the clear, so nothing happens.
    res = client.post("/notes/vault", json=_key(notes=[
        {"id": old[0].id, "title": sealed("Plan"), "body": sealed("the words")}]))
    assert res.status_code == 409 and copy_in(res.get_json()["message"], "vault.notes_changed")
    # As with one not sealed.
    res = client.post("/notes/vault", json=_key(notes=[
        {"id": n.id, "title": sealed(n.title), "body": n.body} for n in old]))
    assert res.status_code == 400
    assert db.session.get(User, user.id).vault_key is None

    sealed_notes = [{"id": n.id, "title": sealed(n.title), "body": sealed(n.body)} for n in old]
    payload = _key(notes=sealed_notes)
    res = client.post("/notes/vault", json=payload)
    assert res.status_code == 200 and res.get_json()["sealed"] == 2
    db.session.expire_all()
    assert db.session.get(User, user.id).vault == {
        "salt": KEY["salt"], "rounds": KEY["rounds"], "key": payload["key"]}
    assert {n.title for n in old} == {s["title"] for s in sealed_notes}
    assert all(n.body.startswith("v1.") for n in old)
    # Someone else's notes are theirs to seal.
    assert Note.query.filter_by(title="Not yours").one()

    # The notes in the clear are gone for good, and so is setting up again.
    assert client.get("/notes/vault/plain").status_code == 409
    assert client.post("/notes/vault", json=_key(notes=[])).status_code == 409


def test_setup_checks_the_key_it_is_given(client, db):
    make_user()
    login(client)
    for bad in ({"salt": "short"}, {"rounds": 1000}, {"rounds": "lots"}, {"key": "in the clear"}):
        assert client.post("/notes/vault", json={**_key(notes=[]), **bad}).status_code == 400
    assert client.post("/notes/vault", json=_key(notes=[])).status_code == 200


def test_a_new_master_password_reseals_only_the_key(client, db):
    user = make_vault(make_user())
    login(client)
    was = user.vault_key
    new = _key(salt="BBBBBBBBBBBBBBBBBBBBBB")
    # The browser says which key it unsealed, so a stale tab cannot clobber a newer one.
    res = client.post("/notes/vault/key", json={**new, "was": sealed("old")})
    assert res.status_code == 409 and copy_in(res.get_json()["message"], "vault.key_changed")
    assert client.post("/notes/vault/key", json={**new, "was": was}).status_code == 200
    db.session.expire_all()
    assert db.session.get(User, user.id).vault["key"] == new["key"]
    assert db.session.get(User, user.id).vault["salt"] == "BBBBBBBBBBBBBBBBBBBBBB"


def test_starting_again_takes_the_sign_in_password(client, db):
    user = make_vault(make_user())
    login(client)
    project = make_project(user)
    db.session.add(Note(project=project, title=sealed("Plan"), body=sealed("x")))
    db.session.commit()

    res = client.post("/notes/vault/reset", data={"password": "wrong"}, follow_redirects=True)
    assert copy_in(res.data, "auth.wrong_password")
    assert Note.query.count() == 1 and db.session.get(User, user.id).has_vault

    res = client.post("/notes/vault/reset", data={"password": "hunter2hunter2"}, follow_redirects=True)
    assert copy_in(res.data, "vault.reset_done")
    db.session.expire_all()
    assert Note.query.count() == 0 and not db.session.get(User, user.id).has_vault


def test_the_account_page(client, db):
    user = make_user()
    login(client)
    html = client.get("/account").data.decode()
    assert copy_in(html, "vault.account_none") and "data-vault-rekey" not in html
    make_vault(user)
    html = client.get("/account").data.decode()
    assert "data-vault-rekey" in html and copy_in(html, "vault.reset_submit")
