import type { RoutePlanRequest, RoutePlanResponse } from '@/types';
import { mockPlanRoutes } from '@/mocks/mockApi';

export const planRoutes = (request: RoutePlanRequest): Promise<RoutePlanResponse> => mockPlanRoutes(request);
