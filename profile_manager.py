import os
import threading
from datetime import date

from grades import grade_rank
import json_store

# Anchored to this file's own location rather than the current working
# directory - Streamlit (and any tool that launches it) can be started from
# a different folder than the project root, which previously meant records
# could silently be written to (or read from) the wrong place.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "climber_profiles")
PR_FILE_PATH = os.path.join(PROFILES_DIR, "personal_records.json")

# Saving a climb is a read-modify-write of one shared JSON file. Streamlit runs
# every browser session's script in its own thread, so as soon as more than one
# person uses the dashboard, two saves interleave: both read the same starting
# state, and whichever writes last erases the other's climb. Measured with 8
# concurrent saves, only 2 survived.
#
# One lock around the whole read-modify-write serialises them. This covers
# threads in a single process, which is exactly the Streamlit case (one server,
# many sessions). Two *separate* Streamlit processes pointed at the same file
# would still need OS-level file locking.
_RECORDS_LOCK = threading.RLock()


def load_all_records():
    return json_store.load(PROFILES_DIR, PR_FILE_PATH, default={}, expected_type=dict)


def get_climbs(climber_name, discipline=None):
    """A climber's logged climbs, newest first. Filters by discipline
    ("Boulder"/"Rope") when given."""
    all_records = load_all_records()
    climbs = all_records.get(climber_name, {}).get("climbs", [])
    if discipline:
        climbs = [c for c in climbs if c.get("discipline") == discipline]
    return sorted(climbs, key=lambda c: c.get("date", ""), reverse=True)


def best_climb(climber_name, discipline):
    """The hardest logged climb for a climber in a discipline, or None."""
    climbs = get_climbs(climber_name, discipline)
    if not climbs:
        return None
    return max(climbs, key=lambda c: grade_rank(discipline, c["grade"]))


def log_climb(climber_name, discipline, grade, status, route_name="", location="", climb_date=None):
    """Appends one logged climb to the climber's history.

    Returns a list of PR alert strings (empty if this climb didn't set a new
    hardest grade for the discipline) - mirrors the shape callers already
    expect from a "did this session set a record" check.
    """
    climb_date = climb_date or date.today().isoformat()

    with _RECORDS_LOCK:
        all_records = load_all_records()
        # setdefault rather than a bare "not in" check: a profile written by an
        # older version is missing "climbs" entirely, and indexing it raised
        # KeyError mid-save - which lost the climb that was being recorded.
        profile = all_records.setdefault(climber_name, {})
        climbs = profile.setdefault("climbs", [])

        previous_best_rank = max(
            (grade_rank(discipline, c["grade"]) for c in climbs if c.get("discipline") == discipline),
            default=-1,
        )

        climbs.append({
            "date": climb_date,
            "discipline": discipline,
            "grade": grade,
            "status": status,
            "route_name": route_name.strip(),
            "location": location.strip(),
        })

        json_store.write_atomically(PROFILES_DIR, PR_FILE_PATH, all_records)

    pr_alerts = []
    if grade_rank(discipline, grade) > previous_best_rank:
        pr_alerts.append(f"🏆 New {discipline} personal best: {grade}!")
    return pr_alerts


def log_session(climber_name, started_at, ended_at):
    """Appends one completed gym/crag-visit session to the climber's history.
    `started_at`/`ended_at` are datetime objects. Returns the duration in
    minutes."""
    duration_min = round((ended_at - started_at).total_seconds() / 60, 1)

    with _RECORDS_LOCK:
        all_records = load_all_records()
        profile = all_records.setdefault(climber_name, {})
        sessions = profile.setdefault("sessions", [])
        sessions.append({
            "date": started_at.date().isoformat(),
            "started_at": started_at.isoformat(timespec="minutes"),
            "ended_at": ended_at.isoformat(timespec="minutes"),
            "duration_min": duration_min,
        })
        json_store.write_atomically(PROFILES_DIR, PR_FILE_PATH, all_records)

    return duration_min


def get_sessions(climber_name=None):
    """Logged visit-sessions, newest first. Every entry across all climbers
    when `climber_name` is omitted (used by the admin dashboard)."""
    all_records = load_all_records()
    if climber_name:
        sessions = [dict(s, climber_name=climber_name) for s in all_records.get(climber_name, {}).get("sessions", [])]
    else:
        sessions = [
            dict(s, climber_name=name)
            for name, profile in all_records.items()
            for s in profile.get("sessions", [])
        ]
    return sorted(sessions, key=lambda s: s.get("started_at", ""), reverse=True)
