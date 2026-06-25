import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ReportRoute } from '../src/routes/report';

describe('report rendering', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders team-arm traces and answered-but-not-scored cells through the report route', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          run: {
            runId: 'run-a',
            comparisonSet: 'demo',
            status: 'scored',
            arms: [
              {
                backendId: 'team-arm',
                label: 'Team Arm',
                modelName: 'served-model-team',
                kind: 'team'
              }
            ],
            nScenarios: 2
          },
          armAggregates: [
            {
              runId: 'run-a',
              armId: 'team-arm',
              benchmark: 0.93,
              answerMeans: { accuracy: 1 },
              harmCount: 0,
              confabCount: 0
            }
          ],
          scenarios: [
            {
              scenarioId: 'scenario-1',
              turns: [{ n: 1, question: 'What medications are active?' }],
              cells: [
                {
                  scenarioId: 'scenario-1',
                  arm: {
                    backendId: 'team-arm',
                    label: 'Team Arm',
                    modelName: 'served-model-team',
                    kind: 'team'
                  },
                  turn: 1,
                  answer: 'The patient is taking metformin.',
                  references: [
                    { idx: 0, resourceType: 'MedicationRequest', resourceUuid: 'med-1' }
                  ],
                  trace: {
                    levelId: 'served-model-team',
                    steps: [{ role: 'retrieval', note: 'Found MedicationRequest/med-1' }]
                  },
                  judge: { accuracy: 1, completeness: 1, relevance: 1 },
                  adjudications: [],
                  scored: true
                }
              ]
            },
            {
              scenarioId: 'scenario-2',
              turns: [{ n: 1, question: 'What allergies are recorded?' }],
              cells: [
                {
                  scenarioId: 'scenario-2',
                  arm: {
                    backendId: 'team-arm',
                    label: 'Team Arm',
                    modelName: 'served-model-team',
                    kind: 'team'
                  },
                  turn: 1,
                  answer: 'No allergies were found.',
                  references: [],
                  adjudications: [],
                  scored: false
                }
              ]
            }
          ]
        })
      }))
    );

    const router = createMemoryRouter([{ path: '/runs/:runId', element: <ReportRoute /> }], {
      initialEntries: ['/runs/run-a']
    });
    render(<RouterProvider router={router} />);

    expect(await screen.findByText('The patient is taking metformin.')).toBeInTheDocument();
    expect(screen.getByLabelText('Trace for served-model-team')).toBeInTheDocument();
    expect(screen.getByText('answered, not scored')).toBeInTheDocument();
  });
});
