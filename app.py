import streamlit as st

from harnesssync.profile_manager import get_profile, save_profile, display_name_taken, DISPLAY_NAME_MAX
from harnesssync.ui import dashboard, feedback, guide, leaderboard, phone_app, projects, sidebar
from harnesssync.ui.common import auth_configured, dev_mode, email_is_verified, report_crash, show_flash

st.set_page_config(page_title="HarnessSync | Climbing Intel", layout="wide")


# ----------------- IDENTITY -----------------
def resolve_user():
    """Returns (user_id, suggested_display_name) for whoever is using the app,
    or stops the script to show a sign-in screen."""
    if auth_configured():
        if not st.user.is_logged_in:
            st.title("🧗 HarnessSync")
            st.subheader("Climb Logging, Volume Pyramids & Project Tracking")
            st.write(
                "Log your sends, track projects across sessions, and see your grade pyramid "
                "and progression over time. Sign in to get started - your log is private to you."
            )
            st.button("Sign in with Google", on_click=st.login, type="primary")
            st.stop()
        email = st.user.get("email")
        if email and not email_is_verified(st.user.get("email_verified")):
            st.error(
                "Your sign-in provider hasn't verified this email address, so it can't be "
                "used to identify your account. Verify it with your provider and sign in again."
            )
            st.button("Sign out", on_click=st.logout)
            st.stop()
        # Falls back to `sub` only when there's no email at all. The provider
        # issues `sub` itself, so it needs no verification of its own.
        user_id = email or st.user.get("sub")
        return user_id, st.user.get("given_name") or st.user.get("name") or ""

    if dev_mode():
        st.sidebar.warning("Dev mode: no login - anyone can use any name. Never deploy like this.")
        name = st.sidebar.text_input("Climber Name", value="Guest", max_chars=DISPLAY_NAME_MAX).strip()
        if not name:
            st.info("Enter a climber name in the sidebar to get started.")
            st.stop()
        return f"dev:{name.lower()}", name

    st.error(
        "Sign-in isn't configured. Add an `[auth]` section to `.streamlit/secrets.toml` "
        "(see DEPLOYMENT.md), or set `HARNESSSYNC_DEV_MODE=1` to run locally without login."
    )
    st.stop()


def render_onboarding(user_id, suggested_name):
    st.title("🧗 Welcome to HarnessSync")
    st.write("Pick the name other climbers will see on the leaderboard. You can change it later.")
    with st.form("onboarding_form"):
        name = st.text_input("Display name", value=suggested_name[:DISPLAY_NAME_MAX], max_chars=DISPLAY_NAME_MAX)
        show = st.checkbox("Show me on the public leaderboard", value=True)
        if st.form_submit_button("Continue", type="primary"):
            if not name.strip():
                st.warning("Display name can't be empty.")
            elif display_name_taken(name, exclude_user_id=user_id):
                st.warning("That name is taken - try another.")
            else:
                save_profile(user_id, name, show)
                st.rerun()
    st.stop()


def render_page():
    user_id, suggested_name = resolve_user()
    profile = get_profile(user_id)
    if profile is None:
        if dev_mode() and not auth_configured():
            save_profile(user_id, suggested_name)
            profile = get_profile(user_id)
        else:
            render_onboarding(user_id, suggested_name)
    display_name = profile["display_name"]

    show_flash()

    # ----------------- SIDEBAR -----------------
    sidebar.render_account(user_id, profile)
    sidebar.render_log_form(user_id)
    sidebar.render_session_timer(user_id, profile)

    # ----------------- MAIN PANEL HEADER -----------------
    st.title("🧗 HarnessSync")
    st.subheader("Climb Logging, Volume Pyramids & Project Tracking")

    dashboard_tab, projects_tab, leaderboard_tab, mobile_tab, user_feedback_tab, guide_tab = st.tabs(
        ["📊 Dashboard", "🎯 Projects", "🏆 Leaderboard", "📱 Phone App", "💬 Feedback", "📖 Guide & Reference"]
    )

    with dashboard_tab:
        dashboard.render(user_id)
    with projects_tab:
        projects.render(user_id)
    with leaderboard_tab:
        leaderboard.render()
    with mobile_tab:
        phone_app.render(user_id)
    with user_feedback_tab:
        feedback.render(user_id, display_name)
    with guide_tab:
        guide.render()


try:
    render_page()
except Exception as error:
    # Mail the traceback, then let it through unchanged: Streamlit still shows
    # and logs the error exactly as before. st.stop() and st.rerun() raise from
    # BaseException precisely so they pass through a handler like this one.
    report_crash(error)
    raise
