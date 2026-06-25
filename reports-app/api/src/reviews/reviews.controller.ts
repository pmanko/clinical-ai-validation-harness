import { Body, Controller, Get, Param, Post } from '@nestjs/common';
import { randomUUID } from 'node:crypto';

import type { AdjudicationDto, CalibratedHeadlineDto, ReviewerTier } from '@reports/shared';
import { InMemoryReportStore } from '../store/report-store.js';

interface ReviewBody {
  scenarioId: string;
  armId: string;
  reviewerId: string;
  reviewerTier?: ReviewerTier;
  axes: Record<string, number>;
  harm: boolean;
  note: string;
}

@Controller('runs/:runId/reviews')
export class ReviewsController {
  constructor(private readonly store: InMemoryReportStore) {}

  @Get()
  list(@Param('runId') runId: string) {
    const adjudications = this.store.getReviews(runId);
    return {
      adjudications,
      calibrated: this.calibrated(adjudications)
    };
  }

  @Post()
  create(@Param('runId') runId: string, @Body() body: ReviewBody) {
    const adjudication: AdjudicationDto = {
      id: randomUUID(),
      runId,
      scenarioId: body.scenarioId,
      armId: body.armId,
      reviewerId: body.reviewerId,
      reviewerTier: body.reviewerTier ?? 'domain',
      axes: body.axes,
      harm: body.harm,
      note: body.note,
      judgedAt: new Date().toISOString()
    };
    this.store.addReview(adjudication);
    return {
      adjudication,
      calibrated: this.calibrated(this.store.getReviews(runId))
    };
  }

  private calibrated(adjudications: AdjudicationDto[]): CalibratedHeadlineDto | undefined {
    if (adjudications.length === 0) {
      return undefined;
    }
    const axisNames = [...new Set(adjudications.flatMap((review) => Object.keys(review.axes)))];
    const estimate = Object.fromEntries(
      axisNames.map((axis) => {
        const values = adjudications
          .map((review) => review.axes[axis])
          .filter((value) => typeof value === 'number' && Number.isFinite(value));
        const mean = values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
        return [axis, Number(mean.toFixed(4))];
      })
    );
    const tiers = [...new Set(adjudications.map((review) => review.reviewerTier))];
    return {
      subset: {
        label: 'reviewed-cells',
        nCells: new Set(adjudications.map((review) => `${review.scenarioId}:${review.armId}`)).size,
        tiers
      },
      estimate,
      uncertainty: {
        method: adjudications.length > 1 ? 'reviewed-subset-range' : 'single-reviewer'
      }
    };
  }
}
