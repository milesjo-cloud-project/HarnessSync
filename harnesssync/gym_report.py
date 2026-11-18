"""Monthly gym wall report: anonymous totals for a pilot gym.

A gym gets something back for hosting the flyer: one page a month showing how
its members climbed. Privacy rules, all enforced here rather than in the UI:

  - Only climbers who joined the gym in their account menu are counted, and
    only Gym climbs dated on or after the day they joined.
  - The report never contains names, emails, notes, route names or single
    climbs. It is totals only.
  - With fewer than MIN_CLIMBERS climbers in the month, nothing but that fact
    is shown, and any grade logged by fewer than MIN_CLIMBERS climbers is
    folded into "Other grades", so no total can point at one person.

Gyms are added by the owner, and only the owner can build a report. Nothing
is emailed: the owner downloads the page and sends it to the gym themselves.

From a terminal, with the same database the app uses:

    DATABASE_URL="postgresql://..." python -m harnesssync.gym_report rock-gym-rexburg 2026-10
"""

import argparse
import calendar
import html
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

import sqlalchemy as sa

from harnesssync.db_store import get_db, rows, climbs, gyms, gym_members
from harnesssync.grades import GRADES_BY_DISCIPLINE, SENT_STATUSES, PROJECT_STATUSES, grade_rank
from harnesssync.states import normalize_state
from harnesssync.support_config import require_owner

MIN_CLIMBERS = 3
GYM_NAME_MAX = 80
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
OTHER_GRADES = "Other grades"


# ----------------- GYMS -----------------
def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").casefold()).strip("-")
    return slug[:40].strip("-")


