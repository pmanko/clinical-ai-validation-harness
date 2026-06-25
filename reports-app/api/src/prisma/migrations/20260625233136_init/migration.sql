-- CreateTable
CREATE TABLE "Run" (
    "runId" TEXT NOT NULL PRIMARY KEY,
    "comparisonSetId" TEXT NOT NULL,
    "runDir" TEXT NOT NULL,
    "parentRunId" TEXT,
    "gitSha" TEXT,
    "datasetVersion" TEXT,
    "schemaMappingVersion" TEXT,
    "evidenceStatus" TEXT,
    "referenceDate" DATETIME,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "generatedAt" DATETIME,
    CONSTRAINT "Run_comparisonSetId_fkey" FOREIGN KEY ("comparisonSetId") REFERENCES "ComparisonSet" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Run_parentRunId_fkey" FOREIGN KEY ("parentRunId") REFERENCES "Run" ("runId") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ComparisonSet" (
    "id" TEXT NOT NULL PRIMARY KEY
);

-- CreateTable
CREATE TABLE "ComparisonSetScenario" (
    "comparisonSetId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,

    PRIMARY KEY ("comparisonSetId", "scenarioId"),
    CONSTRAINT "ComparisonSetScenario_comparisonSetId_fkey" FOREIGN KEY ("comparisonSetId") REFERENCES "ComparisonSet" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ComparisonSetScenario_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ComparisonSetArm" (
    "comparisonSetId" TEXT NOT NULL,
    "armId" TEXT NOT NULL,

    PRIMARY KEY ("comparisonSetId", "armId"),
    CONSTRAINT "ComparisonSetArm_comparisonSetId_fkey" FOREIGN KEY ("comparisonSetId") REFERENCES "ComparisonSet" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ComparisonSetArm_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Scenario" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "patientUuid" TEXT,
    "shouldAbstain" BOOLEAN NOT NULL DEFAULT false,
    "shouldCiteResourceTypes" JSONB,
    "tags" JSONB,
    CONSTRAINT "Scenario_patientUuid_fkey" FOREIGN KEY ("patientUuid") REFERENCES "Patient" ("uuid") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ScenarioTurn" (
    "scenarioId" TEXT NOT NULL,
    "n" INTEGER NOT NULL,
    "question" TEXT NOT NULL,

    PRIMARY KEY ("scenarioId", "n"),
    CONSTRAINT "ScenarioTurn_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Arm" (
    "backendId" TEXT NOT NULL PRIMARY KEY,
    "label" TEXT NOT NULL,
    "endpointUrl" TEXT,
    "modelName" TEXT NOT NULL,
    "indepthEndpointUrl" TEXT,
    "indepthModelName" TEXT,
    "kind" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "ArmRole" (
    "armId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "modelId" TEXT NOT NULL,

    PRIMARY KEY ("armId", "role"),
    CONSTRAINT "ArmRole_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ArmRole_modelId_fkey" FOREIGN KEY ("modelId") REFERENCES "Model" ("modelId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Model" (
    "modelId" TEXT NOT NULL PRIMARY KEY,
    "family" TEXT,
    "params" TEXT,
    "quant" TEXT,
    "note" TEXT
);

-- CreateTable
CREATE TABLE "Patient" (
    "uuid" TEXT NOT NULL PRIMARY KEY,
    "display" TEXT,
    "gender" TEXT,
    "birthdate" DATETIME
);

-- CreateTable
CREATE TABLE "Result" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,
    "armId" TEXT NOT NULL,
    "turn" INTEGER NOT NULL,
    "answer" TEXT NOT NULL,
    "disclaimer" TEXT,
    "responseModel" TEXT,
    "blocks" JSONB,
    "error" TEXT,
    "startedAt" DATETIME,
    "endedAt" DATETIME,
    "referenceDate" DATETIME,
    "httpStatus" INTEGER,
    "latencyMs" INTEGER,
    "jsonValid" BOOLEAN,
    "answerChars" INTEGER,
    "citationCount" INTEGER,
    "abstained" BOOLEAN,
    "tokensIn" INTEGER,
    "tokensOut" INTEGER,
    CONSTRAINT "Result_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("runId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Result_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Result_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ResultReference" (
    "resultId" TEXT NOT NULL,
    "idx" INTEGER NOT NULL,
    "resourceType" TEXT NOT NULL,
    "resourceUuid" TEXT NOT NULL,
    "date" DATETIME,

    PRIMARY KEY ("resultId", "idx"),
    CONSTRAINT "ResultReference_resultId_fkey" FOREIGN KEY ("resultId") REFERENCES "Result" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "IndepthResult" (
    "resultId" TEXT NOT NULL PRIMARY KEY,
    "answer" TEXT NOT NULL,
    "modelName" TEXT,
    "latencyMs" INTEGER,
    "httpStatus" INTEGER,
    "error" TEXT,
    CONSTRAINT "IndepthResult_resultId_fkey" FOREIGN KEY ("resultId") REFERENCES "Result" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Trace" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "resultId" TEXT NOT NULL,
    "levelId" TEXT NOT NULL,
    "steps" JSONB NOT NULL,
    "answerConfidenceLevel" TEXT,
    "answerConfidenceNote" TEXT,
    "indepthConfidenceLevel" TEXT,
    "indepthConfidenceNote" TEXT,
    "inDepthClaims" JSONB,
    "referenceDate" DATETIME,
    CONSTRAINT "Trace_resultId_fkey" FOREIGN KEY ("resultId") REFERENCES "Result" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "JudgeRow" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,
    "armId" TEXT NOT NULL,
    "accuracy" REAL,
    "completeness" REAL,
    "relevance" REAL,
    "abstentionOutcome" TEXT,
    "citationGroundedness" TEXT,
    "harm" BOOLEAN,
    "temporalDateAccuracy" TEXT,
    "temporalWindow" TEXT,
    "temporalTrend" TEXT,
    "citationResolution" JSONB,
    "note" TEXT,
    CONSTRAINT "JudgeRow_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("runId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "JudgeRow_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "JudgeRow_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "JudgeBackground" (
    "judgeRowId" TEXT NOT NULL PRIMARY KEY,
    "support" REAL,
    "addedValue" REAL,
    "noNewHarm" BOOLEAN,
    "conciseness" REAL,
    "nClaims" INTEGER,
    "note" TEXT,
    CONSTRAINT "JudgeBackground_judgeRowId_fkey" FOREIGN KEY ("judgeRowId") REFERENCES "JudgeRow" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ArmAggregate" (
    "runId" TEXT NOT NULL,
    "armId" TEXT NOT NULL,
    "benchmark" REAL NOT NULL,
    "answerMeans" JSONB NOT NULL,
    "inDepthMeans" JSONB,
    "harmCount" INTEGER NOT NULL,
    "confabCount" INTEGER NOT NULL,

    PRIMARY KEY ("runId", "armId"),
    CONSTRAINT "ArmAggregate_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("runId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "ArmAggregate_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Reviewer" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "identity" TEXT NOT NULL,
    "tier" TEXT NOT NULL
);

-- CreateTable
CREATE TABLE "Adjudication" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "scenarioId" TEXT NOT NULL,
    "armId" TEXT NOT NULL,
    "reviewerId" TEXT NOT NULL,
    "axes" JSONB NOT NULL,
    "harm" BOOLEAN NOT NULL,
    "note" TEXT NOT NULL,
    "judgedAt" DATETIME NOT NULL,
    CONSTRAINT "Adjudication_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("runId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Adjudication_scenarioId_fkey" FOREIGN KEY ("scenarioId") REFERENCES "Scenario" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Adjudication_armId_fkey" FOREIGN KEY ("armId") REFERENCES "Arm" ("backendId") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Adjudication_reviewerId_fkey" FOREIGN KEY ("reviewerId") REFERENCES "Reviewer" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PublishedReport" (
    "slug" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "comparisonSetId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "summary" TEXT,
    "takeaway" TEXT,
    "sortOrder" INTEGER NOT NULL,
    "featured" BOOLEAN NOT NULL DEFAULT false,
    "hidden" BOOLEAN NOT NULL DEFAULT false,
    "hasLive" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "PublishedReport_runId_fkey" FOREIGN KEY ("runId") REFERENCES "Run" ("runId") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "CatalogMeta" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT DEFAULT 1,
    "intro" TEXT NOT NULL,
    "scoringNote" TEXT NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "Result_runId_scenarioId_armId_turn_key" ON "Result"("runId", "scenarioId", "armId", "turn");

-- CreateIndex
CREATE UNIQUE INDEX "Trace_resultId_key" ON "Trace"("resultId");

-- CreateIndex
CREATE UNIQUE INDEX "JudgeRow_runId_scenarioId_armId_key" ON "JudgeRow"("runId", "scenarioId", "armId");
