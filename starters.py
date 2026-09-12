"""Starter templates: the branches a new project begins with.

Each starter is a list of branches; ``chain`` makes every branch wait on the
one before it, which is what turns branches into lifecycle phases.

A starter may also seed ``tasks``: ``{branch name: [(title, icon, points)]}``,
all placed in tier 1. That is for templates whose value is the method rather
than the column names — see ``business`` below.
"""
from models import Branch, Project, Task

# The systemisation ladder, spelled out for the templates that use it. Tiers
# rather than branches, because every area of a business climbs the same rungs
# independently and the tier gate stops you systemising what you never mapped.
LADDER = "Tier 1 map it · 2 fix the worst of it · 3 write the checklist · 4 put a number on it"

STARTERS: dict[str, dict] = {
    "blank": {"label": "Blank", "hint": "No branches. Add your own.", "branches": [], "chain": False},
    "lifecycle": {
        "label": "Lifecycle",
        "hint": "Idea → Prototype → Build → Launch → Maintain, each waiting on the last.",
        "branches": [("Idea", "violet"), ("Prototype", "blue"), ("Build", "green"),
                     ("Launch", "amber"), ("Maintain", "teal")],
        "chain": True,
    },
    "engineering": {
        "label": "Engineering job",
        "hint": "Design → Approvals → Construction, construction waiting on approvals.",
        "branches": [("Design", "green"), ("Approvals", "blue"), ("Construction", "red")],
        "chain": "last",
    },
    "software": {
        "label": "Software",
        "hint": "Spec, Build and Ship side by side, plus a Maintain branch that opens after Ship.",
        "branches": [("Spec", "violet"), ("Build", "green"), ("Ship", "amber"), ("Maintain", "teal")],
        "chain": "last",
    },
    # For a business that already runs and needs systemising rather than
    # building. Nothing is chained on purpose: an operating business cannot
    # put Finance on hold until Sales is "finished", and a locked column would
    # grey out work that is actually happening. The sequence lives in the
    # tiers instead, one ladder per area, so each area keeps its own tempo and
    # the board shows at a glance which one you have stopped touching.
    "business": {
        "label": "Running business",
        "hint": ("Five areas of a business that already operates, each improving at its own pace. "
                 + LADDER + ". Starts with one mapping task per area."),
        "branches": [("Sales & marketing", "amber"), ("Delivery", "green"),
                     ("Finance & admin", "blue"), ("People", "violet"),
                     ("Systems & tools", "teal")],
        "chain": False,
        # Worth 3 points each, which is the default gate: finish the map and
        # tier 2 opens by itself. Deliberately one task per area, not a
        # pre-filled backlog of guesses about someone else's business.
        "tasks": {
            "Sales & marketing": [("Map how work is won today", "chart", 3)],
            "Delivery": [("Map how a job runs start to finish", "truck", 3)],
            "Finance & admin": [("Map the money in and out", "cash", 3)],
            "People": [("Map who does what, and what only you can do", "users", 3)],
            "Systems & tools": [("List every tool in use and what it is for", "gear", 3)],
        },
    },
}
DEFAULT_STARTER = "lifecycle"


def apply_starter(project: Project, key: str) -> list[Branch]:
    """Create the starter's branches, and any seeded tasks, on ``project``.

    Nothing is added to the session here; the caller adds the returned
    branches and the ``save-update`` cascade carries the tasks with them.
    """
    spec = STARTERS.get(key) or STARTERS["blank"]
    seeded = spec.get("tasks") or {}
    made: list[Branch] = []
    for pos, (name, hue) in enumerate(spec["branches"]):
        branch = Branch(project=project, name=name, hue=hue, position=pos)
        if spec["chain"] is True and made:
            branch.requires = made[-1]
        elif spec["chain"] == "last" and pos == len(spec["branches"]) - 1 and made:
            branch.requires = made[-1]
        for index, (title, icon, points) in enumerate(seeded.get(name, [])):
            Task(branch=branch, tier=1, position=index, title=title, icon=icon,
                 points_max=points, points_done=0)
        made.append(branch)
    return made
