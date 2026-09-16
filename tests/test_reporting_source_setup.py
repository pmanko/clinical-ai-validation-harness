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
