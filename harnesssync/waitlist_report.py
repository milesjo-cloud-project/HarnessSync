"""Prints phone-app demand: the in-app waitlist, plus the home page survey.

Uses the same database the app does, so point it at production with
DATABASE_URL (the Neon URL from your Streamlit Cloud secrets):

    DATABASE_URL="postgresql://..." python -m harnesssync.waitlist_report

With no DATABASE_URL (and no .streamlit/secrets.toml [database]) it reads
the local SQLite file.

To include the Google Form survey, download its response sheet as CSV
(File > Download > Comma-separated values) and pass it in:

    python -m harnesssync.waitlist_report --survey "responses.csv"

Keep that sheet's sharing set to Restricted - it holds respondents' answers.
"""

import argparse
import csv
from collections import Counter

from harnesssync import waitlist_manager

# Matched against the sheet's column headers (the form's question titles),
# loosely, so small wording edits to the form don't break the report.
SURVEY_COLUMNS = {
    "platform": "mobile platform",
    "discipline": "primary climbing discipline",
    "experience": "experience level",
    "features": "most useful",
    "partner": "find climbing partners",
    "pain": "pain point",
    "email": "email",
}


def load_survey(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _column(headers, key):
    needle = SURVEY_COLUMNS[key]
    return next((h for h in headers if needle in h.lower()), None)


def summarize_survey(responses, waitlist_emails=()):
    """Tallies survey answers. Respondents whose email is already on the
    in-app waitlist are skipped, so nobody is counted twice."""
    headers = list(responses[0]) if responses else []
    col = {key: _column(headers, key) for key in SURVEY_COLUMNS}
    known = {e.lower() for e in waitlist_emails}

    def answer(row, key):
        return (row.get(col[key]) or "").strip() if col[key] else ""

    counted, duplicates = [], 0
    for row in responses:
        if answer(row, "email").lower() in known:
            duplicates += 1
        else:
            counted.append(row)

    platforms = Counter(answer(r, "platform") for r in counted if answer(r, "platform"))
    features = Counter(
        f.strip() for r in counted for f in answer(r, "features").split(",") if f.strip()
    )
    partner = [int(answer(r, "partner")) for r in counted if answer(r, "partner").isdigit()]
    return {
        "total": len(counted),
        "duplicates": duplicates,
        "ios": platforms.get("Apple iOS", 0),
        "android": platforms.get("Android", 0),
        "platforms": platforms,
        "disciplines": Counter(answer(r, "discipline") for r in counted if answer(r, "discipline")),
        "experience": Counter(answer(r, "experience") for r in counted if answer(r, "experience")),
        "features": features,
        "partner_avg": sum(partner) / len(partner) if partner else None,
        "pains": [answer(r, "pain") for r in counted if answer(r, "pain")],
    }


def _print_counts(title, counts):
    if not counts:
        return
    print(f"\n{title}:")
    for label, count in counts.most_common():
        print(f"  {count:>4}  {label}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--survey", help="CSV export of the Google Form response sheet")
    args = parser.parse_args()

    s = waitlist_manager.summary()
    print(f"In-app waitlist: {s['total']} people")
    print(f"  Would install on iPhone:  {s['ios']}")
    print(f"  Would install on Android: {s['android']}")
    for platform, count in s["by_platform"].items():
        print(f"    chose {platform}: {count}")
    _print_counts("What would make a phone app worth it", Counter(s["by_reason"]))
    if s["notes"]:
        print("\nNotes:")
        for note in s["notes"]:
            print(f"  - {note}")

    if not args.survey:
        return

    v = summarize_survey(load_survey(args.survey), waitlist_manager.emails())
    print(f"\n{'=' * 50}\nHome page survey: {v['total']} responses")
    if v["duplicates"]:
        print(f"  (+{v['duplicates']} skipped - already on the in-app waitlist)")
    _print_counts("Platform", v["platforms"])
    _print_counts("Discipline", v["disciplines"])
    _print_counts("Experience", v["experience"])
    _print_counts("Most useful features", v["features"])
    if v["partner_avg"] is not None:
        print(f"\nPartner-finder interest: {v['partner_avg']:.1f} / 5")
    if v["pains"]:
        print("\nBiggest pain points:")
        for pain in v["pains"]:
            print(f"  - {pain}")

    print(f"\n{'=' * 50}\nCombined demand (survey answers aren't verified, and anyone can submit twice)")
    print(f"  iPhone:  {s['ios'] + v['ios']}  ({s['ios']} in-app + {v['ios']} survey)")
    print(f"  Android: {s['android'] + v['android']}  ({s['android']} in-app + {v['android']} survey)")


if __name__ == "__main__":
    main()
