"""Offline phone web app setup and the native app waitlist."""

import streamlit as st
import os
from urllib.parse import urlsplit, urlunsplit

from harnesssync import waitlist_manager
from harnesssync.ui.common import auth_configured, flash


def render(user_id):
    render_offline(user_id)
    st.header("📱 HarnessSync for iPhone & Android")
    st.write(
        "We're deciding whether to build a dedicated phone app. Join the waitlist to get it first - "
        "and tell us what would make it worth installing. Signing up is free and you can leave any time."
    )
    entry = waitlist_manager.get_entry(user_id)
    if entry:
        st.success(f"You're on the waitlist ({entry['platform']}). We'll email {user_id} when it's ready."
                   if auth_configured() else f"You're on the waitlist ({entry['platform']}).")

    with st.form("waitlist_form"):
        platform = st.radio(
            "Which phone would you use it on?", waitlist_manager.PLATFORMS, horizontal=True,
            index=(
                waitlist_manager.PLATFORMS.index(entry["platform"])
                if entry and entry["platform"] in waitlist_manager.PLATFORMS else 0
            ),
        )
        wants = st.multiselect(
            "What would make a phone app worth it over the website? (optional)", waitlist_manager.REASONS,
            default=[w.strip() for w in entry["wants"].split(",") if w.strip() in waitlist_manager.REASONS] if entry else [],
        )
        note = st.text_area("Anything else you'd want in it? (optional)",
                            value=entry["note"] if entry else "", max_chars=waitlist_manager.NOTE_MAX)
        if st.form_submit_button("Update my answers" if entry else "📱 Join the waitlist",
                                 type="primary", width="stretch"):
            waitlist_manager.join(user_id, platform, wants, note)
            flash("success", "Answers updated." if entry else "You're on the waitlist - thanks!")
            st.rerun()

    if entry and st.button("Leave the waitlist"):
        waitlist_manager.leave(user_id)
        flash("info", "You've left the waitlist.")
        st.rerun()


def render_offline(user_id):
    st.header("Offline climbing log")
    st.write("Save climbs and attempts on your phone, view downloaded projects and progress, "
             "and sync when you reconnect. Open the offline log online once before your trip.")
    if os.environ.get("HARNESSSYNC_OFFLINE_ENABLED") != "1":
        st.info("Offline logging needs the offline-enabled server entry point. "
                "The server administrator must start `streamlit run asgi_app.py` before devices can connect.")
        return
    from harnesssync.offline_manager import create_device, revoke_devices

    st.caption("Use a private device. Its connection lasts 30 days. Revoking access stops syncing; "
               "downloaded data stays on the device until you remove it there.")
    if st.button("Connect this device for offline use", key="offline_connect"):
        token = create_device(user_id)
        url = urlsplit(st.context.url or "/")
        path = url.path.rstrip("/") + "/offline/"
        st.session_state["offline_connection"] = (user_id, urlunsplit((url.scheme, url.netloc, path, "", f"device={token}")))
    connection = st.session_state.get("offline_connection")
    if connection and connection[0] == user_id:
        st.link_button("Open offline log on this device", connection[1])
        st.caption("Keep this connection link private. Wait for ‘Offline page downloaded’, then "
                   "bookmark the offline page or add it to your home screen. "
                   "Sync runs when the offline page is open; reopen it after regaining signal.")
    if st.button("Revoke all offline device connections", key="offline_revoke"):
        revoke_devices(user_id)
        st.session_state.pop("offline_connection", None)
        st.success("Device access revoked. Unsynced entries remain on devices; reconnect the same account to sync them.")
