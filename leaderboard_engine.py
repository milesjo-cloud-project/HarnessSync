import pandas as pd

from grades import grade_rank
from profile_manager import get_climbs

SEND_STATUSES = {"Flash", "Redpoint", "Sent"}


def compile_leaderboard(discipline):
    all_climbs = get_climbs(discipline=discipline)
    if not all_climbs:
        return pd.DataFrame()

    climber_groups = {}
    for climb in all_climbs:
        name = climb["climber_name"]
        climber_groups.setdefault(name, []).append(climb)

    leaderboard_data = []
    for name, climbs in climber_groups.items():
        best = max(climbs, key=lambda c: grade_rank(discipline, c["grade"]))
        leaderboard_data.append({
            "Climber": name,
            "Best Grade": best["grade"],
            "Sends": sum(1 for c in climbs if c.get("status") in SEND_STATUSES),
            "Total Logged": len(climbs),
        })

    df = pd.DataFrame(leaderboard_data)
    df["_rank"] = df["Best Grade"].apply(lambda g: grade_rank(discipline, g))
    return df.sort_values(by="_rank", ascending=False).drop(columns="_rank")
