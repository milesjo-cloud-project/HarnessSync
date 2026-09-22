import os
from datetime import date

from grades import grade_rank
import db_store


def load_all_records():
    """Loads all climber records in the legacy dictionary format for compatibility
    with AI coach and existing callers."""
    records = {}
    with db_store.get_db() as conn:
        climbs_cur = conn.execute("SELECT * FROM climbs ORDER BY date DESC, id DESC")
        for row in climbs_cur.fetchall():
            c = dict(row)
            name = c["climber_name"]
            profile = records.setdefault(name, {"climbs": [], "sessions": []})
            profile["climbs"].append({
                "id": c["id"],
                "date": c["date"],
                "discipline": c["discipline"],
                "grade": c["grade"],
                "status": c["status"],
                "route_name": c["route_name"] or "",
                "location": c["location"] or "",
            })

        sessions_cur = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC")
        for row in sessions_cur.fetchall():
            s = dict(row)
            name = s["climber_name"]
            profile = records.setdefault(name, {"climbs": [], "sessions": []})
            profile["sessions"].append({
                "id": s["id"],
                "date": s["date"],
                "started_at": s["started_at"],
                "ended_at": s["ended_at"],
                "duration_min": s["duration_min"],
            })
    return records


def get_climbs(climber_name=None, discipline=None):
    """Retrieves logged climbs, newest first. Can filter by climber_name and/or discipline."""
    query = "SELECT * FROM climbs WHERE 1=1"
    params = []
    if climber_name:
        query += " AND climber_name = ?"
        params.append(climber_name)
    if discipline:
        query += " AND discipline = ?"
        params.append(discipline)
    query += " ORDER BY date DESC, id DESC"

    with db_store.get_db() as conn:
        cur = conn.execute(query, params)
        climbs = [
            {
                "id": row["id"],
                "climber_name": row["climber_name"],
                "date": row["date"],
                "discipline": row["discipline"],
                "grade": row["grade"],
                "status": row["status"],
                "route_name": row["route_name"] or "",
                "location": row["location"] or "",
            }
            for row in cur.fetchall()
        ]
    return climbs


def best_climb(climber_name, discipline):
    """The hardest logged climb for a climber in a discipline, or None."""
    climbs = get_climbs(climber_name, discipline)
    if not climbs:
        return None
    return max(climbs, key=lambda c: grade_rank(discipline, c["grade"]))


def log_climb(climber_name, discipline, grade, status, route_name="", location="", climb_date=None):
    """Appends one logged climb to the database. Returns PR alert strings if a record is set."""
    climb_date = climb_date or date.today().isoformat()
    route_name = route_name.strip()
    location = location.strip()

    # Determine previous best grade rank before inserting
    existing_climbs = get_climbs(climber_name, discipline)
    previous_best_rank = max(
        (grade_rank(discipline, c["grade"]) for c in existing_climbs),
        default=-1,
    )

    with db_store.get_db() as conn:
        conn.execute("""
            INSERT INTO climbs (climber_name, date, discipline, grade, status, route_name, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (climber_name, climb_date, discipline, grade, status, route_name, location))

    pr_alerts = []
    if grade_rank(discipline, grade) > previous_best_rank:
        pr_alerts.append(f"🏆 New {discipline} personal best: {grade}!")
    return pr_alerts


def update_climb(climb_id, discipline, grade, status, route_name="", location="", climb_date=None):
    """Updates an existing climb entry by ID."""
    climb_date = climb_date or date.today().isoformat()
    with db_store.get_db() as conn:
        conn.execute("""
            UPDATE climbs
            SET discipline = ?, grade = ?, status = ?, route_name = ?, location = ?, date = ?
            WHERE id = ?
        """, (discipline, grade, status, route_name.strip(), location.strip(), climb_date, climb_id))


def delete_climb(climb_id):
    """Deletes a climb entry by ID."""
    with db_store.get_db() as conn:
        conn.execute("DELETE FROM climbs WHERE id = ?", (climb_id,))


def log_session(climber_name, started_at, ended_at):
    """Appends one completed visit session to database. Returns duration in minutes."""
    duration_min = round((ended_at - started_at).total_seconds() / 60, 1)
    session_date = started_at.date().isoformat()
    start_str = started_at.isoformat(timespec="minutes")
    end_str = ended_at.isoformat(timespec="minutes")

    with db_store.get_db() as conn:
        conn.execute("""
            INSERT INTO sessions (climber_name, date, started_at, ended_at, duration_min)
            VALUES (?, ?, ?, ?, ?)
        """, (climber_name, session_date, start_str, end_str, duration_min))

    return duration_min


def get_sessions(climber_name=None):
    """Logged visit sessions, newest first."""
    query = "SELECT * FROM sessions"
    params = []
    if climber_name:
        query += " WHERE climber_name = ?"
        params.append(climber_name)
    query += " ORDER BY started_at DESC"

    with db_store.get_db() as conn:
        cur = conn.execute(query, params)
        sessions = [
            {
                "id": row["id"],
                "climber_name": row["climber_name"],
                "date": row["date"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "duration_min": row["duration_min"],
            }
            for row in cur.fetchall()
        ]
    return sessions
