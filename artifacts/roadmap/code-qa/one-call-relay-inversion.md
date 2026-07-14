# One-Call Relay Inversion Proof

**Roadmap:** `MAH-CONSOLIDATION-2026-07-09-v1`  
**Date:** 2026-07-13  
**ChartSearchAI commit:** `0190b74c72e77932be2df41ec752a271c587dc3b` (`test: enforce one-call hub relay`)

## Guard

`ChartSearchAiStreamingTest.chatStream_stagedTeamModel_relaysOneHubCallNotTheLegacyThreeCallDecomposition`
uses a real local HTTP server, counts requests to `/v1/chat/completions`, and asserts that one
product-profile request produces exactly one upstream med-agent-hub call.

## Controlled Mutation

The streaming relay was temporarily changed to send the same product-profile request twice before
reading the normal response. This simulates the architectural regression the guard is intended to
catch without restoring any legacy stage implementation.

Command:

```text
mvn -pl omod -Dtest=ChartSearchAiStreamingTest#chatStream_stagedTeamModel_relaysOneHubCallNotTheLegacyThreeCallDecomposition test
```

Observed red result:

```text
Tests run: 1, Failures: 1, Errors: 0, Skipped: 0
one product profile request must produce exactly one upstream hub call
expected: <1> but was: <2>
```

## Restored Result

The mutation was removed with an explicit reverse patch. The same command then passed:

```text
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

The complete ChartSearchAI reactor was also run after restoration:

```text
API: 43 tests passed
OMOD: 49 tests passed
Total: 92 tests passed, 0 failures, 0 errors, 0 skipped
BUILD SUCCESS
```

The production relay source has no residual mutation. Only the request-count assertion is included
in commit `0190b74c72e77932be2df41ec752a271c587dc3b`.
