"""A printable flyer for one pilot gym, with a QR code that opens the app
straight on the Log screen with that gym's name on it.

The QR only carries the gym's slug (``/?gym=<slug>``). Joining the gym's
monthly report is still the climber's own choice inside the app: scanning the
flyer never opts anyone in.
"""

import html
import io
from urllib.parse import urlencode

from harnesssync.site_health import SITE_URL


def flyer_link(slug, base=SITE_URL):
    return f"{base.rstrip('/')}/?{urlencode({'gym': slug})}"


def qr_svg(url):
    """Inline SVG of a QR code for url. segno is pure Python with no deps."""
    import segno
    buffer = io.BytesIO()
    segno.make(url, error="m").save(
        buffer, kind="svg", scale=8, border=2, dark="#17212b", light="#ffffff",
        xmldecl=False, svgns=True, title="QR code", desc=url,
    )
    return buffer.getvalue().decode("utf-8")


def render_flyer_html(gym, base=SITE_URL):
    """One letter-size page. Print it from the browser."""
    name = html.escape(gym["name"])
    link = flyer_link(gym["slug"], base)
    shown = html.escape(link.split("://", 1)[-1])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HarnessSync at {name}</title>
<style>
  :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #17212b; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #edf2f5; }}
  main {{ width: min(100%, 720px); min-height: 900px; padding: 64px 58px; display: flex; flex-direction: column; align-items: center; text-align: center; background: #fff; }}
  .brand {{ align-self: flex-start; font-weight: 750; font-size: 1.1rem; letter-spacing: .02em; }}
  .gym {{ margin: 56px 0 0; font-size: 1.2rem; font-weight: 700; color: #19765a; text-transform: uppercase; letter-spacing: .08em; }}
  h1 {{ margin: 10px 0 12px; max-width: 560px; font-size: clamp(2.6rem, 8vw, 4.4rem); line-height: .98; letter-spacing: -.05em; }}
  .lead {{ max-width: 520px; font-size: 1.24rem; line-height: 1.5; color: #465664; }}
  ul {{ margin: 24px 0 28px; padding: 0; list-style: none; display: grid; gap: 12px; font-size: 1.1rem; text-align: left; }}
  li::before {{ content: "✓"; color: #19765a; font-weight: 800; margin-right: 12px; }}
  .qr svg {{ width: 240px; height: 240px; }}
  .scan {{ margin: 6px 0 0; font-size: 1.25rem; font-weight: 750; }}
  .privacy {{ margin-top: auto; padding-top: 32px; max-width: 520px; color: #647482; font-size: .92rem; line-height: 1.5; }}
  .url {{ color: #19765a; font-weight: 650; word-break: break-all; }}
  @media print {{
    @page {{ size: letter portrait; margin: 0; }}
    body {{ min-height: 0; background: #fff; }}
    main {{ width: 8.5in; height: 11in; min-height: 0; padding: .6in; }}
  }}
</style>
</head>
<body>
<main>
  <div class="brand">🧗 HarnessSync</div>
  <p class="gym">{name}</p>
  <h1>Make every session count.</h1>
  <p class="lead">A free climbing log for {name} climbers. Log a send or a try in a few taps and watch your grades climb.</p>
  <ul>
    <li>Log boulders and routes in seconds</li>
    <li>Count every try, and how high you got</li>
    <li>See your progress month by month</li>
  </ul>
  <div class="qr">{qr_svg(link)}</div>
  <p class="scan">Scan to log your first climb</p>
  <p class="privacy">Works in your phone browser. Your log is private to you. You choose whether your climbs
  count in {name}'s anonymous monthly totals, and you can stop any time.<br><span class="url">{shown}</span></p>
</main>
</body>
</html>
"""
