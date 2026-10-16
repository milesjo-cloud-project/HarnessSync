"""Private tickets, owner review, and atomic submission rate limiting."""
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
from harnesssync.db_store import get_db, rows, feedback
from harnesssync.support_config import require_owner
from harnesssync.support_notifications import enqueue, stamp
from harnesssync.support_store import lock_account

MESSAGE_MAX = 2000
COOLDOWN = timedelta(minutes=2)
DAILY_LIMIT = 5
CATEGORIES = ["Bug", "Feature Idea", "General"]
AREAS = ["General", "Sign-in", "Log a climb", "Progress", "Projects", "Leaderboard", "Session timer", "Phone App", "Help"]
STATUSES = ["Received", "Investigating", "In progress", "Fixed", "Closed"]


def ticket_ref(ticket_id):
    return f"HS-{ticket_id:06d}"


def load_feedback(user_id):
    if not user_id:
        return []
    with get_db() as conn:
        return rows(conn.execute(sa.select(feedback).where(feedback.c.user_id == user_id)
                                 .order_by(feedback.c.submitted_at.desc(), feedback.c.id.desc())))


def _block_reason(conn, user_id, now):
    recent = conn.execute(sa.select(feedback.c.submitted_at).where(
        feedback.c.user_id == user_id, feedback.c.submitted_at >= stamp(now - timedelta(days=1)))
        .order_by(feedback.c.submitted_at.desc())).scalars().all()
    if len(recent) >= DAILY_LIMIT:
        return f"You've sent {DAILY_LIMIT} messages in the last day - thanks! Please try again tomorrow."
    if recent and recent[0] >= stamp(now - COOLDOWN):
        return "Thanks - give it a couple of minutes before sending another message."
    return None


def feedback_block_reason(user_id, now=None):
    with get_db() as conn:
        return _block_reason(conn, user_id, now or datetime.now(timezone.utc))


def submit_feedback(user_id, display_name, category, rating, message, now=None, *,
                    area="General", steps="", expected="", incident_ref=""):
    now = now or datetime.now(timezone.utc)
    if not user_id or not message.strip():
        raise ValueError("Add a note before sending - even a sentence helps.")
    if category not in CATEGORIES or area not in AREAS or int(rating) not in range(1, 6):
        raise ValueError("Choose a valid category, area and rating.")
    entry = dict(user_id=user_id, display_name=" ".join(display_name.split())[:40],
                 submitted_at=stamp(now), updated_at=stamp(now), category=category,
                 rating=int(rating), message=message.strip()[:MESSAGE_MAX], area=area,
                 steps=steps.strip()[:MESSAGE_MAX], expected=expected.strip()[:MESSAGE_MAX],
                 incident_ref=incident_ref.strip()[:40])
    with get_db() as conn:
        lock_account(conn, user_id)
        blocked = _block_reason(conn, user_id, now)
        if blocked:
            raise ValueError(blocked)
        result = conn.execute(feedback.insert().values(**entry))
        entry["id"] = result.inserted_primary_key[0]
        entry["status"] = "Received"
        reference = ticket_ref(entry["id"])
        body = (f"{reference}\nFrom: {entry['display_name']} ({user_id})\nArea: {area}\n"
                f"Rating: {rating}/5\nIncident: {entry['incident_ref']}\n\n{entry['message']}\n\n"
                f"Steps: {entry['steps']}\nExpected: {entry['expected']}")
        enqueue(conn, f"ticket:{entry['id']}", f"HarnessSync {reference}: {category}",
                body, user_id=user_id, now=now)
    return entry


def owner_tickets(actor, status=None):
    require_owner(actor)
    query = sa.select(feedback).order_by(feedback.c.submitted_at.desc(), feedback.c.id.desc()).limit(200)
    if status:
        query = query.where(feedback.c.status == status)
    with get_db() as conn:
        return rows(conn.execute(query))


def update_ticket(actor, ticket_id, status, reply):
    require_owner(actor)
    if status not in STATUSES:
        raise ValueError("Invalid ticket status.")
    if status == "Fixed" and not reply.strip():
        raise ValueError("Explain the verified, deployed fix before marking this fixed.")
    with get_db() as conn:
        conn.execute(feedback.update().where(feedback.c.id == ticket_id).values(
            status=status, owner_reply=reply.strip()[:MESSAGE_MAX],
            updated_at=stamp(datetime.now(timezone.utc))))


def similar_tickets(actor, ticket):
    """Private duplicate candidates, never exposed to other reporters."""
    require_owner(actor)
    words = set(ticket["message"].lower().split())
    return [t for t in owner_tickets(actor) if t["id"] != ticket["id"] and
            ((ticket["incident_ref"] and ticket["incident_ref"] == t["incident_ref"]) or
             (t["area"] == ticket["area"] and len(words & set(t["message"].lower().split())) >= 4))][:5]
