"""Goals and daily session recaps inside Progress."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from harnesssync.progress_manager import (
    GOAL_KINDS, GOAL_DISCIPLINES, create_goal, delete_goal, get_goals,
    goal_progress, session_recaps,
)
from harnesssync.ui.common import flash
from harnesssync.ui.language import tr, option_label, localized_frame


def render_goals(user_id, climbs, today):
    st.subheader(tr("Personal goals"))
    st.caption(tr("Set a send or climbing-day target. Only completed sends count; editing your log updates progress."))
    with st.expander(tr("Add a goal")):
        with st.form("personal_goal"):
            kind = st.selectbox(tr("Goal"), GOAL_KINDS, format_func=option_label(), key="goal_kind")
            discipline = st.selectbox(tr("Discipline"), GOAL_DISCIPLINES, format_func=option_label(), key="goal_discipline")
            target = st.number_input(tr("Target"), min_value=1, max_value=10000, value=10, step=1)
            start = st.date_input(tr("Start date"), value=today)
            end = st.date_input(tr("Deadline"), value=today + timedelta(days=30))
            if st.form_submit_button(tr("Save goal"), type="primary"):
                try:
                    create_goal(user_id, kind, discipline, target, start.isoformat(), end.isoformat())
                except ValueError as error:
                    st.warning(tr(str(error)))
                else:
                    flash("success", tr("Goal saved."))
                    st.rerun()
    saved = get_goals(user_id)
    if not saved:
        st.info(tr("Add your first personal goal."))
    for goal in saved:
        count, status = goal_progress(goal, climbs, today)
        with st.container(border=True):
            st.write(tr("{kind} · {discipline}", kind=tr(goal["kind"]), discipline=tr(goal["discipline"])))
            st.progress(min(count / goal["target"], 1.0), text=tr(
                "{count} / {target} · {status}", count=count, target=goal["target"], status=tr(status)))
            st.caption(tr("{start} → {end}", start=goal["start_date"], end=goal["end_date"]))
            if st.button(tr("Remove goal"), key=f"remove_goal_{goal['id']}"):
                delete_goal(user_id, goal["id"])
                st.rerun()


def render_recaps(user_id, climbs, sessions, today):
    st.subheader(tr("Session recaps"))
    st.caption(tr("Recaps group climbs by their logged date. Timer minutes are shown separately; climbs do not have exact timestamps."))
    recaps = session_recaps(climbs, sessions, today)
    if not recaps:
        st.info(tr("Log a climb or finish a timed session to see a recap."))
        return
    by_date = {r["date"]: r for r in recaps}
    selected = st.selectbox(tr("Climbing date"), list(by_date), key="recap_date")
    recap = by_date[selected]
    with st.container(horizontal=True):
        st.metric(tr("Climbs logged"), recap["logged"])
        st.metric(tr("Sends"), recap["sends"])
        st.metric(tr("Timed minutes"), recap["minutes"])
    st.write(tr("Best Boulder Send") + ": " + (recap["boulder"]["grade"] if recap["boulder"] else "—"))
    st.write(tr("Best Rope Send") + ": " + (recap["rope"]["grade"] if recap["rope"] else "—"))
    for goal in get_goals(user_id):
        if goal["start_date"] <= selected <= goal["end_date"]:
            count, status = goal_progress(goal, climbs, date.fromisoformat(selected))
            st.write(tr("{kind}: {count} / {target} through {date}", kind=tr(goal["kind"]), count=count,
                        target=goal["target"], date=selected) + " · " + tr(goal["discipline"]))
    if recap["climbs"]:
        frame = pd.DataFrame(recap["climbs"])[["discipline", "grade", "status", "route_name", "location"]]
        frame.columns = ["Discipline", "Grade", "Status", "Route/Problem", "Location"]
        st.dataframe(localized_frame(frame), hide_index=True, width="stretch")
    if sessions:
        with st.expander(tr("Session History")):
            frame = pd.DataFrame(sessions)[["date", "started_at", "ended_at", "duration_min"]]
            frame.columns = ["Date", "Started", "Ended", "Duration (min)"]
            st.dataframe(localized_frame(frame), hide_index=True, width="stretch")
            st.download_button(tr("⬇️ Download my sessions (CSV)"), frame.to_csv(index=False),
                               file_name="harnesssync_sessions.csv", mime="text/csv", on_click="ignore")
