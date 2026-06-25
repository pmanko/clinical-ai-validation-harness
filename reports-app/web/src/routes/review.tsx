import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import type { ReviewsResponseDto } from '@reports/shared';
import { reportsApi } from '../api/client';

export function ReviewRoute() {
  const { runId = '' } = useParams();
  const [reviews, setReviews] = useState<ReviewsResponseDto>({ adjudications: [] });
  const [scenarioId, setScenarioId] = useState('');
  const [armId, setArmId] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [reviewerTier, setReviewerTier] = useState('domain');
  const [note, setNote] = useState('');

  useEffect(() => {
    reportsApi
      .reviews(runId)
      .then(setReviews)
      .catch(() => setReviews({ adjudications: [] }));
  }, [runId]);

  return (
    <main>
      <h1>Review {runId}</h1>
      <form
        aria-label="Score a cell"
        onSubmit={(event) => {
          event.preventDefault();
          reportsApi
            .submitReview(runId, {
              scenarioId,
              armId,
              reviewerId,
              reviewerTier,
              axes: { accuracy: 1, completeness: 1, relevance: 1 },
              harm: false,
              note
            })
            .then(() => reportsApi.reviews(runId).then(setReviews));
        }}
      >
        <h2>Score a cell</h2>
        <label>
          Scenario
          <input value={scenarioId} onChange={(event) => setScenarioId(event.target.value)} />
        </label>
        <label>
          Arm
          <input value={armId} onChange={(event) => setArmId(event.target.value)} />
        </label>
        <label>
          Reviewer
          <input value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} />
        </label>
        <label>
          Tier
          <select value={reviewerTier} onChange={(event) => setReviewerTier(event.target.value)}>
            <option value="owner">owner</option>
            <option value="domain">domain</option>
            <option value="clinical">clinical</option>
          </select>
        </label>
        <label>
          Rationale note
          <textarea value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        <button type="submit">Submit review</button>
      </form>
      {reviews.calibrated ? (
        <section>
          <h2>Calibrated headline</h2>
          <p>
            {reviews.calibrated.subset.label}: {reviews.calibrated.subset.nCells} reviewed cells (
            {reviews.calibrated.subset.tiers.join(', ')})
          </p>
          <pre>{JSON.stringify(reviews.calibrated.estimate, null, 2)}</pre>
        </section>
      ) : (
        <p>No human-reviewed subset yet.</p>
      )}
      {reviews.adjudications.map((review) => (
        <article key={review.id}>
          <h2>
            {review.scenarioId} / {review.armId}
          </h2>
          <p>
            {review.reviewerId} ({review.reviewerTier})
          </p>
          <pre>{JSON.stringify(review.axes, null, 2)}</pre>
          <p>{review.note}</p>
        </article>
      ))}
    </main>
  );
}
