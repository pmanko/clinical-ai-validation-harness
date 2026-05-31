import pytest

from harness.validate.repository import JsonlRepository, MongoRepository


def test_results_roundtrip(tmp_path):
    repo = JsonlRepository(authored_root=tmp_path / "data", run_dir=tmp_path / "run")
    repo.save("results", {"run_id": "r", "backend_id": "b1", "turn": 1, "metrics": {"citation_count": 2}})
    repo.save("results", {"run_id": "r", "backend_id": "b2", "turn": 1, "metrics": {"citation_count": 0}})

    assert len(repo.find("results")) == 2
    b2 = repo.find("results", {"backend_id": "b2"})
    assert len(b2) == 1 and b2[0]["metrics"]["citation_count"] == 0


def test_feedback_roundtrip(tmp_path):
    repo = JsonlRepository(authored_root=tmp_path / "data", run_dir=tmp_path / "run")
    repo.save("feedback", {"run_id": "r", "decision": "pass", "reviewer": "a@b"})
    assert repo.find("feedback", {"decision": "pass"})[0]["reviewer"] == "a@b"


def test_find_authored_scenarios(tmp_path):
    d = tmp_path / "data" / "scenarios"
    d.mkdir(parents=True)
    (d / "x.json").write_text('{"id":"x","patient_ref":"p","turns":[{"n":1,"question":"q"}]}', encoding="utf-8")
    repo = JsonlRepository(authored_root=tmp_path / "data", run_dir=tmp_path / "run")
    found = repo.find("scenarios", {"id": "x"})
    assert len(found) == 1 and found[0]["patient_ref"] == "p"


def test_save_rejects_authored_collection(tmp_path):
    repo = JsonlRepository(authored_root=tmp_path, run_dir=tmp_path)
    with pytest.raises(ValueError):
        repo.save("scenarios", {"id": "x"})


def test_find_unknown_collection_raises(tmp_path):
    repo = JsonlRepository(authored_root=tmp_path, run_dir=tmp_path)
    with pytest.raises(ValueError):
        repo.find("bogus")


def test_mongo_repository_is_a_documented_stub():
    with pytest.raises(NotImplementedError):
        MongoRepository()
