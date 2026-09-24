"""The one home page: Today, the board and the review folded together."""
import re
from datetime import date, timedelta

from conftest import copy_in, login, make_branch, make_project, make_task, make_user


def _tile(html, project_id):
    """The markup of one plot's tile, from its opening tag to the next tile."""
    start = html.rindex("<article", 0, html.index(f'id="p{project_id}"'))
    rest = html[start:]
    end = re.search(r'<article class="[pbr]tile', rest[1:])
    return rest[: end.start() + 1] if end else rest


def test_old_pages_land_on_the_home_page(client, db):
    make_user()
    login(client)
    r = client.get("/board")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    # Review keeps its ticks on the way.
    r = client.get("/review?done=4,5")
    assert r.status_code == 302
    assert r.headers["Location"] == "/?review=1&done=4,5"


def test_a_focus_tile_draws_the_tree_in_miniature(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.name, p.phase = "Death ray", "building"
    design = make_branch(p, "Design", hue="blue")
    make_task(design, "Sketch", points_done=1)
    make_task(design, "Model", points_max=3, points_done=1)
    make_task(design, "Test", tier=2)
    build = make_branch(p, "Build", hue="red", requires=design)
    make_task(build, "Weld")
    db.session.commit()

    tile = _tile(client.get("/").data.decode(), p.id)
    assert tile.startswith('<article class="ptile')
    # One column per scheme in its hue, one pip per machination by state.
    assert tile.count('class="mtree__col') == 2
    assert "hue--blue" in tile and "hue--red" in tile
    assert tile.count("mtree__pip--full") == 1 and tile.count("mtree__pip--part") == 1
    assert tile.count("mtree__pip--empty") == 2
    # Tier 2 is still shut, and Build waits on Design.
    assert "mtree__tier is-closed" in tile
    assert "is-locked" in tile and copy_in(tile, "tile.locked")


def test_a_plot_without_schemes_says_so(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.phase = "idea"
    db.session.commit()
    assert copy_in(_tile(client.get("/").data.decode(), p.id), "tile.no_schemes")


def test_every_tile_offers_every_status_with_its_cap(client, db):
    user = make_user()
    user.status("building").wip_limit = 2
    db.session.commit()
    login(client)
    for name in ("Lair", "Moat"):
        p = make_project(user); p.name, p.phase = name, "building"
    idea = make_project(user); idea.phase = "idea"
    db.session.commit()

    tile = _tile(client.get("/").data.decode(), idea.id)
    for status in user.statuses:
        assert f'name="phase" value="{status.key}"' in tile
    # The current status cannot be picked again, and a full one says so.
    assert re.search(r'value="idea"\s+disabled', tile)
    assert re.search(r'spick__count is-full">\s*2 / 2', tile)


def test_moving_from_a_tile_still_respects_the_cap(client, db):
    user = make_user()
    user.status("building").wip_limit = 1
    db.session.commit()
    login(client)
    first = make_project(user); first.phase = "building"
    second = make_project(user); second.phase = "exploring"
    db.session.commit()
    r = client.post(f"/plots/{second.id}/phase", data={"phase": "building"},
                    headers={"Referer": "/"}, follow_redirects=True)
    assert r.request.path == "/"
    db.session.refresh(second)
    assert second.phase == "exploring"


def test_parked_and_closed_plots_sit_on_shelves(client, db):
    user = make_user()
    login(client)
    later = (date.today() + timedelta(days=20)).isoformat()
    parked = make_project(user); parked.name = "Volcano base"
    finished = make_project(user); finished.name, finished.phase = "Shark tank", "done"
    db.session.commit()
    client.post(f"/plots/{parked.id}/phase", data={"phase": "parked", "parked_until": later})

    html = client.get("/").data.decode()
    shelves = html[html.index('class="shelves"'):]
    assert "Volcano base" in shelves and "Shark tank" in shelves
    assert copy_in(shelves, "board.reopen") and copy_in(shelves, "common.pick_up")
    # Shelved plots are not tiles.
    assert f'id="p{parked.id}"' not in html and f'id="p{finished.id}"' not in html


def test_review_mode_flips_every_live_tile(client, db):
    user = make_user()
    login(client)
    doing = make_project(user); doing.name, doing.phase = "Doing", "building"
    later = make_project(user); later.name, later.phase, later.focused = "Later", "idea", False
    db.session.commit()
    back = make_project(user); back.name = "Back again"
    db.session.commit()
    client.post(f"/plots/{back.id}/phase", data={"phase": "parked",
                                                "parked_until": (date.today() - timedelta(days=1)).isoformat()})

    plain = client.get("/").data.decode()
    assert '<article class="rtile' not in plain
    assert 'href="/?review=1"' in plain

    html = client.get("/?review=1").data.decode()
    # Focus, backburner and the plot back from the shelf, one decision each.
    assert html.count('<article class="rtile') == 3
    assert '<article class="ptile' not in html and '<article class="btile' not in html
    assert copy_in(html, "review.finish") and 'value="unpark"' in html
    assert copy_in(html, "review.progress", done=0, total=3)


def test_a_plot_whose_status_vanished_stays_on_the_page(client, db):
    user = make_user()
    login(client)
    p = make_project(user); p.name, p.phase = "Orphaned scheme", "no-such-status"
    db.session.commit()
    html = client.get("/").data.decode()
    assert f'id="p{p.id}"' in html


def test_there_is_no_manual_touch(client, db):
    """Ticking off a machination or using a routine is the touch; nothing
    else claims work was done."""
    user = make_user()
    login(client)
    p = make_project(user); p.phase = "building"
    db.session.commit()
    for url in ("/", f"/plots/{p.id}"):
        assert "/touch" not in client.get(url).data.decode(), url
    before = p.last_activity_at
    assert client.post(f"/plots/{p.id}/touch").status_code in (404, 405)
    db.session.refresh(p)
    assert p.last_activity_at == before
