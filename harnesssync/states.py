"""The 50 states: names, a look for each one, and where it sits on the passport map.

One table drives everything state-related (the Log banner, the stamps and the
passport map), so adding a detail or fixing a colour is a one-line change.

Every `color` is dark enough for white text on it (WCAG AA, checked by a test).
Emblems are plain emoji, so there is no artwork to license.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StateTheme:
    code: str
    name: str
    tagline: str
    emblem: str
    color: str   # stamp fill and banner background; white text sits on it
    accent: str  # ring and highlight
    row: int     # tile position on the passport map (11 columns x 8 rows)
    col: int


# code: (name, tagline, emblem, color, accent, row, col)
_STATES = {
    "AK": ("Alaska", "Glaciers and big mountains", "🏔️", "#1f4e79", "#9ec9ef", 0, 0),
    "ME": ("Maine", "Granite on the sea", "🦞", "#7a2e1f", "#f2a487", 0, 10),
    "VT": ("Vermont", "Green Mountain crags", "🍁", "#2e5f2b", "#e8a33d", 1, 9),
    "NH": ("New Hampshire", "The Granite State", "🗻", "#3d4f5c", "#c9d6df", 1, 10),
    "WA": ("Washington", "Evergreens and alpine rock", "🌲", "#1d5c3a", "#9fd3a8", 2, 0),
    "ID": ("Idaho", "Sawtooth peaks and City of Rocks", "⛰️", "#3e5a2a", "#d6c27a", 2, 1),
    "MT": ("Montana", "Big Sky granite", "🦌", "#41566b", "#e0b45c", 2, 2),
    "ND": ("North Dakota", "Badlands buttes", "🦬", "#6b4a2b", "#e3c08f", 2, 3),
    "MN": ("Minnesota", "North Shore cliffs", "🛶", "#1f4f6e", "#8ec5e8", 2, 4),
    "IL": ("Illinois", "Big city, big gyms", "🏙️", "#2c3e66", "#a9b8e0", 2, 5),
    "WI": ("Wisconsin", "Devil's Lake quartzite", "🧀", "#7a4a12", "#f2c14e", 2, 6),
    "MI": ("Michigan", "Great Lakes shores", "🌊", "#14507a", "#7fc4ec", 2, 7),
    "NY": ("New York", "Gunks quartzite", "🍎", "#8a1f2b", "#f29aa3", 2, 8),
    "RI": ("Rhode Island", "The Ocean State", "⛵", "#1d4d73", "#f0c75e", 2, 9),
    "MA": ("Massachusetts", "Bay State crags", "⚓", "#243f66", "#c7d3e6", 2, 10),
    "OR": ("Oregon", "Smith Rock and volcanic tuff", "🌋", "#8a3b16", "#f5b183", 3, 0),
    "NV": ("Nevada", "Red Rock sandstone", "🌄", "#9b3324", "#f6c08a", 3, 1),
    "WY": ("Wyoming", "Granite towers and cowboy country", "🤠", "#5c4630", "#e6c79b", 3, 2),
    "SD": ("South Dakota", "Black Hills needles", "🌲", "#33503b", "#c4d8a3", 3, 3),
    "IA": ("Iowa", "Fields and river bluffs", "🌽", "#6b5a12", "#f3dc6b", 3, 4),
    "IN": ("Indiana", "Limestone country", "🏁", "#3b3b3b", "#d9d9d9", 3, 5),
    "OH": ("Ohio", "Sandstone ledges", "🌰", "#7a3a1c", "#e8b07f", 3, 6),
    "PA": ("Pennsylvania", "Boulders in the woods", "🔔", "#4a3a6b", "#c9b8e8", 3, 7),
    "NJ": ("New Jersey", "The Garden State", "🍅", "#9a2a1f", "#a8d98a", 3, 8),
    "CT": ("Connecticut", "Traprock ridges", "🍂", "#7a3f16", "#efb06e", 3, 9),
    "CA": ("California", "Granite walls and desert boulders", "🌅", "#a4371b", "#f7c46b", 4, 0),
    "UT": ("Utah", "Red rock and desert towers", "🏜️", "#a2401f", "#f4b57c", 4, 1),
    "CO": ("Colorado", "Front Range granite", "🏔️", "#22487a", "#f1c84b", 4, 2),
    "NE": ("Nebraska", "Sandhills and big skies", "🌾", "#6e5418", "#ead48a", 4, 3),
    "MO": ("Missouri", "Ozark limestone", "🏞️", "#2f5a4a", "#9fd0bb", 4, 4),
    "KY": ("Kentucky", "Red River Gorge sandstone", "🐎", "#1e4a7a", "#a7c7ea", 4, 5),
    "WV": ("West Virginia", "New River Gorge sandstone", "⛏️", "#4a4a2a", "#e3d27d", 4, 6),
    "VA": ("Virginia", "Blue Ridge crags", "🌄", "#2a4a6e", "#b7cde8", 4, 7),
    "MD": ("Maryland", "Potomac gorge rock", "🦀", "#8a2f1c", "#f0b04a", 4, 8),
    "DE": ("Delaware", "The First State", "🐓", "#2a4a66", "#e7cf8f", 4, 9),
    "AZ": ("Arizona", "Desert granite and canyons", "🌵", "#99401f", "#7fc9a3", 5, 1),
    "NM": ("New Mexico", "Desert basalt and high peaks", "🌶️", "#8f2a1e", "#f2d06b", 5, 2),
    "KS": ("Kansas", "Wide open plains", "🌻", "#6b5212", "#f5d24a", 5, 3),
    "AR": ("Arkansas", "Ozark sandstone bluffs", "🌳", "#2f5a2f", "#b5d99a", 5, 4),
    "TN": ("Tennessee", "Plateau sandstone boulders", "🎸", "#6b2f4a", "#e8a8c4", 5, 5),
    "NC": ("North Carolina", "Blue Ridge granite domes", "🌄", "#2a527a", "#a8cbe8", 5, 6),
    "SC": ("South Carolina", "Palmettos and the crescent moon", "🌙", "#1f3f6b", "#c9d7ef", 5, 7),
    "OK": ("Oklahoma", "Wichita Mountains granite", "🌪️", "#5a4a3a", "#d8c3a5", 6, 3),
    "LA": ("Louisiana", "Bayou country", "🎷", "#4a2f6b", "#e6c35c", 6, 4),
    "MS": ("Mississippi", "The Magnolia State", "🌸", "#6b2f55", "#f2b8d6", 6, 5),
    "AL": ("Alabama", "Southern sandstone boulders", "🪨", "#7a2a2a", "#e8b0a0", 6, 6),
    "GA": ("Georgia", "Peach State sandstone", "🍑", "#9a3a2a", "#f7b98f", 6, 7),
    "HI": ("Hawaii", "Volcanic rock by the sea", "🌺", "#7a1f4a", "#f5a3c7", 7, 0),
    "TX": ("Texas", "Hueco Tanks boulders", "⭐", "#7a2e1f", "#e8c27a", 7, 3),
    "FL": ("Florida", "Flat land, tall gym walls", "🐊", "#1f5a4a", "#f2b35c", 7, 8),
}

STATES = {
    code: StateTheme(code, name, tagline, emblem, color, accent, row, col)
    for code, (name, tagline, emblem, color, accent, row, col) in _STATES.items()
}

# Alphabetical by name, for pickers.
STATE_CODES = tuple(sorted(STATES, key=lambda code: STATES[code].name))

# Brand look for anything that isn't tied to one state (matches .streamlit/config.toml).
DEFAULT_THEME = StateTheme("", "Anywhere", "Every climb adds up", "🧗", "#173e36", "#d5ef83", -1, -1)

MAP_ROWS = 8
MAP_COLS = 11


def normalize_state(value):
    """A two-letter state code, or "" for anything unknown. Accepts names too
    ("utah", "Utah") so imported or typed values still earn their stamp."""
    text = (value or "").strip()
    if not text:
        return ""
    if text.upper() in STATES:
        return text.upper()
    for code, theme in STATES.items():
        if theme.name.casefold() == text.casefold():
            return code
    return ""


def theme_for(code):
    """The state's theme, or the brand theme when there's no (known) state."""
    return STATES.get(normalize_state(code), DEFAULT_THEME)


def state_label(code):
    """For pickers: "Utah (UT)", or "" for no state."""
    theme = STATES.get(code)
    return f"{theme.name} ({code})" if theme else ""
