export type ArmKind = 'single' | 'team';
export type ReviewerTier = 'owner' | 'domain' | 'clinical';

export interface ArmDto {
  backendId: string;
  label: string;
  modelName: string;
  kind: ArmKind;
}

export interface ArmAggregateDto {
  runId: string;
  armId: string;
  benchmark: number;
  answerMeans: Record<string, number>;
  inDepthMeans?: Record<string, number>;
  harmCount: number;
  confabCount: number;
}

export interface ResultReferenceDto {
  idx: number;
  resourceType: string;
  resourceUuid: string;
  date?: string;
}

export interface TraceDto {
  levelId: string;
  steps: unknown[];
  answerConfidenceLevel?: string;
  answerConfidenceNote?: string;
  indepthConfidenceLevel?: string;
  indepthConfidenceNote?: string;
  inDepthClaims?: unknown[];
}

export interface JudgeDto {
  accuracy?: number;
  completeness?: number;
  relevance?: number;
  abstentionOutcome?: string;
  citationGroundedness?: string;
  harm?: boolean;
  temporalDateAccuracy?: string;
  temporalWindow?: string;
  temporalTrend?: string;
  citationResolution?: unknown;
  note?: string;
  background?: unknown;
}

export interface AdjudicationDto {
  id: string;
  runId: string;
  scenarioId: string;
  armId: string;
  reviewerId: string;
  reviewerTier: ReviewerTier;
  axes: Record<string, number>;
  harm: boolean;
  note: string;
  judgedAt: string;
}

export interface ReportCellDto {
  scenarioId: string;
  arm: ArmDto;
  turn: number;
  answer: string;
  references: ResultReferenceDto[];
  trace?: TraceDto;
  indepth?: unknown;
  judge?: JudgeDto;
  adjudications: AdjudicationDto[];
  confidence?: unknown;
  scored: boolean;
}

export interface ScenarioReportDto {
  scenarioId: string;
  turns: Array<{ n: number; question: string }>;
  cells: ReportCellDto[];
}

export interface RunHeaderDto {
  runId: string;
  comparisonSet: string;
  referenceDate?: string;
  status: 'ingesting' | 'answered' | 'scored' | 'published' | 'reviewed';
  parentRunId?: string;
  arms: ArmDto[];
  nScenarios: number;
  gitSha?: string;
  generatedAt?: string;
}

export interface RunReportDto {
  run: RunHeaderDto;
  armAggregates: ArmAggregateDto[];
  scenarios: ScenarioReportDto[];
}

export interface CatalogItemDto {
  slug: string;
  runId: string;
  title: string;
  summary?: string;
  takeaway?: string;
  arms: ArmDto[];
  nQuestions: number;
  date?: string;
  headline: ArmAggregateDto[];
  featured: boolean;
  hidden: boolean;
  sortOrder: number;
  hasLive: boolean;
}

export interface CatalogMetaDto {
  intro: string;
  scoringNote: string;
}

export interface CalibratedHeadlineDto {
  subset: {
    label: string;
    nCells: number;
    tiers: ReviewerTier[];
  };
  estimate: Record<string, number>;
  uncertainty: {
    method: string;
    value?: number;
    interval?: [number, number];
  };
}

export interface ReviewsResponseDto {
  adjudications: AdjudicationDto[];
  calibrated?: CalibratedHeadlineDto;
}

export interface LiveCellEventDto {
  scenarioId: string;
  armId: string;
  turn: number;
  status: string;
  latencyMs?: number;
}
