from harness.import_smoke import run_import_smoke_stub


def test_import_smoke_stub_passes_core_checks() -> None:
    result = run_import_smoke_stub()
    assert result.startup_ok
    assert result.api_read_ok
    assert result.table_checks["patient"]
    assert result.table_checks["encounter"]
    assert result.table_checks["obs"]
