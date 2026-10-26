"""No real webhook, network, account data, or production database is used."""

import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from harnesssync.discord_alerts import AlertStore, Settings, SendFailure, run_once, send_discord, validate_webhook_url
from harnesssync.site_health import Check

WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/fictional_token_for_local_tests_only"
UP = [Check("/", True, 200, "ok", 1)]
DOWN = [Check("/", False, 503, "http_status", 1)]


@pytest.fixture
def settings(tmp_path):
    return Settings(WEBHOOK, tmp_path / "discord.sqlite3")


@pytest.fixture
def store(settings):
    db = AlertStore(settings.state_path)
    yield db
    db.close()


def test_initial_success_and_transient_failures_stay_quiet(settings, store):
    def unexpected(*_args):
        pytest.fail("No notification should be posted")
    for i, checks in enumerate([UP, DOWN, DOWN, UP, UP]):
        result = run_once(settings, store, checker=lambda: checks, sender=unexpected, now=i * 300)
        assert result["event"] is None
        assert result["notification"] == "quiet"


def test_one_outage_and_recovery_notification_with_same_incident(settings, store):
    messages = []
    def post(_settings, body):
        messages.append(body)
        return "123456789012345678"
    for i, checks in enumerate([DOWN] * 7 + [UP] * 5):
        run_once(settings, store, checker=lambda: checks, sender=post, now=i * 300)
    assert len(messages) == 2
    assert "OUTAGE" in messages[0]
    assert "RECOVERED" in messages[1]
    incident = messages[0].split("[")[1].split("]")[0]
    assert f"[{incident}]" in messages[1]
    assert "Sign-in and saving are not verified" in messages[1]


def test_queue_and_counters_survive_restart(settings):
    first = AlertStore(settings.state_path)
    first.record(DOWN, 0)
    first.record(DOWN, 300)
    first.close()
    reopened = AlertStore(settings.state_path)
    try:
        assert reopened.record(DOWN, 600) == "outage"
        assert reopened.status()["notifications"][0]["status"] == "pending"
        assert reopened.record(DOWN, 900) is None
    finally:
        reopened.close()


def test_retry_after_and_recovery_suppress_stale_down_alert(settings, store):
    for now in (0, 300, 600):
        store.record(DOWN, now)
    def rate_limited(*_args):
        raise SendFailure("provider_http_429", retry_after=1000)
    assert store.deliver(settings, 600, rate_limited) == "retry_pending"
    assert store.deliver(settings, 900, rate_limited) == "quiet"
    store.record(UP, 900)
    store.record(UP, 1200)
    messages = []
    assert store.deliver(settings, 1200, lambda _cfg, body: messages.append(body) or "12345") == "posted"
    assert len(messages) == 1 and "RECOVERED" in messages[0]
    states = [row["status"] for row in store.status()["notifications"]]
    assert "superseded" in states


def test_permanent_failure_blocks_until_explicit_retry(settings, store):
    for now in (0, 300, 600):
        store.record(DOWN, now)
    def unauthorized(*_args):
        raise SendFailure("provider_http_401", retryable=False)
    assert store.deliver(settings, 600, unauthorized) == "blocked"
    assert store.deliver(settings, 1000, unauthorized) == "quiet"
    store.retry_blocked()
    assert store.deliver(settings, 1001, lambda *_args: "12345") == "posted"


class Reply(io.BytesIO):
    status = 200


def test_payload_confirms_save_without_mentions_or_secret_logging(settings):
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == WEBHOOK + "?wait=true"
            payload = json.loads(request.data)
            assert payload["allowed_mentions"] == {"parse": []}
            assert payload["content"] == "Fictional outage"
            assert timeout == 15
            return Reply(b'{"id":"123456789012345678"}')
    assert send_discord(settings, "Fictional outage", Opener()) == "123456789012345678"
    assert "fictional_token" not in repr(settings)


@pytest.mark.parametrize("url", [
    "http://discord.com/api/webhooks/12345/fictional_token_for_tests",
    "https://evil.example/api/webhooks/12345/fictional_token_for_tests",
    "https://discord.com.evil.example/api/webhooks/12345/fictional_token_for_tests",
    "https://discord.com@evil.example/api/webhooks/12345/fictional_token_for_tests",
    WEBHOOK + "?wait=false", WEBHOOK + "#private", "https://discord.com/api/users/@me",
])
def test_webhook_destination_is_restricted(url):
    with pytest.raises(ValueError):
        validate_webhook_url(url)


def test_http_errors_do_not_expose_secret_urls_or_response_content(settings):
    class Opener:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 429, "private body", {}, io.BytesIO(b'{"retry_after":12.5,"message":"private"}'))
    with pytest.raises(SendFailure) as caught:
        send_discord(settings, "Fictional outage", Opener())
    assert str(caught.value) == "provider_http_429"
    assert caught.value.retry_after == 12.5
    assert "fictional_token" not in str(caught.value)


def test_invalid_confirmation_never_marks_success(settings):
    class Opener:
        def open(self, request, timeout):
            return Reply(b'{"message":"not a saved message"}')
    with pytest.raises(SendFailure, match="invalid_provider_response"):
        send_discord(settings, "Fictional outage", Opener())


def test_environment_requires_an_absolute_persistent_state_path(monkeypatch):
    monkeypatch.setenv("DISCORD_ALERTS_WEBHOOK_URL", WEBHOOK)
    monkeypatch.setenv("DISCORD_ALERTS_STATE_PATH", "relative.sqlite3")
    with pytest.raises(ValueError, match="absolute path"):
        Settings.from_env()
