# Release review — October 17, 2026

Reviewed application entry point, UI flows, managers, storage and migrations,
support and notification handling, tests, deployment configuration, and public
site/support documentation against AGENTS.md.

## Corrections

- Deselecting the logging discipline now prompts for a choice instead of raising
  a KeyError. An AppTest regression exercises this interaction.
- Project graduation claims the authenticated user's project and inserts its
  send in one transaction. Failed inserts restore the project; concurrent clicks
  produce one send. Tests cover rollback, retry, concurrency, and note retention.
- Ending a session clears the timer and records the session in one transaction.
  Failed writes preserve the running timer. End times before the start are
  rejected. Regression tests cover both cases.
- New profiles default to private leaderboard visibility in both the manager
  and table definition. Existing users' preferences are preserved.
- All pytest tests now use blank in-memory secrets and remove DATABASE_URL,
  preventing incidental access to local production configuration.
- Development-container setup installs requirements-dev.txt and retains
  Streamlit's default CORS and CSRF protection.
- Empty-project guidance points to the current logging flow. Local test scratch
  data is excluded from Git and Docker build context.

## Validation

- Full suite after adding the scheduler: **51 passed, 4 subtests passed**,
  including Streamlit AppTest, using temporary SQLite and mocked email delivery.
- Runtime used locally: Python 3.14.0. CI targets Python 3.12.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.
- Sandbox-local AppTest attempts stalled in Python's socket-pair creation;
  the successful full run used an approved execution outside that restriction.
- Docker build passed after Docker Desktop became available. The temporary
  container returned `ok` from Streamlit's internal health endpoint and was
  stopped after testing. No ports, production secrets, or host data were mounted.
  This checks startup; AppTest covers the application flows.

## Human release checks still required

This is source and automated-test validation, not confirmation of production
configuration. Before announcing the release:

- Require passing Python 3.12 tests and Docker build/smoke checks in CI.
- Verify Google sign-in, onboarding, logging, editing, project graduation,
  reload-persistent session timing, exports, leaderboard opt-in/out, and account
  deletion with fictional accounts in the intended deployment environment.
- Confirm hosted Postgres persistence across a reboot, production dev mode is
  disabled, owner access is restricted to configured verified accounts, and
  support submission/reply plus email outage/retry behavior work there.
- Verify the published Pages support/privacy links and public GitHub fallback.
  Configure and enable the included [notification scheduler](support-email-scheduler.md)
  for unattended retries. Its configuration checks, delivery errors, backoff,
  concurrency, and successful retry behavior pass locally; the GitHub schedule
  and production credentials have not been activated or tested.

No production secrets or hosted data were used. No merge, push, deployment,
reporter contact, or support-status change was performed. The human's manual
merge and deployed verification remain the release gate.
