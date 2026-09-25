import pandas as pd

from grades import grade_rank
from profile_manager import get_leaderboard_climbs


def compile_leaderboard(discipline):
    """One row per opted-in climber, ranked by hardest send, ties broken by send count."""
    sends = get_leaderboard_climbs(discipline)
    if not sends:
        return pd.DataFrame()

    by_climber = {}
    for climb in sends:
        by_climber.setdefault(climb["display_name"], []).append(climb)

    leaderboard_data = []
    for name, climber_sends in by_climber.items():
        best = max(climber_sends, key=lambda c: grade_rank(discipline, c["grade"]))
        leaderboard_data.append({
            "Climber": name,
            "Best Grade": best["grade"],
            "Sends": len(climber_sends),
            "_rank": grade_rank(discipline, best["grade"]),
        })

    df = pd.DataFrame(leaderboard_data)
    return df.sort_values(by=["_rank", "Sends"], ascending=False).drop(columns="_rank")
