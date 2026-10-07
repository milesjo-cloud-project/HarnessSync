"""Climber profiles, climbs, projects and sessions.

Every function that reads or changes a climber's data takes the signed-in
user's `user_id` and filters on it, so one account can never see or modify
another account's rows - even with a guessed record id.
"""

import re
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from harnesssync.grades import grade_rank, SENT_STATUSES
from harnesssync.db_store import get_db, rows, profiles, climbs, projects, sessions, feedback, waitlist

DISPLAY_NAME_MAX = 30
ROUTE_MAX = 80
LOCATION_MAX = 80
NOTES_MAX = 500

# Nobody climbs for twelve hours straight. A session longer than this is a
# timer someone forgot to stop, so it's clamped rather than recorded as-is -
# otherwise one forgotten timer dominates the session history and the CSV.
MAX_SESSION_MIN = 12 * 60


def _clean(text, max_len):
    """Trim, collapse runs of whitespace, and cap length.

    The whitespace collapse is load-bearing, not cosmetic: a display name
    cleaned by this goes into the Subject header of the feedback email, and
    collapsing CR/LF is what stops someone adding their own headers (a Bcc,
    say) by putting a newline in their name. Keep \\s+ covering newlines.
    """
    return re.sub(r"\s+", " ", (text or "")).strip()[:max_len]


# ----------------- PROFILES -----------------
def get_profile(user_id):
    if not user_id:
        return None
    with get_db() as conn:
        found = rows(conn.execute(sa.select(profiles).where(profiles.c.user_id == user_id)))
    return found[0] if found else None


def display_name_taken(display_name, exclude_user_id=None):
    """Case-insensitive, so "Alex" and "alex" can't both be on the leaderboard."""
    query = sa.select(profiles.c.user_id).where(
        sa.func.lower(profiles.c.display_name) == _clean(display_name, DISPLAY_NAME_MAX).lower()
    )
    if exclude_user_id:
        query = query.where(profiles.c.user_id != exclude_user_id)
    with get_db() as conn:
        return conn.execute(query).first() is not None


def save_profile(user_id, display_name, show_on_leaderboard=True):
    """Creates the profile on first sign-in, updates it afterwards."""
    display_name = _clean(display_name, DISPLAY_NAME_MAX)
    if not display_name:
        raise ValueError("Display name can't be empty.")
    with get_db() as conn:
        exists = conn.execute(sa.select(profiles.c.user_id).where(profiles.c.user_id == user_id)).first()
        if exists:
            conn.execute(
                profiles.update().where(profiles.c.user_id == user_id)
                .values(display_name=display_name, show_on_leaderboard=show_on_leaderboard)
            )
        else:
            conn.execute(profiles.insert().values(
                user_id=user_id,
                display_name=display_name,
                show_on_leaderboard=show_on_leaderboard,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ))


def delete_account(user_id):
    """Permanently removes the profile and every row belonging to it."""
    with get_db() as conn:
        for table in (climbs, projects, sessions, feedback, waitlist):
            conn.execute(table.delete().where(table.c.user_id == user_id))
        conn.execute(profiles.delete().where(profiles.c.user_id == user_id))


# ----------------- CLIMBS -----------------
def get_climbs(user_id, discipline=None):
    """A climber's logged climbs, newest first. Never returns other users' data."""
    if not user_id:
        return []
    query = sa.select(climbs).where(climbs.c.user_id == user_id)
    if discipline:
        query = query.where(climbs.c.discipline == discipline)
    query = query.order_by(climbs.c.date.desc(), climbs.c.id.desc())
    with get_db() as conn:
        return rows(conn.execute(query))


def best_send(climb_list, discipline):
    """The hardest *sent* climb in a discipline from an already-loaded list, or None."""
    sends = [c for c in climb_list if c["discipline"] == discipline and c["status"] in SENT_STATUSES]
    return max(sends, key=lambda c: grade_rank(discipline, c["grade"]), default=None)


def best_climb(user_id, discipline):
    """The hardest *sent* climb for a climber in a discipline, or None."""
    return best_send(get_climbs(user_id, discipline), discipline)


