"""The "How's HarnessSync?" survey: a 1-5 rating, an optional comment, and an
optional gym name, so the owner can see what climbers think of the app.

Climbers only ever add their own answers. Only the owner can read them, and
the owner's view and export leave out account emails and display names.
"""

import csv
import io
import re
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from harnesssync.db_store import app_ratings, get_db, rows
from harnesssync.support_config import require_owner

RATINGS = [1, 2, 3, 4, 5]
COMMENT_MAX = 1000
GYM_MAX = 80
# Enough to change your mind after a session, not enough to flood the average.
DAILY_LIMIT = 3
LATEST_COMMENTS = 10


def _stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _one_line(text, max_len):
    return re.sub(r"\s+", " ", text or "").strip()[:max_len]


def _cell(value):
    """Stops a spreadsheet treating a comment like "=SUM(...)" as a formula."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def last_rating(user_id):
    """The climber's own most recent answer, or None."""
    if not user_id:
        return None
    with get_db() as conn:
        found = rows(conn.execute(
            sa.select(app_ratings).where(app_ratings.c.user_id == user_id)
            .order_by(app_ratings.c.submitted_at.desc(), app_ratings.c.id.desc()).limit(1)))
    return found[0] if found else None


def submit_rating(user_id, rating, comment="", gym="", now=None):
    """Saves one answer for the signed-in climber and returns it."""
    now = now or datetime.now(timezone.utc)
    if not user_id:
        raise ValueError("Sign in before rating the app.")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    if rating not in RATINGS:
        raise ValueError("Pick a rating from 1 to 5 stars.")
    entry = dict(user_id=user_id, submitted_at=_stamp(now), rating=rating,
                 comment=(comment or "").strip()[:COMMENT_MAX], gym=_one_line(gym, GYM_MAX))
    with get_db() as conn:
        today = conn.execute(sa.select(sa.func.count()).select_from(app_ratings).where(
            app_ratings.c.user_id == user_id,
            app_ratings.c.submitted_at >= _stamp(now - timedelta(days=1)))).scalar_one()
        if today >= DAILY_LIMIT:
            raise ValueError("Thanks, you've already rated the app a few times today. Try again tomorrow.")
        entry["id"] = conn.execute(app_ratings.insert().values(**entry)).inserted_primary_key[0]
    return entry


def owner_summary(actor, latest=LATEST_COMMENTS):
    """Owner only. Totals and the latest comments, with no names or emails."""
    require_owner(actor)
    with get_db() as conn:
        answers = rows(conn.execute(sa.select(app_ratings).order_by(
            app_ratings.c.submitted_at.desc(), app_ratings.c.id.desc())))
    count = len(answers)
    by_rating = {r: sum(1 for a in answers if a["rating"] == r) for r in RATINGS}
    return {
        "responses": count,
        "climbers": len({a["user_id"] for a in answers}),
        "average": round(sum(a["rating"] for a in answers) / count, 1) if count else None,
        "by_rating": by_rating,
        "latest_comments": [
            {"date": a["submitted_at"][:10], "rating": a["rating"], "gym": a["gym"], "comment": a["comment"]}
            for a in answers if a["comment"]
        ][:latest],
    }


def owner_csv(actor):
    """Owner only. Every answer as CSV for a report, without account emails."""
    require_owner(actor)
    with get_db() as conn:
        answers = rows(conn.execute(sa.select(app_ratings).order_by(
            app_ratings.c.submitted_at, app_ratings.c.id)))
    respondent = {}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["submitted_at", "respondent", "rating", "gym", "comment"])
    for a in answers:
        # A stable number per account, so repeat answers can be told apart
        # from new climbers without exporting who anyone is.
        number = respondent.setdefault(a["user_id"], len(respondent) + 1)
        writer.writerow([a["submitted_at"], number, a["rating"], _cell(a["gym"]), _cell(a["comment"])])
    return out.getvalue()
