import { Injectable } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { access, readFile } from 'node:fs/promises';
import { basename, join } from 'node:path';

import type { ArmAggregateDto, ArmDto, ResultReferenceDto, TraceDto } from '@reports/shared';
import {
  InMemoryReportStore,
  type StoredJudgeRow,
  type StoredResult
} from '../store/report-store.js';

type JsonObject = Record<string, unknown>;

@Injectable()
export class IngestService {
  constructor(private readonly store: InMemoryReportStore) {}

  async ingestRun(runDir: string): Promise<void> {
    const manifest = await this.readOptionalJson(join(runDir, 'run_manifest.json'));
    const results = await this.readOptionalJsonl(join(runDir, 'results.jsonl'));
    const judges = await this.readOptionalJsonl(join(runDir, 'judge.jsonl'));
    const traces = await this.readOptionalJsonl(join(runDir, 'hub-trace', 'trace.jsonl'));
    const summary = await this.readOptionalJson(join(runDir, 'summary.json'));
    const adjudications = await this.readOptionalJsonl(join(runDir, 'adjudication.jsonl'));

    const runId =
      this.stringValue(manifest.runId) ?? this.stringValue(results[0]?.runId) ?? basename(runDir);
    const comparisonSetId = this.stringValue(manifest.comparisonSetId) ?? 'default';

    this.store.upsertRun({
      runId,
      comparisonSetId,
      runDir,
      parentRunId: this.stringValue(manifest.parentRunId),
      gitSha: this.stringValue(manifest.gitSha),
      datasetVersion: this.stringValue(manifest.datasetVersion),
      schemaMappingVersion: this.stringValue(manifest.schemaMappingVersion),
      evidenceStatus: this.stringValue(manifest.evidenceStatus),
      referenceDate: this.stringValue(manifest.referenceDate),
      startedAt: this.stringValue(manifest.startedAt),
      completedAt: this.stringValue(manifest.completedAt),
      generatedAt: this.stringValue(manifest.generatedAt)
    });

    const storedResults = results.map((row) => this.toStoredResult(row, runId));
    for (const result of storedResults) {
      result.trace = this.correlateTrace(result, traces);
      this.store.upsertResult(result);
    }

    for (const judge of judges.map((row) => this.toStoredJudge(row, runId))) {
      this.store.upsertJudge(judge);
    }

    for (const aggregate of this.toAggregates(summary, runId)) {
      this.store.upsertAggregate(aggregate);
    }

    for (const adjudication of adjudications) {
      this.store.addReview({
        id: this.stringValue(adjudication.id) ?? randomUUID(),
        runId: this.stringValue(adjudication.runId) ?? runId,
        scenarioId:
          this.stringValue(adjudication.scenarioId) ??
          this.stringValue(adjudication.scenario_id) ??
          'scenario',
        armId:
          this.stringValue(adjudication.armId) ??
          this.stringValue(adjudication.backend_id) ??
          'arm',
        reviewerId:
          this.stringValue(adjudication.reviewerId) ??
          this.stringValue(adjudication.reviewer) ??
          'reviewer',
        reviewerTier:
          this.stringValue(adjudication.reviewerTier) === 'owner' ||
          this.stringValue(adjudication.reviewerTier) === 'clinical'
            ? (this.stringValue(adjudication.reviewerTier) as 'owner' | 'clinical')
            : 'domain',
        axes: this.recordOfNumbers(adjudication.axes),
        harm: adjudication.harm === true,
        note: this.stringValue(adjudication.note) ?? '',
        judgedAt: this.stringValue(adjudication.judgedAt) ?? new Date().toISOString()
      });
    }
  }

  private toStoredResult(row: JsonObject, fallbackRunId: string): StoredResult {
    const arm = this.toArm(row.arm);
    const scenarioId =
      this.stringValue(row.scenarioId) ?? this.stringValue(row.scenario_id) ?? 'scenario';
    const turn = this.numberValue(row.turn) ?? 1;
    const references = Array.isArray(row.references)
      ? row.references.map((reference, idx) => this.toReference(reference, idx))
      : [];

    return {
      id: `${this.stringValue(row.runId) ?? fallbackRunId}:${scenarioId}:${arm.backendId}:${turn}`,
      runId: this.stringValue(row.runId) ?? fallbackRunId,
      scenarioId,
      question: this.stringValue(row.question) ?? '',
      turn,
      arm,
      answer: this.stringValue(row.answer) ?? '',
      references,
      indepth: row.indepth,
      responseModel: this.stringValue(row.responseModel),
      startedAt: this.stringValue(row.startedAt),
      endedAt: this.stringValue(row.endedAt),
      latencyMs: this.numberValue(row.latencyMs)
    };
  }

