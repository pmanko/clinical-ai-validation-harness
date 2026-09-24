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


PROJECT_PATHS = ("chartsearchai", "catalyst", "med-agent-hub", "validation-harness")
MEDIA_HOST = "https://catalyst.openelis-global.org/media/"


def parsed_page(relative_path):
    html = (LANDING / relative_path).read_text(encoding="utf-8")
    page = LandingParser()
    page.feed(html)
    return html, page


def test_homepage_introduces_four_projects_without_embedded_walkthroughs():
    html, home = parsed_landing()
    assert home.h1_count == 1
    assert {"main-content", "projects", "about", "openmrs", "catalyst", "hub"} <= home.ids
    assert "Open tools for clinical questions and reporting." in html
    for project in PROJECT_PATHS:
        assert f"/{project}/" in home.links
    assert not home.videos
    assert "https://reports.openclinai.org/" in home.links
    assert "Experimental software" in html
    assert "https://openmrs.openclinai.org/" not in home.links


def test_project_pages_have_parents_and_real_next_steps():
    for project in PROJECT_PATHS:
        html, page = parsed_page(f"{project}/index.html")
        assert page.h1_count == 1
        assert "/#projects" in page.links
        assert f'https://openclinai.org/{project}/' in html
        assert any(link.startswith("https://") for link in page.links)
        assert not page.scripts
    _, catalyst = parsed_page("catalyst/index.html")
    assert "/catalyst/reporting-pathways/" in catalyst.links
    assert "/catalyst/questions/" in catalyst.links
    assert "/catalyst/hiv-gallery/" in catalyst.links


def test_reporting_paths_publish_four_reviewed_recordings_with_clear_limits():
    html, page = parsed_page("catalyst/reporting-pathways/index.html")
    assert {f"reporting-path-{number}" for number in range(1, 5)} <= page.ids
    assert "/catalyst/" in page.links
    assert "No Catalyst or AI step is required" in html
    assert "All four recordings were reviewed at normal speed" in html
    assert "the recordings are not presented as server-video evidence" in html
    assert "Owner acceptance remains open" in html
    assert len(page.videos) == len(page.sources) == 4
    assert html.count("What the recording shows") == 4
    for video in page.videos:
        assert "controls" in video and "playsinline" in video
        assert "autoplay" not in video
        assert video.get("preload") == "metadata"
        assert str(video.get("poster") or "").startswith(MEDIA_HOST)
        assert video.get("aria-label")
    for source in page.sources:
        assert source.startswith(MEDIA_HOST)


def test_existing_recordings_and_accessible_playback_are_preserved():
    pages = [parsed_page(f"{project}/index.html") for project in ("chartsearchai", "catalyst")]
    videos = [video for _, page in pages for video in page.videos]
    sources = [src for _, page in pages for src in page.sources]
    assert len(videos) == len(sources) == 4
    assert any("openelis-local-" in src for src in sources)
    assert any("openmrs-cd4-monitoring-local-" in src for src in sources)
    for html, page in pages:
        assert "Transcript (silent recording)" in html
        for video in page.videos:
            assert "controls" in video and "playsinline" in video
            assert "autoplay" not in video
            assert video.get("preload") == "metadata"
            assert video.get("aria-label")
            poster = str(video.get("poster") or "")
            assert poster.startswith(MEDIA_HOST) or local_asset(poster).is_file()
    for src in sources:
        assert src.startswith(MEDIA_HOST)
    _, catalyst = pages[1]
    assert {"https://youtu.be/PRs3jAzQk38", "https://youtu.be/7p83cGMhOzw"} <= set(catalyst.links)


def test_every_site_local_link_fragment_and_image_resolves():
    for path in LANDING.rglob("*.html"):
        _, page = parsed_page(path.relative_to(LANDING))
        for link in page.links:
            parsed = urlparse(link)
            if parsed.scheme or parsed.netloc:
                continue
            destination = LANDING / parsed.path.lstrip("/") if parsed.path.startswith("/") else path.parent / parsed.path
            if not parsed.path:
                destination = path
            elif destination.is_dir():
                destination = destination / "index.html"
            assert destination.is_file(), (path, link)
            if parsed.fragment and destination.suffix == ".html":
                _, target = parsed_page(destination.relative_to(LANDING))
                assert parsed.fragment in target.ids, (path, link)
        for image in page.images:
            assert image.get("alt") is not None
            src = str(image.get("src") or "")
            if not urlparse(src).scheme:
                image_path = LANDING / src.lstrip("/") if src.startswith("/") else path.parent / src
                assert image_path.is_file(), (path, src)


