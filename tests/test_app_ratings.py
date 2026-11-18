"""The "How's HarnessSync?" survey: climbers rate, only the owner reads."""

import csv
import io
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
import sqlalchemy as sa
from streamlit.testing.v1 import AppTest

from harnesssync import app_ratings, db_store, gym_report, profile_manager

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app.py")
OWNER = "owner@example.com"
CLIMBER = "climber@example.test"
GUEST = "dev:guest"  # dev mode's default "Guest" climber
NOW = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def database(tmp_path):
    db_store.configure(f"sqlite:///{(tmp_path / 'ratings.db').as_posix()}")
    with mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": [OWNER]}):
        yield
    db_store.get_engine().dispose()


def test_a_rating_is_saved_with_its_comment_and_gym():
    entry = app_ratings.submit_rating(CLIMBER, 4, "  Love the quick log  ", " The  Rock Gym ", now=NOW)
    assert entry["rating"] == 4
    saved = app_ratings.last_rating(CLIMBER)
    assert (saved["rating"], saved["comment"], saved["gym"]) == (4, "Love the quick log", "The Rock Gym")
    assert app_ratings.last_rating("someone-else@example.test") is None


@pytest.mark.parametrize("rating", [None, 0, 6, "five"])
def test_a_rating_must_be_one_to_five_stars(rating):
    with pytest.raises(ValueError):
        app_ratings.submit_rating(CLIMBER, rating, now=NOW)
    assert app_ratings.last_rating(CLIMBER) is None


def test_comment_and_gym_are_optional_and_capped():
    app_ratings.submit_rating(CLIMBER, 5, now=NOW)
    assert app_ratings.last_rating(CLIMBER)["comment"] == ""
    app_ratings.submit_rating(CLIMBER, 3, "x" * 5000, "g" * 500, now=NOW + timedelta(minutes=1))
    saved = app_ratings.last_rating(CLIMBER)
    assert len(saved["comment"]) == app_ratings.COMMENT_MAX
    assert len(saved["gym"]) == app_ratings.GYM_MAX


def test_one_account_cannot_flood_the_average():
    for minute in range(app_ratings.DAILY_LIMIT):
        app_ratings.submit_rating(CLIMBER, 1, now=NOW + timedelta(minutes=minute))
    with pytest.raises(ValueError):
        app_ratings.submit_rating(CLIMBER, 1, now=NOW + timedelta(hours=2))
    app_ratings.submit_rating(CLIMBER, 5, now=NOW + timedelta(days=1, minutes=5))
    app_ratings.submit_rating("other@example.test", 5, now=NOW + timedelta(hours=2))


def test_only_the_owner_sees_the_summary_and_export():
    app_ratings.submit_rating(CLIMBER, 4, "Nice", now=NOW)
    with pytest.raises(PermissionError):
        app_ratings.owner_summary(CLIMBER)
    with pytest.raises(PermissionError):
        app_ratings.owner_csv(CLIMBER)
    with pytest.raises(PermissionError):
        app_ratings.owner_summary("dev:owner@example.com")


def test_summary_counts_averages_and_lists_the_latest_comments_first():
    assert app_ratings.owner_summary(OWNER)["responses"] == 0
    assert app_ratings.owner_summary(OWNER)["average"] is None
    app_ratings.submit_rating(CLIMBER, 5, "First", "Basalt", now=NOW)
    app_ratings.submit_rating(CLIMBER, 4, "", now=NOW + timedelta(minutes=5))
    app_ratings.submit_rating("other@example.test", 2, "Too many taps", now=NOW + timedelta(hours=1))
    summary = app_ratings.owner_summary(OWNER)
    assert summary["responses"] == 3
    assert summary["climbers"] == 2
    assert summary["average"] == 3.7
    assert summary["by_rating"] == {1: 0, 2: 1, 3: 0, 4: 1, 5: 1}
    assert [c["comment"] for c in summary["latest_comments"]] == ["Too many taps", "First"]
    assert summary["latest_comments"][1]["gym"] == "Basalt"


def test_owner_views_never_include_emails():
    app_ratings.submit_rating(CLIMBER, 5, "=HYPERLINK(\"http://x\")", now=NOW)
    app_ratings.submit_rating(CLIMBER, 4, "Again", now=NOW + timedelta(minutes=5))
    app_ratings.submit_rating("other@example.test", 3, now=NOW + timedelta(minutes=9))
    assert CLIMBER not in repr(app_ratings.owner_summary(OWNER))
    exported = app_ratings.owner_csv(OWNER)
    assert CLIMBER not in exported and "other@example.test" not in exported
    table = list(csv.DictReader(io.StringIO(exported)))
    assert [r["respondent"] for r in table] == ["1", "1", "2"]
    assert table[0]["comment"].startswith("'=")  # not run as a spreadsheet formula


