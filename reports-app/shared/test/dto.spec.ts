import { describe, expect, it } from 'vitest';

import type { CalibratedHeadlineDto } from '../src/dto';

describe('shared DTO contracts', () => {
  it('represents the calibrated headline subset explicitly', () => {
    const calibrated: CalibratedHeadlineDto = {
      subset: { label: 'reviewed-cells', nCells: 1, tiers: ['clinical'] },
      estimate: { accuracy: 1 },
      uncertainty: { method: 'single-reviewer' }
    };

    expect(calibrated.subset).toMatchObject({ label: 'reviewed-cells', nCells: 1 });
  });
});
