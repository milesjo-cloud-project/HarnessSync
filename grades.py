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

SEND_STATUSES = ["Onsight", "Flash", "Redpoint", "Sent", "Project", "Attempt"]
ENVIRONMENTS = ["Gym", "Outdoor"]
WALL_ANGLES = ["Slab", "Vertical", "Overhang", "Roof"]
HOLD_TYPES = ["Crimps", "Slopers", "Jugs", "Pinches", "Pockets", "Mixed"]

# Grade Conversion References
BOULDER_CONVERSION = [
    {"v_scale": "VB", "font_scale": "3", "description": "Beginner"},
    {"v_scale": "V0", "font_scale": "4", "description": "Novice"},
    {"v_scale": "V1", "font_scale": "5", "description": "Novice / Intermediate"},
    {"v_scale": "V2", "font_scale": "5+", "description": "Intermediate"},
    {"v_scale": "V3", "font_scale": "6A", "description": "Intermediate"},
    {"v_scale": "V4", "font_scale": "6B", "description": "Advanced"},
    {"v_scale": "V5", "font_scale": "6C", "description": "Advanced"},
    {"v_scale": "V6", "font_scale": "7A", "description": "Advanced / Expert"},
    {"v_scale": "V7", "font_scale": "7A+", "description": "Expert"},
    {"v_scale": "V8", "font_scale": "7B", "description": "Expert"},
    {"v_scale": "V9", "font_scale": "7B+", "description": "Expert / Elite"},
    {"v_scale": "V10", "font_scale": "7C", "description": "Elite"},
    {"v_scale": "V11", "font_scale": "7C+", "description": "Elite"},
    {"v_scale": "V12", "font_scale": "8A", "description": "Elite / World-Class"},
    {"v_scale": "V13", "font_scale": "8A+", "description": "World-Class"},
    {"v_scale": "V14", "font_scale": "8B", "description": "World-Class"},
    {"v_scale": "V15", "font_scale": "8B+", "description": "World-Class"},
    {"v_scale": "V16", "font_scale": "8C", "description": "World-Class"},
    {"v_scale": "V17", "font_scale": "9A", "description": "Pinnacle"},
]

ROPE_CONVERSION = [
    {"yds": "5.5-5.6", "french": "4a - 4c", "description": "Beginner"},
    {"yds": "5.7-5.8", "french": "5a - 5b", "description": "Novice"},
    {"yds": "5.9", "french": "5c", "description": "Intermediate"},
    {"yds": "5.10a-5.10b", "french": "6a - 6a+", "description": "Intermediate"},
    {"yds": "5.10c-5.10d", "french": "6b - 6b+", "description": "Intermediate / Advanced"},
    {"yds": "5.11a-5.11b", "french": "6c - 6c+", "description": "Advanced"},
    {"yds": "5.11c-5.11d", "french": "7a - 7a+", "description": "Advanced"},
    {"yds": "5.12a-5.12b", "french": "7b - 7b+", "description": "Advanced / Expert"},
    {"yds": "5.12c-5.12d", "french": "7c - 7c+", "description": "Expert"},
    {"yds": "5.13a-5.13b", "french": "8a - 8a+", "description": "Expert / Elite"},
    {"yds": "5.13c-5.13d", "french": "8b - 8b+", "description": "Elite"},
    {"yds": "5.14a-5.14b", "french": "8c - 8c+", "description": "World-Class"},
    {"yds": "5.15a-5.15d", "french": "9a - 9c", "description": "Pinnacle"},
]


def grade_rank(discipline, grade):
    """Index of a grade within its discipline's scale - higher means harder.

    Returns -1 for an unrecognized grade (e.g. old data from a removed
    scale), so it sorts as easiest rather than crashing the comparison.
    """
    try:
        return GRADES_BY_DISCIPLINE[discipline].index(grade)
    except (KeyError, ValueError):
        return -1