def test_the_new_table_is_added_to_an_existing_database_without_losing_data(tmp_path):
    url = f"sqlite:///{(tmp_path / 'existing.db').as_posix()}"
    db_store.configure(url)
    profile_manager.save_profile(CLIMBER, "Climber")
    profile_manager.log_climb(CLIMBER, "Boulder", "V3", "Sent", "2026-11-01")
    with db_store.get_engine().begin() as conn:
        conn.exec_driver_sql("DROP TABLE app_ratings")
    db_store.configure(url)  # what start-up does against the live database
    assert "app_ratings" in sa.inspect(db_store.get_engine()).get_table_names()
    assert len(profile_manager.get_climbs(CLIMBER)) == 1
    app_ratings.submit_rating(CLIMBER, 5, now=NOW)


def test_deleting_the_account_deletes_its_ratings():
    profile_manager.save_profile(CLIMBER, "Climber")
    app_ratings.submit_rating(CLIMBER, 5, "Bye", now=NOW)
    app_ratings.submit_rating("other@example.test", 4, now=NOW)
    profile_manager.delete_account(CLIMBER)
    assert app_ratings.last_rating(CLIMBER) is None
    assert app_ratings.owner_summary(OWNER)["responses"] == 1


# ----------------- THE PAGE -----------------
def _app(at=None, section="⭐ How's HarnessSync?"):
    if at is None:
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.secrets["auth"] = {}
        at.secrets["email"] = {}
        at.secrets["support"] = {}
    at.session_state["main_tabs"] = "☰ More"
    at.session_state["more_section"] = section
    at.run()
    assert [e.value for e in at.exception] == []
    assert [e.value for e in at.error] == []
    return at


def _button(at, label):
    return next(b for b in at.button if b.label == label)


@pytest.fixture
def dev_mode(monkeypatch):
    monkeypatch.setenv("HARNESSSYNC_DEV_MODE", "1")


def test_how_is_harnesssync_is_the_first_section_under_more(dev_mode):
    at = _app()
    assert at.segmented_control(key="more_section").options[0].endswith("How's HarnessSync?")
    assert "How's HarnessSync?" in [h.value for h in at.header]


def test_climber_rates_the_app_from_more(dev_mode):
    at = _app()
    _button(at, "Send rating").click()
    at = _app(at)  # no stars picked: nothing saved, the form stays
    assert any("1 to 5 stars" in w.value for w in at.warning)
    assert app_ratings.last_rating(GUEST) is None

    at.radio(key="rate_app_rating_0").set_value(4)
    next(w for w in at.text_area if w.label.startswith("Anything we should")).set_value("Logging is fast")
    _button(at, "Send rating").click()
    at = _app(at)
    saved = app_ratings.last_rating(GUEST)
    assert (saved["rating"], saved["comment"]) == (4, "Logging is fast")
    assert any("★★★★☆" in s.value for s in at.success)
    # The fresh form is blank again for the next answer.
    assert at.radio(key="rate_app_rating_1").value is None


def test_gym_starts_as_the_climbers_pilot_gym(dev_mode):
    _app()  # creates the dev profile
    slug = gym_report.add_gym(OWNER, "Basalt Bouldering")
    gym_report.join_gym(GUEST, slug, NOW.date())
    at = _app()
    assert next(w for w in at.text_input if w.label == "Your gym (optional)").value == "Basalt Bouldering"


def test_owner_panel_shows_counts_average_and_comments_and_others_cannot(dev_mode):
    app_ratings.submit_rating(CLIMBER, 5, "Love it", "Basalt", now=NOW)
    app_ratings.submit_rating("other@example.test", 3, "", now=NOW)
    owner = AppTest.from_string(
        "from harnesssync.ui.feedback import render\nrender('owner@example.com', 'Owner')",
        default_timeout=30,
    )
    owner.secrets["support"] = {"owner_emails": [OWNER]}
    owner.secrets["email"] = {}
    owner.run()
    assert [e.value for e in owner.exception] == []
    assert "Owner app ratings" in [e.label for e in owner.expander]
    metrics = {m.label: m.value for m in owner.metric}
    assert metrics["Responses"] == "2"
    assert metrics["Average rating"] == "4.0 / 5"
    assert "Love it" in [t.value for t in owner.text]
    assert CLIMBER not in " ".join(c.value for c in owner.caption)

    at = _app(section="💬 Help & report a problem")
    assert "Owner app ratings" not in [e.label for e in at.expander]
