# Email/password accounts

Password mode replaces the Google button with private email/password accounts.
It is opt-in so deploying this code does not unexpectedly change existing sign-in.

## Render configuration and release

After reviewing and deploying the tested code through the normal manual release
gate, add this environment variable to the existing Render web service:

```text
HARNESSSYNC_AUTH_MODE=password
```

Keep `DATABASE_URL` pointing at the existing Neon database. The new
`password_accounts` table is created additively; existing climbing data stays in
place. Do not enable `HARNESSSYNC_DEV_MODE` on the public service.

In Render's `secrets.toml` secret file, configure outgoing account email:

```toml
[email]
address = "your-sending-mailbox@gmail.com"
app_password = "your Gmail app password"
```

These are the same SMTP settings used by support notifications. Account codes
are delivered to the requested mailbox, independently of support's `to_address`.
The service also accepts the existing `HARNESSSYNC_EMAIL_ADDRESS` and
`HARNESSSYNC_EMAIL_APP_PASSWORD` environment variables. Do not mix partial
environment credentials with secret-file credentials. Credentials remain private.

Keep `STREAMLIT_SECRETS_FILES=/etc/secrets/secrets.toml` when using Render's
secret file. Old Google `[auth]` settings are ignored by the app in password mode;
they may be removed after rollout verification. Google's redirect settings are
not used by password accounts.

## Visitor flow

1. Open **Create account or reset password** and request a verification code.
2. Enter that email, the emailed code, and a new password of 12–128 characters.
3. Sign in with the email/password; new climbers choose their display name.
4. Previous Google users must verify the **same email** to keep their existing
   log. Their original database identity is preserved, including letter case.
5. Forgotten passwords use the same verification flow. Requesting a code alone
   leaves the existing password and sessions unchanged. Completing a reset
   invalidates earlier password sessions.

Codes expire after 10 minutes, can be tried five times, and can be requested at
most once per minute per email. Five failed logins lock that email for 15 minutes.
Passwords are stored as individually salted PBKDF2-SHA256 hashes (600,000
iterations); codes are stored as hashes and are single-use. Passwords and codes
are never logged. Code delivery requires working SMTP; it does not fall back to
trusting an email typed into a form.

Password login lasts up to 12 hours in the current Streamlit session. Reloading
or losing the browser connection can require signing in again. This first version
does not provide a persistent “remember me” cookie. Existing offline-device
connections retain their separate expiry/revocation rules.

## Verify before announcing

On the hosted service, verify email delivery, new-account setup, sign-in, logout,
and password recovery using a test mailbox. Verify that an existing account's
data is retained and a second account sees only its own data. Verify owner
support access only after verifying the configured owner's mailbox. No production
data or account email is needed for automated tests.

All tests use mocked email delivery and fictional accounts. Hosted SMTP delivery
and the real Neon migration still require release verification.
