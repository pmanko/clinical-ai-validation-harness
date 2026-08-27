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

    assert "A framework for orchestrating and evaluating open models in clinical workflows." in html
    assert "How each answer is produced." in html
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
    assert 1 <= page.links.count("https://reports.openclinai.org/") <= 5
    assert "OpenMRS demo" in html
    assert "Evaluation reports" in html

    # Catalyst is a first-class product section with the full product-flow
    # recording and project documentation. Superseded reports are not linked.
    assert "Catalyst" in html
    assert "OpenELIS" in html
    assert "HIV" in html
    assert "https://reports.openclinai.org/catalyst-notebook-t094-2026-07-22/" not in page.links
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


def test_catalyst_copy_states_the_current_product_and_open_reference_work():
    html, _ = parsed_landing()

    assert "selected Catalyst contract" in html
    assert "configured SQL source" in html
    assert "complete readable schema" in html
    # The Spark reference path is implemented and is what the recording now
    # shows; the comparison against it is what remains open.
    assert "OpenMRS HIV Spark reference path are implemented" in html
    assert "recording demonstrates the current runtime end to end" in html
    assert "model-team comparison has not been rerun" in html
    for obsolete in (
        "Acceptance of the corrected Spark reference deployment remains open",
        "are not yet implemented or accepted",
        "generated catalog",
        "independently authored gold queries",
        "384 assertions",
        "real models and PostgreSQL",
    ):
        assert obsolete not in html


MEDIA_HOST = "https://catalyst.openelis-global.org/media/"


def test_every_local_media_reference_exists_and_has_accessible_context():
    html, page = parsed_landing()

    # Three recordings: the two ChartSearchAI sessions and Catalyst's single
    # full-scenario cut (question -> checked SQL -> Datasets/Widgets ->
    # published Superset dashboard), which replaced the two short clips.
    assert len(page.videos) == 3
    assert len(page.sources) == 3
    assert len(page.images) >= 3
    assert "1:45 · silent recording at 2× speed" in html

    for image in page.images:
        assert image.get("src")
        assert image.get("alt") is not None
        assert local_asset(str(image["src"])).is_file()

    for video in page.videos:
        assert video.get("controls") is None
        assert video.get("preload") == "metadata"
        assert video.get("aria-label")
        poster = str(video.get("poster") or "")
        assert poster
        # Recordings and their posters are served by the demo host; the
        # hand-made page images stay local. Either is fine — a poster that is
        # neither is a typo, which is what this catches.
        if poster.startswith("http"):
            assert poster.startswith(MEDIA_HOST)
        else:
            assert local_asset(poster).is_file()

    # Every clip is hosted, so nothing here should resolve to a local file.
    # Compare by URL path (e.g. "/media/foo.mp4"), not by stripping MEDIA_HOST
    # textually -- that would drop the "media/" segment and check
    # landing/foo.mp4 instead of the actual local-alias location,
    # landing/media/foo.mp4.
    for source in page.sources:
        assert source.startswith(MEDIA_HOST), source
        assert not local_asset(urlparse(source).path).exists()


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
    # No -L: the recordings are not in this tree at all any more, so there are
    # no symlinks to dereference and landing/ carries only text and small
    # hand-made images.
    assert "rsync -avz --delete" in publish
    assert "rsync -avzL" not in publish
    # A publish that leaves the page pointing at a missing video is broken. The
    # asset list is derived from the page itself, not hand-maintained here, so
    # a recut is caught by editing the page alone -- and verified before
    # syncing anything, so a missing asset leaves the live page untouched.
    assert 'grep -oE "${MEDIA_HOST}[A-Za-z0-9._-]+" "${ROOT}/landing/index.html"' in publish
    assert publish.index("REMOTE_MEDIA_ASSETS") < publish.index('rsync -avz --delete')
    assert publish.count('curl -fsS --retry 8 --retry-delay 2 --max-time 30 "${asset}" -o /dev/null') == 2
    assert "CONFIG_CHANGES=" in publish
    assert 'if [ -n "${CONFIG_CHANGES}" ]' in publish
    assert "proxy config unchanged; no service restart needed" in publish
    assert "docker compose -f compose/openmrs-2.8-refapp.yml up -d --no-deps --force-recreate proxy" in publish
    assert "backend" not in publish
    assert "gateway" not in publish
    assert "frontend" not in publish
    assert "https://${SITE}/media/openmrs-evidence-poster.png" in publish
