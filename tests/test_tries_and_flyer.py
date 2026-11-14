"""Every try on a project is kept with how high it got, and each pilot gym
gets a flyer whose QR opens the app with that gym's name."""

from unittest import mock

import pytest

from harnesssync import db_store, gym_flyer, gym_report, profile_manager
from harnesssync.db_store import get_db, project_tries

ME, OTHER = "me@example.test", "other@example.test"


@pytest.fixture(autouse=True)
def database(tmp_path):
    db_store.configure(f"sqlite:///{(tmp_path / 'tries.db').as_posix()}")
    for user in (ME, OTHER):
        profile_manager.save_profile(user, user.split("@")[0])
    yield
    db_store.get_engine().dispose()


def _try_rows():
    with get_db() as conn:
        return db_store.rows(conn.execute(project_tries.select()))


def test_each_try_is_saved_and_the_best_high_point_wins():
    assert profile_manager.log_project(ME, "Boulder", "V5", "2026-11-01", high_point="Halfway") == "added"
    assert profile_manager.log_project(ME, "Boulder", "V5", "2026-11-02", high_point="Past the crux") == "bumped"
    assert profile_manager.log_project(ME, "Boulder", "V5", "2026-11-03", high_point="") == "bumped"
    project = profile_manager.get_projects(ME)[0]
    profile_manager.add_project_attempt(ME, project["id"], high_point="First moves", try_date="2026-11-04")
    project = profile_manager.get_projects(ME)[0]
    assert project["attempts"] == 4 and project["tries_logged"] == 4
    assert project["high_points"] == ["Halfway", "Past the crux", "First moves"]
    assert project["best_high_point"] == "Past the crux"


def test_old_style_attempts_still_count_without_try_rows():
    profile_manager.log_project(ME, "Rope", "5.10a", "2026-11-01", attempts=3)
    project = profile_manager.get_projects(ME)[0]
    profile_manager.add_project_attempt(ME, project["id"])
    project = profile_manager.get_projects(ME)[0]
    assert (project["attempts"], project["tries_logged"], project["best_high_point"]) == (4, 0, "")


def test_a_try_cannot_be_added_to_someone_elses_project_or_with_a_made_up_high_point():
    profile_manager.log_project(ME, "Boulder", "V3", "2026-11-01", high_point="Halfway")
    mine = profile_manager.get_projects(ME)[0]
    profile_manager.add_project_attempt(OTHER, mine["id"], high_point="Last move")
    assert profile_manager.get_projects(ME)[0]["attempts"] == 1
    assert len(_try_rows()) == 1
    with pytest.raises(ValueError):
        profile_manager.add_project_attempt(ME, mine["id"], high_point="Summit")
    assert profile_manager.get_projects(OTHER) == []


def test_tries_go_with_the_project_when_it_is_sent_deleted_or_the_account_is():
    for grade in ("V2", "V3", "V4"):
        profile_manager.log_project(ME, "Boulder", grade, "2026-11-01", high_point="Halfway")
    v4, v3, v2 = profile_manager.get_projects(ME)
    profile_manager.graduate_project(ME, v2["id"], "2026-11-02")
    profile_manager.delete_project(ME, v3["id"])
    assert [t["project_id"] for t in _try_rows()] == [v4["id"]]
    profile_manager.delete_account(ME)
    assert _try_rows() == []


def test_flyer_link_and_page_name_the_gym_and_carry_a_qr_code():
    with mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": ["owner@example.com"]}):
        slug = gym_report.add_gym("owner@example.com", "<b>Rock & Roll</b> Gym")
    assert gym_flyer.flyer_link(slug) == "https://harnesssync.onrender.com/?gym=b-rock-roll-b-gym"
    page = gym_flyer.render_flyer_html(gym_report.get_gym(slug))
    assert "&lt;b&gt;Rock &amp; Roll&lt;/b&gt; Gym" in page and "<b>Rock" not in page
    assert page.count("<svg") == 1 and "harnesssync.onrender.com/?gym=b-rock-roll-b-gym" in page
