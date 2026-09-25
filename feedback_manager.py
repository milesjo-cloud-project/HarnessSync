from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from db_store import get_db, rows, feedback

MESSAGE_MAX = 2000
# Feedback is emailed to the developer, so cap how often one account can send it
COOLDOWN = timedelta(minutes=2)
DAILY_LIMIT = 5


def _timestamp(dt):
    return dt.isoformat(timespec="seconds")


def load_feedback():
    """All feedback entries, newest first."""
    with get_db() as conn:
        return rows(conn.execute(sa.select(feedback).order_by(feedback.c.submitted_at.desc(), feedback.c.id.desc())))


def feedback_block_reason(user_id, now=None):
    """None if this user may send feedback now, otherwise a message explaining why not."""
    now = now or datetime.now(timezone.utc)
    with get_db() as conn:
        recent = conn.execute(
            sa.select(feedback.c.submitted_at)
            .where(feedback.c.user_id == user_id, feedback.c.submitted_at >= _timestamp(now - timedelta(days=1)))
            .order_by(feedback.c.submitted_at.desc())
        ).scalars().all()
    if len(recent) >= DAILY_LIMIT:
        return f"You've sent {DAILY_LIMIT} messages in the last day - thanks! Please try again tomorrow."
    if recent and recent[0] >= _timestamp(now - COOLDOWN):
        return "Thanks - give it a couple of minutes before sending another message."
    return None


def submit_feedback(user_id, display_name, category, rating, message, now=None):
    """Saves a feedback entry. Callers should check feedback_block_reason first."""
    now = now or datetime.now(timezone.utc)
    entry = {
        "user_id": user_id,
        "display_name": display_name,
        "submitted_at": _timestamp(now),
        "category": category,
        "rating": int(rating),
        "message": message.strip()[:MESSAGE_MAX],
    }
    with get_db() as conn:
        conn.execute(feedback.insert().values(**entry))
    return entry
