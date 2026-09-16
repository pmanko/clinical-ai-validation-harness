import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'provision-reporting-source.py'
spec = importlib.util.spec_from_file_location('reporting_setup', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_existing_sources_and_reporting_metadata_survive_repeat_setup():
    unrelated = {'id': 'openmrs-hiv', 'connectionUri': 'hive2://spark/openmrs'}
    doc = {'dataSources': [unrelated], 'defaultDataSourceId': 'openmrs-hiv'}
    module.source_document(doc, 'reporting-db', 5432, 'clinlims', 'reader', 'demo')
    doc['dataSources'][1]['description'] = 'Keep this annotation'
    module.source_document(doc, 'reporting-db', 5432, 'clinlims', 'reader', 'demo')
    assert len(doc['dataSources']) == 2
    assert doc['dataSources'][0] == unrelated
    assert doc['defaultDataSourceId'] == 'openmrs-hiv'
    assert doc['dataSources'][1]['description'] == 'Keep this annotation'


def test_saved_source_cannot_be_silently_retargeted():
    doc = module.source_document({'dataSources': []}, 'original-db', 5432, 'clinlims', 'reader', 'demo')
    before = doc['dataSources'][0].copy()
    with pytest.raises(ValueError, match='retarget'):
        module.source_document(doc, 'other-db', 5432, 'clinlims', 'reader', 'demo')
    assert doc['dataSources'][0] == before


def test_password_punctuation_is_uri_encoded():
    doc = module.source_document({'dataSources': []}, 'db', 5432, 'clinlims', 'reader', 'demo@:/')
    assert 'demo%40%3A%2F@db' in doc['dataSources'][0]['connectionUri']


def test_command_preserves_credentials_and_original_backup_on_repeat(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys

    registry = tmp_path / 'sources.json'
    original = {'dataSources': [{'id': 'openelis-reporting',
        'connectionUri': 'postgresql://reader:retained%40demo@db:5432/clinlims'}]}
    original_text = json.dumps(original)
    registry.write_text(original_text)
    monkeypatch.delenv('REPORTING_DEMO_PASSWORD', raising=False)
    monkeypatch.setattr(sys, 'argv', ['provision', '--database-container', 'demo-db',
        '--host', 'db', '--registry', str(registry)])
    calls = []
    def provision(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, '', '')
    monkeypatch.setattr(module.subprocess, 'run', provision)
    module.main()
    module.main()
    assert all('password=retained@demo' in command for command in calls)
    assert registry.with_name('sources.json.before-reporting-setup').read_text() == original_text
    assert len(json.loads(registry.read_text())['dataSources']) == 1
    assert not registry.with_name('sources.json.tmp').exists()


def test_failed_provision_does_not_publish_registry_or_expose_password(tmp_path, monkeypatch, capsys):
    import subprocess
    import sys

    registry = tmp_path / 'sources.json'
    original = '{"dataSources": []}\n'
    registry.write_text(original)
    monkeypatch.setenv('REPORTING_DEMO_PASSWORD', 'demo-password-marker')
    monkeypatch.setattr(sys, 'argv', ['provision', '--database-container', 'demo-db',
        '--host', 'db', '--registry', str(registry)])
    monkeypatch.setattr(module.subprocess, 'run', lambda command, **kwargs:
        subprocess.CompletedProcess(command, 1, '', 'refused demo-password-marker'))
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 1
    assert registry.read_text() == original
    assert not registry.with_name('sources.json.before-reporting-setup').exists()
    message = capsys.readouterr().err
    assert 'demo-password-marker' not in message
    assert 'refused [redacted]' in message


def test_duplicate_source_identity_is_rejected_without_mutation():
    document = {'dataSources': [{'id': 'openelis-reporting'}, {'id': 'openelis-reporting'}]}
    with pytest.raises(ValueError, match='Duplicate'):
        module.source_document(document, 'db', 5432, 'clinlims', 'reader', 'demo')
    assert document['dataSources'] == [{'id': 'openelis-reporting'}, {'id': 'openelis-reporting'}]
