"""Loopback-only browser-test fixture. Never reads developer secrets or production data."""
import sys
import os
from pathlib import Path

import streamlit as st
from streamlit.runtime.secrets import Secrets
import uvicorn

from harnesssync import db_store, profile_manager


if __name__ == "__main__":
    folder = Path(sys.argv[1]).resolve()
    safe = Secrets()
    safe._secrets = {}
    st.secrets = safe
    # The ASGI runtime also consults Streamlit's global secrets configuration.
    # Explicitly disable its filesystem sources before constructing it.
    from streamlit import config
    config.set_option("secrets.files", [])
    os.environ["HARNESSSYNC_DEV_MODE"] = "1"
    db_store.configure(f"sqlite:///{folder / 'browser.db'}")
    profile_manager.save_profile("dev:guest", "Browser climber")
    profile_manager.log_climb("dev:guest", "Boulder", "V2", "Sent", "2026-01-01")
    profile_manager.log_project("dev:guest", "Boulder", "V4", "2026-01-01",
                                route_name="Imaginary ridge", environment="Outdoor")
    from app import app
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