def log_climb(user_id, discipline, grade, status, climb_date, route_name="", location="",
              environment="Gym", angle="Vertical", hold_type="Mixed", notes=""):
    """Appends one logged climb. Returns PR alert strings if it's a new best send."""
    previous_best = best_climb(user_id, discipline)
    previous_best_rank = grade_rank(discipline, previous_best["grade"]) if previous_best else -1

    with get_db() as conn:
        conn.execute(climbs.insert().values(
            user_id=user_id, date=climb_date, discipline=discipline, grade=grade, status=status,
            route_name=_clean(route_name, ROUTE_MAX), location=_clean(location, LOCATION_MAX),
            environment=environment, angle=angle, hold_type=hold_type,
            notes=(notes or "").strip()[:NOTES_MAX],
        ))

    if status in SENT_STATUSES and grade_rank(discipline, grade) > previous_best_rank:
        return [f"🏆 New {discipline} personal best: {grade}!"]
    return []


def update_climb(user_id, climb_id, discipline, grade, status, climb_date, route_name="", location="",
                 environment="Gym", angle="Vertical", hold_type="Mixed", notes=""):
    with get_db() as conn:
        conn.execute(
            climbs.update()
            .where(climbs.c.id == climb_id, climbs.c.user_id == user_id)
            .values(
                discipline=discipline, grade=grade, status=status, date=climb_date,
                route_name=_clean(route_name, ROUTE_MAX), location=_clean(location, LOCATION_MAX),
                environment=environment, angle=angle, hold_type=hold_type,
                notes=(notes or "").strip()[:NOTES_MAX],
            )
        )


def delete_climb(user_id, climb_id):
    with get_db() as conn:
        conn.execute(climbs.delete().where(climbs.c.id == climb_id, climbs.c.user_id == user_id))


# ----------------- PROJECTS -----------------
def log_project(user_id, discipline, grade, project_date, route_name="", location="",
                environment="Gym", angle="Vertical", hold_type="Mixed", attempts=1, notes=""):
    """Adds a project. If the climber already has a project with the same
    discipline, grade and route name, adds the attempts to it instead of
    creating a duplicate. Unnamed projects match on location instead, so
    logging "V5 attempt at the gym" twice doesn't make two projects.
    Returns "added" or "bumped"."""
    route_name = _clean(route_name, ROUTE_MAX)
    location = _clean(location, LOCATION_MAX)
    same_project = [
        projects.c.user_id == user_id,
        projects.c.discipline == discipline,
        projects.c.grade == grade,
        sa.func.lower(projects.c.route_name) == route_name.lower(),
    ]
    if not route_name:
        same_project.append(sa.func.lower(projects.c.location) == location.lower())
    with get_db() as conn:
        existing = conn.execute(sa.select(projects.c.id).where(*same_project)).first()
        if existing:
            conn.execute(
                projects.update().where(projects.c.id == existing.id)
                .values(attempts=projects.c.attempts + attempts)
            )
            return "bumped"
        conn.execute(projects.insert().values(
            user_id=user_id, date=project_date, discipline=discipline, grade=grade,
            route_name=route_name, location=location,
            environment=environment, angle=angle, hold_type=hold_type,
            attempts=attempts, notes=(notes or "").strip()[:NOTES_MAX],
        ))
    return "added"


def get_projects(user_id):
    """A climber's active projects, newest first."""
    if not user_id:
        return []
    query = sa.select(projects).where(projects.c.user_id == user_id).order_by(projects.c.id.desc())
    with get_db() as conn:
        return rows(conn.execute(query))


def update_project(user_id, project_id, discipline, grade, project_date, route_name="", location="",
                   environment="Gym", angle="Vertical", hold_type="Mixed", attempts=1, notes=""):
    with get_db() as conn:
        conn.execute(
            projects.update()
            .where(projects.c.id == project_id, projects.c.user_id == user_id)
            .values(
                discipline=discipline, grade=grade, date=project_date,
                route_name=_clean(route_name, ROUTE_MAX), location=_clean(location, LOCATION_MAX),
                environment=environment, angle=angle, hold_type=hold_type,
                attempts=max(1, int(attempts)), notes=(notes or "").strip()[:NOTES_MAX],
            )
        )


def add_project_attempt(user_id, project_id):
    with get_db() as conn:
        conn.execute(
            projects.update()
            .where(projects.c.id == project_id, projects.c.user_id == user_id)
            .values(attempts=projects.c.attempts + 1)
        )


def delete_project(user_id, project_id):
    with get_db() as conn:
        conn.execute(projects.delete().where(projects.c.id == project_id, projects.c.user_id == user_id))


