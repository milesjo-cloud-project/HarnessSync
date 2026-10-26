"""Fictional endpoint responses; no live network or production credentials."""

from urllib.error import HTTPError, URLError

from harnesssync.site_health import MAX_BODY, SITE_URL, Sample, check_public_site


def healthy(path):
    if path == "/_stcore/health":
        return Sample(200, "text/plain; charset=utf-8", b"ok")
    if path.endswith(".js"):
        return Sample(200, "text/javascript", b"indexedDB.open(); self.addEventListener('fetch', handler)")
    return Sample(200, "text/html", b"<html><title>HarnessSync</title></html>")


def test_all_fixed_public_endpoints_can_pass():
    requested = []

    def fetch(path):
        requested.append(path)
        return healthy(path)

    checks = check_public_site(fetch)
    assert len(requested) == 5
    assert all(check.ok for check in checks)
    assert all(path.startswith("/") and "://" not in path for path in requested)
    assert SITE_URL == "https://harnesssync.onrender.com"


def test_startup_pages_and_html_instead_of_javascript_fail():
    def fetch(path):
        if path == "/_stcore/health":
            return Sample(200, "text/plain", b"starting")
        if path.endswith(".js"):
            return Sample(200, "text/html", b"<html>Starting service</html>")
        return healthy(path)

    checks = {c.path: c for c in check_public_site(fetch)}
    assert checks["/_stcore/health"].reason == "health_not_ready"
    assert checks["/offline/sw.js"].reason == "content_type"


def test_failure_does_not_prevent_other_probes_or_expose_error_details():
    def fetch(path):
        if path == "/":
            raise HTTPError(SITE_URL, 503, "private internal detail", {}, None)
        if path == "/offline/":
            raise URLError("private credential must not be included")
        return healthy(path)

    checks = {c.path: c for c in check_public_site(fetch)}
    assert checks["/"].status == 503
    assert checks["/offline/"].reason == "network_unavailable"
    assert checks["/offline/sw.js"].ok
    assert "private" not in repr(checks)


def test_oversized_and_wrong_content_responses_fail():
    def fetch(path):
        if path == "/":
            return Sample(200, "text/html", b"a" * (MAX_BODY + 1))
        if path == "/offline/sw.js":
            return Sample(200, "application/javascript", b"wrong script")
        return healthy(path)

    checks = {c.path: c for c in check_public_site(fetch)}
    assert checks["/"].reason == "response_too_large"
    assert checks["/offline/sw.js"].reason == "unexpected_content"
