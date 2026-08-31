import os
import json
import tempfile
import threading
from datetime import date

from grades import grade_rank

# Anchored to this file's own location rather than the current working
# directory - Streamlit (and any tool that launches it) can be started from
# a different folder than the project root, which previously meant records
# could silently be written to (or read from) the wrong place.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "climber_profiles")
PR_FILE_PATH = os.path.join(PROFILES_DIR, "personal_records.json")

# Every open() below passes encoding explicitly. Python defaults to the
# locale encoding, which is cp1252 on this machine - so a climber name with
# an accent (José, Müller) raised UnicodeEncodeError while saving and threw
# away the climb that was being recorded.
FILE_ENCODING = "utf-8"


def setup_directories():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)
    if not os.path.exists(PR_FILE_PATH):
        with open(PR_FILE_PATH, 'w', encoding=FILE_ENCODING) as f:
            json.dump({}, f)


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


def _write_records_atomically(records):
    """Write via a temp file + os.replace so an interrupted save can't leave a
    half-written (and therefore unparseable) records file behind."""
    fd, tmp_path = tempfile.mkstemp(dir=PROFILES_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=FILE_ENCODING) as f:
            json.dump(records, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, PR_FILE_PATH)  # atomic on Windows and POSIX
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_all_records():
    setup_directories()
    try:
        with open(PR_FILE_PATH, 'r', encoding=FILE_ENCODING) as f:
            records = json.load(f)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        # A truncated or hand-edited records file used to crash the whole
        # dashboard on import. An unreadable file means "no records yet".
        return {}
    return records if isinstance(records, dict) else {}


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

        _write_records_atomically(all_records)

    pr_alerts = []
    if grade_rank(discipline, grade) > previous_best_rank:
        pr_alerts.append(f"🏆 New {discipline} personal best: {grade}!")
    return pr_alerts
