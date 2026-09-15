import os
import threading
from datetime import datetime

import json_store

# Same storage pattern as profile_manager.py: anchored to this file's own
# location, atomic write-then-replace (shared via json_store.py), one lock
# around the read-modify-write so concurrent Streamlit sessions can't
# clobber each other's submissions.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "climber_profiles")
FEEDBACK_FILE_PATH = os.path.join(PROFILES_DIR, "feedback_log.json")

_FEEDBACK_LOCK = threading.RLock()


def load_feedback():
    entries = json_store.load(PROFILES_DIR, FEEDBACK_FILE_PATH, default=[], expected_type=list)
    return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)


def submit_feedback(climber_name, category, rating, message):
    entry = {
        "date": datetime.now().isoformat(timespec="minutes"),
        "climber_name": climber_name,
        "category": category,
        "rating": rating,
        "message": message.strip(),
    }
    with _FEEDBACK_LOCK:
        entries = load_feedback()
        entries.append(entry)
        json_store.write_atomically(PROFILES_DIR, FEEDBACK_FILE_PATH, entries)
    return entry
