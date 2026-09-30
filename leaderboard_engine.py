import pandas as pd

from grades import grade_rank
from profile_manager import get_leaderboard_climbs


def compile_leaderboard(discipline):
    """One row per opted-in climber, ranked by hardest send, ties broken by send count."""
    sends = get_leaderboard_climbs(discipline)
    if not sends:
        return pd.DataFrame()

    # Display names are user-editable and should not define identity. Keep
    # separate accounts separate even if they chose the same public name.
    by_climber = {}
    for climb in sends:
        by_climber.setdefault(climb["user_id"], []).append(climb)

    leaderboard_data = []
    for climber_sends in by_climber.values():
        best = max(climber_sends, key=lambda c: grade_rank(discipline, c["grade"]))
        leaderboard_data.append({
            "Climber": best["display_name"],
            "Best Grade": best["grade"],
            "Sends": len(climber_sends),
            "_rank": grade_rank(discipline, best["grade"]),
        })

    df = pd.DataFrame(leaderboard_data)
    df = df.sort_values(by=["_rank", "Sends"], ascending=False).reset_index(drop=True)
    duplicate_names = df["Climber"].duplicated(keep=False)
    for name in df.loc[duplicate_names, "Climber"].unique():
        indexes = df.index[df["Climber"] == name].tolist()
        for position, index in enumerate(indexes, start=1):
            df.loc[index, "Climber"] = f"{name} ({position})"
    return df.drop(columns="_rank")
