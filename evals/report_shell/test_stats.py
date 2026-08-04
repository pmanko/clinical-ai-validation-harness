from __future__ import annotations

from harness.report_shell.stats import avg, box_stats, ordered_unique, percentile, robust_axis_max


def test_stats_parity_basics() -> None:
    assert ordered_unique([1, 2, 1, None, 2]) == [1, 2, None]
    assert avg([1, 2, 3]) == 2
    assert avg([]) == 0
    assert percentile([0, 10, 20, 30, 40], 0.5) == 20
    stats = box_stats([1, 2, 3, 4, 100])
    assert stats is not None
    assert stats["median"] == 3
    assert 100 in stats["outliers"]
    series = [{"q3": 10}, {"q3": 12}]
    assert robust_axis_max(series, [1, 2, 3, 4, 100]) >= 12
