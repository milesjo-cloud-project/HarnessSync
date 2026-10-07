"""📱 Phone App tab: the native app waitlist."""

import streamlit as st

from harnesssync import waitlist_manager
from harnesssync.ui.common import auth_configured, flash


def render(user_id):
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
