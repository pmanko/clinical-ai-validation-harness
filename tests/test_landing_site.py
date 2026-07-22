from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "landing"


class LandingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.images: list[dict[str, str | None]] = []
        self.videos: list[dict[str, str | None]] = []
        self.sources: list[str] = []
        self.h1_count = 0
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        elif tag == "img":
            self.images.append(values)
        elif tag == "video":
            self.videos.append(values)
        elif tag == "source" and values.get("src"):
            self.sources.append(str(values["src"]))
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "script":
            self.scripts.append(values)


def parsed_landing() -> tuple[str, LandingParser]:
    html = (LANDING / "index.html").read_text(encoding="utf-8")
    parser = LandingParser()
    parser.feed(html)
    return html, parser


def local_asset(path: str) -> Path:
    return LANDING / path.removeprefix("/")


def test_landing_has_one_clear_h1_and_required_project_sections():
    html, page = parsed_landing()

    assert page.h1_count == 1
    assert {"main-content", "project", "hub", "openmrs", "catalyst", "evidence"} <= page.ids
    assert "Med Agent Hub" in html
    assert "OpenMRS integration" in html
    assert "Published validation runs." in html
    assert "Experimental software" in html


def test_landing_uses_plain_project_language_instead_of_advertising_copy():
    html, _ = parsed_landing()

    assert "A test environment for local clinical AI." in html
    assert "How a request is processed." in html
    assert "Recorded OpenMRS sessions." in html
    for phrase in (
        "Build clinical AI that can be inspected",
        "Evidence before confidence",
        "See the staged workflow in motion",
        "Claims are published with the evidence needed to challenge them",
        "Try the integration, then inspect the results",
        "Explore the OpenMRS demo",
        "Explore published reports",
    ):
        assert phrase not in html


def test_primary_destinations_are_first_party_and_prominent():
    html, page = parsed_landing()

    assert 1 <= page.links.count("https://openmrs.openclinai.org/") <= 2
    assert 1 <= page.links.count("https://reports.openclinai.org/") <= 3
    assert "OpenMRS demo" in html
    assert "Evaluation reports" in html

    # Catalyst is a first-class product section: laboratory + HIV program
    # demos, the published acceptance run, and the project documentation.
    assert "Catalyst" in html
    assert "OpenELIS" in html
    assert "HIV" in html
    assert (
        "https://reports.openclinai.org/catalyst-notebook-t094-2026-07-22/"
        in page.links
    )
    assert any(
        link.startswith("https://pmanko.github.io/clinical-ai-validation-harness/")
        for link in page.links
    )

    first_party_hosts = {
        urlparse(link).hostname
        for link in page.links
        if link.startswith("https://") and link.endswith("openclinai.org/")
    }
    assert {"openmrs.openclinai.org", "reports.openclinai.org"} <= first_party_hosts


def test_every_local_media_reference_exists_and_has_accessible_context():
    html, page = parsed_landing()

    assert len(page.videos) == 4
    assert len(page.sources) == 4
    assert len(page.images) >= 3
    assert "1:45 · 2×" in html

    for image in page.images:
        assert image.get("src")
        assert image.get("alt") is not None
        assert local_asset(str(image["src"])).is_file()

    for video in page.videos:
        assert video.get("controls") is None
        assert video.get("preload") == "metadata"
        assert video.get("aria-label")
        assert video.get("poster")
        assert local_asset(str(video["poster"])).is_file()

    for source in page.sources:
        asset = local_asset(source)
        assert asset.is_file()
        assert asset.stat().st_size < 15 * 1024 * 1024


def test_landing_is_static_responsive_and_keyboard_visible():
    html, page = parsed_landing()
    css = (LANDING / "styles.css").read_text(encoding="utf-8")

    assert page.scripts == []
    assert "@media (max-width: 720px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert ".skip-link" in css
    assert 'href="/favicon.svg"' in html
    assert (LANDING / "favicon.svg").is_file()


def test_caddy_serves_landing_at_root_without_redirecting_to_openmrs():
    caddy = (ROOT / "compose" / "Caddyfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose" / "openmrs-2.8-refapp.yml").read_text(encoding="utf-8")

    root_site = caddy.split("{$CADDY_SITE::80}", 1)[1].split("{$CADDY_SITE_OPENMRS::8090}", 1)[0]
    assert "root * /srv/landing" in root_site
    assert "file_server" in root_site
    assert "redir /openmrs/spa" not in root_site
    assert "../landing:/srv/landing:ro" in compose


def test_stable_publish_entrypoint_verifies_the_live_page():
    publish = (ROOT / "scripts" / "publish-landing.sh").read_text(encoding="utf-8")

    assert "uv run pytest -q tests/test_landing_site.py" in publish
    assert "cloud-sync.sh" not in publish
    assert '"${ROOT}/landing/"' in publish
    assert '"${ROOT}/compose/Caddyfile"' in publish
    assert '"${ROOT}/compose/openmrs-2.8-refapp.yml"' in publish
    assert "rsync -avz --delete" in publish
    assert "CONFIG_CHANGES=" in publish
    assert 'if [ -n "${CONFIG_CHANGES}" ]' in publish
    assert "proxy config unchanged; no service restart needed" in publish
    assert "docker compose -f compose/openmrs-2.8-refapp.yml up -d --no-deps --force-recreate proxy" in publish
    assert "backend" not in publish
    assert "gateway" not in publish
    assert "frontend" not in publish
    assert "https://${SITE}/media/openmrs-evidence-poster.png" in publish
