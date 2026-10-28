"""Personal milestones derived from an already user-scoped climbing history.

No award table or side effects: edits, deletions and offline sync are reflected
on the next dashboard visit. Dates are climbing dates, not award timestamps.
"""

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from harnesssync.grades import SENT_STATUSES, grade_rank
from harnesssync.i18n import translate


@dataclass(frozen=True)
class Achievement:
    key: str
    title: str
    description: str
    earned_on: str
    category: str


def achievements(climbs, today, language="en"):
    """Evaluate completed sends only, ignoring invalid/future climbing dates.

    Callers must supply only the authenticated user's climbs. Repeated sends
    count toward volume; climbing days count distinct dates with a send.
    """
    sends = []
    for climb in climbs:
        if climb.get("status") not in SENT_STATUSES:
            continue
        try:
            day = date.fromisoformat(climb["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if day <= today:
            sends.append(climb)
    sends.sort(key=lambda c: (c["date"], c.get("id", 0)))
    earned = []
    def t(message, **values):
        return translate(message, language, **values)

    def award(key, title, description, day, category):
        earned.append(Achievement(key, title, description, day, t(category)))

    for target in (1, 10, 50, 100, 250, 500, 1000):
        if len(sends) >= target:
            award(f"sends-{target}", t("First send") if target == 1 else t("{count} sends", count=target),
                  t("Your first completed climb in the log.") if target == 1 else
                  t("{count} completed climbs logged, including repeat sends.", count=target),
                  sends[target - 1]["date"], "Volume")

    days = sorted({c["date"] for c in sends})
    for target in (5, 20, 50, 100):
        if len(days) >= target:
            award(f"days-{target}", t("{count} climbing days", count=target),
                  t("Completed sends on {count} different days.", count=target), days[target - 1], "Consistency")

    first_try = [c for c in sends if c["status"] in ("Flash", "Onsight")]
    for target in (1, 10, 50):
        if len(first_try) >= target:
            award(f"first-try-{target}", t("First-try finish") if target == 1 else t("{count} first-try sends", count=target),
                  t("A flash or onsight logged.") if target == 1 else
                  t("{count} flashes and onsights logged.", count=target), first_try[target - 1]["date"], "Style")

    grades_seen = set()
    for climb in sends:
        discipline, grade = climb["discipline"], climb["grade"]
        pair = (discipline, grade)
        if grade_rank(discipline, grade) < 0 or pair in grades_seen:
            continue
        grades_seen.add(pair)
        award(f"grade-{discipline.lower()}-{grade}", t("First {grade} send", grade=grade),
              t("Your first logged {discipline} send at {grade}.", discipline=t(discipline.lower()), grade=grade), climb["date"], "Grade")

    return sorted(earned, key=lambda a: (a.earned_on, a.key), reverse=True)


def achievement_card(achievement, language="en"):
    """Render a shareable PNG containing only milestone text and climbing date.

    Deliberately accepts no profile or climb details. Uses a bundled OFL font
    so Render and local machines render all supported languages without OS fonts.
    """
    image = Image.new("RGB", (1200, 630), "#102c33")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 32, 1168, 598), radius=30, outline="#3f6970", width=2)
    draw.polygon([(780, 598), (1010, 270), (1168, 490), (1168, 598)], fill="#19434a")
    draw.polygon([(900, 598), (1110, 350), (1168, 420), (1168, 598)], fill="#24565a")

    def font(size):
        return ImageFont.truetype(str(Path(__file__).with_name("assets") / "card-font.otf"), size)

    def text(xy, value, size, color):
        draw.text(xy, value, font=font(size), fill=color)

    text((80, 70), "HarnessSync", 32, "#91e0cb")
    text((80, 155), translate("ACHIEVEMENT / {category}", language, category=achievement.category.upper()), 22, "#b9d2d4")
    title_size = 64
    while draw.textlength(achievement.title, font=font(title_size)) > 1040:
        title_size -= 1
    text((80, 213), achievement.title, title_size, "#ffffff")
    # Descriptions are fixed product copy; wrap by measured pixel width.
    body_font = font(28)
    line, y = "", 320
    # Wrap by character so Japanese and Chinese work without word spaces.
    for character in achievement.description:
        candidate = line + character
        if draw.textlength(candidate, font=body_font) > 950:
            text((80, y), line, 28, "#d1e1e2")
            line, y = character.lstrip(), y + 40
        else:
            line = candidate
    text((80, y), line, 28, "#d1e1e2")
    text((80, 466), translate("Climbed on {date}", language, date=achievement.earned_on), 25, "#91e0cb")
    text((80, 540), translate("Log a climb. See your progress.", language), 22, "#b9d2d4")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
