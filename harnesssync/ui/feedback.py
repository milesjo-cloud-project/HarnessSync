"""💬 Feedback tab."""

import streamlit as st

from harnesssync import notifications
from harnesssync.feedback_manager import submit_feedback, feedback_block_reason, MESSAGE_MAX


def render(user_id, display_name):
    st.header("💬 Feedback")
    st.caption("Bugs, ideas, or just how it's going - this goes straight to the developer.")

    with st.form("feedback_form", clear_on_submit=True):
        feedback_category = st.selectbox("Category", ["Bug", "Feature Idea", "General"])
        feedback_rating = st.slider("Overall, how's the app working for you?", 1, 5, 4)
        feedback_message = st.text_area("Details", max_chars=MESSAGE_MAX)
        feedback_submitted = st.form_submit_button("Send Feedback", width="stretch")

    if feedback_submitted:
        blocked = feedback_block_reason(user_id)
        if not feedback_message.strip():
            st.warning("Add a note before sending - even a sentence helps.")
        elif blocked:
            st.warning(blocked)
        else:
            submit_feedback(user_id, display_name, feedback_category, feedback_rating, feedback_message)
            emailed = notifications.send_email(
                subject=f"HarnessSync feedback ({feedback_category}) from {display_name}",
                body=(
                    f"From: {display_name} ({user_id})\n"
                    f"Rating: {feedback_rating}/5\nCategory: {feedback_category}\n\n{feedback_message}"
                ),
            )
            st.success(
                "Feedback sent - thank you!"
                if emailed else
                "Feedback saved (email delivery isn't configured, so it wasn't emailed)."
            )
