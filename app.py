"""Existing Streamlit Cloud entry point, including the offline phone app."""
import os
from pathlib import Path

import streamlit as st

from harnesssync.offline_routes import routes

os.environ["HARNESSSYNC_OFFLINE_ENABLED"] = "1"
app = st.App(str(Path(__file__).with_name("streamlit_app.py")), routes=routes)
