"""Offline phone web app setup and the native app waitlist."""

import streamlit as st

from harnesssync.ui.language import tr
from harnesssync.ui.language import current_language, option_label
import os
from urllib.parse import urlsplit, urlunsplit

from harnesssync import waitlist_manager
from harnesssync.ui.common import auth_configured, flash


def render(user_id):
    render_offline(user_id)
    st.header(tr("📱 HarnessSync for iPhone & Android"))
    st.write(
        tr("We're deciding whether to build a dedicated phone app. Join the waitlist to get it first - "
        "and tell us what would make it worth installing. Signing up is free and you can leave any time.")
    )
    entry = waitlist_manager.get_entry(user_id)
    if entry:
        message = tr("You're on the waitlist ({platform}).", platform=tr(entry['platform']))
        if auth_configured():
            message += " " + tr("We'll email {user} when it's ready.", user=user_id)
        st.success(message)

    with st.form("waitlist_form"):
        platform = st.radio(
            tr("Which phone would you use it on?"), waitlist_manager.PLATFORMS, horizontal=True,
            format_func=option_label(),
            index=(
                waitlist_manager.PLATFORMS.index(entry["platform"])
                if entry and entry["platform"] in waitlist_manager.PLATFORMS else 0
            ),
        )
        wants = st.multiselect(
            tr("What would make a phone app worth it over the website? (optional)"), waitlist_manager.REASONS,
            format_func=option_label(),
            default=[w.strip() for w in entry["wants"].split(",") if w.strip() in waitlist_manager.REASONS] if entry else [],
        )
        note = st.text_area(tr("Anything else you'd want in it? (optional)"),
                            value=entry["note"] if entry else "", max_chars=waitlist_manager.NOTE_MAX)
        if st.form_submit_button(tr("Update my answers") if entry else tr("📱 Join the waitlist"),
                                 type="primary", width="stretch"):
            waitlist_manager.join(user_id, platform, wants, note)
            flash("success", tr("Answers updated.") if entry else tr("You're on the waitlist - thanks!"))
            st.rerun()

    if entry and st.button(tr("Leave the waitlist")):
        waitlist_manager.leave(user_id)
        flash("info", tr("You've left the waitlist."))
        st.rerun()


def render_offline(user_id):
    st.header(tr("Offline climbing log"))
    st.write(tr("Save climbs and attempts on your phone, view downloaded projects and progress, "
             "and sync when you reconnect. Open the offline log online once before your trip."))
    if os.environ.get("HARNESSSYNC_OFFLINE_ENABLED") != "1":
        st.info("Offline logging needs the offline-enabled server entry point. "
                "The server administrator must start `streamlit run asgi_app.py` before devices can connect.")
        return
    from harnesssync.offline_manager import create_device, revoke_devices

    st.caption(tr("Use a private device. Its connection lasts 30 days. Revoking access stops syncing; "
               "downloaded data stays on the device until you remove it there."))
    if st.button(tr("Connect this device for offline use"), key="offline_connect"):
        token = create_device(user_id)
        url = urlsplit(st.context.url or "/")
        path = url.path.rstrip("/") + "/offline/"
        st.session_state["offline_connection"] = (user_id, urlunsplit((url.scheme, url.netloc, path, f"lang={current_language()}", f"device={token}")))
    connection = st.session_state.get("offline_connection")
    if connection and connection[0] == user_id:
        url = urlsplit(connection[1])
        link = urlunsplit((url.scheme, url.netloc, url.path, f"lang={current_language()}", url.fragment))
        st.link_button(tr("Open offline log on this device"), link)
        st.caption(tr("Keep this connection link private. Wait for ‘Offline page downloaded’, then "
                   "bookmark the offline page or add it to your home screen. "
                   "Sync runs when the offline page is open; reopen it after regaining signal."))
    if st.button(tr("Revoke all offline device connections"), key="offline_revoke"):
        revoke_devices(user_id)
        st.session_state.pop("offline_connection", None)
        st.success(tr("Device access revoked. Unsynced entries remain on devices; reconnect the same account to sync them."))
