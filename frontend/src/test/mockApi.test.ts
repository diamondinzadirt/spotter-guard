import { afterEach, describe, expect, it, vi } from 'vitest';
import { planRoutes } from '@/services/mockApi';
import type { RoutePlanRequest } from '@/types';

const request: RoutePlanRequest = {
  origin: 'Denver, CO', destination: 'Kansas City, MO', departure_time: '2026-10-23T12:00:00.000Z', load_weight_lb: 42000, checkpoint_interval_miles: 10,
};

afterEach(() => vi.restoreAllMocks());

describe('route planning adapter', () => {
  it('serializes the selected journey and interval', async () => {
    const response = { ok: true, json: vi.fn().mockResolvedValue({ routes: [], weather_frames: {} }) } as unknown as Response;
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);
    await planRoutes(request);
    expect(fetchMock).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ body: JSON.stringify(request), method: 'POST' }));
  });

  it('rejects incomplete successful responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: () => Promise.resolve({ routes: [] }) } as Response);
    await expect(planRoutes(request)).rejects.toThrow('response was incomplete');
  });

  it('reports network failures clearly', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'));
    await expect(planRoutes(request)).rejects.toThrow('Unable to reach the route-planning service');
  });
});
