"""State stamps (a climber's passport) and the per-state themes behind them."""

import base64
import re
from datetime import date
from unittest import mock

import pytest
import sqlalchemy as sa

from harnesssync import db_store, gym_report, profile_manager, stamps
from harnesssync.states import DEFAULT_THEME, MAP_COLS, MAP_ROWS, STATES, normalize_state, theme_for

ME, OTHER, OWNER = "me@example.test", "other@example.test", "owner@example.com"


@pytest.fixture
def database(tmp_path):
    db_store.configure(f"sqlite:///{(tmp_path / 'stamps.db').as_posix()}")
    for user in (ME, OTHER):
        profile_manager.save_profile(user, user.split("@")[0])
    yield
    db_store.get_engine().dispose()


# ----------------- THE STATE TABLE -----------------
def _contrast_with_white(color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(color[i:i + 2], 16)) for i in (1, 3, 5))
    return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05)


def test_all_fifty_states_have_a_complete_theme_and_their_own_map_tile():
    assert len(STATES) == 50
    assert len({(t.row, t.col) for t in STATES.values()}) == 50
    for code, theme in STATES.items():
        assert re.fullmatch(r"[A-Z]{2}", code) and theme.code == code
        assert theme.name and theme.tagline and theme.emblem
        assert re.fullmatch(r"#[0-9a-f]{6}", theme.color) and re.fullmatch(r"#[0-9a-f]{6}", theme.accent)
        assert 0 <= theme.row < MAP_ROWS and 0 <= theme.col < MAP_COLS
        # White text sits on every stamp and banner: keep it readable (WCAG AA).
        assert _contrast_with_white(theme.color) >= 4.5, code


def test_states_are_read_from_codes_or_names_and_unknown_ones_fall_back_to_the_brand():
    assert normalize_state("ut") == "UT"
    assert normalize_state("  Utah ") == "UT"
    assert normalize_state("new hampshire") == "NH"
    assert normalize_state("Narnia") == normalize_state("") == normalize_state(None) == ""
    assert theme_for("CO").tagline == "Front Range granite"
    assert theme_for("") is DEFAULT_THEME and theme_for("XX") is DEFAULT_THEME


# ----------------- EARNING STAMPS -----------------
def test_a_stamp_is_dated_by_the_first_climb_in_that_state_and_skips_bad_rows():
    history = [
        {"state": "UT", "date": "2026-11-03"},
        {"state": "UT", "date": "2026-10-01"},
        {"state": "id", "date": "2026-09-15"},
        {"state": "", "date": "2026-01-01"},
        {"state": "ZZ", "date": "2026-01-01"},
        {"state": "CO", "date": "not a date"},
        {"state": "WA", "date": "2030-01-01"},  # future-dated, not counted yet
    ]
    earned = stamps.earned_stamps(history, today=date(2026, 11, 18))
    assert [(s.code, s.earned_on) for s in earned] == [("ID", "2026-09-15"), ("UT", "2026-10-01")]
    assert earned[1].tagline == STATES["UT"].tagline


def test_any_climb_or_project_earns_the_stamp_and_only_for_its_own_climber(database):
    assert not profile_manager.climbed_in_state(ME, "UT")
    profile_manager.log_climb(ME, "Boulder", "V3", "Sent", "2026-11-01", state="UT")
    profile_manager.log_project(ME, "Rope", "5.11a", "2026-10-20", state="Idaho", high_point="")
    profile_manager.log_climb(OTHER, "Boulder", "V5", "Sent", "2026-11-01", state="CO")
    assert profile_manager.climbed_in_state(ME, "ut")
    assert not profile_manager.climbed_in_state(ME, "CO")
    mine = stamps.earned_stamps(profile_manager.get_state_history(ME))
    assert [s.code for s in mine] == ["ID", "UT"]
    assert profile_manager.get_state_history("") == []


