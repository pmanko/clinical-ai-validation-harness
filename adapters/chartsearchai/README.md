# ChartSearchAI adapter contract

ChartSearchAI is the OpenMRS authorization, session, persistence, and streaming
relay for med-agent-hub product profiles. Its stable repository-level check is:

- `make chartsearch-test`

Live product validation uses `make chartsearchai-local` and the Playwright relay,
multi-turn, and cancellation gates. The deleted Java inference/retrieval tests are
not adapter entrypoints; answer quality is evaluated through the hub profile path.
