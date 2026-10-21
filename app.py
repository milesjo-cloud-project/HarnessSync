"""Compatibility entry point for the existing Streamlit Cloud deployment."""
from asgi_app import app  # Streamlit CLI discovers this ASGI application.
