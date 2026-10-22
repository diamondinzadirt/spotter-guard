import { describe, expect, it } from 'vitest';
import { CITIES_BY_STATE } from '@/data/cities';
import { US_STATES } from '@/data/states';

describe('curated location selectors', () => {
  it('contains every state plus DC and the required defaults', () => {
    expect(US_STATES).toHaveLength(51);
    expect(CITIES_BY_STATE.CO).toContain('Denver');
    expect(CITIES_BY_STATE.MO).toContain('Kansas City');
    expect(CITIES_BY_STATE.KS).toContain('Kansas City');
    expect(CITIES_BY_STATE.MO).not.toEqual(CITIES_BY_STATE.KS);
  });

  it('keeps city choices state-scoped', () => {
    expect(CITIES_BY_STATE.CO).not.toContain('Kansas City');
    expect(CITIES_BY_STATE.MO).toContain('St. Louis');
  });
});
