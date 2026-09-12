from conftest import login, make_project, make_user


def test_register_and_land_on_today(client):
    r = client.post("/register", data={"email": "New@Example.com", "password": "longenough1"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert b"Today" in r.data and b"Inbox" in r.data
    # email normalised to lower case
    r = client.post("/login", data={"email": "new@example.com", "password": "longenough1"})
    assert r.status_code == 302


def test_register_rejects_short_password(client):
    r = client.post("/register", data={"email": "a@b.c", "password": "short"}, follow_redirects=True)
    assert b"at least 8" in r.data


def test_login_bad_password(client):
    make_user()
    r = login(client, password="wrong")
    assert b"Invalid email or password" in r.data


def test_anonymous_is_redirected_to_login(client):
    r = client.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    r = client.get("/projects/1")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_logout_is_post_only(client):
    make_user()
    login(client)
    assert client.get("/logout").status_code == 405
    r = client.post("/logout")
    assert r.status_code == 302


def test_other_users_project_is_404(client):
    owner = make_user("owner@example.com")
    project = make_project(owner)
    make_user("intruder@example.com")
    login(client, email="intruder@example.com")
    assert client.get(f"/projects/{project.id}").status_code == 404
    assert client.post(f"/projects/{project.id}/delete").status_code == 404


def test_account_password_change(client):
    make_user()
    login(client)
    r = client.post("/account", data={"display_name": "R", "current_password": "hunter2hunter2",
                                      "new_password": "newpassword9"}, follow_redirects=True)
    assert b"Account updated" in r.data
    client.post("/logout")
    assert client.post("/login", data={"email": "ruben@example.com", "password": "newpassword9"}).status_code == 302
