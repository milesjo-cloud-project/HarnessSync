import pandas as pd

from grades import grade_rank
from profile_manager import get_leaderboard_climbs


def compile_leaderboard(discipline):
    """One row per opted-in climber, ranked by hardest send, ties broken by send count."""
    grade_counts = get_leaderboard_climbs(discipline)
    if not grade_counts:
        return pd.DataFrame()

    # Display names are user-editable and should not define identity. Keep
    # separate accounts separate even if they chose the same public name.
    by_climber = {}
    for row in grade_counts:
        by_climber.setdefault(row["user_id"], []).append(row)

    leaderboard_data = []
    for climber_grades in by_climber.values():
        best = max(climber_grades, key=lambda r: grade_rank(discipline, r["grade"]))
        leaderboard_data.append({
            "Climber": best["display_name"],
            "Best Grade": best["grade"],
            "Sends": sum(r["sends"] for r in climber_grades),
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
