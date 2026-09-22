"""Database models for Villainy.

In the interface a Project is a *plot*, a Branch a *scheme* and a Task a
*machination*. The code keeps the plain names; only the words changed.

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

A branch may also end in an ``Ultimate``: its end goal, drawn below every
tier. It opens by the tier rule and is claimed with a click, and a branch
with one is not complete until it is claimed.

Points on a locked tier cannot be changed (``Task.editable``), enforced by the
routes, not just hidden by the template.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone

from flask import current_app, has_app_context
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from copytext import tx
from icons import DEFAULT_ICON
from extensions import db, login_manager


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _Labels(Mapping):
    """A fixed set of keys whose display words come from the copy catalogue.

    Behaves like the plain dict it replaced (``items()``, ``in``, ``get``) but
    looks each label up when asked, so a catalogue edit shows without a restart.
    """

    def __init__(self, prefix: str, keys: tuple):
        self._prefix, self._keys = prefix, keys

    def __getitem__(self, key):
        if key not in self._keys:
            raise KeyError(key)
        return tx(f"{self._prefix}.{key}")

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)


# Column tints. Stored as short strings so adding one is a CSS change, not a
# migration; the CSS classes are .col--<hue> in static/branchwork/theme.css.
HUES = _Labels("hue", ("green", "blue", "red", "amber", "violet", "teal"))

STATE_FULL = "full"       # every point earned
STATE_PART = "part"       # some points earned
STATE_EMPTY = "empty"     # none yet

# Plot statuses belong to each account (``Status``); these are what a new
# account starts with, named from the catalogue's [phase] table at creation
# and the user's to change after that. Kinds: ``active`` statuses are the
# board's columns, walked in order by "advance"; a ``parked`` status is a
# shelf with a return date; ``closed`` ones hold finished or abandoned plots.
STATUS_KINDS = ("active", "parked", "closed")
DEFAULT_STATUSES = (
    ("idea", "violet", "active"), ("exploring", "blue", "active"),
    ("building", "green", "active"), ("maintaining", "teal", "active"),
    ("done", "grey", "closed"), ("parked", "amber", "parked"), ("dropped", "red", "closed"),
)
# A status may also be grey, which suits a shelf; a scheme may not.
STATUS_HUES = _Labels("hue", ("green", "blue", "red", "amber", "violet", "teal", "grey"))

# How often a project expects to be touched. 0 means no tempo (never "due").
CADENCES = _Labels("cadence", (7, 14, 30, 90, 0))

# Activity event kinds. ``points`` and ``task`` come from the tree, ``touch``
# from the "touched it" button, ``phase`` from the board, ``git`` from
# ``flask sync-git``, ``review`` from the weekly review, ``routine`` from
# using a routine.
EVENT_KINDS = ("points", "task", "touch", "phase", "git", "review", "park", "routine")


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
    statuses = db.relationship(
        "Status", backref="user", order_by="Status.position, Status.id",
        cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Every account starts with the default statuses, so nothing else
        # has to cope with an account that has none.
        if not self.statuses:
            self.statuses = default_statuses()

    def status(self, key: str | None) -> Status | None:
        return next((s for s in self.statuses if s.key == key), None)

    @property
    def default_status(self) -> Status:
        """Where a new plot starts. The settings page never allows an
        account with no active status, so there is always one."""
        return next(s for s in self.statuses if s.is_active)

    @property
    def parked_status(self) -> Status | None:
        """The status the review's Park button uses, if the account has one."""
        return next((s for s in self.statuses if s.is_parked), None)

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
    # Am I giving this time right now? Deliberately independent of ``phase``,
    # which says how far along a project is: something can be well into
    # Building and still not be what you are touching this weekend. Also
    # lighter than the Parked phase, which is a dated shelf -- this is just
    # "not now", flipped as often as you like.
    focused = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    phase = db.Column(db.String(20), nullable=False, default="idea", server_default="idea")
    cadence_days = db.Column(db.Integer, nullable=False, default=14, server_default="14")
    # Why this project exists, in one line. Sits above the next action
    # everywhere the two appear together: the next action says what to do,
    # the objective says what it is in aid of.
    objective = db.Column(db.String(300), nullable=True)
    next_action = db.Column(db.String(200), nullable=True)
    parked_until = db.Column(db.Date, nullable=True)
    # The active status a plot was in when it went onto a shelf, so picking
    # it back up returns it there instead of to the start.
    shelved_from = db.Column(db.String(20), nullable=True)
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
    routines = db.relationship(
        "Routine", backref="project", order_by="Routine.position, Routine.id",
        cascade="all, delete-orphan")
    threads = db.relationship(
        "Thread", backref="project", order_by="Thread.id",
        cascade="all, delete-orphan")

    # ── Tempo ───────────────────────────────────────────────────────────────
    @property
    def status(self) -> Status | None:
        """This plot's status from its owner's set; ``phase`` holds the key."""
        return self.owner.status(self.phase) if self.owner is not None else None

    @property
    def is_active(self) -> bool:
        status = self.status
        return status is not None and status.is_active

    @property
    def is_parked(self) -> bool:
        status = self.status
        return status is not None and status.is_parked

    @property
    def phase_label(self) -> str:
        status = self.status
        return status.name if status is not None else self.phase

    @property
    def phase_hue(self) -> str:
        status = self.status
        return status.hue if status is not None else "grey"

    @property
    def next_status(self) -> Status | None:
        """Where "advance" goes: the next active status, and past the last one
        the first closed status. From a shelf, the way back."""
        if self.owner is None:
            return None
        status = self.status
        if status is None or not status.is_active:
            return self.owner.status(self.resume_phase)
        statuses = list(self.owner.statuses)
        later = statuses[statuses.index(status) + 1:]
        return (next((s for s in later if s.is_active), None)
                or next((s for s in statuses if s.is_closed), None))

    @property
    def resume_phase(self) -> str:
        """The key a shelved plot is picked back up into: the active status it
        left, if that still exists, else the first active one."""
        back = self.owner.status(self.shelved_from)
        if back is not None and back.is_active:
            return back.key
        return self.owner.default_status.key

    def change_phase(self, status: Status, *, park_until: date | None = None,
                     kind: str = "phase", record: bool = True) -> None:
        """Move to a status, remembering where a shelved plot came from."""
        old = self.status
        if status.is_active:
            self.shelved_from = None
        elif old is not None and old.is_active:
            self.shelved_from = old.key
        self.parked_until = park_until if status.is_parked else None
        if status.key != self.phase:
            before = old.name if old is not None else self.phase
            self.phase = status.key
            if record:
                self.record(kind, note=f"{before} → {status.name}")

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
        return (self.is_parked and self.parked_until is not None
                and self.parked_until <= _utcnow().date())

    @property
    def cadence_label(self) -> str:
        return CADENCES.get(self.cadence_days, tx("cadence.every", n=self.cadence_days))

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
    def ultimates(self) -> list[Ultimate]:
        return [b.ultimate for b in self.branches if b.ultimate is not None]

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


