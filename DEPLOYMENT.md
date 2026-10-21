# Deploying HarnessSync

HarnessSync runs on **Streamlit Community Cloud** (free), with **Google sign-in**
and a free hosted **Postgres** database. The database has to be hosted
elsewhere because Streamlit Cloud wipes the app's disk on every reboot and
redeploy, so a local SQLite file would lose everyone's climbs.

About 30 minutes, start to finish.

---

## 1. Create the database (Neon)

1. Sign up at <https://neon.tech> (free tier is plenty).
2. Create a project. Pick the region closest to your users (e.g. US East).
3. On the project dashboard, click **Connect** and copy the connection string.
   It looks like
   `postgresql://neondb_owner:abc123@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`

The app creates its tables automatically on first start.

> Using Supabase instead? Copy the **Session pooler** connection string, not
> the "Direct connection" one. The direct one is IPv6-only and Streamlit
> Cloud can't reach it.

## 2. Create the Google sign-in client

1. Go to <https://console.cloud.google.com>, create a project called "HarnessSync".
2. Open **Google Auth Platform** (search for "OAuth consent screen").
   - **Branding:** app name "HarnessSync", your support email.
   - **Audience:** *External*. Then click **Publish app**. While it's in
     "Testing", only accounts you list as test users can sign in. Apps that only
     ask for name + email don't need Google's verification review.
3. **Clients → Create client → Web application.** Under *Authorized redirect URIs* add both:
   - `http://localhost:8501/oauth2callback`
   - `https://<your-app>.streamlit.app/oauth2callback` (you pick `<your-app>` in step 4, so choose it now)
4. Copy the **Client ID** and **Client secret**.

## 3. Try it locally

1. `pip install -r requirements-dev.txt`
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in
   the `[auth]` section. Generate `cookie_secret` with
   `python -c "import secrets; print(secrets.token_hex(32))"`.
   Leave `[database]` commented out to use a local SQLite file.
3. `streamlit run asgi_app.py`, sign in, log a climb. The wrapper serves the offline
   phone app and sync API alongside the existing Streamlit UI.

Want to skip sign-in while hacking locally? Remove `[auth]` and set
`HARNESSSYNC_DEV_MODE=1` (or `[app] dev_mode = true`). Never deploy that way:
anyone could act as anyone.

## 4. Deploy to Streamlit Community Cloud

1. Merge your branch into `main` and push to GitHub.
2. Go to <https://share.streamlit.io> → **Create app** → *Deploy a public app from GitHub*.
   - Repository: `milesjo-cloud-project/HarnessSync`, branch `main`, main file `asgi_app.py`.
   - **App URL:** the `<your-app>` name you used in step 2.
3. Open **Advanced settings**:
   - Python version: 3.12
   - **Secrets:** paste your full secrets file, with two changes:
     - `redirect_uri = "https://<your-app>.streamlit.app/oauth2callback"`
     - uncomment `[database]` and paste the Neon URL from step 1.
4. **Deploy.** Then open the app, sign in, log a climb, reboot the app from the
   Cloud menu, and check the climb is still there. That confirms the database is wired up.

## Keep in mind

- **Offline release:** existing deployments using `app.py` must switch to `asgi_app.py`
  after the human has reviewed and merged the change. A reboot alone does not change
  the entry point. Verify that the hosting platform supports Streamlit 1.65's ASGI
  entry point and serves `/offline/sw.js` as JavaScript before enabling phone use.
  Docker uses the new entry point automatically on the next approved release.
- **Phone setup:** use HTTPS and the default root URL (no reverse-proxy subpath).
  Sign in, open **Phone App**, connect the device, and open the offline log. Wait for
  the download confirmation, then bookmark it or add it to the home screen. Test
  airplane-mode reopening, a climb and an attempt, then reconnect and verify both
  appear once in the main app. Repeat with a response interrupted during sync.
- **Offline boundaries:** only downloaded projects and climb history are available
  without signal. New sends and attempts can be queued; editing/deleting existing
  records, completing existing projects, session timers, sign-in and leaderboards
  remain in the main app. Automatic sync runs while the offline page is open or
  when it is reopened, rather than while the phone app is closed. Pending entries
  survive reloads but browser data deletion can erase them. Device access expires
  after 30 days; reconnect the same account to renew without losing its queue.
