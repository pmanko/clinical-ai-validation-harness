# Local Dev and Validation Runbook

This runbook captures the current verified setup path and validation ladder for `openmrs-module-chartsearchai`.

## 1) Host Prerequisites

- Java: `21.0.5` (build/test)
- Maven: `3.9.9`
- Docker CLI: available
- Git: available

For OpenMRS SDK `referenceapplication:2.7.0`, Java 8 is also required to run the SDK Tomcat runtime.

## 2) Build Contracts (Verified)

From repo root:

```bash
mvn package
mvn -pl api install
```

Observed result: success.

## 3) Embedding Artifacts (Verified Layout)

Runtime model files were staged at:

- `~/openmrs/ai/chartsearchai/all-MiniLM-L6-v2.onnx`
- `~/openmrs/ai/chartsearchai/vocab.txt`

Eval model files were staged at:

- `~/openmrs/ai/chartsearchai-model-dir/model.onnx`
- `~/openmrs/ai/chartsearchai-model-dir/vocab.txt`

## 4) OpenMRS SDK Server Setup (Non-Interactive)

The following command is currently the working non-interactive setup command:

```bash
mvn openmrs-sdk:setup \
  -DserverId=ai \
  -Ddistro=referenceapplication:2.7.0 \
  -DtestMode=true \
  -DbatchAnswers=H2,8080,no\ debugging,no
```

Important notes:

- In SDK `6.8.0`, setup prompts for port before DB in this flow.
- `-DserverPort` is not supported in this plugin version.
- `-Ddebug` can be used to avoid the debug prompt.
- `referenceapplication:2.7.0` reports `db.h2.supported=false`, so this batch-mode path can configure a server directory but still leaves runtime bootstrap incomplete for a clean first-run flow.

## 5) Module Deploy and Runtime Files

Deploy module:

```bash
cp omod/target/chartsearchai-1.0.0-SNAPSHOT.omod ~/openmrs/ai/modules/
```

Runtime file staged at:

- `~/openmrs/ai/openmrs-runtime.properties`

Current placeholder key:

- `chartsearchai.llm.remote.apikey=lm-studio`

## 6) Validation Ladder (Executed)

### 6.1 Fast contract

```bash
mvn -pl api install
```

Result: success.

### 6.2 Enriched retrieval eval (default model)

```bash
mvn -pl api test \
  -Dtest=EnrichedRetrievalEvalTest \
  -Dsurefire.excludedGroups= \
  -Dchartsearchai.embedding.model.dir="$HOME/openmrs/ai/chartsearchai-model-dir"
```

Result: fails with 2 assertion failures (`physicalInjury_*`, `eyeProblems_*`), no infra errors after model files were restored.

### 6.3 Enriched retrieval eval (medcpt flag)

```bash
mvn -pl api test \
  -Dtest=EnrichedRetrievalEvalTest \
  -Dsurefire.excludedGroups= \
  -Dchartsearchai.embedding.model.dir="$HOME/openmrs/ai/chartsearchai-model-dir" \
  -Dchartsearchai.eval.model=medcpt \
  -Dchartsearchai.models.base="$HOME/openmrs/ai"
```

Result: same 2 assertion failures.

### 6.4 Opt-in LLM evals

```bash
mvn -pl api test \
  -Dtest=LlmAnswerQualityTest \
  -Dchartsearchai.llm.quality.test=true \
  -Dchartsearchai.llm.quality.endpoint=http://localhost:1234/v1/chat/completions

mvn -pl api test \
  -Dtest=PromptInjectionEvalTest \
  -Dchartsearchai.prompt.injection.test=true \
  -Dchartsearchai.prompt.injection.endpoint=http://localhost:1234/v1/chat/completions
```

Result: both commands succeed, but tests are skipped in current environment.

## 7) LM Studio Check

Health probe used:

```bash
curl http://localhost:1234/health
```

Current state during this run: connection refused.

## 8) Querystore Contract Check

Repository cloned to:

- `~/code/openmrs-module-querystore`

Command:

```bash
mvn -pl api install
```

Result: fails at test compile due missing `org.testcontainers.elasticsearch` classes in default profile.

Workaround (packaging only, no tests/test-compile):

```bash
mvn -pl api -Dmaven.test.skip=true install
```

Result: success.

## 9) Known Blockers for Next Phase

- OpenMRS SDK run for `referenceapplication:2.7.0` needs Java 8 runtime (`JDK 21` is rejected).
- End-to-end non-interactive SDK setup with DB bootstrap is fragile in this plugin/distro combination.
- LM Studio endpoint was unavailable during this run, so live LLM quality/injection execution was not validated.