def default_statuses() -> list[Status]:
    """A fresh copy of the starting set, named from the catalogue."""
    cap = current_app.config.get("DEFAULT_WIP_BUILDING_LIMIT", 3) if has_app_context() else 3
    return [Status(key=key, name=tx(f"phase.{key}"), hue=hue, kind=kind, position=position,
                   wip_limit=cap if key == "building" else 0)
            for position, (key, hue, kind) in enumerate(DEFAULT_STATUSES)]


class Status(db.Model):
    """One of an account's plot statuses: a board column or a shelf.

    ``key`` is what ``Project.phase`` stores and it never changes, so
    renaming, recolouring or reordering a status leaves its plots where they
    are. ``wip_limit`` caps how many plots may sit in an active status at
    once; 0 means no cap.
    """
    __tablename__ = "statuses"
    __table_args__ = (db.UniqueConstraint("user_id", "key", name="uq_statuses_user_key"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    key = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    hue = db.Column(db.String(20), nullable=False, default="grey", server_default="grey")
    kind = db.Column(db.String(10), nullable=False, default="active", server_default="active")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    wip_limit = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    @property
    def is_active(self) -> bool:
        return self.kind == "active"

    @property
    def is_parked(self) -> bool:
        return self.kind == "parked"

    @property
    def is_closed(self) -> bool:
        return self.kind == "closed"


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
        """Every task fully pointed and the ultimate, if there is one,
        claimed. An empty branch is not complete."""
        if not self.tasks or self.points_done < self.points_max:
            return False
        return self.ultimate is None or self.ultimate.achieved

    @property
    def is_sealed(self) -> bool:
        """Claimed ultimate: the scheme is finished with, and its points hold
        still until the claim is taken back."""
        return self.ultimate is not None and self.ultimate.achieved

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
            return tx("gate.opens_when", name=self.requires.name)
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

        Each row: ``{"tier", "tasks", "open", "have", "need", "reason",
        "points", "fill", "charged"}``. ``have`` is the points in the row
        above (what the gate counts); ``need`` is the project's gate size.
        ``points`` is this row's own points and ``fill`` how far they go
        towards opening the row below, 0 to 1, so a tier is full exactly when
        it holds enough to open the next one. A closed row reads 0: points
        there cannot count yet.
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
                    tx("gate.needs_points", gate=gate, have=have)
                    if prev["open"] else tx("gate.above_locked"))
            points = sum(t.points_done for t in tasks)
            fill = min(1.0, points / gate) if open_ and gate > 0 else 0.0
            row = {"tier": n, "tasks": tasks, "open": open_, "have": have,
                   "need": gate, "reason": reason, "points": points,
                   "fill": fill, "charged": fill >= 1.0}
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

    # ── Ultimate ────────────────────────────────────────────────────────────
    def ultimate_gate(self) -> tuple[bool, str | None]:
        """Whether the ultimate can be claimed and, if not, why.

        The same rule as a new tier: the last tier must hold enough points
        to open another. So the ultimate is always the step after the last
        tier, however many tiers come to sit above it.
        """
        rows = self.tiers()
        if not rows:
            return False, tx("ultimate.needs_machinations")
        if self.is_locked:
            return False, self.lock_reason
        last = rows[-1]
        if not last["open"]:
            return False, tx("gate.above_locked")
        if last["points"] < last["need"]:
            return False, tx("gate.needs_points", gate=last["need"], have=last["points"])
        return True, None


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False, index=True)
    tier = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    title = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(30), nullable=False, default=DEFAULT_ICON, server_default=DEFAULT_ICON)
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
        """Points may change only on an open tier of an unlocked branch, and
        not once the branch's ultimate is claimed."""
        return not self.branch.is_sealed and self.branch.tier_open(self.tier)

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


