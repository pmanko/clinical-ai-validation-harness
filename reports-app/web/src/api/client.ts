import type {
  CatalogItemDto,
  CatalogMetaDto,
  ReviewsResponseDto,
  RunReportDto
} from '@reports/shared';

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const reportsApi = {
  catalog: () => getJson<CatalogItemDto[]>('/api/catalog'),
  catalogMeta: () => getJson<CatalogMetaDto>('/api/catalog/meta'),
  publish: async (body: {
    runId: string;
    slug: string;
    title?: string;
    summary?: string;
    takeaway?: string;
  }) => {
    const response = await fetch('/api/catalog', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      throw new Error(`Publish failed: ${response.status}`);
    }
    return (await response.json()) as CatalogItemDto;
  },
  curate: async (slug: string, body: Partial<CatalogItemDto>) => {
    const response = await fetch(`/api/catalog/${slug}`, {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      throw new Error(`Curate failed: ${response.status}`);
    }
    return (await response.json()) as CatalogItemDto;
  },
  report: (runId: string) => getJson<RunReportDto>(`/api/runs/${runId}/report`),
  reviews: (runId: string) => getJson<ReviewsResponseDto>(`/api/runs/${runId}/reviews`),
  submitReview: async (
    runId: string,
    body: {
      scenarioId: string;
      armId: string;
      reviewerId: string;
      reviewerTier: string;
      axes: Record<string, number>;
      harm: boolean;
      note: string;
    }
  ) => {
    const response = await fetch(`/api/runs/${runId}/reviews`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      throw new Error(`Review failed: ${response.status}`);
    }
    return (await response.json()) as { calibrated?: ReviewsResponseDto['calibrated'] };
  },
  exportRun: (runId: string) => getJson<RunReportDto>(`/api/runs/${runId}/export`)
};
