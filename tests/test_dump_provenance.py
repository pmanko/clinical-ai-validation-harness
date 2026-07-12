from __future__ import annotations

import gzip
import json
from pathlib import Path

from harness.validate.dump_provenance import sha256_file, verify_dump


def _write_dump(
    tmp_path: Path, sql: bytes, *, module_state_included: bool = False
) -> tuple[Path, Path]:
    dump = tmp_path / "corpus.sql.gz"
    with gzip.open(dump, "wb") as stream:
        stream.write(sql)
    provenance = tmp_path / "corpus.sql.gz.provenance.json"
    provenance.write_text(
        json.dumps(
            {
                "output_sha256": sha256_file(dump),
                "output_bytes": dump.stat().st_size,
                "excluded_module_prefixes": ["chartsearchai", "querystore"],
                "module_state_included": module_state_included,
            }
        ),
        encoding="utf-8",
    )
    return dump, provenance


def test_clean_portable_gzip_passes(tmp_path: Path) -> None:
    dump, provenance = _write_dump(
        tmp_path,
        b"CREATE TABLE `patient` (`patient_id` int);\n"
        b"INSERT INTO `liquibasechangelog` VALUES ('core-1','core.xml');\n",
    )

    metadata, issues = verify_dump(dump, provenance)

    assert issues == []
    assert metadata["output_sha256"] == sha256_file(dump)


def test_consumer_module_table_fails(tmp_path: Path) -> None:
    dump, provenance = _write_dump(
        tmp_path, b"CREATE TABLE `chartsearchai_chat_session` (`id` int);\n"
    )

    _, issues = verify_dump(dump, provenance)

    assert "consumer-module table survived: chartsearchai" in issues


def test_consumer_module_changelog_row_fails(tmp_path: Path) -> None:
    dump, provenance = _write_dump(
        tmp_path,
        b"INSERT INTO `liquibasechangelog` VALUES "
        b"('querystore-001','liquibase/querystore.xml');\n",
    )

    _, issues = verify_dump(dump, provenance)

    assert "consumer-module Liquibase row survived: querystore" in issues


def test_hash_mismatch_fails(tmp_path: Path) -> None:
    dump, provenance = _write_dump(tmp_path, b"SELECT 1;\n")
    metadata = json.loads(provenance.read_text(encoding="utf-8"))
    metadata["output_sha256"] = "0" * 64
    provenance.write_text(json.dumps(metadata), encoding="utf-8")

    _, issues = verify_dump(dump, provenance)

    assert any("sha256 mismatch" in issue for issue in issues)


def test_full_backup_may_include_module_state(tmp_path: Path) -> None:
    dump, provenance = _write_dump(
        tmp_path,
        b"CREATE TABLE `chartsearchai_chat_session` (`id` int);\n",
        module_state_included=True,
    )

    _, issues = verify_dump(dump, provenance)

    assert issues == []


def test_seed_mode_rejects_full_backup_module_state(tmp_path: Path) -> None:
    dump, provenance = _write_dump(
        tmp_path,
        b"CREATE TABLE `chartsearchai_chat_session` (`id` int);\n",
        module_state_included=True,
    )

    _, issues = verify_dump(dump, provenance, require_portable=True)

    assert issues == [
        "seed input must be a portable corpus without consumer-module state"
    ]


def test_portable_corpus_may_exclude_additional_module_prefixes(tmp_path: Path) -> None:
    dump, provenance = _write_dump(tmp_path, b"SELECT 1;\n")
    metadata = json.loads(provenance.read_text(encoding="utf-8"))
    metadata["excluded_module_prefixes"].append("othermodule")
    provenance.write_text(json.dumps(metadata), encoding="utf-8")

    _, issues = verify_dump(dump, provenance)

    assert issues == []
