"""SQLite database storage engine for HarnessSync.

Replaces raw JSON file operations with SQLite (WAL mode) to guarantee process safety across concurrent Streamlit processes, instant queries, and full CRUD operations (add, edit, delete).
Automatically imports legacy JSON data from climber_profiles/ on startup.
"""

import os
import sqlite3
import json
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "climber_profiles")
DB_PATH = os.path.join(PROFILES_DIR, "harness_sync.db")

def get_legacy_pr_file():
    return os.path.join(PROFILES_DIR, "personal_records.json")


def get_legacy_feedback_file():
    return os.path.join(PROFILES_DIR, "feedback_log.json")



def ensure_profiles_dir():
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)


@contextmanager
def get_db():
    ensure_profiles_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initializes tables and performs schema migrations if needed."""
    ensure_profiles_dir()
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS climbs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                climber_name TEXT NOT NULL,
                date TEXT NOT NULL,
                discipline TEXT NOT NULL,
                grade TEXT NOT NULL,
                status TEXT NOT NULL,
                route_name TEXT DEFAULT '',
                location TEXT DEFAULT '',
                environment TEXT DEFAULT 'Gym',
                angle TEXT DEFAULT 'Vertical',
                hold_type TEXT DEFAULT 'Mixed'
            )
        """)

        # Alter table if upgrading existing DB
        cur = conn.execute("PRAGMA table_info(climbs)")
        cols = [r["name"] for r in cur.fetchall()]
        if "environment" not in cols:
            conn.execute("ALTER TABLE climbs ADD COLUMN environment TEXT DEFAULT 'Gym'")
        if "angle" not in cols:
            conn.execute("ALTER TABLE climbs ADD COLUMN angle TEXT DEFAULT 'Vertical'")
        if "hold_type" not in cols:
            conn.execute("ALTER TABLE climbs ADD COLUMN hold_type TEXT DEFAULT 'Mixed'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                climber_name TEXT NOT NULL,
                date TEXT NOT NULL,
                discipline TEXT NOT NULL,
                grade TEXT NOT NULL,
                route_name TEXT DEFAULT '',
                location TEXT DEFAULT '',
                environment TEXT DEFAULT 'Gym',
                angle TEXT DEFAULT 'Vertical',
                hold_type TEXT DEFAULT 'Mixed',
                attempts INTEGER DEFAULT 1,
                notes TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                climber_name TEXT NOT NULL,
                date TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                duration_min REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                climber_name TEXT NOT NULL,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                rating INTEGER NOT NULL,
                message TEXT NOT NULL
            )
        """)

        # Migration from legacy JSON if table is empty
        _migrate_legacy_json(conn)


def _migrate_legacy_json(conn):
    # Check climbs
    cur = conn.execute("SELECT COUNT(*) as count FROM climbs")
    climb_count = cur.fetchone()["count"]
    pr_file = get_legacy_pr_file()
    if climb_count == 0 and os.path.exists(pr_file):
        try:
            with open(pr_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for climber_name, profile in data.items():
                    if isinstance(profile, dict):
                        for c in profile.get("climbs", []):
                            conn.execute("""
                                INSERT INTO climbs (climber_name, date, discipline, grade, status, route_name, location)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                climber_name,
                                c.get("date", ""),
                                c.get("discipline", ""),
                                c.get("grade", ""),
                                c.get("status", ""),
                                c.get("route_name", ""),
                                c.get("location", ""),
                            ))
                        for s in profile.get("sessions", []):
                            conn.execute("""
                                INSERT INTO sessions (climber_name, date, started_at, ended_at, duration_min)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                climber_name,
                                s.get("date", ""),
                                s.get("started_at", ""),
                                s.get("ended_at", ""),
                                float(s.get("duration_min", 0)),
                            ))
        except Exception as e:
            print(f"Warning: JSON climb migration skipped due to: {e}")

    # Check feedback
    cur = conn.execute("SELECT COUNT(*) as count FROM feedback")
    fb_count = cur.fetchone()["count"]
    fb_file = get_legacy_feedback_file()
    if fb_count == 0 and os.path.exists(fb_file):
        try:
            with open(fb_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    conn.execute("""
                        INSERT INTO feedback (climber_name, date, category, rating, message)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        item.get("climber_name", "Guest"),
                        item.get("date", ""),
                        item.get("category", "General"),
                        int(item.get("rating", 5)),
                        item.get("message", ""),
                    ))
        except Exception as e:
            print(f"Warning: JSON feedback migration skipped due to: {e}")


# Run DB initialization on module load
init_db()
