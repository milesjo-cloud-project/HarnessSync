"""Prints the mobile-app waitlist numbers.

Uses the same database the app does, so point it at production with
DATABASE_URL (the Neon URL from your Streamlit Cloud secrets):

    DATABASE_URL="postgresql://..." python waitlist_report.py

With no DATABASE_URL (and no .streamlit/secrets.toml [database]) it reads
the local SQLite file.
"""

import waitlist_manager


def main():
    s = waitlist_manager.summary()
    print(f"Waitlist: {s['total']} people")
    print(f"  Would install on iPhone:  {s['ios']}")
    print(f"  Would install on Android: {s['android']}")
    for platform, count in s["by_platform"].items():
        print(f"    chose {platform}: {count}")
    print("\nWhat would make a phone app worth it:")
    for reason, count in sorted(s["by_reason"].items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4}  {reason}")
    if s["notes"]:
        print("\nNotes:")
        for note in s["notes"]:
            print(f"  - {note}")


if __name__ == "__main__":
    main()
