import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import type { CatalogItemDto } from '@reports/shared';
import { reportsApi } from '../api/client';
import { ArmCard, ScoreTable } from '../components';

export function CatalogRoute() {
  const [items, setItems] = useState<CatalogItemDto[]>([]);
  const [modelFilter, setModelFilter] = useState('');
  const [publishRunId, setPublishRunId] = useState('');
  const [publishSlug, setPublishSlug] = useState('');
  const [publishTitle, setPublishTitle] = useState('');

  useEffect(() => {
    reportsApi
      .catalog()
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  const filtered = useMemo(
    () =>
      items.filter(
        (item) =>
          !modelFilter ||
          item.arms.some(
            (arm) => arm.backendId.includes(modelFilter) || arm.modelName.includes(modelFilter)
          )
      ),
    [items, modelFilter]
  );

  return (
    <main>
      <h1>Validation Reports</h1>
      <form
        aria-label="Publish run"
        onSubmit={(event) => {
          event.preventDefault();
          reportsApi
            .publish({
              runId: publishRunId,
              slug: publishSlug,
              title: publishTitle || publishSlug
            })
            .then((item) => setItems((current) => [...current, item]));
        }}
      >
        <h2>Publish a run</h2>
        <label>
          Run ID
          <input value={publishRunId} onChange={(event) => setPublishRunId(event.target.value)} />
        </label>
        <label>
          Slug
          <input value={publishSlug} onChange={(event) => setPublishSlug(event.target.value)} />
        </label>
        <label>
          Title
          <input value={publishTitle} onChange={(event) => setPublishTitle(event.target.value)} />
        </label>
        <button type="submit">Publish</button>
      </form>
      <label>
        Filter by model or arm
        <input value={modelFilter} onChange={(event) => setModelFilter(event.target.value)} />
      </label>
      {filtered.map((item) => (
        <article key={item.slug}>
          <h2>
            <Link to={`/runs/${item.runId}`}>{item.title}</Link>
          </h2>
          {item.summary ? <p>{item.summary}</p> : null}
          <label>
            Title
            <input
              defaultValue={item.title}
              onBlur={(event) =>
                reportsApi
                  .curate(item.slug, { title: event.target.value })
                  .then((updated) =>
                    setItems((current) =>
                      current.map((candidate) =>
                        candidate.slug === updated.slug ? updated : candidate
                      )
                    )
                  )
              }
            />
          </label>
          <label>
            Summary
            <textarea
              defaultValue={item.summary}
              onBlur={(event) =>
                reportsApi
                  .curate(item.slug, { summary: event.target.value })
                  .then((updated) =>
                    setItems((current) =>
                      current.map((candidate) =>
                        candidate.slug === updated.slug ? updated : candidate
                      )
                    )
                  )
              }
            />
          </label>
          <label>
            Takeaway
            <textarea
              defaultValue={item.takeaway}
              onBlur={(event) =>
                reportsApi
                  .curate(item.slug, { takeaway: event.target.value })
                  .then((updated) =>
                    setItems((current) =>
                      current.map((candidate) =>
                        candidate.slug === updated.slug ? updated : candidate
                      )
                    )
                  )
              }
            />
          </label>
          <div>
            {item.arms.map((arm) => (
              <ArmCard key={arm.backendId} arm={arm} />
            ))}
          </div>
          <ScoreTable aggregates={item.headline} />
          <button
            type="button"
            onClick={() =>
              reportsApi
                .curate(item.slug, { featured: !item.featured })
                .then((updated) =>
                  setItems((current) =>
                    current.map((candidate) =>
                      candidate.slug === updated.slug ? updated : candidate
                    )
                  )
                )
            }
          >
            {item.featured ? 'Unfeature' : 'Feature'}
          </button>
          <button
            type="button"
            onClick={() =>
              reportsApi
                .curate(item.slug, { hidden: true })
                .then((updated) =>
                  setItems((current) =>
                    current.map((candidate) =>
                      candidate.slug === updated.slug ? updated : candidate
                    )
                  )
                )
            }
          >
            Hide
          </button>
          <button
            type="button"
            onClick={() =>
              reportsApi
                .curate(item.slug, { sortOrder: item.sortOrder - 1 })
                .then((updated) =>
                  setItems((current) =>
                    current.map((candidate) =>
                      candidate.slug === updated.slug ? updated : candidate
                    )
                  )
                )
            }
          >
            Move up
          </button>
        </article>
      ))}
    </main>
  );
}