- **Sync traffic and recovery:** an empty queue does not poll the server. Downloaded
  history refreshes on opening/returning to the page, reconnecting, or pressing
  **Sync now**; failed pending writes retry while online. Export unsynced entries
  before clearing browser data. To recover on another browser, connect the same
  account, choose the JSON file under **Restore an unsynced backup**, and press
  **Restore backup**. Restore works offline after connection setup, preserves
  existing entries, and retains operation IDs so repeated imports are safe. Files
  from another account, invalid entries and conflicting IDs are rejected before
  any entries are added. Backups contain private climbing data, not device tokens.
  Each import accepts up to 10 MB / 10,000 entries.
- **Device privacy:** tokens are generated by the signed-in app, stored only as
  hashes on the server, and delivered in a URL fragment removed on page load.
  Private snapshots and pending entries live in browser IndexedDB. Public page
  assets are the only service-worker cache entries. Revoking device access blocks
  future API access; remove downloaded data on the device separately. Account
  deletion also removes device credentials and deduplication receipts.
- **Offline regression:** CI runs `tests/offline_browser.cjs` with Playwright against
  the real ASGI wrapper, a fictional dev account, blank secrets and a temporary
  SQLite database. It connects through the UI, reopens the app without networking,
  logs a send and an attempt, reloads, reconnects, and retries a committed write
  whose acknowledgement was lost. Bump the service worker's cache version whenever
  offline page assets change in a later release. Actual iPhone/Android testing and
  hosted sign-in remain part of the human's release verification.
  It also checks that idle pages make no sync requests, manual refresh still works,
  exported entries recover on a fresh browser, and invalid/conflicting imports
  leave the queue intact without duplicating sends or attempts.

- **Secrets file:** use the sections in `.streamlit/secrets.toml.example`. Drop leftover
  `[anthropic]` and `[admin]` sections from removed features. Owner access now uses `[support]`.
- **Sleeping apps:** Community Cloud puts apps to sleep after a stretch with no visitors.
  The next visitor sees a "wake up" button for a few seconds. Data is unaffected.
- **Backups:** Neon keeps point-in-time history on the free tier (see *Restore* in its dashboard).
- **Feedback email** is rate-limited per user (one message per 2 minutes, 5 per day).

## Support dashboard and reviewed fixes

Add this to the deployed secrets:

```toml
[support]
owner_emails = ["your-verified-google-email@example.com"]
```

Sign in with that verified
Google account, then open **Help & report a problem → Owner support dashboard**. Local
`dev:` identities never receive owner access. Reports and additive schema upgrades work
without email configuration; existing feedback becomes Received tickets.

No in-app model or AI API key is required. The owner can review and download a
redacted repair brief for a separate Codex Cloud task. See
[the repair workflow](docs/codex-repair-workflow.md) for environment setup, test
commands and the manual release gate. Retired `[support] openai_api_key` and
`model` settings may be removed; the app no longer reads them.

Email alerts are saved in the database before delivery. New reports and crashes attempt
their own notification immediately. Retry due notifications from the owner dashboard, or
run `python -m harnesssync.support_notifications` against the same production database
and email settings using an external scheduler. Streamlit does not run a reliable background
worker. A CLI run delivers at most 25 due messages; failures back off up to six hours.
The included [GitHub Actions scheduler](docs/support-email-scheduler.md) runs independently
of your computer and the app's sleep state once configured and enabled.
Without a scheduled worker or owner retry, failed messages stay queued. SMTP may deliver
duplicates if a process stops after sending; references identify the same report/incident.

Publish `docs/support.html` with the Pages site alongside the app update. Confirm GitHub
Issues is enabled for this repository and the public fallback form works; GitHub reports
require a GitHub account. Never post private account data there. Test sign-in failure,
report submission, owner reply, denied owner access, and email outage behavior before
announcing the feature. Existing deployments must use hosted Postgres to retain reports.

## Phone app demand report

- **Phone app waitlist:** to see how many people want an iPhone/Android app and why, run
  `DATABASE_URL="<your Neon URL>" python -m harnesssync.waitlist_report` from the repo root. The
  emails are in the `waitlist` table's `user_id` column if you want to contact people.
  To fold in the home page survey, download the Google Form's response sheet as CSV and add
  `--survey responses.csv`. Keep that sheet's sharing **Restricted**.
