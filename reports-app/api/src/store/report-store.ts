import type {
  AdjudicationDto,
  ArmAggregateDto,
  ArmDto,
  CatalogItemDto,
  CatalogMetaDto,
  JudgeDto,
  ReportCellDto,
  ResultReferenceDto,
  RunHeaderDto,
  RunReportDto,
  ScenarioReportDto,
  TraceDto
} from '@reports/shared';

export interface StoredRun {
  runId: string;
  comparisonSetId: string;
  runDir: string;
  parentRunId?: string;
  gitSha?: string;
  datasetVersion?: string;
  schemaMappingVersion?: string;
  evidenceStatus?: string;
  referenceDate?: string;
  startedAt?: string;
  completedAt?: string;
  generatedAt?: string;
}

export interface StoredResult {
  id: string;
  runId: string;
  scenarioId: string;
  question: string;
  turn: number;
  arm: ArmDto;
  answer: string;
  references: ResultReferenceDto[];
  trace?: TraceDto;
  indepth?: unknown;
  responseModel?: string;
  startedAt?: string;
  endedAt?: string;
  latencyMs?: number;
}

export interface StoredJudgeRow extends JudgeDto {
  runId: string;
  scenarioId: string;
  armId: string;
}

export interface StoreSnapshot {
  runs: StoredRun[];
  results: StoredResult[];
  judges: StoredJudgeRow[];
  aggregates: ArmAggregateDto[];
  catalog: CatalogItemDto[];
  reviews: AdjudicationDto[];
}

export class InMemoryReportStore {
  private runs = new Map<string, StoredRun>();
  private results = new Map<string, StoredResult>();
  private judges = new Map<string, StoredJudgeRow>();
  private aggregates = new Map<string, ArmAggregateDto>();
  private catalog = new Map<string, CatalogItemDto>();
  private reviews = new Map<string, AdjudicationDto>();
  private catalogMeta: CatalogMetaDto = {
    intro: 'Validation run reports',
    scoringNote: 'Automated score aggregates are ingested from producer artifacts.'
  };

  upsertRun(run: StoredRun) {
    this.runs.set(run.runId, { ...this.runs.get(run.runId), ...run });
  }

  upsertResult(result: StoredResult) {
    this.results.set(result.id, result);
  }

  upsertJudge(row: StoredJudgeRow) {
    this.judges.set(`${row.runId}:${row.scenarioId}:${row.armId}`, row);
  }

  upsertAggregate(aggregate: ArmAggregateDto) {
    this.aggregates.set(`${aggregate.runId}:${aggregate.armId}`, aggregate);
  }

  upsertCatalogItem(item: CatalogItemDto) {
    this.catalog.set(item.slug, item);
  }

  getCatalogItem(slug: string): CatalogItemDto | undefined {
    return this.catalog.get(slug);
  }

  patchCatalogItem(slug: string, patch: Partial<CatalogItemDto>): CatalogItemDto {
    const current = this.catalog.get(slug);
    if (!current) {
      throw new Error(`Unknown catalog slug: ${slug}`);
    }
    const updated = { ...current, ...patch, slug: current.slug, runId: current.runId };
    this.catalog.set(slug, updated);
    return updated;
  }

  getCatalog(includeHidden = false): CatalogItemDto[] {
    return [...this.catalog.values()]
      .filter((item) => includeHidden || !item.hidden)
      .sort((a, b) => a.sortOrder - b.sortOrder || a.title.localeCompare(b.title));
  }

  listRuns(): RunHeaderDto[] {
    return [...this.runs.keys()].map((runId) => this.getRun(runId));
  }

  getCatalogMeta(): CatalogMetaDto {
    return this.catalogMeta;
  }

  setCatalogMeta(meta: CatalogMetaDto) {
    this.catalogMeta = meta;
  }

  addReview(review: AdjudicationDto) {
    this.reviews.set(review.id, review);
  }

  getReviews(runId: string): AdjudicationDto[] {
    return [...this.reviews.values()].filter((review) => review.runId === runId);
  }

