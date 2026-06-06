from harness.validate.reconcile import resolve_citations, scout_summary


def test_resolve_citations_flags_references_not_in_the_chart():
    # Layer-1 deterministic check: each reference's resourceUuid must resolve to a real
    # record in the patient's chart. A uuid not in the chart = a fabricated reference.
    refs = [
        {"index": 169, "resourceUuid": "ccbd1e8c-1691-11df-97a5-7038c432aabf", "resourceType": "obs"},
        {"index": 999, "resourceUuid": "not-a-real-uuid", "resourceType": "obs"},
    ]
    valid = {"ccbd1e8c-1691-11df-97a5-7038c432aabf", "other-real-uuid"}
    r = resolve_citations(refs, valid)
    assert r["n_refs"] == 2 and r["n_resolved"] == 1 and r["n_unresolved"] == 1
    assert r["unresolved"] == [{"index": 999, "resourceUuid": "not-a-real-uuid"}]
    assert r["rate"] == 0.5
    # A real-index-wrong-claim (e2b's [203] -> a real obs) RESOLVES here by design;
    # catching the wrong claim is the semantic layer's job, not this one.
    assert resolve_citations(
        [{"index": 203, "resourceUuid": "ccbd1e8c-1691-11df-97a5-7038c432aabf"}], valid
    )["n_unresolved"] == 0
    # No references -> rate is None (not 0), so it doesn't drag an arm's mean down.
    assert resolve_citations([], valid)["rate"] is None


def test_scout_summary_aggregates_citation_resolution():
    # P2: the judge writes each cell's resolve_citations() output into the row as
    # `citation_resolution`; scout_summary must pool it per arm so the report shows a
    # resolution rate (n_resolved/n_refs) and total fabricated (unresolved) references.
    rows = [
        {"backend_id": "A", "citation_resolution": {"n_refs": 4, "n_resolved": 3, "n_unresolved": 1}},
        {"backend_id": "A", "citation_resolution": {"n_refs": 2, "n_resolved": 2, "n_unresolved": 0}},
        {"backend_id": "A"},  # abstain / no refs -> contributes nothing, never drags the rate
    ]
    a = next(x for x in scout_summary(rows, ["A"]) if x["backend"] == "A")
    assert a["citation_resolution"] == {"n_refs": 6, "n_resolved": 5, "n_unresolved": 1, "rate": 0.83}
    # No judged rows -> zero counts, rate None (so it never drags an aggregate down).
    z = scout_summary([], ["A"])[0]
    assert z["citation_resolution"] == {"n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "rate": None}


def test_scout_summary_per_arm_aggregates():
    rows = [
        {"scenario_id": "s1", "backend_id": "A", "accuracy": 8, "completeness": 6, "relevance": 9,
         "abstention_outcome": "n-a", "citation_groundedness": "supported", "harm": False,
         "temporal_date_accuracy": "ok", "temporal_window": "n-a", "temporal_trend": "n-a"},
        {"scenario_id": "s2", "backend_id": "A", "accuracy": 4, "completeness": 4, "relevance": 5,
         "abstention_outcome": "failed-to-abstain", "citation_groundedness": "unsupported", "harm": True,
         "temporal_date_accuracy": "wrong", "temporal_window": "over-claimed", "temporal_trend": "fabricated"},
        {"scenario_id": "s1", "backend_id": "B", "accuracy": 10, "completeness": 10, "relevance": 10,
         "abstention_outcome": "correct", "citation_groundedness": "supported", "harm": False,
         "temporal_date_accuracy": "minor", "temporal_window": "ok", "temporal_trend": "ok"},
    ]
    s = scout_summary(rows, ["A", "B"])
    a = next(x for x in s if x["backend"] == "A")
    assert a["n"] == 2
    assert a["accuracy_mean"] == 6.0 and a["completeness_mean"] == 5.0 and a["relevance_mean"] == 7.0
    assert a["harm_count"] == 1
    assert a["abstention"]["failed-to-abstain"] == 1 and a["abstention"]["n-a"] == 1
    assert a["groundedness"]["supported"] == 1 and a["groundedness"]["unsupported"] == 1
    # temporal failure tallies (the date/window/trend axis)
    assert a["temporal"] == {"date_wrong": 1, "date_minor": 0, "window_over": 1, "trend_fab": 1}
    b = next(x for x in s if x["backend"] == "B")
    assert b["n"] == 1 and b["accuracy_mean"] == 10.0 and b["harm_count"] == 0
    assert b["temporal"] == {"date_wrong": 0, "date_minor": 1, "window_over": 0, "trend_fab": 0}
    # an arm with no judged rows still appears with n=0 / None means
    z = scout_summary([], ["A"])
    assert z[0] == {"backend": "A", "n": 0, "accuracy_mean": None, "completeness_mean": None,
                    "relevance_mean": None, "harm_count": 0, "abstention": {}, "groundedness": {},
                    "temporal": {"date_wrong": 0, "date_minor": 0, "window_over": 0, "trend_fab": 0},
                    "citation_resolution": {"n_refs": 0, "n_resolved": 0, "n_unresolved": 0, "rate": None}}