def graduate_project(user_id, project_id, send_date, send_status="Redpoint"):
    """Moves a project into the climb log as a send. Returns PR alerts."""
    with get_db() as conn:
        found = rows(conn.execute(
            sa.select(projects).where(projects.c.id == project_id, projects.c.user_id == user_id)
        ))
    if not found:
        return []
    p = found[0]
    alerts = log_climb(
        user_id, p["discipline"], p["grade"], send_status, send_date,
        route_name=p["route_name"], location=p["location"],
        environment=p["environment"], angle=p["angle"], hold_type=p["hold_type"],
        notes=p["notes"],
    )
    delete_project(user_id, project_id)
    return alerts


# ----------------- SESSIONS -----------------
def log_session(user_id, started_at, ended_at):
    """Records one completed gym/crag session. Returns duration in minutes.

    A session beyond MAX_SESSION_MIN is clamped. The end time is moved with
    it rather than only the duration, so start, end and duration still agree
    with each other in the history table and the CSV export.
    """
    duration_min = round((ended_at - started_at).total_seconds() / 60, 1)
    if duration_min > MAX_SESSION_MIN:
        duration_min = float(MAX_SESSION_MIN)
        ended_at = started_at + timedelta(minutes=MAX_SESSION_MIN)
    with get_db() as conn:
        conn.execute(sessions.insert().values(
            user_id=user_id,
            date=started_at.date().isoformat(),
            started_at=started_at.isoformat(timespec="minutes"),
            ended_at=ended_at.isoformat(timespec="minutes"),
            duration_min=duration_min,
        ))
    return duration_min


def start_session_timer(user_id, started_at):
    """Saves the running timer on the profile, so a reload doesn't lose it."""
    with get_db() as conn:
        conn.execute(
            profiles.update().where(profiles.c.user_id == user_id)
            .values(active_session_started=started_at.isoformat(timespec="seconds"))
        )


def active_session_start(user_id, profile=None):
    """When the user's running session timer started, or None if it isn't running.
    Pass the already-loaded profile to skip a database round trip."""
    if profile is None:
        profile = get_profile(user_id)
    if not profile or not profile.get("active_session_started"):
        return None
    try:
        return datetime.fromisoformat(profile["active_session_started"])
    except ValueError:
        return None


def end_session_timer(user_id, ended_at):
    """Stops the running timer and logs the session. Returns its duration in
    minutes, or None if no timer was running (e.g. ended in another tab)."""
    started_at = active_session_start(user_id)
    if started_at is None:
        return None
    with get_db() as conn:
        # Only clear the exact timer we read: a double-click (or a second tab)
        # finds it already cleared and doesn't log the session twice.
        cleared = conn.execute(
            profiles.update()
            .where(profiles.c.user_id == user_id,
                   profiles.c.active_session_started == started_at.isoformat(timespec="seconds"))
            .values(active_session_started=None)
        ).rowcount
    if not cleared:
        return None
    return log_session(user_id, started_at, ended_at)


def get_sessions(user_id):
    """Logged sessions, newest first."""
    if not user_id:
        return []
    query = sa.select(sessions).where(sessions.c.user_id == user_id).order_by(sessions.c.started_at.desc())
    with get_db() as conn:
        return rows(conn.execute(query))


# ----------------- LEADERBOARD -----------------
def get_leaderboard_climbs(discipline):
    """Send counts per climber and grade in a discipline, from climbers who
    opted in to the leaderboard, tagged with their public display name (never
    their email). Counted in the database so it returns one row per grade a
    climber has sent, not one row per send."""
    # Sending the same named route again is a repeat, not new volume, so each
    # distinct name counts once - otherwise logging one route fifty times
    # reads as fifty sends, and send count is the tie-break within a grade.
    # Unnamed climbs still count per log: two "V4, no name" entries really are
    # two different gym problems, which is how most bouldering gets logged.
    route = sa.func.coalesce(climbs.c.route_name, "")
    sends = (
        sa.func.count(sa.distinct(sa.case((route != "", sa.func.lower(route)))))
        + sa.func.count(sa.case((route == "", 1)))
    ).label("sends")
    query = (
        sa.select(profiles.c.user_id, profiles.c.display_name, climbs.c.grade, sends)
        .join(profiles, profiles.c.user_id == climbs.c.user_id)
        .where(
            climbs.c.discipline == discipline,
            climbs.c.status.in_(SENT_STATUSES),
            profiles.c.show_on_leaderboard.is_(True),
        )
        .group_by(profiles.c.user_id, profiles.c.display_name, climbs.c.grade)
    )
    with get_db() as conn:
        return rows(conn.execute(query))
