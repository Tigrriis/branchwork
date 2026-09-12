"""Starter templates: the branches a new project begins with.

Each starter is a list of branches; ``chain`` makes every branch wait on the
one before it, which is what turns branches into lifecycle phases.
"""
from models import Branch, Project

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
}
DEFAULT_STARTER = "lifecycle"


def apply_starter(project: Project, key: str) -> list[Branch]:
    """Create the starter's branches on ``project`` (not yet committed)."""
    spec = STARTERS.get(key) or STARTERS["blank"]
    made: list[Branch] = []
    for pos, (name, hue) in enumerate(spec["branches"]):
        branch = Branch(project=project, name=name, hue=hue, position=pos)
        if spec["chain"] is True and made:
            branch.requires = made[-1]
        elif spec["chain"] == "last" and pos == len(spec["branches"]) - 1 and made:
            branch.requires = made[-1]
        made.append(branch)
    return made
