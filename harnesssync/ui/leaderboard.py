"""🏆 Leaderboard tab."""

import streamlit as st

from harnesssync.ui.common import cached_leaderboard


def render():
    st.header("🏆 Leaderboard")
    st.caption("Ranked by hardest send (Onsight, Flash, Redpoint or Sent) within each discipline. "
               "You can hide yourself from the leaderboard in the 👤 account menu.")
    lb_discipline = st.radio("Leaderboard discipline", ["Boulder", "Rope"], horizontal=True,
                             key="leaderboard_discipline")
    lb_df = cached_leaderboard(lb_discipline)

    if lb_df.empty:
        st.info(f"No {lb_discipline} sends logged yet. Log one to get on the board.")
    else:
        lb_df = lb_df.reset_index(drop=True)
        medals = ["🥇", "🥈", "🥉"]
        lb_df.insert(0, "Rank", [medals[i] if i < 3 else str(i + 1) for i in range(len(lb_df))])
        st.dataframe(lb_df, width="stretch", hide_index=True)
