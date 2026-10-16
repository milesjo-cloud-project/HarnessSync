"""Server-owned support settings. No caller-provided roles or addresses."""
import os

HELP_URL = "https://milesjo-cloud-project.github.io/HarnessSync/support.html"


def settings():
    try:
        import streamlit as st
        return dict(st.secrets.get("support", {}))
    except Exception:
        return {}


def is_owner(user_id):
    owners = settings().get("owner_emails", [])
    return bool(user_id and not user_id.startswith("dev:") and isinstance(owners, list)
                and user_id.casefold() in {str(email).strip().casefold() for email in owners})


def require_owner(user_id):
    if not is_owner(user_id):
        raise PermissionError("Owner access required.")


def ai_config():
    config = settings()
    return (config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY"),
            config.get("model") or os.environ.get("HARNESSSYNC_SUPPORT_MODEL"))
