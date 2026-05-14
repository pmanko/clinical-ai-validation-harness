from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

_ENV_OVERRIDE_RE = re.compile(r"^HARNESS_TARGET_[A-Z0-9_]+$")
_ALLOWED_IDS = frozenset({"chartsearchai", "querystore", "openmrs_chatbot", "catalyst"})
_ALLOWED_PROFILES = frozenset({"local", "vm"})
_ALLOWED_EVIDENCE = frozenset(
    {"release", "development", "fixture", "scaffolding", "unavailable"}
)
_ALLOWED_SURFACE_KIND = frozenset({"command", "api", "workflow", "unavailable"})
_ALLOWED_EVIDENCE_MODE = frozenset(
    {"real_path_required", "fixture_backed", "scaffolding_only", "unavailable"}
)


@dataclass(frozen=True)
class ValidationSurface:
    kind: str
    description: str
    evidence_mode: str
    command: tuple[str, ...] = ()

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "ValidationSurface":
        kind = str(raw["kind"])
        if kind not in _ALLOWED_SURFACE_KIND:
            raise ValueError(f"validation_surface.kind not allowed: {kind!r}")
        evidence_mode = str(raw["evidence_mode"])
        if evidence_mode not in _ALLOWED_EVIDENCE_MODE:
            raise ValueError(f"validation_surface.evidence_mode not allowed: {evidence_mode!r}")
        cmd = raw.get("command") or []
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise ValueError("validation_surface.command must be a list of strings when present")
        return ValidationSurface(
            kind=kind,
            description=str(raw["description"]),
            evidence_mode=evidence_mode,
            command=tuple(cmd),
        )


@dataclass(frozen=True)
class ValidationTarget:
    id: str
    display_name: str
    submodule_path: str
    environment_override: str
    evidence_status: str
    supported_profiles: tuple[str, ...]
    shared_profiles: tuple[str, ...]
    validation_surface: ValidationSurface
    required_services: tuple[str, ...] = ()
    target_compose_files: tuple[str, ...] = ()
    readiness_notes: str | None = None

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "ValidationTarget":
        tid = str(raw["id"])
        if tid not in _ALLOWED_IDS:
            raise ValueError(f"target id not in initial set: {tid!r}")
        sub = str(raw["submodule_path"])
        if not sub.startswith("targets/"):
            raise ValueError(f"submodule_path must start with targets/: {sub!r}")
        if tid == "catalyst" and sub != "targets/catalyst":
            raise ValueError("Catalyst submodule_path must be targets/catalyst")
        env_o = str(raw["environment_override"])
        if not _ENV_OVERRIDE_RE.match(env_o):
            raise ValueError(f"environment_override must match HARNESS_TARGET_*: {env_o!r}")
        ev = str(raw["evidence_status"])
        if ev not in _ALLOWED_EVIDENCE:
            raise ValueError(f"evidence_status not allowed: {ev!r}")
        sup = tuple(str(x) for x in raw["supported_profiles"])
        for p in sup:
            if p not in _ALLOWED_PROFILES:
                raise ValueError(f"supported_profiles references unknown profile: {p!r}")
        shp = tuple(str(x) for x in raw.get("shared_profiles") or [])
        rs = tuple(str(x) for x in raw.get("required_services") or [])
        tcf = tuple(str(x) for x in raw.get("target_compose_files") or [])
        surface = ValidationSurface.from_mapping(raw["validation_surface"])
        if ev == "release" and surface.evidence_mode != "real_path_required":
            raise ValueError("evidence_status release requires real_path_required surface")
        return ValidationTarget(
            id=tid,
            display_name=str(raw["display_name"]),
            submodule_path=sub,
            environment_override=env_o,
            evidence_status=ev,
            supported_profiles=sup,
            shared_profiles=shp,
            validation_surface=surface,
            required_services=rs,
            target_compose_files=tcf,
            readiness_notes=raw.get("readiness_notes"),
        )


@dataclass(frozen=True)
class EnvironmentProfile:
    id: str
    description: str
    artifact_root: str
    enabled_targets: tuple[str, ...]
    shared_compose_files: tuple[str, ...]
    active_compose_profiles: tuple[str, ...] = ()
    required_env: tuple[str, ...] = ()
    allows_overrides: bool = True

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "EnvironmentProfile":
        pid = str(raw["id"])
        if pid not in _ALLOWED_PROFILES:
            raise ValueError(f"profile id not allowed: {pid!r}")
        et = tuple(str(x) for x in raw["enabled_targets"])
        scf = tuple(str(x) for x in raw["shared_compose_files"])
        acp = tuple(str(x) for x in raw.get("active_compose_profiles") or [])
        renv = tuple(str(x) for x in raw.get("required_env") or [])
        return EnvironmentProfile(
            id=pid,
            description=str(raw["description"]),
            artifact_root=str(raw["artifact_root"]),
            enabled_targets=et,
            shared_compose_files=scf,
            active_compose_profiles=acp,
            required_env=renv,
            allows_overrides=bool(raw.get("allows_overrides", True)),
        )


