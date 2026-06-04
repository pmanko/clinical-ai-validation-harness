from harness.validate.report import _box_stats, _metric_distributions


def test_box_stats_quartiles_whiskers_outliers():
    s = _box_stats([1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert (s["min"], s["q1"], s["median"], s["q3"], s["max"], s["n"]) == (1, 3, 5, 7, 9, 9)
    assert s["outliers"] == [] and s["mean"] == 5

    # 100 sits beyond q3 + 1.5*IQR -> an outlier; the whisker stops at the last inlier
    s2 = _box_stats([10, 11, 12, 13, 14, 100])
    assert 100 in s2["outliers"]
    assert s2["whisker_hi"] == 14 and 100 not in (s2["whisker_lo"], s2["whisker_hi"])

    assert _box_stats([]) is None


def test_metric_distributions_per_arm_excludes_errors():
    results = [
        {"backend_id": "A", "metrics": {"http_status": 200, "latency_ms": 100, "citation_count": 2, "answer_chars": 50}},
        {"backend_id": "A", "metrics": {"http_status": 200, "latency_ms": 300, "citation_count": 4, "answer_chars": 90}},
        {"backend_id": "A", "metrics": {"http_status": 500, "latency_ms": 0, "citation_count": 0, "answer_chars": 0}},
        {"backend_id": "B", "metrics": {"http_status": 200, "latency_ms": 200, "citation_count": 1, "answer_chars": 40}},
    ]
    d = _metric_distributions(results, ["A", "B"])
    assert set(d.keys()) >= {"latency_ms", "citation_count", "answer_chars"}
    lat_a = next(x for x in d["latency_ms"]["series"] if x["backend"] == "A")
    assert lat_a["n"] == 2  # the http 500 row is excluded from the distribution
    assert lat_a["min"] == 100 and lat_a["max"] == 300
    # arm B has one good row
    lat_b = next(x for x in d["latency_ms"]["series"] if x["backend"] == "B")
    assert lat_b["n"] == 1 and lat_b["median"] == 200
