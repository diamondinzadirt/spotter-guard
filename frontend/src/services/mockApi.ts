import type { RoutePlanRequest, RoutePlanResponse } from '@/types';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const planRoutes = async (request: RoutePlanRequest): Promise<RoutePlanResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/routes/plan`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
  });
  const payload = await response.json() as RoutePlanResponse | { error?: { code?: string; message?: string } };
  if (!response.ok) throw new Error(payload && 'error' in payload ? payload.error?.message ?? 'Route planning failed' : 'Route planning failed');
  return payload as RoutePlanResponse;
};
