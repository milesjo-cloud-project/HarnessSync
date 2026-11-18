"""New, signed-out visitors see the landing page before the sign-in screen."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from harnesssync import db_store
from harnesssync.support_config import SITE_URL

APP_PATH = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
GOOGLE_AUTH = {
    "redirect_uri": "http://localhost:8501/oauth2callback",
    "cookie_secret": "fictional-test-secret",
    "client_id": "fictional-client",
    "client_secret": "fictional-secret",
    "server_metadata_url": "https://accounts.example.test/.well-known/openid-configuration",
}


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    monkeypatch.delenv("HARNESSSYNC_DEV_MODE", raising=False)
    db_store.configure(f"sqlite:///{(tmp_path / 'landing.db').as_posix()}")
    yield
    db_store.get_engine().dispose()


def _app(auth=None, from_site=False, gym=None):
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.secrets["auth"] = auth or {}
    app.secrets["email"] = {}
    app.secrets["support"] = {}
    app.user = {"is_logged_in": False}
    if from_site:
        app.query_params["from"] = "site"
    if gym:
        app.query_params["gym"] = gym
    app.run()
    assert not app.exception
    return app


def _scripts(app):
    return [element.proto.body for element in app.get("html")]


def _redirected(app):
    return any("location.replace" in body and SITE_URL in body for body in _scripts(app))


@pytest.fixture
def password_mode(monkeypatch):
    monkeypatch.setenv("HARNESSSYNC_AUTH_MODE", "password")


def test_new_password_visitor_is_sent_to_landing_page(password_mode):
    app = _app()
    assert _redirected(app)
    assert not any(w.label == "Email" for w in app.text_input)
    assert any(e.proto.url == SITE_URL for e in app.get("link_button"))


def test_visitor_from_landing_page_sees_sign_in_and_is_remembered(password_mode):
    app = _app(from_site=True)
    assert not _redirected(app)
    assert any(w.label == "Email" for w in app.text_input)
    assert any("localStorage.setItem" in body for body in _scripts(app))


def test_no_script_fallback_button_continues_to_sign_in(password_mode):
    app = _app()
    next(b for b in app.button if b.label == "I already have an account").click().run()
    assert not app.exception
    assert any(w.label == "Email" for w in app.text_input)
    assert not _redirected(app)


def test_google_sign_in_screen_redirects_only_new_visitors(monkeypatch):
    monkeypatch.delenv("HARNESSSYNC_AUTH_MODE", raising=False)
    new = _app(auth=GOOGLE_AUTH)
    assert _redirected(new)
    assert not any(b.label == "Sign in with Google" for b in new.button)
    returning = _app(auth=GOOGLE_AUTH, from_site=True)
    assert not _redirected(returning)
    assert any(b.label == "Sign in with Google" for b in returning.button)


def test_returning_browser_redirect_keeps_visitor_in_the_app():
    # A browser that has seen the landing page is sent back to this app with
    # the marker, never to another origin or with other query parameters.
    from harnesssync.ui import landing_redirect
    script = landing_redirect._REDIRECT
    assert 'url.searchParams.set("from", "site")' in script
    assert script.index("localStorage.getItem") < script.index(SITE_URL)


def test_gym_flyer_link_goes_straight_to_sign_in_with_the_gym_name(password_mode):
    from unittest import mock
    from harnesssync import gym_report
    with mock.patch("harnesssync.support_config.settings", return_value={"owner_emails": ["owner@example.com"]}):
        slug = gym_report.add_gym("owner@example.com", "Basalt Bouldering")
    app = _app(gym=slug)
    assert not _redirected(app)
    assert any(w.label == "Email" for w in app.text_input)
    assert any("Basalt Bouldering climbers" in i.value for i in app.info)
    # A made-up gym doesn't skip the landing page.
    assert _redirected(_app(gym="no-such-gym"))
