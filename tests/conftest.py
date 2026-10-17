"""Keep every test independent of developer credentials and hosted databases."""
import pytest
import streamlit as st
from streamlit.runtime.secrets import Secrets


@pytest.fixture(autouse=True)
def isolated_secrets(monkeypatch):
    secrets = Secrets()
    secrets._secrets = {"auth": {}, "email": {}, "support": {}, "database": {}, "app": {}}
    monkeypatch.setattr(st, "secrets", secrets)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in ("HARNESSSYNC_EMAIL_ADDRESS", "HARNESSSYNC_EMAIL_APP_PASSWORD", "HARNESSSYNC_EMAIL_TO_ADDRESS"):
        monkeypatch.delenv(key, raising=False)