  getRun(runId: string): RunHeaderDto {
    const run = this.mustRun(runId);
    const resultRunId = this.resultRunIdFor(run);
    const results = this.resultsForRun(resultRunId);
    const arms = this.uniqueArms(results);
    const aggregateCount = this.aggregatesForRun(run.runId).length;
    const reviewCount = this.getReviews(run.runId).length;
    const status: RunHeaderDto['status'] =
      reviewCount > 0
        ? 'reviewed'
        : this.catalogHasRun(run.runId)
          ? 'published'
          : aggregateCount > 0
            ? 'scored'
            : results.length > 0
              ? 'answered'
              : 'ingesting';

    return {
      runId: run.runId,
      comparisonSet: run.comparisonSetId,
      referenceDate: run.referenceDate,
      status,
      parentRunId: run.parentRunId,
      arms,
      nScenarios: new Set(results.map((result) => result.scenarioId)).size,
      gitSha: run.gitSha,
      generatedAt: run.generatedAt
    };
  }

  getReport(runId: string): RunReportDto {
    const run = this.mustRun(runId);
    const resultRunId = this.resultRunIdFor(run);
    const results = this.resultsForRun(resultRunId);
    const reviews = this.getReviews(runId);
    const scenarios = new Map<string, ScenarioReportDto>();

    for (const result of results) {
      const judge = this.judges.get(`${run.runId}:${result.scenarioId}:${result.arm.backendId}`);
      const scenario = scenarios.get(result.scenarioId) ?? {
        scenarioId: result.scenarioId,
        turns: [{ n: result.turn, question: result.question }],
        cells: []
      };
      if (!scenario.turns.some((turn) => turn.n === result.turn)) {
        scenario.turns.push({ n: result.turn, question: result.question });
      }
      const cellReviews = reviews.filter(
        (review) => review.scenarioId === result.scenarioId && review.armId === result.arm.backendId
      );
      const cell: ReportCellDto = {
        scenarioId: result.scenarioId,
        arm: result.arm,
        turn: result.turn,
        answer: result.answer,
        references: result.references,
        trace: result.trace,
        indepth: result.indepth,
        judge,
        adjudications: cellReviews,
        scored: Boolean(judge)
      };
      scenario.cells.push(cell);
      scenario.cells.sort(
        (a, b) => a.turn - b.turn || a.arm.backendId.localeCompare(b.arm.backendId)
      );
      scenarios.set(result.scenarioId, scenario);
    }

    return {
      run: this.getRun(runId),
      armAggregates: this.aggregatesForRun(run.runId),
      scenarios: [...scenarios.values()].sort((a, b) => a.scenarioId.localeCompare(b.scenarioId))
    };
  }

  getExport(runId: string): RunReportDto {
    return this.getReport(runId);
  }

  snapshot(): StoreSnapshot {
    return {
      runs: [...this.runs.values()],
      results: [...this.results.values()],
      judges: [...this.judges.values()],
      aggregates: [...this.aggregates.values()],
      catalog: [...this.catalog.values()],
      reviews: [...this.reviews.values()]
    };
  }

  restore(snapshot: Partial<StoreSnapshot>) {
    for (const run of snapshot.runs ?? []) {
      this.runs.set(run.runId, run);
    }
    for (const result of snapshot.results ?? []) {
      this.results.set(result.id, result);
    }
    for (const judge of snapshot.judges ?? []) {
      this.judges.set(`${judge.runId}:${judge.scenarioId}:${judge.armId}`, judge);
    }
    for (const aggregate of snapshot.aggregates ?? []) {
      this.aggregates.set(`${aggregate.runId}:${aggregate.armId}`, aggregate);
    }
    for (const item of snapshot.catalog ?? []) {
      this.catalog.set(item.slug, item);
    }
    for (const review of snapshot.reviews ?? []) {
      this.reviews.set(review.id, review);
    }
  }

  private mustRun(runId: string): StoredRun {
    const run = this.runs.get(runId);
    if (!run) {
      throw new Error(`Unknown run: ${runId}`);
    }
    return run;
  }

  private resultRunIdFor(run: StoredRun): string {
    return run.parentRunId && !this.resultsForRun(run.runId).length ? run.parentRunId : run.runId;
  }

  private resultsForRun(runId: string): StoredResult[] {
    return [...this.results.values()]
      .filter((result) => result.runId === runId)
      .sort((a, b) => a.scenarioId.localeCompare(b.scenarioId) || a.turn - b.turn);
  }

  private aggregatesForRun(runId: string): ArmAggregateDto[] {
    return [...this.aggregates.values()].filter((aggregate) => aggregate.runId === runId);
  }

  private uniqueArms(results: StoredResult[]): ArmDto[] {
    const arms = new Map<string, ArmDto>();
    for (const result of results) {
      arms.set(result.arm.backendId, result.arm);
    }
    return [...arms.values()];
  }

  private catalogHasRun(runId: string): boolean {
    return [...this.catalog.values()].some((item) => item.runId === runId);
  }
}
