"""Climber profiles, climbs, projects and sessions.

Every function that reads or changes a climber's data takes the signed-in
user's `user_id` and filters on it, so one account can never see or modify
another account's rows - even with a guessed record id.
"""

import re
from datetime import datetime, timezone

import sqlalchemy as sa

from grades import grade_rank, SENT_STATUSES
from db_store import get_db, rows, profiles, climbs, projects, sessions, feedback

DISPLAY_NAME_MAX = 30
ROUTE_MAX = 80
LOCATION_MAX = 80
NOTES_MAX = 500


def _clean(text, max_len):
    """Trim, collapse runs of whitespace, and cap length."""
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
        for table in (climbs, projects, sessions, feedback):
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


def best_climb(user_id, discipline):
    """The hardest *sent* climb for a climber in a discipline, or None."""
    sends = [c for c in get_climbs(user_id, discipline) if c["status"] in SENT_STATUSES]
    return max(sends, key=lambda c: grade_rank(discipline, c["grade"]), default=None)


def log_climb(user_id, discipline, grade, status, climb_date, route_name="", location="",
              environment="Gym", angle="Vertical", hold_type="Mixed"):
    """Appends one logged climb. Returns PR alert strings if it's a new best send."""
    previous_best = best_climb(user_id, discipline)
    previous_best_rank = grade_rank(discipline, previous_best["grade"]) if previous_best else -1

    with get_db() as conn:
        conn.execute(climbs.insert().values(
            user_id=user_id, date=climb_date, discipline=discipline, grade=grade, status=status,
            route_name=_clean(route_name, ROUTE_MAX), location=_clean(location, LOCATION_MAX),
            environment=environment, angle=angle, hold_type=hold_type,
        ))

    if status in SENT_STATUSES and grade_rank(discipline, grade) > previous_best_rank:
        return [f"🏆 New {discipline} personal best: {grade}!"]
    return []


def update_climb(user_id, climb_id, discipline, grade, status, climb_date, route_name="", location="",
                 environment="Gym", angle="Vertical", hold_type="Mixed"):
    with get_db() as conn:
        conn.execute(
            climbs.update()
            .where(climbs.c.id == climb_id, climbs.c.user_id == user_id)
            .values(
                discipline=discipline, grade=grade, status=status, date=climb_date,
                route_name=_clean(route_name, ROUTE_MAX), location=_clean(location, LOCATION_MAX),
                environment=environment, angle=angle, hold_type=hold_type,
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
    creating a duplicate. Returns "added" or "bumped"."""
    route_name = _clean(route_name, ROUTE_MAX)
    with get_db() as conn:
        if route_name:
            existing = conn.execute(
                sa.select(projects.c.id).where(
                    projects.c.user_id == user_id,
                    projects.c.discipline == discipline,
                    projects.c.grade == grade,
                    sa.func.lower(projects.c.route_name) == route_name.lower(),
                )
            ).first()
            if existing:
                conn.execute(
                    projects.update().where(projects.c.id == existing.id)
                    .values(attempts=projects.c.attempts + attempts)
                )
                return "bumped"
        conn.execute(projects.insert().values(
            user_id=user_id, date=project_date, discipline=discipline, grade=grade,
            route_name=route_name, location=_clean(location, LOCATION_MAX),
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
    )
    delete_project(user_id, project_id)
    return alerts


# ----------------- SESSIONS -----------------
def log_session(user_id, started_at, ended_at):
    """Records one completed gym/crag session. Returns duration in minutes."""
    duration_min = round((ended_at - started_at).total_seconds() / 60, 1)
    with get_db() as conn:
        conn.execute(sessions.insert().values(
            user_id=user_id,
            date=started_at.date().isoformat(),
            started_at=started_at.isoformat(timespec="minutes"),
            ended_at=ended_at.isoformat(timespec="minutes"),
            duration_min=duration_min,
        ))
    return duration_min


def get_sessions(user_id):
    """Logged sessions, newest first."""
    if not user_id:
        return []
    query = sa.select(sessions).where(sessions.c.user_id == user_id).order_by(sessions.c.started_at.desc())
    with get_db() as conn:
        return rows(conn.execute(query))


# ----------------- LEADERBOARD -----------------
def get_leaderboard_climbs(discipline):
    """All sends in a discipline from climbers who opted in to the leaderboard,
    tagged with their public display name (never their email)."""
    query = (
        sa.select(profiles.c.display_name, climbs.c.grade, climbs.c.status)
        .join(profiles, profiles.c.user_id == climbs.c.user_id)
        .where(
            climbs.c.discipline == discipline,
            climbs.c.status.in_(SENT_STATUSES),
            profiles.c.show_on_leaderboard.is_(True),
        )
    )
    with get_db() as conn:
        return rows(conn.execute(query))
