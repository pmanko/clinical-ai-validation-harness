# chartsearchai adapter contract

Initial command plan:

- `mvn -pl api test -Dtest=LlmInferenceServiceTest`
- `mvn -pl api test -Dtest=EnrichedRetrievalEvalTest`
- `mvn -pl api test -Dtest=EnrichedRetrievalEvalTest -Dchartsearchai.eval.model=medcpt`

All runs should emit harness run metadata and per-run JSONL events.
