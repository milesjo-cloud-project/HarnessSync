"""Offline presentation artifacts contain public source and need no account."""
import importlib.util
import io
from pathlib import Path
import zipfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_demo_downloads", ROOT / "scripts/build_demo_downloads.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.resources = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts += 1
        if tag in ("script", "img", "link", "iframe", "source"):
            for key in ("src", "href"):
                if key in attrs:
                    self.resources.append(attrs[key])


def test_single_file_demo_has_no_external_runtime_dependencies():
    outputs = builder.build_outputs()
    html = outputs[builder.OFFLINE_FILE].decode("utf-8")
    parser = Resources()
    parser.feed(html)
    assert parser.scripts == 1
    assert all(url.startswith("data:") for url in parser.resources)
    assert "navigator.serviceWorker" not in html
    assert html.index('<div class="demo-shell"') < html.index("<script>")
    assert "This single-file demo works offline" in html
    assert 'href="index.html"' not in html  # single-file copy needs no siblings


def test_share_archive_is_reproducible_and_contains_only_public_allowlist():
    outputs = builder.build_outputs()
    assert outputs == builder.build_outputs()
    with zipfile.ZipFile(io.BytesIO(outputs[builder.ARCHIVE_FILE])) as archive:
        assert set(archive.namelist()) == {*builder.PUBLIC_FILES, builder.OFFLINE_FILE, "demo-sw.js", "START-HERE.txt"}
        assert archive.read(builder.OFFLINE_FILE) == outputs[builder.OFFLINE_FILE]
        assert archive.read("demo-sw.js") == outputs["demo-sw.js"]


def test_cache_version_changes_with_public_files_and_artifacts_are_current():
    original = {"demo.html": b"fictional demo"}
    assert builder.service_worker(original) != builder.service_worker({"demo.html": b"updated demo"})
    for name, expected in builder.build_outputs().items():
        current = (builder.DOCS / name).read_bytes()
        if not name.endswith(".zip"):
            current = current.replace(b"\r\n", b"\n")
        assert current == expected, f"Run python scripts/build_demo_downloads.py: {name} is stale"
