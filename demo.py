"""`flask seed-demo`: build the example project from the design boards.

    flask --app app seed-demo --email you@example.com [--password ...]

Creates the user if the email is new (a password is then required) and adds
an "Office fit-out, Level 3" project with three branches, so a fresh
database has something to look at.
"""
from datetime import datetime, timedelta, timezone

import click
from flask import Blueprint

from extensions import db
from models import Branch, InboxItem, Project, Routine, Task, User

demo_bp = Blueprint("demo", __name__, cli_group=None)

DEMO = {
    "name": "Office fit-out, Level 3",
    "code": "2026-014",
    "branches": [
        {"name": "Design", "hue": "green", "tiers": [
            [("Brief & survey", "doc", 3, 3), ("Concept layouts", "layout", 2, 2), ("Detailed drawings", "pencil", 4, 2)],
            [("Site measure-up", "ruler", 1, 1), ("Client brief signed", "sign", 1, 1), ("Option A / B review", "flag", 2, 2)],
            [("Services coordination", "wrench", 2, 0), ("Issue for tender", "list", 1, 0)]]},
        {"name": "Approvals", "hue": "blue", "tiers": [
            [("Landlord consent", "key", 1, 1), ("Building permit", "seal", 3, 2)],
            [("Fire engineering report", "fire", 2, 2), ("Certifier lodgement", "calendar", 1, 0)]]},
        {"name": "Construction", "hue": "red", "requires": "Approvals", "tiers": [
            [("Tender & award", "list", 3, 0), ("Site works", "hardhat", 5, 0), ("Handover", "home", 2, 0)],
            [("Shortlist contractors", "users", 2, 0), ("Award contract", "trophy", 1, 0), ("Demolition", "hammer", 2, 0)],
            [("Fit-out & services", "truck", 4, 0)]]},
    ],
}


EXTRA_PROJECTS = [
    # name, phase, cadence, objective, next action, days since touch
    ("Lead-lag scanner", "exploring", 14,
     "Find one repeatable signal worth trading before spending more weekends on it",
     "Backtest the FRED series against last quarter", 19),
    ("Drainage sizing tool", "maintaining", 30,
     "Cut an hour off every drainage job I quote",
     "Fix the unit-conversion bug in the report", 6),
    ("Field notes app", "idea", 30,
     "Stop losing site observations between the van and the office", None, 2),
    ("Old portfolio site", "parked", 30,
     "Decide if it still earns its keep, or retire it cleanly",
     "Decide whether to rebuild or retire", 60),
]


DEMO_ROUTINES = [
    # title, icon, every N days, days since last done (None: never done)
    ("Site walk", "hardhat", 7, 9),
    ("Client update", "mail", 14, 5),
    ("Progress claim", "cash", 30, 26),
    ("Check the programme", "calendar", 7, None),
]


def build_demo(user: User) -> Project:
    project = Project(owner=user, name=DEMO["name"], code=DEMO["code"], gate_points=3,
                      phase="building", cadence_days=7,
                      objective="Deliver the fit-out on budget so the client comes back for Level 4",
                      next_action="Issue detailed drawings for tender")
    db.session.add(project)
    by_name: dict[str, Branch] = {}
    for pos, spec in enumerate(DEMO["branches"]):
        branch = Branch(project=project, name=spec["name"], hue=spec["hue"], position=pos)
        db.session.add(branch)
        by_name[spec["name"]] = branch
        for tier_no, tier in enumerate(spec["tiers"], start=1):
            for i, (title, icon, pmax, pdone) in enumerate(tier):
                task = Task(branch=branch, tier=tier_no, position=i, title=title, icon=icon,
                            points_max=pmax)
                task.set_points(pdone)
                db.session.add(task)
    db.session.flush()
    for spec in DEMO["branches"]:
        if spec.get("requires"):
            by_name[spec["name"]].requires = by_name[spec["requires"]]

    # A plausible activity history so the strips and "last touched" mean something.
    now = datetime.now(timezone.utc)
    # Routines in every state the bar shows: overdue, cooling, nearly ready, ready.
    for pos, (title, icon, every, done_ago) in enumerate(DEMO_ROUTINES):
        routine = Routine(project=project, title=title, icon=icon, every_days=every, position=pos)
        if done_ago is not None:
            routine.last_done_at = now - timedelta(days=done_ago)
        db.session.add(routine)
    for days_ago in (1, 3, 4, 8, 9, 15, 16, 23, 30, 31, 45, 52, 60):
        project.record("points", delta=1, note="Progress", at=now - timedelta(days=days_ago))
    for name, phase, cadence, objective, action, age in EXTRA_PROJECTS:
        extra = Project(owner=user, name=name, phase=phase, cadence_days=cadence,
                        objective=objective, next_action=action,
                        parked_until=(now + timedelta(days=14)).date() if phase == "parked" else None)
        db.session.add(extra)
        for days_ago in (age, age + 7, age + 20):
            extra.record("touch", note="Worked on it", at=now - timedelta(days=days_ago))
    db.session.add(InboxItem(user=user, text="Try a hex-grid layout for the tree view"))
    db.session.add(InboxItem(user=user, text="Ask the certifier about the fire report timing"))
    db.session.commit()
    return project


@demo_bp.cli.command("seed-demo")
@click.option("--email", required=True)
@click.option("--password", default=None, help="Required when the user does not exist yet.")
def seed_demo(email: str, password: str | None):
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is None:
        if not password or len(password) < 8:
            raise click.ClickException("New user: pass --password with at least 8 characters.")
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        click.echo(f"created user {email}")
    project = build_demo(user)
    click.echo(f"seeded project #{project.id} “{project.name}” for {email}")
