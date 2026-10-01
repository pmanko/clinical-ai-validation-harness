"""Supplied provenance and API observations, without workspace policy checks."""

from __future__ import annotations


from typing import Any



def observed_api_provenance(target_id: str, **identity: Any) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "target_source": "observed_api",
        "target_actual_sha": None,
        "evidence_status": "development",
        "decision_rationale": (
            "Identity captured from the configured service API; no source revision "
            "or checkout state is inferred from these observations."
        ),
        **identity,
    }
