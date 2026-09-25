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
3. `streamlit run app.py`, sign in, log a climb.

Want to skip sign-in while hacking locally? Remove `[auth]` and set
`HARNESSSYNC_DEV_MODE=1` (or `[app] dev_mode = true`). Never deploy that way:
anyone could act as anyone.

## 4. Deploy to Streamlit Community Cloud

1. Merge your branch into `main` and push to GitHub.
2. Go to <https://share.streamlit.io> → **Create app** → *Deploy a public app from GitHub*.
   - Repository: `milesjo-cloud-project/HarnessSync`, branch `main`, main file `app.py`.
   - **App URL:** the `<your-app>` name you used in step 2.
3. Open **Advanced settings**:
   - Python version: 3.12
   - **Secrets:** paste your full secrets file, with two changes:
     - `redirect_uri = "https://<your-app>.streamlit.app/oauth2callback"`
     - uncomment `[database]` and paste the Neon URL from step 1.
4. **Deploy.** Then open the app, sign in, log a climb, reboot the app from the
   Cloud menu, and check the climb is still there. That confirms the database is wired up.

## Keep in mind

- **Secrets file:** only paste the sections above. Drop the leftover `[anthropic]`
  and `[admin]` sections from the removed features.
- **Sleeping apps:** Community Cloud puts apps to sleep after a stretch with no visitors.
  The next visitor sees a "wake up" button for a few seconds. Data is unaffected.
- **Backups:** Neon keeps point-in-time history on the free tier (see *Restore* in its dashboard).
- **Feedback email** is rate-limited per user (one message per 2 minutes, 5 per day).
