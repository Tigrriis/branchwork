"""`flask sync-git`: read commits from each project's repo folder into activity.

    flask --app app sync-git [--email you@example.com] [--since 2026-01-01]

For every project with a ``repo_path``, commits since the newest git event
already recorded (or ``--since``) become ``git`` activity events, one per
commit, keyed by the short hash so re-running never duplicates. "Last
touched" then reflects real work without anyone logging it by hand.
"""
import os
import subprocess
from datetime import date, datetime, timedelta, timezone

import click
from flask import Blueprint

from extensions import db
from models import ActivityEvent, Project, User

gitsync_bp = Blueprint("gitsync", __name__, cli_group=None)

DEFAULT_LOOKBACK_DAYS = 365


def read_commits(repo_path: str, since: datetime) -> list[tuple[str, datetime, str]]:
    """(short hash, committed at, subject) for commits after ``since``."""
    if not os.path.isdir(repo_path):
        raise FileNotFoundError(repo_path)
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "--all", "--no-merges",
         f"--since={since.isoformat()}", "--format=%h%x09%ct%x09%s"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git log failed")
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        short, ts = parts[0], parts[1]
        subject = parts[2] if len(parts) > 2 else ""
        commits.append((short, datetime.fromtimestamp(int(ts), tz=timezone.utc), subject[:150]))
    return commits


def sync_project(project: Project, since: datetime | None = None) -> int:
    """Record new commits as events; return how many were added."""
    if not project.repo_path:
        return 0
    known = {e.note.split(" ", 1)[0] for e in project.events if e.kind == "git" and e.note}
    if since is None:
        newest = max((e.created_at for e in project.events if e.kind == "git"), default=None)
        if newest is not None and newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        since = (newest - timedelta(days=1)) if newest else (
            datetime.now(timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS))
    added = 0
    for short, at, subject in read_commits(project.repo_path, since):
        if short in known:
            continue
        project.record("git", note=f"{short} {subject}".strip(), at=at)
        known.add(short)
        added += 1
    return added


@gitsync_bp.cli.command("sync-git")
@click.option("--email", default=None, help="Only this user's projects.")
@click.option("--since", default=None, help="ISO date; default: since the last synced commit.")
def sync_git(email: str | None, since: str | None):
    since_dt = None
    if since:
        since_dt = datetime.combine(date.fromisoformat(since), datetime.min.time(), tzinfo=timezone.utc)
    query = Project.query.filter(Project.repo_path.isnot(None))
    if email:
        user = User.query.filter_by(email=email.strip().lower()).first()
        if user is None:
            raise click.ClickException(f"no user {email}")
        query = query.filter_by(owner_id=user.id)
    total = 0
    for project in query.all():
        try:
            n = sync_project(project, since_dt)
        except (FileNotFoundError, RuntimeError) as exc:
            click.echo(f"  {project.name}: skipped ({exc})")
            continue
        total += n
        click.echo(f"  {project.name}: {n} new commit(s) from {project.repo_path}")
    db.session.commit()
    click.echo(f"sync-git: {total} event(s) added")
