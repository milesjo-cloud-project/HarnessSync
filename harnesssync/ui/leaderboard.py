"""🏆 Leaderboard tab."""

import streamlit as st

from harnesssync.ui.language import option_label, tr, localized_frame

from harnesssync.ui.common import cached_leaderboard


def render():
    st.header(tr("🏆 Leaderboard"))
    st.caption(tr("Ranked by hardest send (Onsight, Flash, Redpoint or Sent) within each discipline. "
               "You can hide yourself from the leaderboard in the 👤 account menu."))
    lb_discipline = st.radio(tr("Leaderboard discipline"), ["Boulder", "Rope"], horizontal=True,
                             key="leaderboard_discipline", format_func=option_label())
    lb_df = cached_leaderboard(lb_discipline)

    if lb_df.empty:
        st.info(tr("No {discipline} sends logged yet. Log one to get on the board.", discipline=tr(lb_discipline)))
    else:
        lb_df = lb_df.reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        lb_df.insert(0, "Rank", [medals[i] if i < 3 else str(i + 1) for i in range(len(lb_df))])
        st.dataframe(localized_frame(lb_df), width="stretch", hide_index=True)
