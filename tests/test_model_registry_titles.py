from harness.validate.model_registry import arm_card


def test_wide_team_titles_include_role_model_sizes():
    low = arm_card("wide-team-12b-contract-warn")
    assert low["title"] == "Gemma 4B coord · Gemma 12B writer · Qwen 14B val"
    assert low["short_title"] == low["title"]

    high = arm_card("wide-team-high-contract-warn")
    assert high["title"] == (
        "Gemma 31B coord · MedGemma 27B expert · Qwen 35B writer · Gemma 31B val"
    )
    assert high["short_title"] == high["title"]
