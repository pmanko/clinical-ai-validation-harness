from harness.validate.agreement import krippendorff_alpha, pass_agreement, verdict


def test_alpha_is_one_for_perfect_agreement_and_none_without_disagreement_to_correct():
    assert krippendorff_alpha([[1, 1], [2, 2], [3, 3]], "ordinal") == 1.0
    assert krippendorff_alpha([["a", "a"], ["a", "a"]], "nominal") is None
    assert krippendorff_alpha([[1], [2]], "ordinal") is None


def test_nominal_alpha_matches_the_hand_computed_value():
    # Units aa, ab, bb: D_o = 1/3, D_e = 0.6, alpha = 0.444.
    assert krippendorff_alpha([["a", "a"], ["a", "b"], ["b", "b"]], "nominal") == 0.444


def test_ordinal_alpha_counts_a_near_miss_less_than_a_far_one():
    near = krippendorff_alpha([[1, 2], [1, 1], [3, 3], [2, 2]], "ordinal")
    far = krippendorff_alpha([[1, 3], [1, 1], [3, 3], [2, 2]], "ordinal")
    nominal = krippendorff_alpha([[1, 2], [1, 1], [3, 3], [2, 2]], "nominal")
    assert near is not None and far is not None and nominal is not None
    assert near > far
    assert near > nominal


def test_a_missing_rating_drops_the_unit_rather_than_the_measure():
    assert krippendorff_alpha([[1, None], [2, 2], [3, 3]], "ordinal") == 1.0


def test_verdict_names_the_threshold_band():
    assert verdict(0.85) == "good"
    assert verdict(0.7) == "acceptable"
    assert verdict(0.3) == "below acceptable"
    assert verdict(None) == "not measurable"


def test_pass_agreement_reports_alpha_per_axis_and_the_widest_cells():
    def row(s, acc, harm):
        return {"scenario_id": s, "backend_id": "b", "accuracy": acc, "completeness": acc,
                "relevance": acc, "harm": harm, "abstention_outcome": "n-a",
                "citation_groundedness": "supported"}
    actors = {
        "p1": [row("s1", 9, False), row("s2", 2, True)],
        "p2": [row("s1", 9, False), row("s2", 8, False)],
        "p3": [row("s1", 8, False), row("s2", 7, False)],
    }

    out = pass_agreement(actors)

    assert out["actors"] == ["p1", "p2", "p3"]
    assert out["n_cells"] == 2
    assert out["alpha"]["accuracy"]["level"] == "ordinal"
    assert out["alpha"]["harm"]["level"] == "nominal"
    assert out["alpha"]["abstention_outcome"]["alpha"] is None  # every pass said n-a
    assert out["thresholds"] == {"acceptable": 0.667, "good": 0.8}
    assert out["spread_cells"][0]["scenario_id"] == "s2"
    assert out["spread_cells"][0]["range"] > out["spread_cells"][1]["range"]
