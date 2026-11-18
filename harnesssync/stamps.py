"""State stamps: a climber's passport of the states they've climbed in.

A state's stamp is earned by the first climb or project logged in that state,
whatever the outcome (a try counts, not just a send). Like achievements, there
is no award table: stamps are worked out from the log, so editing or deleting
a climb updates the passport on the next visit.

The SVG here is built from the state table in states.py and escapes every
piece of text. st.html only keeps HTML tags (no inline <svg>), so each SVG is
shown as an <img> with a data: URI, which it does keep.
"""

import base64
from dataclasses import dataclass
from datetime import date
from html import escape

from harnesssync.states import MAP_COLS, MAP_ROWS, STATES, normalize_state, theme_for

LOCKED_FILL = "#e9eddf"
LOCKED_TEXT = "#53665e"
INK = "#173e36"
PAPER = "#fffef9"


@dataclass(frozen=True)
class Stamp:
    code: str
    name: str
    tagline: str
    emblem: str
    earned_on: str


def earned_stamps(history, today=None):
    """One Stamp per state in the history, dated by the first climb there,
    oldest first. `history` is rows with "state" and "date" (climbs, projects,
    or get_state_history). Unknown states and bad or future dates are skipped."""
    first = {}
    for entry in history:
        code = normalize_state(entry.get("state"))
        if not code:
            continue
        try:
            day = date.fromisoformat(entry.get("date") or "")
        except (TypeError, ValueError):
            continue
        if today is not None and day > today:
            continue
        if code not in first or day < first[code]:
            first[code] = day
    ordered = sorted(first.items(), key=lambda item: (item[1], STATES[item[0]].name))
    return [Stamp(code, STATES[code].name, STATES[code].tagline, STATES[code].emblem, day.isoformat())
            for code, day in ordered]


def passport_map_svg(earned_codes, title="Your climbing passport"):
    """A tile map of the 50 states: earned states in their own colour, the
    rest greyed out. Scales to any width through its viewBox."""
    earned_codes = set(earned_codes)
    tile, gap = 44, 4
    width = MAP_COLS * (tile + gap) - gap
    height = MAP_ROWS * (tile + gap) - gap
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(title)}" style="width:100%;max-width:560px;height:auto;display:block">'
    ]
    for code in sorted(STATES, key=lambda c: (STATES[c].row, STATES[c].col)):
        theme = STATES[code]
        x, y = theme.col * (tile + gap), theme.row * (tile + gap)
        earned = code in earned_codes
        fill = theme.color if earned else LOCKED_FILL
        text = "#ffffff" if earned else LOCKED_TEXT
        label = f"{theme.name}: {'stamp earned' if earned else 'not yet'}"
        parts.append(
            f'<g><title>{escape(label)}</title>'
            f'<rect x="{x}" y="{y}" width="{tile}" height="{tile}" rx="7" fill="{fill}"'
            + (f' stroke="{theme.accent}" stroke-width="2"' if earned else "") + "/>"
            f'<text x="{x + tile / 2}" y="{y + (17 if earned else 27)}" text-anchor="middle" '
            f'font-family="system-ui,-apple-system,Segoe UI,Arial,sans-serif" font-size="13" '
            f'font-weight="700" fill="{text}">{code}</text>'
        )
        if earned:
            parts.append(
                f'<text x="{x + tile / 2}" y="{y + 37}" text-anchor="middle" font-size="15">{theme.emblem}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def stamp_svg(code, earned_on=None, size=132):
    """One round passport stamp in the state's colours. Without earned_on it's
    drawn as a locked, grey outline."""
    theme = theme_for(code)
    earned = earned_on is not None
    color = theme.color if earned else LOCKED_FILL
    ring = theme.accent if earned else "#d6dcd1"
    ink = "#ffffff" if earned else LOCKED_TEXT
    name = escape(theme.name.upper())
    font = "system-ui,-apple-system,Segoe UI,Arial,sans-serif"
    # Long names get a smaller arc label so they still fit around the top.
    name_size = 11 if len(theme.name) <= 10 else 9
    emblem = theme.emblem if earned else "🔒"
    date_line = escape(earned_on) if earned else "LOCKED"
    path_id = f"arc-{escape(theme.code or 'any')}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 132 132" width="{size}" height="{size}" '
        f'role="img" aria-label="{escape(theme.name)} stamp{", earned " + escape(earned_on) if earned else ", locked"}">'
        f'<defs><path id="{path_id}" d="M 24 66 A 42 42 0 0 1 108 66"/></defs>'
        f'<circle cx="66" cy="66" r="62" fill="{color}" stroke="{ring}" stroke-width="4"/>'
        f'<circle cx="66" cy="66" r="52" fill="none" stroke="{ring}" stroke-width="1.5" stroke-dasharray="3 3"/>'
        f'<text font-family="{font}" font-size="{name_size}" font-weight="800" letter-spacing="1.5" fill="{ink}">'
        f'<textPath href="#{path_id}" startOffset="50%" text-anchor="middle">{name}</textPath></text>'
        f'<text x="66" y="80" text-anchor="middle" font-size="34">{emblem}</text>'
        f'<text x="66" y="104" text-anchor="middle" font-family="{font}" font-size="10" font-weight="700" '
        f'letter-spacing="1" fill="{ink}">{date_line}</text>'
        f"</svg>"
    )


def svg_img(svg, alt, width=None):
    """An <img> tag showing an SVG, for st.html."""
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    size = f' width="{int(width)}"' if width else ' style="width:100%;max-width:560px;height:auto"'
    return f'<img src="data:image/svg+xml;base64,{data}" alt="{escape(alt)}"{size}>'


def passport_map_html(earned_codes, alt):
    return svg_img(passport_map_svg(earned_codes, alt), alt)


def state_banner_html(code, heading, tagline=None):
    """A slim banner in the state's colours, for the Log screen."""
    theme = theme_for(code)
    tagline = theme.tagline if tagline is None else tagline
    return (
        f'<div style="background:{theme.color};color:#fff;border-radius:12px;padding:10px 14px;'
        f'display:flex;align-items:center;gap:12px;border-left:6px solid {theme.accent};'
        f'font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif">'
        f'<span style="font-size:28px;line-height:1" aria-hidden="true">{theme.emblem}</span>'
        f'<span><strong style="font-size:16px">{escape(heading)}</strong><br>'
        f'<span style="font-size:13px;opacity:.92">{escape(tagline)}</span></span></div>'
    )


def stamp_grid_html(stamps, size=112):
    """Earned stamps, wrapping on a phone, each with its tagline under it."""
    cells = []
    for stamp in stamps:
        cells.append(
            f'<figure style="margin:0;width:{size + 20}px;text-align:center">'
            f'{svg_img(stamp_svg(stamp.code, stamp.earned_on, size), f"{stamp.name} stamp, {stamp.earned_on}", size)}'
            f'<figcaption style="font:12px/1.3 system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:{INK};'
            f'margin-top:4px">{escape(stamp.tagline)}</figcaption></figure>'
        )
    return f'<div style="display:flex;flex-wrap:wrap;gap:12px">{"".join(cells)}</div>'
