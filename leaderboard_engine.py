import pandas as pd

from grades import grade_rank
from profile_manager import get_climbs, load_all_records

SEND_STATUSES = {"Flash", "Redpoint", "Sent"}


def compile_leaderboard(discipline):
    all_records = load_all_records()
    leaderboard_data = []

    for name in all_records:
        climbs = get_climbs(name, discipline)
        if not climbs:
            continue
        best = max(climbs, key=lambda c: grade_rank(discipline, c["grade"]))
        leaderboard_data.append({
            "Climber": name,
            "Best Grade": best["grade"],
            "Sends": sum(1 for c in climbs if c.get("status") in SEND_STATUSES),
            "Total Logged": len(climbs),
        })

    if not leaderboard_data:
        return pd.DataFrame()

    df = pd.DataFrame(leaderboard_data)
    df["_rank"] = df["Best Grade"].apply(lambda g: grade_rank(discipline, g))
    return df.sort_values(by="_rank", ascending=False).drop(columns="_rank")
