# ChartSearchAI adapter contract

ChartSearchAI is the OpenMRS authorization, session, persistence, and streaming
boundary for two providers:

- the bundled provider retains ChartSearchAI's local and configured remote inference paths;
- the configured med-agent-hub provider relays one staged profile request to the hub.

Provider selection is explicit, starts a new conversation, and has no automatic fallback. The
shared backend persists provider-neutral answer envelopes, evidence, validation state, and
cancellation outcomes. Its stable repository-level check is:

- `make chartsearch-test`

Live product validation uses `make chartsearchai-local` and the Playwright relay,
multi-turn, and cancellation gates. Bundled-provider and hub-provider behavior are both exercised
through the same UI/session contract; hub answer quality is additionally evaluated through its
profile path.
