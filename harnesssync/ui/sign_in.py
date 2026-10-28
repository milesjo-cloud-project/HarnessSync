"""Email/password sign-in and mailbox-verified password setup/recovery."""
import streamlit as st

from harnesssync.ui.language import tr
from harnesssync.ui.language import render_language_selector

from harnesssync import password_auth
from harnesssync.support_config import HELP_URL


def resolve_user():
    session = st.session_state.get("password_session")
    user_id = password_auth.session_user(session)
    if user_id:
        return user_id, ""
    if session:
        st.session_state.clear()
    render_language_selector()
    st.title("🧗 HarnessSync")
    st.subheader(tr("A simple log for every gym session"))
    st.write(tr("Sign in to your private climbing log."))
    st.caption(tr("Previously used Google? Set a password using the same email to keep your climbs."))
    with st.form("password_sign_in", clear_on_submit=True):
        email = st.text_input(tr("Email"), max_chars=254)
        password = st.text_input(tr("Password"), type="password", max_chars=128)
        if st.form_submit_button(tr("Sign in"), type="primary"):
            try:
                session = password_auth.sign_in(email, password)
                if session:
                    st.session_state.clear()
                    st.session_state["password_session"] = session
                    st.rerun()
                st.error(tr("Email or password is incorrect. After repeated attempts, wait 15 minutes."))
            except ValueError as error:
                st.error(tr(str(error)))
    with st.expander(tr("Create account or reset password")):
        st.write(tr("First verify your email. We'll send a code that expires in 10 minutes."))
        with st.form("request_password_code"):
            setup_email = st.text_input(tr("Account email"), max_chars=254)
            if st.form_submit_button(tr("Email verification code")):
                try:
                    password_auth.request_code(setup_email)
                    st.success(tr("Code sent. Check your inbox and spam folder."))
                except ValueError as error:
                    st.error(tr(str(error)))
        with st.form("set_password", clear_on_submit=True):
            verified_email = st.text_input(tr("Email to verify"), max_chars=254)
            code = st.text_input(tr("Verification code"), max_chars=32)
            new_password = st.text_input(tr("New password"), type="password", max_chars=128,
                                         help=tr("Use 12–128 characters."))
            confirmation = st.text_input(tr("Confirm password"), type="password", max_chars=128)
            if st.form_submit_button(tr("Set password")):
                if new_password != confirmation:
                    st.error(tr("Passwords don't match."))
                else:
                    try:
                        password_auth.set_password(verified_email, code, new_password)
                        st.success(tr("Password saved. Sign in above."))
                    except ValueError as error:
                        st.error(tr(str(error)))
    st.link_button(tr("Having trouble? Get help"), HELP_URL)
    st.stop()
