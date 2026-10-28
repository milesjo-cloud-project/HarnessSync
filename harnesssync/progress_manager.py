"""Personal goals and deterministic recaps from an account's existing log."""

from datetime import date

import sqlalchemy as sa

from harnesssync.db_store import get_db, goals, rows
from harnesssync.grades import SENT_STATUSES
from harnesssync.profile_manager import best_send

GOAL_KINDS = ["Sends", "Climbing days"]
GOAL_DISCIPLINES = ["All", "Boulder", "Rope"]


def create_goal(user_id, kind, discipline, target, start_date, end_date):
    if not user_id:
        raise ValueError("Sign in before saving a goal.")
    if kind not in GOAL_KINDS or discipline not in GOAL_DISCIPLINES:
        raise ValueError("Choose a supported goal.")
    if isinstance(target, bool) or not isinstance(target, int) or not 1 <= target <= 10000:
        raise ValueError("Choose a target between 1 and 10,000.")
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start > end:
        raise ValueError("The deadline must be on or after the start date.")
    with get_db() as conn:
        conn.execute(goals.insert().values(
            user_id=user_id, kind=kind, discipline=discipline, target=target,
            start_date=start.isoformat(), end_date=end.isoformat(),
        ))


def get_goals(user_id):
    if not user_id:
        return []
    with get_db() as conn:
        return rows(conn.execute(sa.select(goals).where(goals.c.user_id == user_id)
                                 .order_by(goals.c.end_date, goals.c.id)))


def delete_goal(user_id, goal_id):
    with get_db() as conn:
        conn.execute(goals.delete().where(goals.c.user_id == user_id, goals.c.id == goal_id))


def goal_progress(goal, climbs, today):
    """Completed sends only, through today; edits and deletions recalculate totals."""
    end = min(goal["end_date"], today.isoformat())
    matching = [c for c in climbs if goal["start_date"] <= c["date"] <= end
                and c["status"] in SENT_STATUSES
                and (goal["discipline"] == "All" or c["discipline"] == goal["discipline"])]
    count = len({c["date"] for c in matching}) if goal["kind"] == "Climbing days" else len(matching)
    status = "Achieved" if count >= goal["target"] else (
        "Ended" if goal["end_date"] < today.isoformat() else "Upcoming" if goal["start_date"] > today.isoformat() else "In progress")
    return count, status


def session_recaps(climbs, sessions, today):
    """Group by logged climbing date, never claim date-only logs match a timer interval."""
    days = sorted({r["date"] for r in [*climbs, *sessions] if r["date"] <= today.isoformat()}, reverse=True)
    result = []
    for day in days:
        records = [c for c in climbs if c["date"] == day]
        timed = [s for s in sessions if s["date"] == day]
        result.append(dict(
            date=day, climbs=records, logged=len(records),
            sends=sum(c["status"] in SENT_STATUSES for c in records),
            minutes=round(sum(s["duration_min"] for s in timed), 1), timers=timed,
            boulder=best_send(records, "Boulder"), rope=best_send(records, "Rope"),
        ))
    return result
