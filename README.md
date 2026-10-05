# 🧗 HarnessSync

A free climbing log for boulderers and rope climbers: log sends, track projects
across sessions, time your sessions, and see your grade pyramid and progression.

**Live app:** <https://harnesssync.streamlit.app> ·
**Home & privacy policy:** <https://milesjo-cloud-project.github.io/HarnessSync/>

## Features

- Log climbs with grade (V-scale or YDS), send style, wall angle, hold type and location
- Projects with attempt counts and beta notes, graduated to the log when you send
- Session timer that survives page reloads
- Send volume pyramid, send-style breakdown and grade progression charts
- Opt-in leaderboard (display name only, never email)
- CSV export and one-click account deletion
- Waitlist for a native iPhone / Android app (📱 Phone App tab)

## Run it locally

```sh
pip install -r requirements-dev.txt
HARNESSSYNC_DEV_MODE=1 streamlit run app.py   # no Google sign-in, local SQLite
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
| `app.py` | Streamlit UI: sign-in, sidebar logging, tabs (the entry point Streamlit Cloud runs) |
| `harnesssync/db_store.py` | Database tables and connection (SQLite locally, Postgres in production) |
| `harnesssync/profile_manager.py` | Profiles, climbs, projects, sessions - every query scoped to the signed-in user |
| `harnesssync/leaderboard_engine.py` | Builds the opt-in leaderboard |
| `harnesssync/feedback_manager.py` / `notifications.py` | In-app feedback, rate limiting, email delivery |
| `harnesssync/waitlist_manager.py` / `waitlist_report.py` | Phone app waitlist and the demand report (`python -m harnesssync.waitlist_report`) |
| `harnesssync/grades.py` | Grade scales and conversion tables |
| `harnesssync/user_guide.py` | Guide & Reference tab |
| `tests/` | pytest suite |
| `docs/` | GitHub Pages site: home page, privacy policy, Meta Ray-Ban Display session timer |
| `climber_profiles/` | Local SQLite database (git-ignored) |

## Deploying

See [DEPLOYMENT.md](DEPLOYMENT.md) (Streamlit Community Cloud + Google sign-in + Neon Postgres).
