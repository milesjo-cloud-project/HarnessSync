"""Read-only public checks for the owner's confirmed Render deployment.

No app imports, secrets, database access, scheduled jobs or message delivery.
This establishes public endpoint availability, not authenticated flow health.
"""

import json
from dataclasses import asdict, dataclass
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


SITE_URL = "https://harnesssync.onrender.com"
MAX_BODY = 512 * 1024


@dataclass(frozen=True)
class Sample:
    status: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class Check:
    path: str
    ok: bool
    status: int | None
    reason: str
    elapsed_ms: int


class NoRedirect(HTTPRedirectHandler):
    """A login or unexpected-host redirect must not be reported as healthy."""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def fetch_public(path):
    # Callers cannot replace the origin or provide arbitrary URLs through SMS.
    request = Request(SITE_URL + path, headers={"User-Agent": "HarnessSync-health-check/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        return Sample(response.status, response.headers.get_content_type(), response.read(MAX_BODY + 1))


def check_public_site(fetch=fetch_public):
    """Check fixed public endpoints, retaining no response bodies in results.

    A fetch callable can be injected for deterministic tests with fictional
    responses. Production always checks the owner's configured origin.
    """
    checks = []
    for path, types, marker in (
        ("/_stcore/health", {"text/plain"}, b"ok"),
        ("/", {"text/html"}, b"<html"),
        ("/offline/", {"text/html"}, b"HarnessSync"),
        ("/offline/app.js", {"text/javascript", "application/javascript"}, b"indexedDB.open"),
        ("/offline/sw.js", {"text/javascript", "application/javascript"}, b"self.addEventListener"),
    ):
        started = monotonic()
        status, reason = None, "ok"
        try:
            sample = fetch(path)
            status = sample.status
            if status != 200:
                reason = "http_status"
            elif sample.content_type.split(";", 1)[0].strip().lower() not in types:
                reason = "content_type"
            elif len(sample.body) > MAX_BODY:
                reason = "response_too_large"
            elif path == "/_stcore/health" and sample.body.strip() != marker:
                reason = "health_not_ready"
            elif marker not in sample.body:
                reason = "unexpected_content"
        except HTTPError as error:
            status, reason = error.code, "http_status"
        except (TimeoutError, URLError, OSError):
            reason = "network_unavailable"
        checks.append(Check(path, reason == "ok", status, reason, round((monotonic() - started) * 1000)))
    return checks


def main():
    checks = check_public_site()
    healthy = all(check.ok for check in checks)
    print(json.dumps({"site": SITE_URL, "public_endpoints_ok": healthy,
                      "authenticated_flows_checked": False,
                      "checks": [asdict(check) for check in checks]}))
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
