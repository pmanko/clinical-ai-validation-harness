# G09 — Hub start-without-querystore, live evidence (2026-07-24)

Deployment: `harness-med-agent-hub` rebuilt at `HUB_BUILD_REVISION=a279a56` (this session's tip),
`QUERYSTORE_BASE_URL`/`QUERYSTORE_USERNAME`/`QUERYSTORE_PASSWORD` all empty (fully unconfigured,
not partially configured — `config.py`'s `partially_configured` guard only fires on a partial set).

## 1. Startup

```
$ export QUERYSTORE_BASE_URL="" QUERYSTORE_USERNAME="" QUERYSTORE_PASSWORD=""
$ make med-agent-hub-up
...
    med-agent-hub healthy after 6 s

$ docker exec harness-med-agent-hub sh -c 'echo "QUERYSTORE_BASE_URL=[$QUERYSTORE_BASE_URL] QUERYSTORE_USERNAME=[$QUERYSTORE_USERNAME] QUERYSTORE_PASSWORD=[$QUERYSTORE_PASSWORD]"'
QUERYSTORE_BASE_URL=[] QUERYSTORE_USERNAME=[] QUERYSTORE_PASSWORD=[]

$ curl -fsS http://localhost:18081/health
{"status":"healthy","uptime_seconds":29.88, ...}
```

The hub starts and reports healthy with zero querystore configuration — this is not a degraded or
partial-failure state, it is the documented supported deployment shape (`InlineChartSource`/
`StaticKnowledgeSource`).

## 2. Real request, no patient ref, inline chart

Request (`POST /v1/chat/completions`, no `patient` field — nothing that could trigger a
querystore lookup even if it were configured):

```json
{
  "model": "single-e4b-checked",
  "stream": false,
  "messages": [
    {"role": "system", "content": "You are a clinical assistant."},
    {"role": "user", "content": "Patient records (most recent first):\n[1] (2026-06-01) Active order: Lisinopril 10 mg daily\n[2] (2026-05-15) Allergy: Penicillin. Reaction: rash\n[3] (2026-01-10) Patient: 54-year-old Male"},
    {"role": "user", "content": "What medications is the patient on?"}
  ]
}
```

Response content (parsed from the completion's `message.content`, formatted for readability):

```json
{
  "answer": "The patient is currently on Lisinopril 10 mg daily [1].",
  "citations": [1],
  "references": [{
    "index": 1, "sourceId": "inline:1", "source": "inline",
    "resourceType": "ChartRecord", "date": "2026-06-01",
    "resolutionStatus": "resolved", "groundingStatus": "verified", "grounded": true
  }],
  "confidence": {"answer": {"level": "green", "note": ""}},
  "answerValidation": {"status": "checked", "label": "Checked", "issues": []},
  "context": {
    "sources": ["inline", "knowledge-base"],
    "ledger_records": 6,
    "included": [
      {"source_id": "inline:1", "reason": "recent_core"},
      {"source_id": "inline:2", "reason": "mandatory"},
      {"source_id": "inline:3", "reason": "recent_core"}
    ]
  },
  "temporalGate": {"status": "not_applicable"}
}
```

`"sources": ["inline", "knowledge-base"]` — never `"querystore"` — confirms the context assembly
genuinely used `InlineChartSource`, not a degraded/empty querystore path. The answer is correctly
grounded against the inline chart's Lisinopril record (`groundingStatus: verified`), the allergy
record was pulled in as `mandatory` even though nothing in the question asked about allergies
(the same mandatory-core policy as the querystore-backed path), and the full validation pipeline
(`answerValidation.status: checked`) ran to completion. This is a real, functioning turn, not a
liveness-only check.

## Conclusion

G09 (source independence) is fully demonstrated: the hub starts, serves, validates, and grounds a
real clinical answer with zero querystore configuration present, via the pre-existing
`InlineChartSource`/mandatory-core/grounding pipeline — no code changes were needed for this,
only the recorded run the roadmap gate was missing.
