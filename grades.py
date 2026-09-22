"""Shared climbing grade scales: Yosemite Decimal System (roped) and V-scale (bouldering).

Both scales are ordered easiest-to-hardest, so a grade's index in its list is
its difficulty rank - the only thing needed to compare two grades or find a
climber's hardest send.
"""

YDS_GRADES = [
    "5.0", "5.1", "5.2", "5.3", "5.4", "5.5",
    "5.6", "5.7", "5.8", "5.9",
    "5.10a", "5.10b", "5.10c", "5.10d",
    "5.11a", "5.11b", "5.11c", "5.11d",
    "5.12a", "5.12b", "5.12c", "5.12d",
    "5.13a", "5.13b", "5.13c", "5.13d",
    "5.14a", "5.14b", "5.14c", "5.14d",
    "5.15a", "5.15b", "5.15c", "5.15d",
]

V_GRADES = ["VB"] + [f"V{n}" for n in range(18)]  # VB, V0-V17

GRADES_BY_DISCIPLINE = {
    "Boulder": V_GRADES,
    "Rope": YDS_GRADES,
}

SEND_STATUSES = ["Flash", "Redpoint", "Sent", "Fall", "Project"]


def grade_rank(discipline, grade):
    """Index of a grade within its discipline's scale - higher means harder.

    Returns -1 for an unrecognized grade (e.g. old data from a removed
    scale), so it sorts as easiest rather than crashing the comparison.
    """
    try:
        return GRADES_BY_DISCIPLINE[discipline].index(grade)
    except (KeyError, ValueError):
        return -1
