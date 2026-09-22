from datetime import datetime
import db_store


def load_feedback():
    """Loads all feedback entries, newest first."""
    with db_store.get_db() as conn:
        cur = conn.execute("SELECT * FROM feedback ORDER BY date DESC, id DESC")
        entries = [
            {
                "id": row["id"],
                "date": row["date"],
                "climber_name": row["climber_name"],
                "category": row["category"],
                "rating": row["rating"],
                "message": row["message"],
            }
            for row in cur.fetchall()
        ]
    return entries


def submit_feedback(climber_name, category, rating, message):
    """Submits a feedback entry to SQLite."""
    date_str = datetime.now().isoformat(timespec="minutes")
    msg_clean = message.strip()
    with db_store.get_db() as conn:
        conn.execute("""
            INSERT INTO feedback (climber_name, date, category, rating, message)
            VALUES (?, ?, ?, ?, ?)
        """, (climber_name, date_str, category, rating, msg_clean))

    return {
        "date": date_str,
        "climber_name": climber_name,
        "category": category,
        "rating": rating,
        "message": msg_clean,
    }
