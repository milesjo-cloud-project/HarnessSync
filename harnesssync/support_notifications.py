"""Durable, leased email outbox. Run: python -m harnesssync.support_notifications.

SMTP delivery is at-least-once: a crash after acceptance may cause a duplicate.
Ticket and incident references make duplicates identifiable.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import sqlalchemy as sa

from harnesssync import notifications
from harnesssync.db_store import get_db, notification_outbox as outbox
from harnesssync.support_store import insert_once


def stamp(value):
    return value.isoformat(timespec="seconds")


def enqueue(conn, event_key, subject, body, user_id="", now=None):
    insert_once(conn, outbox, dict(event_key=event_key, subject=subject[:200], body=body,
                                 user_id=user_id, next_attempt=stamp(now or datetime.now(timezone.utc))))


def deliver_pending(limit=5, now=None, event_key=None):
    """Claim due messages. Failed deliveries back off up to six hours."""
    if not notifications.is_configured():
        return 0
    now = now or datetime.now(timezone.utc)
    due = [outbox.c.sent_at.is_(None), outbox.c.next_attempt <= stamp(now)]
    if event_key:
        due.append(outbox.c.event_key == event_key)
    with get_db() as conn:
        candidates = conn.execute(sa.select(outbox.c.event_key).where(*due)
                                  .order_by(outbox.c.next_attempt).limit(limit)).scalars().all()
    delivered = 0
    for key in candidates:
        lease = uuid4().hex
        with get_db() as conn:
            claimed = conn.execute(outbox.update().where(outbox.c.event_key == key, *due)
                                   .values(lease=lease, next_attempt=stamp(now + timedelta(minutes=2)),
                                           attempts=outbox.c.attempts + 1)).rowcount
            if not claimed:
                continue
            entry = conn.execute(sa.select(outbox).where(outbox.c.event_key == key)).mappings().one()
        try:
            success = notifications.send_email(subject=entry["subject"], body=entry["body"])
        except Exception:
            success = False
        with get_db() as conn:
            values = dict(lease="", next_attempt=stamp(now + timedelta(
                minutes=min(360, 2 ** min(entry["attempts"], 9)))))
            if success:
                values.update(sent_at=stamp(now), body="")
            conn.execute(outbox.update().where(outbox.c.event_key == key, outbox.c.lease == lease)
                         .values(**values))
        delivered += bool(success)
    return delivered


if __name__ == "__main__":
    print(f"Delivered {deliver_pending(limit=25)} queued notifications.")