@dataclass(frozen=True)
class SharedInfrastructureService:
    id: str
    owner: str
    compose_file: str
    service_names: tuple[str, ...]
    docker_profiles: tuple[str, ...] = ()

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "SharedInfrastructureService":
        owner = str(raw["owner"])
        if owner != "harness":
            raise ValueError("shared infrastructure owner must be harness")
        cf = str(raw["compose_file"])
        if not (cf.startswith("compose/") or cf == "compose"):
            raise ValueError(f"compose_file must be under compose/: {cf!r}")
        sn = tuple(str(x) for x in raw["service_names"])
        dp = tuple(str(x) for x in raw.get("docker_profiles") or [])
        return SharedInfrastructureService(
            id=str(raw["id"]),
            owner=owner,
            compose_file=cf,
            service_names=sn,
            docker_profiles=dp,
        )



@dataclass(frozen=True)
class HarnessTargetsDocument:
    schema_version: int
    targets: tuple[ValidationTarget, ...]
    profiles: tuple[EnvironmentProfile, ...]
    shared_infrastructure: tuple[SharedInfrastructureService, ...]

    @staticmethod
    def load(path: Path) -> "HarnessTargetsDocument":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("targets.yaml must be a mapping at the top level")
        sv = int(raw["schema_version"])
        if sv != 1:
            raise ValueError(f"unsupported schema_version: {sv}")
        targets = tuple(ValidationTarget.from_mapping(t) for t in raw["targets"])
        profiles = tuple(EnvironmentProfile.from_mapping(p) for p in raw["profiles"])
        shared = tuple(SharedInfrastructureService.from_mapping(s) for s in raw["shared_infrastructure"])
        doc = HarnessTargetsDocument(
            schema_version=sv,
            targets=targets,
            profiles=profiles,
            shared_infrastructure=shared,
        )
        doc.validate_cross_field()
        project_root = path.parent.parent
        msgs = doc.compose_conflicts(project_root)
        if msgs:
            raise ValueError("compose conflicts: " + "; ".join(msgs))
        return doc

    def compose_conflicts(self, project_root: Path) -> list[str]:
        from .compose import detect_compose_conflicts

        harness_paths = [project_root / s.compose_file for s in self.shared_infrastructure]
        target_pairs: list[tuple[str, Path]] = []
        for t in self.targets:
            root = project_root / t.submodule_path
            for rel in t.target_compose_files:
                target_pairs.append((t.id, root / rel))
        return detect_compose_conflicts(harness_paths, target_pairs)

    def validate_cross_field(self) -> None:
        if len(self.targets) < 4:
            raise ValueError("targets must include at least four initial targets")
        if len(self.profiles) < 2:
            raise ValueError("profiles must include at least local and vm")
        ids = [t.id for t in self.targets]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate target id")
        prof_ids = {p.id for p in self.profiles}
        if len(prof_ids) != len(self.profiles):
            raise ValueError("duplicate profile id")
        shared_ids = {s.id for s in self.shared_infrastructure}
        if len(shared_ids) != len(self.shared_infrastructure):
            raise ValueError("duplicate shared_infrastructure id")
        for t in self.targets:
            for p in t.supported_profiles:
                if p not in prof_ids:
                    raise ValueError(f"target {t.id} references unknown profile {p!r}")
            for s in t.shared_profiles:
                if s not in shared_ids:
                    raise ValueError(f"target {t.id} references unknown shared_infrastructure {s!r}")
        conflicts = detect_required_service_conflicts(self.targets)
        if conflicts:
            raise ValueError("required service conflicts: " + "; ".join(conflicts))


def parse_service_token(token: str) -> tuple[str, str | None]:
    """Split mysql:8.0 into (mysql, 8.0); bare name has version None."""
    if ":" in token:
        name, ver = token.split(":", 1)
        return name.strip(), ver.strip() or None
    return token.strip(), None


def detect_required_service_conflicts(targets: Sequence[ValidationTarget]) -> list[str]:
    """Return human-readable conflict messages for incompatible required_services."""
    by_name: dict[str, dict[str | None, set[str]]] = {}
    for t in targets:
        for tok in t.required_services:
            name, ver = parse_service_token(tok)
            by_name.setdefault(name, {}).setdefault(ver, set()).add(t.id)
    out: list[str] = []
    for name, versions in by_name.items():
        distinct = {v for v in versions if v is not None}
        if len(distinct) > 1:
            out.append(
                f"service {name!r} required with incompatible versions: {sorted(distinct)!r}"
            )
    return out


def default_targets_path(project_root: Path) -> Path:
    return project_root.resolve() / "harness" / "targets.yaml"
