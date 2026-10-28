"""Static help, private reports, and an owner-controlled repair handoff."""
import streamlit as st

from harnesssync.ui.language import option_label, tr, current_language
import sqlalchemy as sa

from harnesssync import feedback_manager as tickets
from harnesssync.support_help import HELP
from harnesssync.repair_brief import build_repair_brief
from harnesssync.db_store import get_db, notification_outbox
from harnesssync.incidents import owner_incidents
from harnesssync.support_config import HELP_URL, is_owner
from harnesssync.support_notifications import deliver_pending
from harnesssync.ui.common import flash, render_safely


def render(user_id, display_name):
    st.header(tr("Help & report a problem"))
    st.caption(tr("Get help, tell us what failed, and follow your reports here."))
    st.link_button(tr("Can't sign in or use the app?"), HELP_URL)
    if current_language() != "en":
        st.caption(tr("Some help articles and administrative tools are currently available in English."))
    with st.expander(tr("Quick help")):
        topic = st.selectbox(tr("What do you need help with?"), list(HELP))
        st.write(HELP[topic])
    st.subheader(tr("Send a report or idea"))
    # Rotate form keys only after success; validation/storage failures retain the draft.
    version = st.session_state.get("report_form_version", 0)
    with st.form(f"feedback_form_{version}"):
        category = st.selectbox(tr("Category"), tickets.CATEGORIES, format_func=option_label())
        area = st.selectbox(tr("Affected area"), tickets.AREAS, format_func=option_label())
        rating = st.slider(tr("Overall, how's the app working for you?"), 1, 5, 4)
        message = st.text_area(tr("What happened or what would you like?"), max_chars=tickets.MESSAGE_MAX)
        steps = st.text_area(tr("Steps to reproduce (optional)"), max_chars=tickets.MESSAGE_MAX,
                             placeholder=tr("What did you click? Include your browser and phone/computer type if relevant."))
        expected = st.text_area(tr("What did you expect? (optional)"), max_chars=tickets.MESSAGE_MAX)
        reference = st.text_input(tr("Incident reference (optional)"), max_chars=40, placeholder="INC-...")
        st.caption(tr("Reports are visible to you and the owner. The owner may use reviewed, redacted details with coding tools to investigate. Don't include passwords, codes, or sensitive personal details."))
        submitted = st.form_submit_button(tr("Send report"), type="primary", width="stretch")
    if submitted:
        try:
            entry = tickets.submit_feedback(user_id, display_name, category, rating, message,
                area=area, steps=steps, expected=expected, incident_ref=reference)
        except ValueError as error:
            st.warning(str(error))
        except Exception:
            st.error(tr("We couldn't save your report. Your draft is still here; please try again."))
        else:
            try:
                deliver_pending(limit=1, event_key=f"ticket:{entry['id']}")
            except Exception:
                pass  # report + notification are committed; delivery can retry later
            st.session_state["report_form_version"] = version + 1
            flash("success", tr("Report {reference} received. Follow it in My reports.", reference=tickets.ticket_ref(entry['id'])))
            st.rerun()

    st.subheader(tr("My reports"))
    st.caption(tr("Owner replies and status changes appear here. Refresh to check for updates."))
    if st.button(tr("Refresh reports")):
        st.rerun()
    entries = tickets.load_feedback(user_id)
    if not entries:
        st.info(tr("Your submitted reports will appear here."))
    for entry in entries:
        with st.expander(f"{tickets.ticket_ref(entry['id'])} · {tr(entry['status'])} · {tr(entry['area'])}"):
            st.caption(f"Submitted {entry['submitted_at']} · Updated {entry['updated_at'] or entry['submitted_at']}")
            st.text(entry["message"])
            if entry["owner_reply"]:
                st.write(tr("Owner reply"))
                st.text(entry["owner_reply"])
            else:
                st.caption(tr("No owner reply yet."))
    if is_owner(user_id):
        with st.expander("Owner support dashboard"):
            render_safely("Owner support", render_owner, user_id)


def render_owner(actor):
    st.subheader("Reports")
    status_filter = st.selectbox("Filter reports", ["All"] + tickets.STATUSES)
    entries = tickets.owner_tickets(actor, None if status_filter == "All" else status_filter)
    st.caption("Latest 200 matching reports. Other users cannot access this dashboard.")
    if entries:
        ticket_id = st.selectbox("Choose report", [e["id"] for e in entries], format_func=tickets.ticket_ref)
        ticket = next(e for e in entries if e["id"] == ticket_id)
        st.caption(f"{ticket['display_name']} · {ticket['user_id']} · {ticket['category']} · {ticket['area']}")
        st.text(ticket["message"])
        st.text(f"Steps: {ticket['steps']}\nExpected: {ticket['expected']}\nIncident: {ticket['incident_ref']}")
        similar = tickets.similar_tickets(actor, ticket)
        if similar:
            st.caption("Possible related reports: " + ", ".join(tickets.ticket_ref(e["id"]) for e in similar))
        with st.form(f"owner_reply_{ticket_id}"):
            status = st.selectbox("Report status", tickets.STATUSES, index=tickets.STATUSES.index(ticket["status"]))
            reply = st.text_area("Reply visible to the reporter", value=ticket["owner_reply"], max_chars=2000)
            deployed = st.checkbox("For Fixed: I verified the fix and deployed it")
            save = st.form_submit_button("Save status and reply")
        if save:
            try:
                if status == "Fixed" and not deployed:
                    raise ValueError("Verify and deploy the fix before marking it Fixed.")
                tickets.update_ticket(actor, ticket_id, status, reply)
            except ValueError as error:
                st.warning(str(error))
            else:
                flash("success", "Report updated. The reporter can see your reply in My reports.")
                st.rerun()
        with st.expander("Prepare a fix with Codex Cloud"):
            st.write("Review the repair brief, then paste it into a Codex Cloud task for this repository.")
            st.caption("Account identifiers are omitted and common secrets are redacted. Review the text for other private details before sharing. Nothing is sent automatically.")
            brief = st.text_area("Review repair brief before sharing",
                                 value=build_repair_brief(actor, ticket_id),
                                 key=f"repair_brief_{ticket_id}", height=300)
            st.download_button("Download Codex repair brief", brief,
                               file_name=f"{tickets.ticket_ref(ticket_id)}-repair.md", mime="text/markdown")
            st.link_button("Codex Cloud setup guide", "https://learn.chatgpt.com/docs/cloud")
            st.caption("Codex prepares code and tests. Review the PR and merge it yourself when ready to publish. Keep this report open until the deployed fix is verified.")
    else:
        st.info("No reports match this filter.")
    st.subheader("Crash incidents")
    for incident in owner_incidents(actor):
        with st.expander(f"{incident['id']} · {incident['area']} · {incident['occurrences']} occurrences"):
            st.caption(f"First: {incident['first_seen']} · Last: {incident['last_seen']}")
            st.code(incident["diagnostic"], language="text")
    with get_db() as conn:
        pending = conn.execute(sa.select(sa.func.count()).select_from(notification_outbox)
                               .where(notification_outbox.c.sent_at.is_(None))).scalar_one()
    st.caption(f"Queued email notifications: {pending}. Retries use backoff; owner replies are delivered in My reports.")
    if st.button("Retry due notifications"):
        delivered = deliver_pending()
        st.info(f"Delivered {delivered} notifications. Missing email configuration leaves messages queued.")