def test_legacy_homepage_fragments_retain_onward_links():
    _, home = parsed_landing()
    assert {"project", "openmrs", "catalyst", "hub", "evidence", "wahs", "paths", "reporting-pathways", "catalyst-openelis-video", "catalyst-openmrs-video"} <= home.ids
    assert "/catalyst/#catalyst-openelis-video" in home.links
    assert "/catalyst/#catalyst-openmrs-video" in home.links


def test_landing_is_static_responsive_and_keyboard_visible():
    html, page = parsed_landing()
    css = (LANDING / "styles.css").read_text() + (LANDING / "projects.css").read_text()
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
    assert '"${MEDIA_HOST}[A-Za-z0-9._/-]+" "${ROOT}/landing/"' in publish
    assert "--include='*.html'" in publish
    assert publish.index("REMOTE_MEDIA_ASSETS") < publish.index('rsync -avz --delete')
    assert publish.count('curl -fsS --retry 8 --retry-delay 2 --max-time 30 "${asset}" -o /dev/null') == 2
    assert "CONFIG_CHANGES=" in publish
    assert 'if [ -n "${CONFIG_CHANGES}" ]' in publish
    assert "proxy config unchanged; no service restart needed" in publish
    assert "docker compose -f compose/openmrs-2.8-refapp.yml up -d --no-deps --force-recreate proxy" in publish
    assert 'PUBLISH_MODE="${1:-full}"' in publish
    assert '"${PUBLISH_MODE}" != "--landing-only"' in publish
    assert 'if [ "${PUBLISH_MODE}" = "--landing-only" ]; then' in publish
    assert "landing-only mode; proxy configuration and services unchanged" in publish
    assert 'if [ "${PUBLISH_MODE}" = "full" ] && [ ! -f "${ROOT}/.env.chartsearch.cloud" ]; then' in publish
    assert 'SITE="${CADDY_SITE:-openclinai.org}"' in publish
    assert 'cmp - "${local_page}"' in publish
    assert '-name \'*.html\' -o -name \'*.css\'' in publish
    assert "backend" not in publish
    assert "gateway" not in publish
    assert "frontend" not in publish
    assert "https://${SITE}/media/openmrs-evidence-poster.png" in publish


def test_question_gallery_has_playable_clips_details_and_working_navigation():
    _, home = parsed_landing()
    _, catalyst = parsed_page("catalyst/index.html")
    gallery_path = LANDING / "catalyst/questions/index.html"
    gallery = LandingParser()
    markup = gallery_path.read_text(encoding="utf-8")
    gallery.feed(markup)
    assert "/catalyst/questions/" in catalyst.links
    assert gallery.h1_count == 1
    assert gallery.videos and len(gallery.videos) == len(gallery.sources)
    assert markup.count("<details") == len(gallery.videos)
    assert gallery.scripts == []
    for video in gallery.videos:
        assert "controls" in video and "playsinline" in video
        assert "autoplay" not in video
        assert video.get("preload") == "metadata"
        assert video.get("aria-label")
        assert str(video.get("poster")).startswith(MEDIA_HOST)
    for source in gallery.sources:
        assert source.startswith(MEDIA_HOST) and source.endswith(".mp4")
        assert source in gallery.links
    for link in gallery.links:
        if link.startswith("#"):
            assert link[1:] in gallery.ids
        elif link.startswith("/#"):
            assert link[2:] in home.ids
        elif link.startswith("/") and link.endswith("/"):
            assert (LANDING / link.lstrip("/") / "index.html").is_file()


def test_screenshot_walkthrough_is_easy_to_find_without_browsing_videos():
    home, parser = parsed_landing()
    assert "/catalyst/hiv-gallery/" in parser.links
    catalyst, _ = parsed_page("catalyst/index.html")
    opening = catalyst.split("<video", 1)[0]
    assert 'href="/catalyst/hiv-gallery/"' in opening
    assert "Screenshot walkthrough" in opening