def test_editing_keeps_the_state_unless_changed_and_sending_a_project_keeps_it(database):
    profile_manager.log_climb(ME, "Boulder", "V3", "Sent", "2026-11-01", state="UT")
    climb = profile_manager.get_climbs(ME)[0]
    profile_manager.update_climb(ME, climb["id"], "Boulder", "V4", "Sent", "2026-11-01")
    assert profile_manager.get_climbs(ME)[0]["state"] == "UT"
    profile_manager.update_climb(ME, climb["id"], "Boulder", "V4", "Sent", "2026-11-01", state="NV")
    assert profile_manager.get_climbs(ME)[0]["state"] == "NV"
    # Someone else can't move my climb to another state.
    profile_manager.update_climb(OTHER, climb["id"], "Boulder", "V4", "Sent", "2026-11-01", state="TX")
    assert profile_manager.get_climbs(ME)[0]["state"] == "NV"

    profile_manager.log_project(ME, "Boulder", "V6", "2026-11-02", high_point="")
    profile_manager.log_project(ME, "Boulder", "V6", "2026-11-03", high_point="", state="WY")
    project = profile_manager.get_projects(ME)[0]
    assert project["state"] == "WY"  # picked up from a later try
    profile_manager.log_project(ME, "Boulder", "V6", "2026-11-04", high_point="", state="MT")
    assert profile_manager.get_projects(ME)[0]["state"] == "WY"  # but never moved by one
    profile_manager.graduate_project(ME, project["id"], "2026-11-05")
    assert {c["state"] for c in profile_manager.get_climbs(ME)} == {"NV", "WY"}


def test_older_databases_gain_state_columns_without_losing_climbs(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy-states.db').as_posix()}"
    db_store.configure(url)
    profile_manager.log_climb(ME, "Boulder", "V2", "Sent", "2026-01-01")
    with db_store.get_engine().begin() as conn:
        for table in ("climbs", "projects", "gyms"):
            conn.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN state")
    db_store.configure(url)
    try:
        for table in ("climbs", "projects", "gyms"):
            columns = {c["name"] for c in sa.inspect(db_store.get_engine()).get_columns(table)}
            assert "state" in columns
        climb = profile_manager.get_climbs(ME)[0]
        assert (climb["grade"], climb["state"]) == ("V2", "")
    finally:
        db_store.get_engine().dispose()


def test_a_pilot_gym_carries_its_state_and_only_the_owner_sets_it(database):
    with mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": [OWNER]}):
        slug = gym_report.add_gym(OWNER, "Red Rock Gym", "UT")
        assert gym_report.get_gym(slug)["state"] == "UT"
        gym_report.set_gym_state(OWNER, slug, "Nevada")
        assert gym_report.get_gym(slug)["state"] == "NV"
        assert gym_report.list_gyms()[0]["state"] == "NV"
        with pytest.raises(PermissionError):
            gym_report.set_gym_state(ME, slug, "TX")


# ----------------- DRAWING -----------------
def _decoded_images(html):
    return [base64.b64decode(data).decode("utf-8") for data in re.findall(r"base64,([A-Za-z0-9+/=]+)", html)]


def test_the_map_colours_only_earned_states():
    svg = stamps.passport_map_svg({"UT", "ID"})
    assert svg.count("<rect") == 50
    assert STATES["UT"].color in svg and STATES["ID"].color in svg
    assert STATES["CO"].color not in svg
    assert svg.count(stamps.LOCKED_FILL) == 48


def test_passport_html_uses_images_and_escapes_text():
    html = stamps.passport_map_html({"UT"}, 'Map "with" <tags>')
    assert "<svg" not in html  # st.html drops inline SVG; an <img> survives
    assert 'alt="Map &quot;with&quot; &lt;tags&gt;"' in html
    assert "<svg" in _decoded_images(html)[0]
    grid = stamps.stamp_grid_html(stamps.earned_stamps([{"state": "UT", "date": "2026-11-01"}]))
    assert "Red rock and desert towers" in grid
    (stamp,) = _decoded_images(grid)
    assert "UTAH" in stamp and "2026-11-01" in stamp and STATES["UT"].color in stamp
    banner = stamps.state_banner_html("UT", "Climbing in <Utah>")
    assert "&lt;Utah&gt;" in banner and STATES["UT"].color in banner


def test_a_locked_stamp_is_grey():
    svg = stamps.stamp_svg("CO")
    assert "LOCKED" in svg and STATES["CO"].color not in svg
