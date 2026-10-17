# Automatic support email retries

The `Support email retries` GitHub Actions workflow retries the database outbox
on GitHub's servers. Your computer and Docker Desktop can be off, and the
Streamlit app can be asleep. Reports are already saved before email is attempted.

The workflow is disabled until the repository variable below is enabled. Adding
the file does not activate delivery or copy Streamlit secrets into GitHub.

## Activate after reviewing and merging

1. Review and manually merge the tested changes into the repository's default
   branch. The workflow accepts scheduled or manual runs on that branch only.
2. In GitHub, open **Settings → Secrets and variables → Actions → Secrets**.
   Add these repository secrets directly in GitHub, not in code or chat:

   | GitHub secret | Value |
   | --- | --- |
   | `SUPPORT_DATABASE_URL` | The same hosted Postgres database used by the app, including the provider's SSL settings |
   | `SUPPORT_EMAIL_ADDRESS` | The same Gmail sending address as Streamlit's `[email] address` |
   | `SUPPORT_EMAIL_APP_PASSWORD` | Its Gmail app password, matching `[email] app_password` |
   | `SUPPORT_EMAIL_TO_ADDRESS` | The owner's notification address, matching `[email] to_address`; optional, defaults to the sender |

   These credentials let the worker read queued private report emails and send
   them to the owner. Only trusted maintainers should change workflow code.
   Credentials are passed only to the delivery step, not checkout or installation.
3. Under **Variables**, add `SUPPORT_EMAIL_RETRIES_ENABLED` with value `true`.
4. Open **Actions → Support email retries → Run workflow**. Choose the default
   branch and verify that the delivery step completes. A skipped job usually
   means the enable variable is missing or the wrong branch was selected.
5. Enable GitHub Actions failure notifications in your GitHub notification
   settings. Check subsequent scheduled runs and the app's queued-email count.
   A controlled end-to-end test may deliver existing due notifications too;
   use a staging database and test recipient when testing intentional outages.

The scheduled worker uses `python -m harnesssync.support_notifications --scheduled`.
It requires explicit Postgres and SMTP environment settings, refuses SQLite or
missing settings, and never falls back to a local secrets file. It exits with a
failure on database or email delivery errors. Logs contain counts and generic
errors, not message bodies, account addresses, passwords, or database URLs.
Normal in-app delivery continues to use Streamlit secrets when no email environment
variables are set. If any email environment variable is set, that configuration
is used as a whole; missing values are not borrowed from Streamlit secrets.

## Timing and recovery

- Runs are requested every 15 minutes, at minutes 7, 22, 37 and 52 UTC each hour.
  Each run attempts up to 25 due messages. Larger queues drain over later runs.
- Each failed message retains its contents and backs off up to six hours.
  A successful send clears its queued body. Runs do not overlap within this
  workflow; database leases also coordinate with in-app delivery and owner retries.
- SMTP delivery is at-least-once. A process that stops after SMTP accepts an
  email can cause a duplicate on retry. Ticket/incident references identify it.
- GitHub schedules can be delayed or dropped under load. Public-repository
  schedules are disabled after 60 days without repository activity; re-enable
  the workflow in Actions if needed. This is a best-effort scheduler, not an
  urgent-alert service. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
- Runner usage follows your repository's GitHub Actions plan and limits.
  For guaranteed scheduling or larger volume, run the same command on a managed
  worker with the same environment secrets.

If a run fails, verify the database URL, network access, SMTP app password, and
recipient settings in GitHub. Rotate the GitHub copies whenever the app's
credentials change. Backoff remains in force during manual reruns; a successful
run with zero deliveries can mean no messages are due yet.

To pause retries, set `SUPPORT_EMAIL_RETRIES_ENABLED` to `false` (including manual
runs) or disable the workflow in Actions. Reports and unsent notifications remain
stored; the owner dashboard can still retry due messages.

GitHub stores credentials as [Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
The enable flag is a [configuration variable](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables), not a secret.
