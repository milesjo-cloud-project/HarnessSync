"""Language selection before sign-in and an account-scoped saved preference."""

import streamlit as st
from functools import partial

from harnesssync.i18n import LANGUAGES, translate
from harnesssync.profile_manager import set_language


def current_language():
    language = st.session_state.get("ui_language", "en")
    return language if language in LANGUAGES else "en"


def tr(message, **values):
    return translate(message, current_language(), **values)


def option_label():
    # Bind the language when rendering. Streamlit/testing can format retained
    # option values later, outside the script's session context.
    return partial(translate, language=current_language())


def localized_frame(frame):
    """Translate presentation columns and enums, never free text or exports."""
    frame = frame.copy()
    for column in ("Discipline", "Status", "Send style", "Env", "Environment", "Angle", "Holds"):
        if column in frame:
            frame[column] = frame[column].map(lambda value: tr(value) if isinstance(value, str) else value)
    return frame.rename(columns=tr)


def render_language_selector(user_id=None, profile=None):
    language = (profile or {}).get("language", "en")
    if user_id and (st.session_state.get("_language_account") != user_id
                    or st.session_state.get("_language_saved") != language):
        # A different account must never inherit the previous account's choice.
        st.session_state["ui_language"] = language if language in LANGUAGES else "en"
        st.session_state["_language_account"] = user_id
        st.session_state["_language_saved"] = language

    def changed():
        if user_id:
            set_language(user_id, current_language())

    st.sidebar.selectbox(
        "Language / Idioma / Langue / 言語 / 언어 / 语言", list(LANGUAGES),
        format_func=LANGUAGES.get, key="ui_language", on_change=changed,
    )


def english_notice():
    if current_language() != "en":
        st.info(tr("Some reference articles, owner tools and diagnostic messages are currently available in English only. Your own notes and replies are shown as written."))
