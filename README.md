# 🧗 HarnessSync

A free climbing log for boulderers and rope climbers: log sends, track projects
across sessions, time your sessions, and see your grade pyramid and progression.

**Live app:** <https://harnesssync.onrender.com> ·
**Home & privacy policy:** <https://milesjo-cloud-project.github.io/HarnessSync/>

**Gym pilot flyer:** [Open the print-ready flyer](docs/gym-flyer.html) · [QR code](docs/gym-qr.svg)

## Features

- Log climbs with grade (V-scale or YDS), send style, wall angle, hold type and location
- Projects with attempt counts and beta notes, graduated to the log when you send
- Session timer that survives page reloads
- Send volume pyramid, send-style breakdown and grade progression charts
- One Progress area with Overview, Personal goals, Session recaps and Achievements.
  Goals track sends or climbing days within a date range. Daily recaps combine
  logged climbs with separately recorded timer minutes, without guessing exact
  climb times. Edits and deletions recalculate goal progress.
- Quick logging asks for discipline, grade and result. Optional details are
  collapsed; the main app and phone logger reuse the account/device's previous
  grade and location. Route names are cleared for the next entry.
- Personal achievements in Progress: send counts, climbing days, first-try sends,
  and first sends at each grade, with private-by-default downloadable PNG cards.
  Milestones reflect current logs (including past history and synced phone entries);
  edits/deletions recalculate them. Repeat sends count toward volume; days require
  a completed send. Sharing an image is manual and includes only milestone/date.
- Opt-in leaderboard (display name only, never email)
- Language selector: English, Spanish, French, Japanese, Korean and Simplified
  Chinese for core climbing flows and achievement cards. Signed-in choices are
  saved per account; phone changes work offline and sync to that account on
  reconnect. The phone logger receives account language changes on its next sync.
  Climbing grades keep their existing V/YDS notation and stored values stay
  unchanged. User-written notes and replies are never machine-translated.
  Some help/reference articles, owner tools and diagnostic messages remain English.
- CSV export and one-click account deletion
- Private support tickets, status and owner replies, crash references, and retryable email alerts
- Owner-reviewed repair briefs for Codex Cloud, with manual PR review and publishing
- Offline phone web app: device storage for climbs/attempts, downloaded projects and progress,
  and automatic duplicate-safe sync when the page is open again (📱 Phone App tab).
- Export and restore unsynced offline backups on the same account; no idle sync polling.
- Waitlist for a native iPhone / Android app (📱 Phone App tab)

## Run it locally

```sh
pip install -r requirements-dev.txt
HARNESSSYNC_DEV_MODE=1 streamlit run asgi_app.py   # no Google sign-in, local SQLite
```

To run with Google sign-in, copy `.streamlit/secrets.toml.example` to
`.streamlit/secrets.toml` and fill in `[auth]`. Docker works too:
`docker compose up`.

## Tests

```sh
python -m pytest
```

Translations live in `harnesssync/locales/*.json`. After updating them, run
`python scripts/build_offline_locales.py` to refresh the public offline bundle.
For new card characters, regenerate the bundled font as described in
`harnesssync/assets/README.md`. No external translation service is used.

## Layout

| File | What it does |
| --- | --- |
| `asgi_app.py` | Server entry point: Streamlit UI plus offline assets and sync API |
| `app.py` | Compatibility launcher for existing Streamlit Cloud deployments |
| `streamlit_app.py` | Sign-in, sidebar and tabs, rendered by the ASGI server |
| `harnesssync/ui/` | The page, one module per part: `sidebar`, `dashboard`, `projects`, `leaderboard`, `phone_app`, `feedback`, `guide`, plus shared `common` helpers |
| `harnesssync/db_store.py` | Database tables and connection (SQLite locally, Postgres in production) |
| `harnesssync/profile_manager.py` | Profiles, climbs, projects, sessions - every query scoped to the signed-in user |
| `harnesssync/leaderboard_engine.py` | Builds the opt-in leaderboard |
| `harnesssync/feedback_manager.py` / `support_notifications.py` | Private tickets, owner replies, rate limiting, durable email queue |
| `harnesssync/repair_brief.py` / `incidents.py` | Reviewed Codex repair briefs and sanitized crash grouping |
| `harnesssync/waitlist_manager.py` / `waitlist_report.py` | Phone app waitlist and the demand report (`python -m harnesssync.waitlist_report`) |
| `harnesssync/grades.py` | Grade scales and conversion tables |
| `tests/` | pytest suite |
| `docs/` | GitHub Pages site: home page and privacy policy |
| `climber_profiles/` | Local SQLite database (git-ignored) |

## Deploying

Email/password sign-in is available as an alternative to Google. See
[password account setup](docs/password-accounts.md) for Render settings, mailbox
verification, password recovery, and existing-account migration.

See [DEPLOYMENT.md](DEPLOYMENT.md) (Streamlit Community Cloud + Google sign-in + Neon Postgres).
For unattended support email retries, enable the included
[GitHub Actions scheduler](docs/support-email-scheduler.md). It runs while your computer is off.

## Fixing reported problems

See [the Codex Cloud repair workflow](docs/codex-repair-workflow.md). Reports work without an AI service; the owner reviews each fix and manually merges the PR when ready to publish.

Optional [Discord uptime alerts](docs/discord-alerts.md) use UptimeRobot for
external checks and outage/recovery notifications. No extra Render worker is
needed. The site has no in-app AI runtime or automated coding agent.
