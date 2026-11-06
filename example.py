"""The example plot every new account starts with.

It is the plot drawn on the landing page, "Take over the world", made
real: the same schemes, tiles, points and lock, with a title on every
machination, so the first thing a new account sees is a tree with something
in it to click. It is an ordinary plot, so it can be edited or deleted like
any other. Every word is in the copy file, under [landing] for the names the
landing page shares and [example] for the rest.
"""
from copytext import tx
from extensions import db
from models import Branch, Project, Task, Ultimate, User

# Per scheme: (copy key for its name, hue, icon of its ultimate, tiers).
# Each tile is (copy key for its title, icon, points done, points max). The
# numbers match landing.demo_plot, so the example looks like the landing page.
SCHEMES = [
    ("landing.demo_scheme_1", "green", "crown", [
        [("example.m_plans", "doc", 3, 3), ("example.m_observatory", "hall", 2, 2),
         ("example.m_throne", "crown", 2, 4)],
        [("example.m_lease", "doc_tick", 1, 1), ("example.m_inspection", "ballot", 2, 2)],
    ]),
    ("landing.demo_scheme_2", "blue", None, [
        [("example.m_account", "bank", 1, 1), ("example.m_heist", "coin", 2, 3)],
        [("example.m_key", "key", 1, 2), ("example.m_payroll", "inbox", 0, 1)],
    ]),
    ("landing.demo_scheme_3", "red", None, [
        [("example.m_volcano", "volcano", 0, 3), ("example.m_henchmen", "crew", 0, 2),
         ("example.m_device", "bomb", 0, 5)],
        [("example.m_pond", "flask", 0, 2)],
    ]),
]


def add_example_plot(user: User) -> Project:
    """Give ``user`` the example plot, in focus. The caller commits."""
    status = user.status("building") or user.default_status
    project = Project(owner=user, name=tx("landing.demo_plot"), phase=status.key,
                      gate_points=3, cadence_days=14, focused=True,
                      objective=tx("example.objective"), next_action=tx("example.next_action"))
    db.session.add(project)
    branches = []
    for position, (name_key, hue, ultimate_icon, tiers) in enumerate(SCHEMES):
        branch = Branch(project=project, name=tx(name_key), hue=hue, position=position)
        db.session.add(branch)
        for tier, tiles in enumerate(tiers, start=1):
            for index, (title_key, icon, done, most) in enumerate(tiles):
                task = Task(branch=branch, tier=tier, position=index, title=tx(title_key),
                            icon=icon, points_max=most)
                task.set_points(done)
                db.session.add(task)
        if ultimate_icon:
            db.session.add(Ultimate(branch=branch, title=tx("landing.demo_ultimate"),
                                    icon=ultimate_icon))
        branches.append(branch)
    # The Device waits on Funding, as on the landing page.
    branches[2].requires = branches[1]
    project.record("touch", note="Example plot")
    return project
