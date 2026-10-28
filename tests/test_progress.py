"""Goals and recaps use fictional account data and reflect later log edits."""

from datetime import date, datetime, timedelta, timezone

import pytest

from harnesssync import db_store, profile_manager as pm
from harnesssync import progress_manager as progress


@pytest.fixture
def accounts(tmp_path):
    db_store.configure(f"sqlite:///{tmp_path / 'progress.db'}")
    for user in ("fictional:alex", "fictional:blair"):
        pm.save_profile(user, user)
    yield "fictional:alex", "fictional:blair"
    db_store.get_engine().dispose()


def test_goals_are_scoped_and_recalculate_after_edits(accounts):
    alex, blair = accounts
    progress.create_goal(alex, "Sends", "Boulder", 2, "2026-01-01", "2026-01-31")
    assert progress.get_goals(blair) == []
    goal = progress.get_goals(alex)[0]
    progress.delete_goal(blair, goal["id"])
    assert len(progress.get_goals(alex)) == 1
    for discipline, status, day in [("Boulder", "Sent", "2026-01-01"), ("Boulder", "Flash", "2026-01-01"),
                                    ("Boulder", "Attempt", "2026-01-02"), ("Rope", "Sent", "2026-01-02"),
                                    ("Boulder", "Sent", "2026-02-01")]:
        pm.log_climb(alex, discipline, "V2" if discipline == "Boulder" else "5.8", status, day)
    climbs = pm.get_climbs(alex)
    assert progress.goal_progress(goal, climbs, date(2026, 1, 20)) == (2, "Achieved")
    days_goal = {**goal, "kind": "Climbing days"}
    assert progress.goal_progress(days_goal, climbs, date(2026, 1, 20)) == (1, "In progress")
    assert progress.goal_progress(days_goal, climbs, date(2026, 2, 2)) == (1, "Ended")
    assert progress.goal_progress(goal, climbs, date(2025, 12, 31)) == (0, "Upcoming")
    supporting = next(c for c in climbs if c["status"] == "Flash")
    pm.delete_climb(alex, supporting["id"])
    assert progress.goal_progress(goal, pm.get_climbs(alex), date(2026, 1, 20)) == (1, "In progress")
    pm.delete_account(alex)
    assert progress.get_goals(alex) == []


@pytest.mark.parametrize("changes", [
    {"target": 0}, {"target": True}, {"target": 1.5}, {"target": 10001},
    {"kind": "Unknown"}, {"discipline": "Unknown"},
    {"start_date": "2026-02-30"}, {"end_date": "2025-01-01"}, {"user_id": ""},
])
def test_invalid_goals_do_not_write(accounts, changes):
    values = dict(user_id=accounts[0], kind="Sends", discipline="All", target=10,
                  start_date="2026-01-01", end_date="2026-01-31")
    with pytest.raises(ValueError):
        progress.create_goal(**{**values, **changes})
    assert progress.get_goals(accounts[0]) == []


def test_daily_recap_combines_timers_without_claiming_exact_climb_times(accounts):
    alex, blair = accounts
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    pm.log_session(alex, start, start + timedelta(minutes=30))
    pm.log_session(alex, start + timedelta(hours=2), start + timedelta(hours=3))
    pm.log_climb(alex, "Boulder", "V3", "Flash", "2026-01-01")
    pm.log_climb(alex, "Boulder", "V5", "Attempt", "2026-01-01")
    pm.log_climb(alex, "Rope", "5.9", "Sent", "2026-01-02")
    pm.log_climb(alex, "Rope", "5.10a", "Sent", "2026-01-05")
    pm.log_climb(blair, "Boulder", "V9", "Sent", "2026-01-01")
    recaps = progress.session_recaps(pm.get_climbs(alex), pm.get_sessions(alex), date(2026, 1, 3))
    assert [r["date"] for r in recaps] == ["2026-01-02", "2026-01-01"]
    assert recaps[0]["minutes"] == 0
    assert recaps[1]["minutes"] == 90
    assert recaps[1]["logged"] == 2
    assert recaps[1]["sends"] == 1
    assert recaps[1]["boulder"]["grade"] == "V3"
    assert recaps[1]["rope"] is None


def test_logging_defaults_are_last_saved_and_account_scoped(accounts):
    alex, blair = accounts
    pm.log_climb(alex, "Boulder", "V3", "Flash", "2026-01-02", location="Fictional gym")
    pm.log_climb(alex, "Rope", "5.9", "Sent", "2026-01-01", location="Fictional crag")
    assert pm.get_logging_defaults(alex)["discipline"] == "Rope"
    assert pm.get_logging_defaults(alex, "Boulder")["location"] == "Fictional gym"
    assert pm.get_logging_defaults(blair) == {}