def add_gym(actor, name, state=""):
    """Owner only. Returns the new gym's slug. state is the gym's two-letter
    US state, so climbs logged from its flyer start in that state."""
    require_owner(actor)
    name = re.sub(r"\s+", " ", name or "").strip()[:GYM_NAME_MAX]
    slug = slugify(name)
    if not slug:
        raise ValueError("Enter the gym's name.")
    with get_db() as conn:
        if conn.execute(sa.select(gyms.c.slug).where(gyms.c.slug == slug)).first():
            raise ValueError("That gym is already on the list.")
        conn.execute(gyms.insert().values(
            slug=slug, name=name, state=normalize_state(state),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return slug


def list_gyms():
    """Gym names and slugs only, for the climber's picker."""
    with get_db() as conn:
        return rows(conn.execute(sa.select(gyms.c.slug, gyms.c.name, gyms.c.state).order_by(gyms.c.name)))


def set_gym_state(actor, slug, state):
    """Owner only. Sets or fixes a pilot gym's state (gyms added before states existed have none)."""
    require_owner(actor)
    with get_db() as conn:
        conn.execute(gyms.update().where(gyms.c.slug == slug).values(state=normalize_state(state)))


def get_gym(slug):
    with get_db() as conn:
        found = rows(conn.execute(sa.select(gyms).where(gyms.c.slug == slug)))
    return found[0] if found else None


# ----------------- MEMBERSHIP (the climber's opt-in) -----------------
def get_membership(user_id):
    if not user_id:
        return None
    with get_db() as conn:
        found = rows(conn.execute(sa.select(gym_members).where(gym_members.c.user_id == user_id)))
    return found[0] if found else None


def join_gym(user_id, slug, today):
    """Opt the signed-in climber into one gym's report. Switching gyms restarts
    the counting date, so a new gym never sees climbs from before the switch."""
    if not user_id:
        raise ValueError("Sign in before choosing a gym.")
    if get_gym(slug) is None:
        raise ValueError("Unknown gym.")
    current = get_membership(user_id)
    if current and current["gym_slug"] == slug:
        return
    with get_db() as conn:
        conn.execute(gym_members.delete().where(gym_members.c.user_id == user_id))
        conn.execute(gym_members.insert().values(user_id=user_id, gym_slug=slug, joined_on=today.isoformat()))


def leave_gym(user_id):
    with get_db() as conn:
        conn.execute(gym_members.delete().where(gym_members.c.user_id == user_id))


# ----------------- REPORT -----------------
def month_bounds(year, month):
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def previous_month(today):
    return (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)


def _counted_climbs(conn, slug, start, end):
    """Gym climbs from opted-in members, dated inside the month and on or after
    each member's join date. Returns user ids too, but they never leave this module."""
    query = (
        sa.select(climbs.c.user_id, climbs.c.date, climbs.c.discipline, climbs.c.grade, climbs.c.status)
        .join(gym_members, gym_members.c.user_id == climbs.c.user_id)
        .where(
            gym_members.c.gym_slug == slug,
            climbs.c.environment == "Gym",
            climbs.c.date >= start.isoformat(),
            climbs.c.date <= end.isoformat(),
            climbs.c.date >= gym_members.c.joined_on,
        )
    )
    return rows(conn.execute(query))


def summarize(slug, year, month):
    """The anonymous totals for one gym and month. No identifiers in the result."""
    gym = get_gym(slug)
    if gym is None:
        raise ValueError("Unknown gym.")
    start, end = month_bounds(year, month)
    with get_db() as conn:
        found = _counted_climbs(conn, slug, start, end)
        members = conn.execute(
            sa.select(sa.func.count()).select_from(gym_members)
            .where(gym_members.c.gym_slug == slug, gym_members.c.joined_on <= end.isoformat())
        ).scalar_one()

    climbers = {c["user_id"] for c in found}
    report = {
        "gym": gym["name"],
        "month": start.strftime("%B %Y"),
        "members": members,
        "climbers": len(climbers),
        "withheld": len(climbers) < MIN_CLIMBERS,
        "min_climbers": MIN_CLIMBERS,
    }
    if report["withheld"]:
        return report

    sends = [c for c in found if c["status"] in SENT_STATUSES]
    weekday = Counter(date.fromisoformat(c["date"]).weekday() for c in found)
    report.update({
        "logged": len(found),
        "sends": len(sends),
        "send_rate": round(100 * len(sends) / len(found)) if found else 0,
        "by_weekday": [{"day": WEEKDAYS[i], "climbs": weekday.get(i, 0)} for i in range(7)],
        "busiest_day": WEEKDAYS[max(range(7), key=lambda i: (weekday.get(i, 0), -i))],
        "disciplines": [_discipline_summary(d, found) for d in GRADES_BY_DISCIPLINE
                        if any(c["discipline"] == d for c in found)],
    })
    return report


def _discipline_summary(discipline, found):
    entries = [c for c in found if c["discipline"] == discipline]
    by_grade = defaultdict(lambda: {"logged": 0, "sends": 0, "tries": 0, "climbers": set()})
    for c in entries:
        bucket = by_grade[c["grade"]]
        bucket["logged"] += 1
        bucket["sends"] += c["status"] in SENT_STATUSES
        bucket["tries"] += c["status"] in PROJECT_STATUSES
        bucket["climbers"].add(c["user_id"])

    shown, other = [], {"grade": OTHER_GRADES, "logged": 0, "sends": 0, "tries": 0}
    for grade in sorted(by_grade, key=lambda g: grade_rank(discipline, g)):
        bucket = by_grade[grade]
        if len(bucket["climbers"]) >= MIN_CLIMBERS:
            shown.append({"grade": grade, "logged": bucket["logged"], "sends": bucket["sends"], "tries": bucket["tries"]})
        else:
            for key in ("logged", "sends", "tries"):
                other[key] += bucket[key]
    if other["logged"]:
        shown.append(other)

    real = [g for g in shown if g["grade"] != OTHER_GRADES]
    most_logged = max(real, key=lambda g: g["logged"])["grade"] if real else None
    # Where members keep trying and not sending: useful to setters.
    stuck = [g for g in real if g["tries"] > g["sends"]]
    hardest_stuck = max(stuck, key=lambda g: (g["tries"] - g["sends"], grade_rank(discipline, g["grade"])))["grade"] if stuck else None
    return {
        "discipline": discipline,
        "logged": len(entries),
        "sends": sum(c["status"] in SENT_STATUSES for c in entries),
        "most_logged": most_logged,
        "most_tried": hardest_stuck,
        "grades": shown,
    }


def owner_report(actor, slug, year, month):
    require_owner(actor)
    return summarize(slug, year, month)


# ----------------- OUTPUT -----------------
def _discipline_label(discipline):
    return {"Boulder": "Bouldering", "Rope": "Roped climbing"}.get(discipline, discipline)


def render_text(report):
    """Plain text the owner can paste into their own email to the gym."""
    lines = [f"{report['gym']} wall report, {report['month']}", ""]
    if report["withheld"]:
        lines.append(f"Fewer than {report['min_climbers']} climbers logged gym climbs this month, "
                     "so totals are held back to keep everyone anonymous.")
        lines.append(f"Climbers signed up for your report: {report['members']}")
        return "\n".join(lines)
    lines += [
        f"Climbers logging: {report['climbers']} (of {report['members']} signed up)",
        f"Climbs logged: {report['logged']}",
        f"Sends: {report['sends']} ({report['send_rate']}% of logged climbs)",
        f"Busiest day: {report['busiest_day']}",
    ]
    for d in report["disciplines"]:
        lines += ["", f"{_discipline_label(d['discipline'])}: {d['logged']} logged, {d['sends']} sends"]
        if d["most_logged"]:
            lines.append(f"  Most-logged grade: {d['most_logged']}")
        if d["most_tried"]:
            lines.append(f"  Most tries without a send: {d['most_tried']}")
        for g in d["grades"]:
            lines.append(f"  {g['grade']}: {g['logged']} logged, {g['sends']} sends")
    lines += ["", "Totals only, from climbers who chose to share. No names or single climbs are included.",
              f"Grades logged by fewer than {report['min_climbers']} climbers are grouped as \"{OTHER_GRADES}\"."]
    return "\n".join(lines)


def render_html(report):
    """A self-contained one-page report the owner can download and attach."""
    e = html.escape
    head = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(report['gym'])} wall report, {e(report['month'])}</title>
<style>
body{{margin:0;background:#f5f3eb;color:#173e36;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:720px;margin:0 auto;padding:32px 20px}}
h1{{font-size:34px;line-height:1.1;margin:4px 0 4px}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#4d6a62}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:24px 0}}
.kpi{{border-top:3px solid #173e36;padding-top:6px}}
.kpi b{{display:block;font-size:34px;line-height:1.1;font-variant-numeric:tabular-nums}}
.kpi span{{font-size:14px;color:#4d6a62}}
h2{{font-size:20px;margin:28px 0 8px}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #d6dcd1}}
th{{font-size:13px;color:#4d6a62;font-weight:600}}
.days{{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;align-items:end;height:120px;border-bottom:2px solid #173e36}}
.days div{{background:#7f9c86;min-height:2px}}
.daylabels{{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;font-size:12px;color:#4d6a62;text-align:center}}
.note{{font-size:13px;color:#4d6a62;margin-top:28px;border-top:1px solid #d6dcd1;padding-top:12px}}
</style></head><body><main>
<p class="eyebrow">HarnessSync wall report</p>
<h1>{e(report['gym'])}</h1>
<p>{e(report['month'])}</p>"""
    if report["withheld"]:
        body = (f"<p>Fewer than {report['min_climbers']} climbers logged gym climbs this month, so totals are "
                f"held back to keep everyone anonymous.</p><p>Climbers signed up for your report: "
                f"<b>{report['members']}</b></p>")
        return head + body + "</main></body></html>"

    kpis = [(report["climbers"], "climbers logging"), (report["logged"], "climbs logged"),
            (report["sends"], "sends"), (f"{report['send_rate']}%", "send rate")]
    body = '<div class="kpis">' + "".join(
        f'<div class="kpi"><b>{e(str(v))}</b><span>{e(label)}</span></div>' for v, label in kpis) + "</div>"
    peak = max(d["climbs"] for d in report["by_weekday"]) or 1
    body += "<h2>Climbs by day of the week</h2><div class=\"days\">" + "".join(
        f'<div style="height:{round(100 * d["climbs"] / peak)}%" title="{d["day"]}: {d["climbs"]}"></div>'
        for d in report["by_weekday"]) + "</div><div class=\"daylabels\">" + "".join(
        f"<span>{d['day']}</span>" for d in report["by_weekday"]) + "</div>"
    for d in report["disciplines"]:
        body += f"<h2>{e(_discipline_label(d['discipline']))}</h2><p>"
        facts = []
        if d["most_logged"]:
            facts.append(f"Most-logged grade: <b>{e(d['most_logged'])}</b>")
        if d["most_tried"]:
            facts.append(f"Most tries without a send: <b>{e(d['most_tried'])}</b>")
        body += " · ".join(facts) + "</p><table><thead><tr><th>Grade</th><th>Logged</th><th>Sends</th><th>Tries</th></tr></thead><tbody>"
        body += "".join(f"<tr><td>{e(g['grade'])}</td><td>{g['logged']}</td><td>{g['sends']}</td><td>{g['tries']}</td></tr>"
                        for g in d["grades"]) + "</tbody></table>"
    body += (f'<p class="note">Totals only, from {report["members"]} climbers who chose to share their gym climbs with '
             f'{e(report["gym"])}. No names, notes or single climbs are included. Grades logged by fewer than '
             f'{report["min_climbers"]} climbers are grouped as "{OTHER_GRADES}".</p>')
    return head + body + "</main></body></html>"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gym", help="gym slug, as shown in the owner's gym list")
    parser.add_argument("month", nargs="?", help="YYYY-MM (default: last month)")
    parser.add_argument("--html", help="also write the one-page report to this file")
    args = parser.parse_args()
    if args.month:
        year, month = (int(part) for part in args.month.split("-"))
    else:
        year, month = previous_month(date.today())
    report = summarize(args.gym, year, month)
    print(render_text(report))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(report))


if __name__ == "__main__":
    main()
