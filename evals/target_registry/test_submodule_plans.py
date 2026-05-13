from harness.submodules import plan_submodule_update


def test_submodule_sync_plan_includes_recursive_init() -> None:
    plan = plan_submodule_update(["targets/chartsearchai", "targets/querystore"], depth=1)
    assert len(plan.commands) == 2
    assert plan.commands[0][:5] == ["git", "submodule", "update", "--init", "--recursive"]
    assert plan.commands[0][5:7] == ["--depth", "1"]
    assert plan.commands[0][-1] == "targets/chartsearchai"
    assert plan.commands[1][-1] == "targets/querystore"


def test_submodule_sync_plan_without_depth() -> None:
    plan = plan_submodule_update(["targets/openmrs_chatbot"])
    assert plan.commands[0] == [
        "git",
        "submodule",
        "update",
        "--init",
        "--recursive",
        "targets/openmrs_chatbot",
    ]