class Ultimate(db.Model):
    """A scheme's end goal: one per scheme, drawn below every tier.

    Tiers are numbered and the ultimate is not, so a new tier always lands
    above it. It opens by the tier rule (the last tier holds enough points to
    open another) and is claimed with a click rather than pointed. Once
    claimed it counts towards the scheme being complete, so a scheme that
    waits on this one waits for the ultimate too.
    """
    __tablename__ = "ultimates"

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id", ondelete="CASCADE"),
                          nullable=False, unique=True)
    title = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(30), nullable=False, default=DEFAULT_ICON, server_default=DEFAULT_ICON)
    notes = db.Column(db.Text, nullable=True)
    achieved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    branch = db.relationship(
        "Branch", backref=db.backref("ultimate", uselist=False, cascade="all, delete-orphan"))

    @property
    def achieved(self) -> bool:
        return self.achieved_at is not None

    @property
    def open(self) -> bool:
        return self.branch.ultimate_gate()[0]

    @property
    def reason(self) -> str | None:
        return self.branch.ultimate_gate()[1]

    @property
    def state(self) -> str:
        """``achieved``, ``open`` or ``closed``: the tree's three looks. A
        claimed ultimate stays lit even if the tier above loses a point."""
        if self.achieved:
            return "achieved"
        return "open" if self.open else "closed"

    def set_achieved(self, value: bool) -> None:
        if value and not self.achieved:
            self.achieved_at = _utcnow()
        elif not value:
            self.achieved_at = None


