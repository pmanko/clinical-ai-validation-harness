from pathlib import Path

from harness.adapters.chartsearchai import ChartSearchAiAdapter
from harness.adapters.querystore import QueryStoreAdapter


def test_chartsearchai_adapter_has_real_command_plan() -> None:
    adapter = ChartSearchAiAdapter(Path("/tmp/chartsearchai"))
    plan = adapter.command_plan()
    assert any("EnrichedRetrievalEvalTest" in cmd for cmd in plan)


def test_querystore_adapter_has_real_command_plan() -> None:
    adapter = QueryStoreAdapter(Path("/tmp/querystore"))
    plan = adapter.command_plan()
    assert plan == ["mvn -pl api install"]
