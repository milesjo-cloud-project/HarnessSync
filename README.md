# 🧗 HarnessSync

A free climbing log for boulderers and rope climbers: log sends, track projects
across sessions, time your sessions, and see your grade pyramid and progression.

**Live app:** <https://harnesssync.streamlit.app> ·
**Home & privacy policy:** <https://milesjo-cloud-project.github.io/HarnessSync/>

**Gym pilot flyer:** [Open the print-ready flyer](docs/gym-flyer.html) · [QR code](docs/gym-qr.svg)

## Features

- Log climbs with grade (V-scale or YDS), send style, wall angle, hold type and location
- Projects with attempt counts and beta notes, graduated to the log when you send
- Session timer that survives page reloads
- Send volume pyramid, send-style breakdown and grade progression charts
- Opt-in leaderboard (display name only, never email)
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

See [DEPLOYMENT.md](DEPLOYMENT.md) (Streamlit Community Cloud + Google sign-in + Neon Postgres).
For unattended support email retries, enable the included
[GitHub Actions scheduler](docs/support-email-scheduler.md). It runs while your computer is off.

## Fixing reported problems

See [the Codex Cloud repair workflow](docs/codex-repair-workflow.md). Reports work without an AI service; the owner reviews each fix and manually merges the PR when ready to publish.
