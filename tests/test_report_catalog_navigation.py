"""The catalog preserves historical entries without presenting unavailable reports as links."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('report_catalog', ROOT / 'scripts/build-reports-index.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def test_catalog_retains_historical_catalyst_entries():
    rows = json.loads((ROOT / 'reports-index.json').read_text())['runs']
    by_slug = {row['slug']: row for row in rows}
    assert len(by_slug) == len(rows)
    for slug in ('catalyst-phase1-comparison', 'catalyst-t094-release', 'catalyst-notebook-t094-2026-07-22'):
        assert by_slug[slug]['family'] == 'catalyst'
        assert 'Historical' in by_slug[slug]['context']


def test_unavailable_report_is_retained_without_a_broken_action(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, 'REPORTS', tmp_path)
    monkeypatch.setattr(catalog, 'VALIDATE', tmp_path)
    html = catalog._card({'slug':'old-run', 'title':'Historical run', 'family':'catalyst',
                          'context':'Historical development report.', 'availability':'unavailable'})
    assert 'Historical run' in html and 'Historical development report.' in html
    assert 'Report unavailable' in html
    assert 'old-run/index.html' not in html
    assert 'Catalyst SQL' in html


def test_catalog_generation_keeps_entries_and_adds_parent_links(tmp_path, monkeypatch):
    reports = tmp_path / 'reports'
    reports.mkdir()
    manifest = tmp_path / 'catalog.json'
    manifest.write_text(json.dumps({'runs': [
        {'slug':'old-run', 'title':'Old recorded result', 'family':'catalyst', 'context':'Historical development report.', 'availability':'unavailable'},
        {'slug':'available-run', 'title':'Available result'},
    ]}))
    # main changes these module paths for its supported isolated output mode.
    for name in ('ROOT','REPORTS','VALIDATE','MANIFEST','BACKENDS','_RAW'):
        monkeypatch.setattr(catalog, name, getattr(catalog, name))
    catalog.main(['--root', str(tmp_path), '--reports-root', str(reports), '--manifest', str(manifest)])
    html = (reports / 'index.html').read_text()
    assert 'https://openclinai.org/' in html
    assert 'https://openclinai.org/validation-harness/' in html
    assert 'Old recorded result' in html and 'Available result' in html
    assert 'rel="canonical" href="https://reports.openclinai.org/"' in html
    xml = (reports / 'sitemap.xml').read_text()
    assert 'available-run/index.html' in xml
    assert 'old-run' not in xml
    assert 'available-run/index.html' in html
    assert 'old-run/index.html' not in html


def test_landing_sitemap_uses_canonical_urls_and_excludes_other_origins(tmp_path):
    import runpy
    build = runpy.run_path(str(ROOT / 'scripts/build-landing-sitemap.py'))['build']
    (tmp_path / 'index.html').write_text('<link rel="canonical" href="https://openclinai.org/">')
    (tmp_path / 'alias.html').write_text('<link rel="canonical" href="https://wahs.openclinai.org/">')
    xml = build(tmp_path).decode()
    assert 'https://openclinai.org/' in xml
    assert 'wahs.openclinai.org' not in xml


def test_landing_sitemap_fails_for_unclassified_page(tmp_path):
    import runpy
    import pytest
    build = runpy.run_path(str(ROOT / 'scripts/build-landing-sitemap.py'))['build']
    (tmp_path / 'index.html').write_text('<h1>Missing canonical</h1>')
    with pytest.raises(ValueError, match='expected one canonical'):
        build(tmp_path)