class Thread(db.Model):
    """A sequence link from a machination to what comes after it: another
    machination, or a scheme's ultimate.

    Usually the two sit in different schemes, which is the point: the columns
    show what belongs together, and a thread shows what follows what. It is
    drawn as a bold curved arrow across the tree: grey until the machination
    it leads from is finished, orange once the sequence is under way, and
    green when both ends are done.

    Deliberately not a gate. Tier gates and scheme locks decide what can be
    worked on; a thread only says what the order is.

    Exactly one of ``to_task_id`` and ``to_ultimate_id`` is set. An ultimate
    only ever ends a thread: nothing comes after the end goal.
    """
    __tablename__ = "threads"
    __table_args__ = (
        db.UniqueConstraint("from_task_id", "to_task_id", name="uq_threads_pair"),
        db.UniqueConstraint("from_task_id", "to_ultimate_id", name="uq_threads_ultimate_pair"),
        db.CheckConstraint("(to_task_id IS NULL) <> (to_ultimate_id IS NULL)",
                           name="ck_threads_one_target"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    from_task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    to_task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
                           nullable=True, index=True)
    to_ultimate_id = db.Column(db.Integer, db.ForeignKey("ultimates.id", ondelete="CASCADE"),
                               nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    source = db.relationship("Task", foreign_keys=[from_task_id],
                             backref=db.backref("threads_out", cascade="all, delete-orphan"))
    target_task = db.relationship("Task", foreign_keys=[to_task_id],
                                  backref=db.backref("threads_in", cascade="all, delete-orphan"))
    target_ultimate = db.relationship(
        "Ultimate", foreign_keys=[to_ultimate_id],
        backref=db.backref("threads_in", cascade="all, delete-orphan"))

    @property
    def target(self) -> Task | Ultimate:
        """Whichever end this thread has. Both kinds carry a title and a
        branch, which is all the tree and the forms ask of it."""
        return self.target_ultimate if self.to_ultimate_id or self.target_ultimate else self.target_task

    @target.setter
    def target(self, value) -> None:
        if isinstance(value, Ultimate):
            self.target_ultimate, self.target_task = value, None
        else:
            self.target_task, self.target_ultimate = value, None

    @property
    def started(self) -> bool:
        """Is the machination this leads from finished? Until it is, the
        sequence has not begun and the arrow stays grey."""
        return self.source.state == STATE_FULL

    @property
    def done(self) -> bool:
        """Both ends finished, which is what turns the arrow green. One end
        alone leaves the sequence unfinished, so it stays orange."""
        if not self.started:
            return False
        target = self.target
        if isinstance(target, Ultimate):
            return target.achieved
        return target.state == STATE_FULL


class Routine(db.Model):
    """Something a plot needs doing on a tempo: an ability with a cooldown.

    ``last_done_at`` starts the cooldown and ``every_days`` is its length.
    ``charge`` runs from 0 just after use to 1 when it is ready again, and a
    routine that has never been done is ready. The sums live here so the plot
    page, Today and the tests all read the same clock.
    """
    __tablename__ = "routines"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    icon = db.Column(db.String(30), nullable=False, default=DEFAULT_ICON, server_default=DEFAULT_ICON)
    every_days = db.Column(db.Integer, nullable=False, default=7, server_default="7")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    last_done_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    @property
    def cooldown(self) -> timedelta:
        return timedelta(days=max(1, self.every_days or 1))

    @property
    def ready_at(self) -> datetime | None:
        done = _aware(self.last_done_at)
        return done + self.cooldown if done is not None else None

    @property
    def charge(self) -> float:
        done = _aware(self.last_done_at)
        if done is None:
            return 1.0
        elapsed = (_utcnow() - done).total_seconds()
        return max(0.0, min(1.0, elapsed / self.cooldown.total_seconds()))

    @property
    def is_ready(self) -> bool:
        return self.charge >= 1.0

    @property
    def days_left(self) -> int:
        """Whole days until ready, rounded up; 0 once ready."""
        if self.is_ready:
            return 0
        return max(1, math.ceil((self.ready_at - _utcnow()).total_seconds() / 86400))

    @property
    def overdue_days(self) -> int:
        """Whole days it has sat ready past its tempo; 0 if never done."""
        ready_at = self.ready_at
        if ready_at is None:
            return 0
        return max(0, (_utcnow() - ready_at).days)

    def mark_done(self, at: datetime | None = None) -> None:
        """Use it: restart the cooldown and count it as work on the plot."""
        at = _aware(at) or _utcnow()
        self.last_done_at = at
        self.project.record("routine", note=self.title, at=at)


class Template(db.Model):
    """A user's own starter: the branches a new project begins with.

    The built-ins in ``starters.py`` are code; these are data, owned by one
    user, and the two are offered side by side on the new-project form. A
    built-in can be duplicated into one of these to be edited.
    """
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    hint = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    user = db.relationship("User", backref=db.backref("templates", cascade="all, delete-orphan"))
    branches = db.relationship(
        "TemplateBranch", backref="template", order_by="TemplateBranch.position",
        cascade="all, delete-orphan")

    @property
    def key(self) -> str:
        """How the new-project form names it, distinct from a built-in key."""
        return f"custom:{self.id}"

    @property
    def summary(self) -> str:
        return " → ".join(b.name for b in self.branches) if self.branches else tx("templates.summary_empty")


class TemplateBranch(db.Model):
    __tablename__ = "template_branches"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("templates.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    hue = db.Column(db.String(20), nullable=False, default="green", server_default="green")
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    # Whether this branch waits on the one before it, which is what turns a
    # list of branches into a sequence of phases.
    waits = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    # Starting tasks, one per line, "Title" or "Title | 3" for the points.
    # Kept as the text the form shows rather than a third table: the editor is
    # a textarea, so storing anything else would only be a round trip.
    tasks_text = db.Column(db.Text, nullable=True)

    def tasks(self) -> list[tuple[str, int]]:
        """Parsed (title, points). Junk lines are skipped, not an error."""
        out: list[tuple[str, int]] = []
        for line in (self.tasks_text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            title, _, raw = line.partition("|")
            title = title.strip()[:120]
            if not title:
                continue
            try:
                points = max(1, min(int(raw.strip()), 20))
            except ValueError:
                points = 1
            out.append((title, points))
        return out


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
    """A captured idea that is not a task yet.

    It sits in one of two inboxes, and ``project_id`` is what says which:
    unset means the loose inbox on Today, set means that project's own idea
    list under its tree. Moving one into the tree sets ``task_id``, and that
    -- not ``project_id`` -- is what marks it filed.

    Lifecycle: open -> filed (became a task) | parked (revisit later) | done.
    Parked items come back once ``revisit_on`` passes.
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
        if self.task_id is not None:
            return "filed"
        if self.revisit_on is not None and self.revisit_on > _utcnow().date():
            return "parked"
        return "open"

    @property
    def resurfaced(self) -> bool:
        """Was parked and the date has now passed."""
        return (self.status == "open" and self.revisit_on is not None
                and self.revisit_on <= _utcnow().date())

    @property
    def is_loose(self) -> bool:
        """Open and attached to no project: belongs on Today, not under a tree."""
        return self.status == "open" and self.project_id is None
