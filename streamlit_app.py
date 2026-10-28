import streamlit as st

from harnesssync.ui.language import tr
from harnesssync.ui.language import current_language, render_language_selector, english_notice

from harnesssync.profile_manager import get_profile, save_profile, set_language, display_name_taken, DISPLAY_NAME_MAX
from harnesssync.ui import dashboard, feedback, guide, leaderboard, log_climb, phone_app, projects, sidebar
from harnesssync.ui.common import auth_configured, dev_mode, email_is_verified, render_safely, show_flash, password_auth_enabled
from harnesssync.support_config import HELP_URL

st.set_page_config(page_title="HarnessSync | Climbing Intel", layout="wide")


# ----------------- IDENTITY -----------------
def resolve_user():
    """Returns (user_id, suggested_display_name) for whoever is using the app,
    or stops the script to show a sign-in screen."""
    if password_auth_enabled():
        from harnesssync.ui.sign_in import resolve_user as resolve_password_user
        return resolve_password_user()
    if auth_configured():
        if not st.user.is_logged_in:
            render_language_selector()
            st.title("🧗 HarnessSync")
            st.subheader(tr("A simple log for every gym session"))
            st.write(
                tr("Record a climb in a few taps, keep track of projects, and see your progress "
                "over time. Your climbing log is private to you.")
            )
            st.button(tr("Sign in with Google"), on_click=st.login, type="primary")
            st.link_button(tr("Having trouble? Get help"), HELP_URL)
            st.stop()
        email = st.user.get("email")
        if email and not email_is_verified(st.user.get("email_verified")):
            st.error(
                "Your sign-in provider hasn't verified this email address, so it can't be "
                "used to identify your account. Verify it with your provider and sign in again."
            )
            st.button(tr("Sign out"), on_click=st.logout)
            st.link_button(tr("Get sign-in help"), HELP_URL)
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
    st.link_button(tr("Get help"), HELP_URL)
    st.stop()


def render_onboarding(user_id, suggested_name):
    st.title(tr("🧗 Welcome to HarnessSync"))
    st.write(tr("Choose a display name. Your climbing log stays private; sharing on the leaderboard is optional."))
    with st.form("onboarding_form"):
        name = st.text_input(tr("Display name"), value=suggested_name[:DISPLAY_NAME_MAX], max_chars=DISPLAY_NAME_MAX)
        show = st.checkbox(tr("Show me on the public leaderboard"), value=False)
        if st.form_submit_button(tr("Continue"), type="primary"):
            if not name.strip():
                st.warning(tr("Display name can't be empty."))
            elif display_name_taken(name, exclude_user_id=user_id):
                st.warning(tr("That name is taken - try another."))
            else:
                save_profile(user_id, name, show)
                set_language(user_id, current_language())
                st.rerun()
    st.stop()


def render_page():
    user_id, suggested_name = resolve_user()
    profile = get_profile(user_id)
    if profile is None:
        if dev_mode() and not auth_configured() and not password_auth_enabled():
            save_profile(user_id, suggested_name)
            profile = get_profile(user_id)
        else:
            render_language_selector()
            render_onboarding(user_id, suggested_name)
    render_language_selector(user_id, profile)
    display_name = profile["display_name"]

    show_flash()

    # ----------------- SIDEBAR -----------------
    render_safely("Account", sidebar.render_account, user_id, profile)
    render_safely("Session timer", sidebar.render_session_timer, user_id, profile)
    st.sidebar.link_button(tr("Help & support"), HELP_URL)

    # ----------------- MAIN PANEL HEADER -----------------
    st.title("🧗 HarnessSync")
    st.subheader(tr("Log a climb. See your progress."))

    sections = [
        ("🧗 Log a climb", "Log a climb", log_climb.render, (user_id,)),
        ("📊 Progress", "Progress", dashboard.render, (user_id,)),
        ("🎯 Projects", "Projects", projects.render, (user_id,)),
        ("🏆 Leaderboard", "Leaderboard", leaderboard.render, ()),
        ("📱 Phone App", "Phone App", phone_app.render, (user_id,)),
        ("💬 Help & report a problem", "Help", feedback.render, (user_id, display_name)),
        ("📖 Guide & Reference", "Guide", guide.render, ()),
    ]
    labels = [tr(s[0]) for s in sections]
    previous_labels = st.session_state.get("_main_tab_labels", labels)
    selected = st.session_state.get("main_tabs")
    if previous_labels != labels and selected in previous_labels:
        st.session_state["main_tabs"] = labels[previous_labels.index(selected)]
    st.session_state["_main_tab_labels"] = labels
    tabs = st.tabs(labels, key="main_tabs", on_change="rerun")
    for tab, (_, area, render, args) in zip(tabs, sections):
        if tab.open:
            with tab:
                if area in {"Guide", "Help"}:
                    english_notice()
                render_safely(area, render, *args)


render_safely("App", render_page)
