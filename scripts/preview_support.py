"""Reporting-only demo with fictional data; bind the server to localhost."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harnesssync import db_store, feedback_manager, notifications, support_config
from harnesssync.ui import common, feedback

OWNER = "preview-owner@example.invalid"
USER = "preview-climber@example.invalid"
common._secret_section = lambda _name: {}
notifications._get_email_secrets = lambda: {}
support_config.settings = lambda: {"owner_emails": [OWNER]}
folder = ROOT / "climber_profiles" / "support-review"
folder.mkdir(parents=True, exist_ok=True)
db_store.configure("sqlite:///" + str(folder / "preview.db"))
if not feedback_manager.load_feedback(USER):
    feedback_manager.submit_feedback(USER, "Sample climber", "Bug", 3,
        "The save button didn't respond after my phone reconnected.",
        now=datetime.now(timezone.utc) - timedelta(hours=2), area="Log a climb",
        steps="Open Log a climb, reconnect Wi-Fi, then tap Save.",
        expected="The climb should appear in Progress.")

st.set_page_config(page_title="HarnessSync | Reporting preview", layout="wide")
st.title("HarnessSync · Reports and reviewed fixes")
st.info("Local preview with fictional data. Email delivery is disabled; no reports are uploaded.")
owner_view = st.sidebar.radio("Preview view", ["Climber", "Owner"]) == "Owner"
common.show_flash()
feedback.render(OWNER if owner_view else USER, "Owner" if owner_view else "Sample climber")
