"""Gym wall reports: the climber's opt-in, and the owner's monthly report page."""

import pandas as pd
import streamlit as st

from harnesssync.ui.language import tr

from harnesssync import gym_flyer, gym_report
from harnesssync.ui.common import flash, user_now


# ----------------- ARRIVING FROM A GYM FLYER (?gym=<slug>) -----------------
def arriving_gym():
    """The pilot gym a flyer link named, or None. Read from the address bar on
    every run, so it survives the password sign-in clearing Session State."""
    slug = st.query_params.get("gym")
    if not slug or len(slug) > 40:
        return None
    return gym_report.get_gym(slug)


def render_sign_in_banner():
    """Above the sign-in form, so a climber who scanned a flyer sees it's the right place."""
    gym = arriving_gym()
    if gym:
        st.info(tr("Welcome, {gym} climbers! Sign in or create an account to start logging.", gym=gym["name"]))


def _done_arriving():
    st.query_params.pop("gym", None)


def render_arrival(user_id):
    """Top of the Log screen after a flyer scan. Joining the gym's report is an
    explicit tap: scanning alone never opts anyone in. Returns the gym or None."""
    gym = arriving_gym()
    if gym is None:
        return None
    membership = gym_report.get_membership(user_id)
    if membership and membership["gym_slug"] == gym["slug"]:
        st.success(tr("Climbing at {gym}. Your gym climbs count in its monthly report.", gym=gym["name"]))
        return gym
    with st.container(border=True):
        st.markdown(f"**{tr('Climbing at {gym} today?', gym=gym['name'])}**")
        st.caption(tr("Your gym sees anonymous totals only, never your name, notes or single climbs. "
                      "Only gym climbs you log after joining count."))
        join_label = (tr("Switch my report to {gym}", gym=gym["name"]) if membership
                      else tr("Count my climbs for {gym}", gym=gym["name"]))
        col_yes, col_no = st.columns(2)
        if col_yes.button(join_label, type="primary", width="stretch", key="arrival_join"):
            gym_report.join_gym(user_id, gym["slug"], user_now().date())
            flash("success", tr("You're counted in {gym}'s monthly report.", gym=gym["name"]))
            st.rerun()
        if col_no.button(tr("Not now"), width="stretch", key="arrival_skip"):
            _done_arriving()
            st.rerun()
    return gym


def render_member(user_id):
    """Inside the account menu. Hidden until the owner has added a pilot gym."""
    gyms = gym_report.list_gyms()
    if not gyms:
        return
    names = {g["slug"]: g["name"] for g in gyms}
    membership = gym_report.get_membership(user_id)
    current = membership["gym_slug"] if membership and membership["gym_slug"] in names else ""
    options = [""] + list(names)

    st.markdown("---")
    with st.form("gym_form"):
        choice = st.selectbox(tr("Your gym"), options, index=options.index(current),
                              format_func=lambda slug: names.get(slug) or tr("No gym"))
        share = st.checkbox(tr("Count my gym climbs in my gym's monthly report"), value=bool(current))
        st.caption(tr("Your gym sees anonymous totals only, never your name, notes or single climbs. "
                      "Only gym climbs you log after joining count."))
        if st.form_submit_button(tr("Save gym"), width="stretch"):
            if choice and share:
                gym_report.join_gym(user_id, choice, user_now().date())
                flash("success", tr("You're counted in {gym}'s monthly report.", gym=names[choice]))
            else:
                gym_report.leave_gym(user_id)
                flash("success", tr("You're not in any gym's report."))
            st.rerun()


def _recent_months(today, count=12):
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append((year, month))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return months


def render_owner(actor):
    """Owner only (gym_report.add_gym and owner_report both check)."""
    st.subheader("Gym wall reports")
    st.caption("Anonymous monthly totals for each pilot gym. Nothing is sent from here: "
               "download the page or copy the text and send it to the gym yourself.")
    with st.form("add_gym_form", clear_on_submit=True):
        name = st.text_input("Add a pilot gym", max_chars=gym_report.GYM_NAME_MAX,
                             placeholder="e.g. The Rock Gym, Rexburg")
        if st.form_submit_button("Add gym"):
            try:
                gym_report.add_gym(actor, name)
            except ValueError as error:
                st.warning(str(error))
            else:
                flash("success", f"Added {name.strip()}. Its climbers can now join it from their account menu.")
                st.rerun()

    gyms = gym_report.list_gyms()
    if not gyms:
        st.info("Add a gym, then climbers can join it from their account menu.")
        return
    names = {g["slug"]: g["name"] for g in gyms}
    slug = st.selectbox("Gym", list(names), format_func=names.get, key="gym_report_gym")

    link = gym_flyer.flyer_link(slug)
    st.caption("Flyer link. It opens the app on Log with this gym's name and asks climbers "
               "to opt in. Scanning never opts anyone in by itself.")
    st.code(link, language=None)
    st.download_button("Download printable flyer", gym_flyer.render_flyer_html({"slug": slug, "name": names[slug]}),
                       file_name=f"{slug}-flyer.html", mime="text/html", key=f"gym_flyer_{slug}")
    months = _recent_months(user_now().date())
    year, month = st.selectbox("Month", months, index=1, key="gym_report_month",
                               format_func=lambda ym: gym_report.month_bounds(*ym)[0].strftime("%B %Y"))

    report = gym_report.owner_report(actor, slug, year, month)
    if report["withheld"]:
        st.info(f"Fewer than {report['min_climbers']} climbers logged gym climbs here that month, "
                "so the report holds back its totals.")
        st.caption(f"Climbers signed up for this gym's report: {report['members']}")
    else:
        cols = st.columns(4)
        cols[0].metric("Climbers logging", report["climbers"])
        cols[1].metric("Climbs logged", report["logged"])
        cols[2].metric("Sends", report["sends"])
        cols[3].metric("Send rate", f"{report['send_rate']}%")
        st.caption(f"Busiest day: {report['busiest_day']} · {report['members']} climbers signed up")
        st.bar_chart(pd.DataFrame(report["by_weekday"]).set_index("day"), height=200)
        for d in report["disciplines"]:
            st.write(f"**{d['discipline']}** · most logged: {d['most_logged'] or '-'} · "
                     f"most tries without a send: {d['most_tried'] or '-'}")
            st.dataframe(pd.DataFrame(d["grades"]), hide_index=True, width="stretch")

    file_name = f"{slug}-{year}-{month:02d}-wall-report.html"
    st.download_button("Download report page", gym_report.render_html(report),
                       file_name=file_name, mime="text/html")
    st.text_area("Email text to paste", gym_report.render_text(report), height=240, key=f"gym_text_{slug}_{year}_{month}")
