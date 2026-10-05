"""Waitlist for a native iPhone / Android app.

Only signed-in users can join, so every row is a real Google account - the
count is a trustworthy signal of demand rather than a pile of form spam.
Run `python -m harnesssync.waitlist_report` to see the numbers.
"""

from datetime import datetime, timezone

import sqlalchemy as sa

from harnesssync.db_store import get_db, rows, waitlist

PLATFORMS = ["iPhone", "Android", "Both"]
# What would make a phone app worth installing over the website. Answers
# tell us which native-only features would justify building one.
REASONS = [
    "Log climbs offline at the crag",
    "Faster logging between attempts",
    "Session timer on the lock screen",
    "Reminders / notifications",
    "Apple Health / Google Fit sync",
    "Home-screen icon, no browser",
]
NOTE_MAX = 500


def get_entry(user_id):
    if not user_id:
        return None
    with get_db() as conn:
        found = rows(conn.execute(sa.select(waitlist).where(waitlist.c.user_id == user_id)))
    return found[0] if found else None


def join(user_id, platform, wants=(), note="", now=None):
    """Adds the user to the waitlist, or updates their answers if already on it."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform: {platform}")
    values = {
        "platform": platform,
        "wants": ", ".join(w for w in wants if w in REASONS),
        "note": (note or "").strip()[:NOTE_MAX],
    }
    with get_db() as conn:
        exists = conn.execute(sa.select(waitlist.c.user_id).where(waitlist.c.user_id == user_id)).first()
        if exists:
            conn.execute(waitlist.update().where(waitlist.c.user_id == user_id).values(**values))
        else:
            joined_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
            conn.execute(waitlist.insert().values(user_id=user_id, joined_at=joined_at, **values))


def leave(user_id):
    with get_db() as conn:
        conn.execute(waitlist.delete().where(waitlist.c.user_id == user_id))


def emails():
    """Everyone on the waitlist. user_id is the Google sign-in email."""
    with get_db() as conn:
        return conn.execute(sa.select(waitlist.c.user_id)).scalars().all()


def summary():
    """Totals for deciding whether a native app is worth building."""
    with get_db() as conn:
        entries = rows(conn.execute(sa.select(waitlist)))
    by_platform = {p: 0 for p in PLATFORMS}
    by_reason = {r: 0 for r in REASONS}
    for e in entries:
        by_platform[e["platform"]] = by_platform.get(e["platform"], 0) + 1
        for reason in filter(None, (w.strip() for w in e["wants"].split(","))):
            if reason in by_reason:
                by_reason[reason] += 1
    return {
        "total": len(entries),
        # "Both" counts toward each store
        "ios": by_platform["iPhone"] + by_platform["Both"],
        "android": by_platform["Android"] + by_platform["Both"],
        "by_platform": by_platform,
        "by_reason": by_reason,
        "notes": [e["note"] for e in entries if e["note"]],
    }
