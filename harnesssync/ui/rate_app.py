"""More > How's HarnessSync?: a quick rating for climbers, and the owner's summary."""

import pandas as pd
import streamlit as st

from harnesssync import app_ratings, gym_report
from harnesssync.ui.common import flash
from harnesssync.ui.language import tr


def _stars(rating):
    return "★" * rating + "☆" * (5 - rating)


def _current_gym_name(user_id):
    membership = gym_report.get_membership(user_id)
    gym = gym_report.get_gym(membership["gym_slug"]) if membership else None
    return gym["name"] if gym else ""


def render(user_id):
    st.header(tr("How's HarnessSync?"))
    st.caption(tr("Takes ten seconds. Your answer helps decide what to fix and build next."))
    previous = app_ratings.last_rating(user_id)
    if previous:
        st.success(tr("Thanks! You rated HarnessSync {stars} on {date}. You can rate it again any time.",
                      stars=_stars(previous["rating"]), date=previous["submitted_at"][:10]))

    # Rotate the form key only after a save, so a refused answer keeps the draft.
    version = st.session_state.get("rate_app_version", 0)
    with st.form(f"rate_app_form_{version}"):
        rating = st.radio(tr("Your rating"), app_ratings.RATINGS, index=None, horizontal=True,
                          format_func=_stars, key=f"rate_app_rating_{version}")
        comment = st.text_area(tr("Anything we should change or keep? (optional)"),
                               max_chars=app_ratings.COMMENT_MAX, key=f"rate_app_comment_{version}")
        gym = st.text_input(tr("Your gym (optional)"), value=_current_gym_name(user_id),
                            max_chars=app_ratings.GYM_MAX, key=f"rate_app_gym_{version}")
        st.caption(tr("Only the HarnessSync owner sees answers, without your name or email."))
        submitted = st.form_submit_button(tr("Send rating"), type="primary", width="stretch")
    if submitted:
        try:
            app_ratings.submit_rating(user_id, rating, comment, gym)
        except ValueError as error:
            st.warning(tr(str(error)))
        else:
            st.session_state["rate_app_version"] = version + 1
            flash("success", tr("Thanks for rating HarnessSync!"))
            st.rerun()


def render_owner(actor):
    """Owner only (owner_summary and owner_csv both check)."""
    summary = app_ratings.owner_summary(actor)
    st.subheader("How's HarnessSync? answers")
    if not summary["responses"]:
        st.info("No answers yet. Climbers find the survey under More > How's HarnessSync?.")
        return
    cols = st.columns(3)
    cols[0].metric("Responses", summary["responses"])
    cols[1].metric("Climbers", summary["climbers"])
    cols[2].metric("Average rating", f"{summary['average']} / 5")
    st.dataframe(pd.DataFrame({"Rating": [_stars(r) for r in app_ratings.RATINGS],
                               "Answers": [summary["by_rating"][r] for r in app_ratings.RATINGS]}),
                 hide_index=True, width="stretch")
    st.markdown("**Latest comments**")
    if not summary["latest_comments"]:
        st.caption("No comments yet, only ratings.")
    for item in summary["latest_comments"]:
        where = f" · {item['gym']}" if item["gym"] else ""
        st.caption(f"{item['date']} · {_stars(item['rating'])}{where}")
        st.text(item["comment"])
    st.download_button("Download all answers (CSV)", app_ratings.owner_csv(actor),
                       file_name="harnesssync-ratings.csv", mime="text/csv", key="rate_app_csv")
