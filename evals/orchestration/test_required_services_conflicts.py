from harness.targets import ValidationSurface, ValidationTarget, detect_required_service_conflicts


def test_detect_required_service_conflicts_mysql_version_mismatch() -> None:
    surf = ValidationSurface("command", "x", "real_path_required", ())
    a = ValidationTarget(
        id="chartsearchai",
        display_name="A",
        submodule_path="targets/chartsearchai",
        environment_override="HARNESS_TARGET_CHARTSEARCHAI",
        evidence_status="development",
        supported_profiles=("local", "vm"),
        shared_profiles=(),
        validation_surface=surf,
        required_services=("mysql:8.0",),
    )
    b = ValidationTarget(
        id="querystore",
        display_name="B",
        submodule_path="targets/querystore",
        environment_override="HARNESS_TARGET_QUERYSTORE",
        evidence_status="development",
        supported_profiles=("local", "vm"),
        shared_profiles=(),
        validation_surface=surf,
        required_services=("mysql:5.7",),
    )
    msgs = detect_required_service_conflicts((a, b))
    assert msgs and "mysql" in msgs[0]


def test_detect_required_service_conflicts_no_false_positive_for_same_version() -> None:
    surf = ValidationSurface("command", "x", "real_path_required", ())
    a = ValidationTarget(
        id="chartsearchai",
        display_name="A",
        submodule_path="targets/chartsearchai",
        environment_override="HARNESS_TARGET_CHARTSEARCHAI",
        evidence_status="development",
        supported_profiles=("local", "vm"),
        shared_profiles=(),
        validation_surface=surf,
        required_services=("mysql:8.0",),
    )
    b = ValidationTarget(
        id="querystore",
        display_name="B",
        submodule_path="targets/querystore",
        environment_override="HARNESS_TARGET_QUERYSTORE",
        evidence_status="development",
        supported_profiles=("local", "vm"),
        shared_profiles=(),
        validation_surface=surf,
        required_services=("mysql:8.0",),
    )
    assert detect_required_service_conflicts((a, b)) == []
