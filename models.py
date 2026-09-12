"""Database models for Branchwork.

A ``Project`` is a skill tree. It splits into ``Branch`` columns, each branch
stacks its ``Task`` tiles in numbered tiers, and every task carries points
(``points_done`` of ``points_max``): a plain checkbox is a task worth one point.

Two rules give the tree its shape, both computed here so every route and
template agrees:

* **Tier gates.** Tier N of a branch opens once tier N-1 holds at least
  ``project.gate_points`` points (and is itself open). The first tier is
  always open unless the whole branch is locked.
* **Branch locks.** A branch may require another branch; it stays locked, all
  tiers dimmed, until that branch is complete.

Points on a locked tier cannot be changed (``Task.editable``), enforced by the
routes, not just hidden by the template.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Column tints. Stored as short strings so adding one is a CSS change, not a
# migration; the CSS classes are .col--<hue> in static/branchwork/theme.css.
HUES = {
    "green": "Green",
    "blue": "Blue",
    "red": "Red",
    "amber": "Amber",
    "violet": "Violet",
    "teal": "Teal",
}

STATE_FULL = "full"       # every point earned
STATE_PART = "part"       # some points earned
STATE_EMPTY = "empty"     # none yet

# Project lifecycle. The first four are "active" and appear on the board's
# main columns; the rest are shelves. ``PHASE_ADVANCE`` is the path the
# review page's "advance" button walks.
PHASES = {
    "idea": "Idea",
    "exploring": "Exploring",
    "building": "Building",
    "maintaining": "Maintaining",
    "done": "Done",
    "parked": "Parked",
    "dropped": "Dropped",
}
ACTIVE_PHASES = ("idea", "exploring", "building", "maintaining")
PHASE_ADVANCE = ["idea", "exploring", "building", "maintaining", "done"]

# How often a project expects to be touched. 0 means no tempo (never "due").
CADENCES = {7: "Weekly", 14: "Fortnightly", 30: "Monthly", 90: "Quarterly", 0: "No tempo"}

# Activity event kinds. ``points`` and ``task`` come from the tree, ``touch``
# from the "touched it" button, ``phase`` from the board, ``git`` from
# ``flask sync-git``, ``review`` from the weekly review.
EVENT_KINDS = ("points", "task", "touch", "phase", "git", "review", "park")


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite hands naive datetimes back; treat them as UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    projects = db.relationship(
        "Project", backref="owner", order_by="Project.created_at",
        cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def public_name(self) -> str:
        return self.display_name or self.email.split("@", 1)[0]


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(40), nullable=True)          # "2026-014", optional
    description = db.Column(db.Text, nullable=True)
    gate_points = db.Column(db.Integer, nullable=False, default=3, server_default="3")
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    # ── Portfolio fields ────────────────────────────────────────────────────
    phase = db.Column(db.String(20), nullable=False, default="idea", server_default="idea")
    cadence_days = db.Column(db.Integer, nullable=False, default=14, server_default="14")
    next_action = db.Column(db.String(200), nullable=True)
    parked_until = db.Column(db.Date, nullable=True)
    # Local folder with a git history; ``flask sync-git`` turns its commits
    # into activity so "last touched" stays honest without manual logging.
    repo_path = db.Column(db.String(400), nullable=True)
    # Denormalised from ``events`` so the dashboard can sort without joins.
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=True)

    branches = db.relationship(
        "Branch", backref="project", order_by="Branch.position, Branch.id",
        cascade="all, delete-orphan")
    events = db.relationship(
        "ActivityEvent", backref="project", order_by="ActivityEvent.created_at",
        cascade="all, delete-orphan")

    # ── Tempo ───────────────────────────────────────────────────────────────
    @property
    def is_active(self) -> bool:
        return self.phase in ACTIVE_PHASES

    @property
    def phase_label(self) -> str:
        return PHASES.get(self.phase, self.phase)

    @property
    def next_phase(self) -> str | None:
        if self.phase in PHASE_ADVANCE:
            i = PHASE_ADVANCE.index(self.phase)
            return PHASE_ADVANCE[i + 1] if i + 1 < len(PHASE_ADVANCE) else None
        return "exploring"   # parked / dropped come back in at exploring

    @property
    def touched_at(self) -> datetime:
        return _aware(self.last_activity_at) or _aware(self.created_at) or _utcnow()

    @property
    def days_since_touch(self) -> int:
        return max(0, (_utcnow() - self.touched_at).days)

    @property
    def overdue_days(self) -> int | None:
        """Days past the cadence, negative while still within it; None if untracked."""
        if not self.is_active or not self.cadence_days:
            return None
        return self.days_since_touch - self.cadence_days

    @property
    def is_due(self) -> bool:
        overdue = self.overdue_days
        return overdue is not None and overdue >= 0

    @property
    def parked_expired(self) -> bool:
        return (self.phase == "parked" and self.parked_until is not None
                and self.parked_until <= _utcnow().date())

    @property
    def cadence_label(self) -> str:
        return CADENCES.get(self.cadence_days, f"Every {self.cadence_days} days")

    def record(self, kind: str, *, task: Task | None = None, delta: int = 0,
               note: str | None = None, at: datetime | None = None) -> ActivityEvent:
        """Append an activity event and move ``last_activity_at`` forward."""
        at = _aware(at) or _utcnow()
        event = ActivityEvent(project=self, task=task, kind=kind, delta=delta,
                              note=(note or None), created_at=at)
        db.session.add(event)
        if self.last_activity_at is None or at > self.touched_at:
            self.last_activity_at = at
        return event

    def activity_strip(self, weeks: int = 12) -> list[int]:
        """Event counts per week, oldest first, the current week last."""
        today = _utcnow().date()
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(weeks=weeks - 1)
        counts = [0] * weeks
        for event in self.events:
            day = _aware(event.created_at).date()
            if day < start:
                continue
            index = (day - start).days // 7
            if 0 <= index < weeks:
                counts[index] += 1
        return counts

    # ── Progress ────────────────────────────────────────────────────────────
    @property
    def tasks(self) -> list[Task]:
        return [t for b in self.branches for t in b.tasks]

    @property
    def points_max(self) -> int:
        return sum(b.points_max for b in self.branches)

    @property
    def points_done(self) -> int:
        return sum(b.points_done for b in self.branches)

    @property
    def percent(self) -> int:
        return round(100 * self.points_done / self.points_max) if self.points_max else 0

    def count_state(self, state: str) -> int:
        return sum(1 for t in self.tasks if t.state == state)


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    hue = db.Column(db.String(20), nullable=False, default="green", server_default="green")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # The branch this one waits on. Nullable; must be in the same project.
    requires_branch_id = db.Column(
        db.Integer, db.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)

    tasks = db.relationship(
        "Task", backref="branch", order_by="Task.tier, Task.position, Task.id",
        cascade="all, delete-orphan")
    requires = db.relationship(
        "Branch", remote_side=[id], foreign_keys=[requires_branch_id], post_update=True)

    # ── Progress ────────────────────────────────────────────────────────────
    @property
    def points_max(self) -> int:
        return sum(t.points_max for t in self.tasks)

    @property
    def points_done(self) -> int:
        return sum(t.points_done for t in self.tasks)

    @property
    def percent(self) -> int:
        return round(100 * self.points_done / self.points_max) if self.points_max else 0

    @property
    def is_complete(self) -> bool:
        """Every task fully pointed. An empty branch is not complete."""
        return bool(self.tasks) and self.points_done >= self.points_max

    @property
    def is_locked(self) -> bool:
        """True while the required branch is unfinished.

        Walks the requirement chain with a visited set, so a cycle that slipped
        past form validation degrades to "locked" instead of recursing forever.
        """
        seen = {self.id}
        node = self.requires
        while node is not None:
            if node.id in seen:
                return True
            if not node.is_complete:
                return True
            seen.add(node.id)
            node = node.requires
        return False

    @property
    def lock_reason(self) -> str | None:
        if self.requires is None:
            return None
        if self.is_locked:
            return f"Opens when {self.requires.name} is complete"
        return None

    # ── Tiers ───────────────────────────────────────────────────────────────
    @property
    def tier_numbers(self) -> list[int]:
        return sorted({t.tier for t in self.tasks})

    @property
    def next_tier(self) -> int:
        nums = self.tier_numbers
        return (nums[-1] + 1) if nums else 1

    def tiers(self) -> list[dict]:
        """Ordered tier rows with their open/closed state.

        Each row: ``{"tier", "tasks", "open", "have", "need", "reason"}``.
        ``have`` is the points in the row above (what the gate counts);
        ``need`` is the project's gate size.
        """
        gate = self.project.gate_points if self.project else 3
        locked = self.is_locked
        rows: list[dict] = []
        prev: dict | None = None
        for n in self.tier_numbers:
            tasks = [t for t in self.tasks if t.tier == n]
            if locked:
                open_, have, reason = False, None, self.lock_reason
            elif prev is None:
                open_, have, reason = True, None, None
            else:
                have = sum(t.points_done for t in prev["tasks"])
                open_ = prev["open"] and have >= gate
                reason = None if open_ else (
                    f"Needs {gate} points in the tier above · {have}/{gate}"
                    if prev["open"] else "Tier above is still locked")
            row = {"tier": n, "tasks": tasks, "open": open_, "have": have,
                   "need": gate, "reason": reason}
            rows.append(row)
            prev = row
        return rows

    def tier_open(self, n: int) -> bool:
        for row in self.tiers():
            if row["tier"] == n:
                return row["open"]
        # A tier with no tasks yet: open if the last existing tier is open
        # and satisfies the gate (i.e. the "+ tier" row is usable).
        rows = self.tiers()
        if self.is_locked:
            return False
        if not rows:
            return True
        last = rows[-1]
        return last["open"] and sum(t.points_done for t in last["tasks"]) >= last["need"]


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False, index=True)
    tier = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    title = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(30), nullable=False, default="check", server_default="check")
    points_max = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    points_done = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def state(self) -> str:
        if self.points_done <= 0:
            return STATE_EMPTY
        if self.points_done >= self.points_max:
            return STATE_FULL
        return STATE_PART

    @property
    def editable(self) -> bool:
        """Points may change only on an open tier of an unlocked branch."""
        return self.branch.tier_open(self.tier)

    def set_points(self, value: int) -> None:
        # Column defaults only apply at flush, so a brand-new task may still
        # hold None here.
        pmax = self.points_max or 1
        current = self.points_done or 0
        value = max(0, min(int(value), pmax))
        was_complete = current >= pmax
        self.points_done = value
        now_complete = value >= pmax
        if now_complete and not was_complete:
            self.completed_at = _utcnow()
        elif not now_complete:
            self.completed_at = None

    def adjust(self, delta: int) -> None:
        self.set_points((self.points_done or 0) + delta)


class ActivityEvent(db.Model):
    """One thing that happened to a project: the tempo is read from these."""
    __tablename__ = "activity_events"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    kind = db.Column(db.String(20), nullable=False)
    delta = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, index=True)

    task = db.relationship("Task", foreign_keys=[task_id])


class InboxItem(db.Model):
    """A captured idea or note that belongs to no project yet.

    Lifecycle: open -> filed (became a task) | parked (revisit later) | done.
    Parked items come back to the inbox once ``revisit_on`` passes.
    """
    __tablename__ = "inbox_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    revisit_on = db.Column(db.Date, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    done_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", backref=db.backref("inbox_items", cascade="all, delete-orphan"))
    project = db.relationship("Project", foreign_keys=[project_id])

    @property
    def status(self) -> str:
        if self.done_at is not None:
            return "done"
        if self.project_id is not None:
            return "filed"
        if self.revisit_on is not None and self.revisit_on > _utcnow().date():
            return "parked"
        return "open"

    @property
    def resurfaced(self) -> bool:
        """Was parked and the date has now passed."""
        return (self.status == "open" and self.revisit_on is not None
                and self.revisit_on <= _utcnow().date())
