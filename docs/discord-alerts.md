# HarnessSync Discord uptime alerts

The monitor checks https://harnesssync.onrender.com every five minutes, posts an
outage after three consecutive failures, and posts recovery after two consecutive
successes. Stable healthy or down states stay quiet. It runs independently of the
climbing app, without AI, Twilio, a bot account, incoming commands or code changes.

Source and tests are prepared locally. No server, channel, webhook, worker, or
live message has been created or activated by adding this code.

## 1. Create your Discord destination

Use Discord on desktop or in a browser:

1. Add a server with the **+** button in the server list and choose **Create My
   Own**. Name it `HarnessSync` (or another name you prefer).
2. Create a text channel named `harnesssync-alerts`. Set it to **Private Channel**
   and give access only to yourself and anyone you explicitly want to see alerts.
3. Open **Server Settings → Integrations → Webhooks → New Webhook** (the button
   can also be named **Create Webhook**). Name it `HarnessSync Monitor`, select
   `#harnesssync-alerts`, and save.
4. Choose **Copy Webhook URL**. Store it directly in the worker's private
   `DISCORD_ALERTS_WEBHOOK_URL` environment setting. It contains a secret; do not
   paste it into chat, a public issue, or a repository file. If exposed, replace
   the webhook in Discord.
5. On your phone, enable Discord notifications and set this channel's notification
   preference to **All Messages**. Alerts deliberately do not mention users or
   `@everyone`. Posting in the channel does not by itself guarantee a phone push.

Use a normal text channel, rather than a forum or media channel. The worker accepts
direct `https://discord.com/api/webhooks/...` URLs (including `/api/v10/webhooks/...`)
without extra query parameters. It adds `wait=true` itself to confirm message save.

Official webhook setup: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks

## 2. Configure independent hosting

Create a separate **Python background worker** on Render from the reviewed repo
revision, rather than adding a loop to Streamlit. The monitor uses Python's
standard library and needs no third-party packages, OpenAI key, bot token,
Twilio credentials, GitHub write token, or Neon connection.

- Root directory: repository root.
- Build command: `python -m compileall -q harnesssync/discord_alerts.py harnesssync/site_health.py`
- Start command: `python -m harnesssync.discord_alerts`
- Python: 3.12 or newer.
- Instances: **one**.
- Persistent disk: mount at `/var/data`.
- Environment settings:
  - `DISCORD_ALERTS_WEBHOOK_URL`: your private channel webhook URL.
  - `DISCORD_ALERTS_STATE_PATH`: `/var/data/harnesssync-discord/alerts.sqlite3`.
  - `DISCORD_ALERTS_ENABLED`: `true`, after configuration is reviewed.

The worker and persistent disk are separately billed hosting resources. Nothing
in this setup provisions or purchases them automatically. The webhook needs no
SMS service or per-SMS charge. The process must stay running while your computer
is off. Render's ordinary filesystem is ephemeral; keep the monitor state on its
persistent disk so restarts retain counters and previously posted incident IDs.

Render background workers: https://render.com/docs/background-workers
Persistent disks: https://render.com/docs/disks

## 3. Verify before relying on it

With environment settings configured privately in the worker environment:

```sh
python -m harnesssync.discord_alerts --test-message
python -m harnesssync.discord_alerts --once
python -m harnesssync.discord_alerts --status
```

The first command intentionally posts one test message. Confirm it appears in
your private channel and that your phone notifies you. The one-shot check records
one sample and sends only a due confirmed incident/recovery notification. Then
leave the normal start command running.

An initial healthy site sends no incident alert. Do not break the live app to
test an outage. The pytest suite exercises thresholds, failed delivery, retries,
restart persistence, stale-alert suppression and Discord payloads with fictional
HTTP responses and temporary SQLite files.

## Behavior and recovery

- Each outage has a stable incident reference. Recovery uses the same reference.
  Retried messages cannot create extra outbox records for the same transition.
- Discord must confirm a saved message before it is marked `posted`. This confirms
  channel posting, not a phone notification or a human reading it.
- HTTP 429 respects Discord's retry timing. Temporary failures back off; invalid
  credentials or a deleted webhook block the current alert. Five failed attempts
  also block it. Health checks continue and safe reason codes appear in worker
  logs and `--status`; the secret webhook URL is never printed.
- After fixing provider settings, use `--retry-blocked --once` to retry the current
  blocked notification. Old pending/blocked outage alerts are superseded on
  recovery, so a stale DOWN message is not posted after recovery.
- A provider response lost after a successful post can cause a duplicate retry.
  The incident reference identifies the same event; exactly-once external message
  delivery is not promised.
- Checks cover the public health endpoint, homepage and offline page/scripts.
  They do not verify sign-in, saving climbs, sync correctness or Neon.
- The worker cannot notify about its own complete failure. Use Render's worker
  failure notifications or a separate dead-man check for that coverage. A shared
  Render outage can affect both the app and its monitor.
- Disabling/stopping the worker pauses monitoring and posting. No action here
  merges code, deploys HarnessSync or changes support-report status.

The paused AI prototype is excluded from the proposed release. Automated coding
and two-way Discord commands would be a separate future feature.
