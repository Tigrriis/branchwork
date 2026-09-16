"""Machination icons: the set is whatever SVG files sit in the icon folder."""
import pytest

import icons


@pytest.fixture
def icon_dir(tmp_path, monkeypatch):
    """An empty icon folder in place of the real one, restored afterwards."""
    monkeypatch.setattr(icons, "ICON_DIR", str(tmp_path))
    icons.refresh()
    yield tmp_path
    monkeypatch.undo()
    icons.refresh()


def test_the_set_is_the_folder_and_the_bomb_is_the_default():
    icons.refresh()
    assert "bomb" in icons.icon_names()
    assert icons.default_icon() == "bomb"


def test_white_is_drawn_in_the_surrounding_colour():
    svg = str(icons.icon_svg("bomb", 24))
    assert 'width="24"' in svg and 'height="24"' in svg and 'viewBox="0 0 18 18"' in svg
    assert "currentColor" in svg and "#fff" not in svg.lower()
    assert svg.startswith("<svg") and "<?xml" not in svg and "DOCTYPE" not in svg


def test_unknown_or_retired_names_fall_back_to_the_default():
    assert icons.icon_svg("hammer") == icons.icon_svg("bomb")
    assert icons.clean_icon("hammer") == "bomb"
    assert icons.clean_icon(None) == "bomb"
    assert icons.clean_icon("bomb") == "bomb"


def test_a_new_file_joins_the_set_and_unsafe_or_badly_named_ones_do_not(icon_dir):
    assert icons.icon_names() == [] and str(icons.icon_svg("anything")) == ""

    (icon_dir / "Skull.svg").write_text(
        '<svg viewBox="0 0 10 10" style="stroke-linecap:round"><defs><linearGradient id="g"/></defs>'
        '<path fill="url(#g)" stroke="#FFFFFF" d="M0 0h10"/><use href="#g"/>'
        '<path style="fill:#e0a53a" d="M1 1h1"/></svg>', encoding="utf-8")
    (icon_dir / "evil.svg").write_text('<svg viewBox="0 0 1 1" onload="alert(1)"></svg>', encoding="utf-8")
    (icon_dir / "sneaky.svg").write_text('<svg viewBox="0 0 1 1"><script>x()</script></svg>', encoding="utf-8")
    (icon_dir / "has space.svg").write_text('<svg viewBox="0 0 1 1"></svg>', encoding="utf-8")
    (icon_dir / "no-viewbox.svg").write_text('<svg width="1"></svg>', encoding="utf-8")
    icons.refresh()

    assert icons.icon_names() == ["skull"]
    assert icons.default_icon() == "skull"          # no bomb here, so the first icon stands in
    svg = str(icons.icon_svg("skull", 10))
    assert 'id="mi-skull-g"' in svg and "url(#mi-skull-g)" in svg and 'href="#mi-skull-g"' in svg
    assert 'stroke="currentColor"' in svg
    assert "fill:#e0a53a" in svg                    # colours other than white are kept
    assert 'style="stroke-linecap:round"' in svg


def test_the_pickers_offer_the_new_set(client, db):
    from conftest import login, make_branch, make_project, make_user

    user = make_user()
    login(client)
    project = make_project(user)
    branch = make_branch(project)
    for url in (f"/branches/{branch.id}/tasks/new", f"/projects/{project.id}/routines/new"):
        html = client.get(url).data.decode()
        assert 'name="icon" value="bomb"' in html, url
        assert 'value="hammer"' not in html and 'value="check"' not in html, url
