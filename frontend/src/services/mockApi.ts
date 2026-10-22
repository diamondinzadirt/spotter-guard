import type { RoutePlanRequest, RoutePlanResponse } from '@/types';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const planRoutes = async (request: RoutePlanRequest, options?: { signal?: AbortSignal }): Promise<RoutePlanResponse> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/routes/plan`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal: options?.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Unable to reach the route-planning service. Check your connection and retry.');
  }
  let payload: RoutePlanResponse | { error?: { code?: string; message?: string } };
  try {
    payload = await response.json() as RoutePlanResponse | { error?: { code?: string; message?: string } };
  } catch {
    throw new Error('The route-planning service returned an invalid response. Retry the analysis.');
  }
  if (!response.ok) throw new Error(payload && 'error' in payload ? payload.error?.message ?? 'Route planning failed. Check your inputs and retry.' : 'Route planning failed. Check your inputs and retry.');
  if (!('routes' in payload) || !Array.isArray(payload.routes) || !('weather_frames' in payload)) throw new Error('The route-planning response was incomplete. Retry the analysis.');
  return payload as RoutePlanResponse;
};