  private toStoredJudge(row: JsonObject, fallbackRunId: string): StoredJudgeRow {
    return {
      runId: this.stringValue(row.runId) ?? fallbackRunId,
      scenarioId:
        this.stringValue(row.scenarioId) ?? this.stringValue(row.scenario_id) ?? 'scenario',
      armId: this.stringValue(row.armId) ?? this.stringValue(row.backendId) ?? 'arm',
      accuracy: this.numberValue(row.accuracy),
      completeness: this.numberValue(row.completeness),
      relevance: this.numberValue(row.relevance),
      abstentionOutcome: this.stringValue(row.abstentionOutcome),
      citationGroundedness: this.stringValue(row.citationGroundedness),
      harm: typeof row.harm === 'boolean' ? row.harm : undefined,
      temporalDateAccuracy: this.stringValue(row.temporalDateAccuracy),
      temporalWindow: this.stringValue(row.temporalWindow),
      temporalTrend: this.stringValue(row.temporalTrend),
      citationResolution: row.citationResolution,
      note: this.stringValue(row.note),
      background: row.background
    };
  }

  private toAggregates(summary: JsonObject, fallbackRunId: string): ArmAggregateDto[] {
    const rows = Array.isArray(summary.aggregates) ? summary.aggregates : [];
    return rows.map((row) => {
      const aggregate = row as JsonObject;
      return {
        runId:
          this.stringValue(aggregate.runId) ?? this.stringValue(summary.runId) ?? fallbackRunId,
        armId: this.stringValue(aggregate.armId) ?? 'arm',
        benchmark: this.numberValue(aggregate.benchmark) ?? 0,
        answerMeans: this.recordOfNumbers(aggregate.answerMeans),
        inDepthMeans:
          aggregate.inDepthMeans && typeof aggregate.inDepthMeans === 'object'
            ? this.recordOfNumbers(aggregate.inDepthMeans)
            : undefined,
        harmCount: this.numberValue(aggregate.harmCount) ?? 0,
        confabCount: this.numberValue(aggregate.confabCount) ?? 0
      };
    });
  }

  private correlateTrace(result: StoredResult, traces: JsonObject[]): TraceDto | undefined {
    const started = result.startedAt ? Date.parse(result.startedAt) : undefined;
    const ended = result.endedAt ? Date.parse(result.endedAt) : undefined;
    const match = traces.find((trace) => {
      if (this.stringValue(trace.levelId) !== result.arm.modelName) {
        return false;
      }
      const timestamp = this.stringValue(trace.ts);
      if (!timestamp || !started || !ended) {
        return true;
      }
      const at = Date.parse(timestamp);
      return at >= started - 5000 && at <= ended + 5000;
    });

    if (!match) {
      return undefined;
    }
    return {
      levelId: this.stringValue(match.levelId) ?? result.arm.modelName,
      steps: Array.isArray(match.steps) ? match.steps : [],
      answerConfidenceLevel: this.stringValue(match.answerConfidenceLevel),
      answerConfidenceNote: this.stringValue(match.answerConfidenceNote),
      indepthConfidenceLevel: this.stringValue(match.indepthConfidenceLevel),
      indepthConfidenceNote: this.stringValue(match.indepthConfidenceNote),
      inDepthClaims: Array.isArray(match.inDepthClaims) ? match.inDepthClaims : undefined
    };
  }

  private toArm(value: unknown): ArmDto {
    const arm = value && typeof value === 'object' ? (value as JsonObject) : {};
    const backendId = this.stringValue(arm.backendId) ?? this.stringValue(arm.armId) ?? 'arm';
    const modelName = this.stringValue(arm.modelName) ?? backendId;
    return {
      backendId,
      label: this.stringValue(arm.label) ?? backendId,
      modelName,
      kind: this.stringValue(arm.kind) === 'team' ? 'team' : 'single'
    };
  }

  private toReference(value: unknown, fallbackIdx: number): ResultReferenceDto {
    const reference = value && typeof value === 'object' ? (value as JsonObject) : {};
    return {
      idx: this.numberValue(reference.idx) ?? fallbackIdx,
      resourceType: this.stringValue(reference.resourceType) ?? 'Unknown',
      resourceUuid:
        this.stringValue(reference.resourceUuid) ?? this.stringValue(reference.uuid) ?? '',
      date: this.stringValue(reference.date)
    };
  }

  private async readOptionalJson(path: string): Promise<JsonObject> {
    try {
      await access(path);
      return JSON.parse(await readFile(path, 'utf8')) as JsonObject;
    } catch {
      return {};
    }
  }

  private async readOptionalJsonl(path: string): Promise<JsonObject[]> {
    try {
      await access(path);
      const text = await readFile(path, 'utf8');
      return text
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => JSON.parse(line) as JsonObject);
    } catch {
      return [];
    }
  }

  private stringValue(value: unknown): string | undefined {
    return typeof value === 'string' && value.length > 0 ? value : undefined;
  }

  private numberValue(value: unknown): number | undefined {
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  }

  private recordOfNumbers(value: unknown): Record<string, number> {
    if (!value || typeof value !== 'object') {
      return {};
    }
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).filter(
        (entry): entry is [string, number] => {
          return typeof entry[1] === 'number' && Number.isFinite(entry[1]);
        }
      )
    );
  }
}
