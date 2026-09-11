"""Publication must follow the selected commit and reject missing or changed assets."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sync-catalyst-design.py'
spec = importlib.util.spec_from_file_location('sync_catalyst_design', SCRIPT)
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


@pytest.fixture
def source(tmp_path, monkeypatch):
    repo = tmp_path / 'source'
    repo.mkdir()
    git(repo, 'init', '-q')
    shared = repo / publish.SHARED
    integration = repo / publish.INTEGRATION
    shared.mkdir(parents=True)
    integration.mkdir(parents=True)
    for name in ['appearance.css', 'appearance.js', 'mock.css', 'mock.js', 'mock.html']:
        (shared / name).write_text('approved ' + name)
    for name in ['app.mjs', 'integration.css', 'model.mjs', 'review.js']:
        (integration / name).write_text('draft ' + name)
    (integration / 'app.html').write_text('<link href="../staff-workbench-ux/mock.css">')
    (integration / 'index.html').write_text('''<script src="../staff-workbench-ux/appearance.js"></script>
<iframe src="../staff-workbench-ux/mock.html"></iframe><iframe src="app.html?app=catalyst"></iframe>
<a id="spec-link" href="../staff-workbench-ux/spec.md">Spec</a>
<a id="source-revision" href="spec.md">Working tree</a>
<script src="review.js" data-approved-spec="../staff-workbench-ux/spec.md" data-integration-spec="spec.md"></script>''')
    git(repo, 'add', 'docs')
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
    revision = git(repo, 'rev-parse', 'HEAD')
    monkeypatch.setattr(publish, 'ROOT', tmp_path / 'output')
    monkeypatch.setattr(sys, 'argv', ['sync', '--source', str(repo), '--revision', revision])
    return repo, revision


def test_publishes_committed_source_with_matching_revision_links_and_hashes(source):
    repo, revision = source
    (repo / publish.SHARED / 'mock.css').write_text('uncommitted changes must not publish')
    assert publish.main() == 0
    dest = publish.ROOT / 'site/public/catalyst-design'
    assert (dest / 'mock.css').read_text() == 'approved mock.css'
    manifest = json.loads((dest / 'source.json').read_text())
    assert manifest['revision'] == revision
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((dest / name).read_bytes()).hexdigest() == digest
    html = (dest / 'index.html').read_text()
    assert 'src="integration/app.html?app=catalyst"' in html
    assert 'src="integration/review.js"' in html
    assert f'/commit/{revision}' in html and revision[:12] in html
    assert manifest['integrationSpecification'] in html
    assert manifest['approvedSpecification'] in html
    assert 'Working tree' not in html and '../staff-workbench-ux/' not in html
    assert (dest / 'integration/app.html').read_text() == '<link href="../mock.css">'


def test_check_detects_missing_and_modified_assets_without_repairing_them(source, monkeypatch, capsys):
    assert publish.main() == 0
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--check'])
    assert publish.main() == 0
    dest = publish.ROOT / 'site/public/catalyst-design'
    (dest / 'mock.css').write_text('drift')
    (dest / 'integration/app.mjs').unlink()
    assert publish.main() == 1
    output = capsys.readouterr().out
    assert 'mock.css' in output and 'integration/app.mjs' in output
    assert (dest / 'mock.css').read_text() == 'drift'
    assert not (dest / 'integration/app.mjs').exists()


def test_invalid_revision_does_not_create_publication(source, monkeypatch):
    repo, _ = source
    monkeypatch.setattr(sys, 'argv', ['sync', '--source', str(repo), '--revision', 'no-such-revision'])
    with pytest.raises(subprocess.CalledProcessError):
        publish.main()
    assert not publish.ROOT.exists()


def test_incomplete_commit_does_not_replace_existing_publication(source):
    repo, _ = source
    assert publish.main() == 0
    dest = publish.ROOT / 'site/public/catalyst-design'
    original = (dest / 'source.json').read_bytes()
    git(repo, 'rm', publish.INTEGRATION + '/app.mjs')
    git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'incomplete source')
    with pytest.raises(subprocess.CalledProcessError):
        publish.expected_files(repo, 'HEAD')
    assert (dest / 'source.json').read_bytes() == original
