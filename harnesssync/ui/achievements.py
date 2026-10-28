"""Achievements within the signed-in climber's Progress tab."""

import streamlit as st

from harnesssync.ui.language import tr
from harnesssync.ui.language import current_language

from harnesssync.achievements import achievements, achievement_card


def render(climbs, today):
    st.subheader(tr("Achievements"), icon=":material/emoji_events:")
    st.caption(
        tr("Celebrate your own progress. Milestones use your current climb history, "
        "including past climbs; editing or deleting a climb updates them.")
    )
    language = current_language()
    earned = achievements(climbs, today, language)
    if not earned:
        st.info(tr("Log your first completed send to unlock an achievement and a shareable card."))
        return

    st.write("**" + tr("{count} achievements earned", count=len(earned)) + "**")
    with st.expander(tr("View all earned achievements")):
        st.dataframe(
            [{tr("Achievement"): a.title, tr("Category"): a.category, tr("Climbed on"): a.earned_on,
              tr("What you achieved"): a.description} for a in earned],
            hide_index=True, width="stretch",
        )
    # Use stable IDs rather than array indexes: deleting a climb must not switch
    # a retained selection to an unrelated award.
    options = {a.key: a for a in earned}
    if st.session_state.get("achievement_card") not in options:
        st.session_state.pop("achievement_card", None)
    selected = st.selectbox(
        tr("Choose an achievement to share"), options,
        format_func=lambda key: f"{options[key].title} · {options[key].earned_on}",
        key="achievement_card",
    )
    award = options[selected]
    card = achievement_card(award, language)
    st.image(card, width=700, alt=f"{award.title}. {award.description} " + tr("Climbed on {date}", date=award.earned_on))
    st.caption(
        tr("Download the image to share in a message or social post. "
        "It includes only the milestone and climbing date, with no account or route details. "
        "Nothing is posted automatically.")
    )
    st.download_button(
        tr("Download achievement card"), card,
        file_name=f"harnesssync-{award.key}.png", mime="image/png",
        icon=":material/download:", on_click="ignore",
    )
