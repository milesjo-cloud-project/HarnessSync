"""State stamps: the climber's passport, inside Progress."""

import streamlit as st

from harnesssync.profile_manager import get_state_history
from harnesssync.stamps import earned_stamps, passport_map_html, stamp_grid_html, state_banner_html
from harnesssync.states import STATES
from harnesssync.ui.language import tr


def render(user_id, today):
    st.subheader(tr("Climbing passport"), icon=":material/travel_explore:")
    st.caption(tr("Earn a state's stamp with your first climb there. Pick the state when you log a climb."))
    stamps = earned_stamps(get_state_history(user_id), today)
    earned = {s.code for s in stamps}

    st.metric(tr("States stamped"), tr("{count} of {total}", count=len(stamps), total=len(STATES)))
    st.html(passport_map_html(earned, tr("Map of the 50 states with your stamped states in colour")))
    if not stamps:
        st.info(tr("No stamps yet. Log a climb with its state to earn your first one."))
        return

    newest = stamps[-1]
    st.html(state_banner_html(newest.code, tr("Latest stamp: {state}", state=newest.name)))
    st.write("**" + tr("Your stamps") + "**")
    st.html(stamp_grid_html(stamps))
