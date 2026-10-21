"""Same-origin PWA assets and bearer-authenticated sync; no cookie authentication."""

import json
from pathlib import Path

import anyio
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from harnesssync.offline_manager import synchronize, DeviceUnauthorized

ASSETS = Path(__file__).parent / "offline_web"
SECURITY = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
}


async def asset(request):
    filename = request.path_params.get("filename") or "index.html"
    if filename not in {"index.html", "app.js", "style.css", "sw.js", "manifest.webmanifest", "icon.svg"}:
        return JSONResponse({"error": "Not found"}, status_code=404, headers=SECURITY)
    types = {".js": "text/javascript", ".html": "text/html", ".css": "text/css",
             ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml"}
    return FileResponse(ASSETS / filename, media_type=types[Path(filename).suffix], headers=SECURITY)


async def sync(request):
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse({"error": "Reconnect this device from the Phone App tab."}, status_code=401, headers=SECURITY)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 250_000:
            return JSONResponse({"error": "Sync request too large."}, status_code=413, headers=SECURITY)
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {"operations"}:
            raise ValueError("Invalid sync request.")
        result = await anyio.to_thread.run_sync(synchronize, authorization[7:], payload["operations"])
    except DeviceUnauthorized as error:
        return JSONResponse({"error": str(error)}, status_code=401, headers=SECURITY)
    except (ValueError, TypeError) as error:
        return JSONResponse({"error": str(error)}, status_code=400, headers=SECURITY)
    except Exception:
        return JSONResponse({"error": "Sync unavailable. Your queued entries remain on this device."}, status_code=503, headers=SECURITY)
    return JSONResponse(result, headers=SECURITY)


routes = [Route("/offline/", asset), Route("/offline/api/sync", sync, methods=["POST"]),
          Route("/offline/{filename}", asset)]
