"""Check the shareable report's navigation, assets and optional host wiring."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "landing" / "wahs"


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.references = []
        self.sections = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "section":
            self.sections.append(attrs.get("id"))
        for key in ("href", "src"):
            if key in attrs:
                self.references.append(attrs[key])


def test_report_navigation_and_download_are_complete():
    page = ReportParser()
    page.feed((REPORT / "index.html").read_text())
    assert len(page.ids) == len(set(page.ids)), "Duplicate fragment targets"
    assert set(page.sections) == {
        "overview", "capabilities", "workflow", "research", "next", "evidence"
    }
    for reference in page.references:
        url = urlparse(reference)
        if url.scheme or url.netloc:
            continue
        if url.path:
            assert (REPORT / url.path).is_file(), reference
        elif url.fragment:
            assert url.fragment in page.ids, reference
    with ZipFile(REPORT / "WAHS-OpenClinAI-Design-Report.docx") as document:
        assert document.testzip() is None
        assert "word/document.xml" in document.namelist()


def test_report_is_discoverable_on_the_homepage():
    homepage = (ROOT / "landing" / "index.html").read_text()
    report = (REPORT / "index.html").read_text()
    assert 'href="https://wahs.openclinai.org/"' in homepage
    assert 'rel="canonical" href="https://wahs.openclinai.org/"' in report


def test_wahs_host_is_optional_and_uses_the_existing_static_volume():
    caddy = (ROOT / "compose" / "Caddyfile").read_text()
    compose = (ROOT / "compose" / "openmrs-2.8-refapp.yml").read_text()
    assert "{$CADDY_SITE_WAHS::8092}" in caddy
    assert "root * /srv/landing/wahs" in caddy
    assert "CADDY_SITE_WAHS: ${CADDY_SITE_WAHS:-:8092}" in compose
    assert "../landing:/srv/landing:ro" in compose
