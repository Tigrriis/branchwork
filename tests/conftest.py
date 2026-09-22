"""Test fixtures: an in-memory app, a client, and helpers for users and trees.

CSRF is disabled for tests so form posts don't have to scrape a token.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from extensions import db as _db  # noqa: E402
from models import Branch, Project, Task, Ultimate, User  # noqa: E402
from markupsafe import escape  # noqa: E402
import copytext  # noqa: E402

# Under test a missing copy key or placeholder raises instead of showing [key].
copytext.STRICT = True


def copy_in(html, key, **values) -> bool:
    """Is this catalogue line on the page, escaped the way the page escapes it?

    Tests assert through the catalogue rather than literal English, so editing
    the copy never breaks them.
    """
    if isinstance(html, bytes):
        html = html.decode()
    return str(escape(copytext.tx(key, **values))) in html


def copy_prefix_in(html, key) -> bool:
    """The fixed words before a line's first {placeholder}, for messages whose
    filled-in values a test cannot predict."""
    if isinstance(html, bytes):
        html = html.decode()
    return str(escape(copytext.catalogue()[key].split("{", 1)[0])) in html


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-key",
    })
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def make_user(email="ruben@example.com", password="hunter2hunter2") -> User:
    user = User(email=email)
    user.set_password(password)
    _db.session.add(user)
    _db.session.commit()
    return user


def login(client, email="ruben@example.com", password="hunter2hunter2"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def make_project(user: User, gate_points: int = 3) -> Project:
    project = Project(owner=user, name="Fit-out", gate_points=gate_points)
    _db.session.add(project)
    _db.session.commit()
    return project


def make_branch(project: Project, name="Design", hue="green", requires: Branch | None = None) -> Branch:
    branch = Branch(project=project, name=name, hue=hue, position=len(project.branches), requires=requires)
    _db.session.add(branch)
    _db.session.commit()
    return branch


def make_task(branch: Branch, title="Task", tier=1, points_max=1, points_done=0) -> Task:
    task = Task(branch=branch, title=title, tier=tier, points_max=points_max,
                position=len([t for t in branch.tasks if t.tier == tier]))
    task.set_points(points_done)
    _db.session.add(task)
    _db.session.commit()
    return task


def make_ultimate(branch: Branch, title="The big one") -> Ultimate:
    ultimate = Ultimate(branch=branch, title=title)
    _db.session.add(ultimate)
    _db.session.commit()
    return ultimate


def status_rows(user) -> list[list[str]]:
    """The statuses settings form as it would post: one editable row per status,
    [id, name, hue, kind, cap]."""
    return [[str(s.id), s.name, s.hue, s.kind, str(s.wip_limit)] for s in user.statuses]


def post_statuses(client, rows, **extra):
    fields = ("status_id", "status_name", "status_hue", "status_kind", "status_cap")
    data = {field: [row[i] for row in rows] for i, field in enumerate(fields)}
    data.update(extra)
    return client.post("/settings/statuses", data=data, follow_redirects=True)
