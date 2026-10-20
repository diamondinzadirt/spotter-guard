import type { RoutePlanRequest, RoutePlanResponse } from '@/types';

const makeCheckpoints = (risk: RoutePlanResponse['routes'][number]['overall_risk']) =>
  Array.from({ length: 10 }, (_, index) => {
    const mile = (index + 1) * 50;
    const riskLevel = index < 2 ? 'severe' : index < 4 ? 'high' : index < 6 ? 'moderate' : 'low';
    return {
      id: `${risk}-${mile}`,
      mile,
      arrival_time: new Date(Date.UTC(2026, 9, 19, 14 + Math.floor(mile / 70), (mile % 70) * 0.8)).toISOString(),
      wind_mph: risk === 'no_travel' ? 56 - index * 2 : 40 - index * 3,
      rainfall_in_hr: risk === 'severe' ? Math.max(0.04, 0.42 - index * 0.04) : Math.max(0, 0.22 - index * 0.025),
      snowfall_in_hr: risk === 'no_travel' ? 0.4 : index < 2 ? 0.08 : 0,
      risk_level: risk === 'no_travel' && index < 2 ? 'no_travel' : riskLevel,
      x: 18 + index * 7.1,
      y: 65 - Math.sin(index * 0.9) * 16 - index * 1.8,
    } as const;
  });

const frames = (metric: 'wind' | 'rain' | 'snow') =>
  Array.from({ length: 7 }, (_, frameIndex) => ({
    offset_hours: frameIndex * 8,
    valid_at: new Date(Date.UTC(2026, 9, 19, 14 + frameIndex * 8)).toISOString(),
    points: Array.from({ length: 22 }, (_, index) => ({
      x: 11 + (index % 11) * 7.5,
      y: 25 + Math.floor(index / 11) * 22 + Math.sin(index * 2.4 + frameIndex) * 5,
      intensity: Math.min(1, Math.max(0.12, (metric === 'wind' ? 0.32 : metric === 'rain' ? 0.22 : 0.14) + frameIndex * 0.07 + Math.sin(index + frameIndex) * 0.12)),
      value: Math.round(((metric === 'wind' ? 18 : metric === 'rain' ? 0.08 : 0.2) + frameIndex * (metric === 'wind' ? 2.4 : metric === 'rain' ? 0.035 : 0.18) + Math.sin(index + frameIndex) * (metric === 'wind' ? 4 : 0.04)) * 100) / 100,
      unit: metric === 'wind' ? 'mph' : 'in/hr',
    })),
  }));

export const mockPlanRoutes = async (request: RoutePlanRequest): Promise<RoutePlanResponse> => {
  void request;
  await new Promise((resolve) => setTimeout(resolve, 550));
  return {
    recommended_route_id: 'i70-central',
    routes: [
      {
        id: 'i70-central', name: 'I-70 Central', description: 'Direct interstate run across the central Kansas plains.', distance_miles: 571, duration_minutes: 562, arrival_time: '2026-10-19T23:21:00-06:00', overall_risk: 'severe', severe_miles: 75, high_miles: 84, average_risk: 1.83, recommended: true,
        no_travel_miles: 0, geometry: [{ x: 15, y: 67 }, { x: 26, y: 59 }, { x: 38, y: 55 }, { x: 49, y: 48 }, { x: 61, y: 43 }, { x: 72, y: 34 }, { x: 87, y: 28 }],
        checkpoints: makeCheckpoints('severe'), risk_segments: [{ start_mile: 0, end_mile: 75, risk_level: 'severe' }, { start_mile: 75, end_mile: 159, risk_level: 'high' }, { start_mile: 159, end_mile: 280, risk_level: 'moderate' }, { start_mile: 280, end_mile: 571, risk_level: 'low' }],
      },
      {
        id: 'northern-nebraska', name: 'Northern Nebraska', description: 'Longer northern arc via I-76 and I-80 through Nebraska.', distance_miles: 629, duration_minutes: 651, arrival_time: '2026-10-20T00:50:00-06:00', overall_risk: 'no_travel', severe_miles: 53, high_miles: 17, average_risk: 1.74, recommended: false,
        no_travel_miles: 53, geometry: [{ x: 15, y: 67 }, { x: 24, y: 48 }, { x: 37, y: 31 }, { x: 51, y: 23 }, { x: 67, y: 24 }, { x: 77, y: 33 }, { x: 87, y: 28 }],
        checkpoints: makeCheckpoints('no_travel'), risk_segments: [{ start_mile: 0, end_mile: 53, risk_level: 'no_travel' }, { start_mile: 53, end_mile: 70, risk_level: 'high' }, { start_mile: 70, end_mile: 230, risk_level: 'moderate' }, { start_mile: 230, end_mile: 629, risk_level: 'low' }],
      },
      {
        id: 'southern-plains', name: 'Southern Plains', description: 'Southern detour via Garden City, Dodge City and Wichita.', distance_miles: 640, duration_minutes: 651, arrival_time: '2026-10-20T00:51:00-06:00', overall_risk: 'severe', severe_miles: 104, high_miles: 84, average_risk: 1.82, recommended: false,
        no_travel_miles: 0, geometry: [{ x: 15, y: 67 }, { x: 28, y: 77 }, { x: 42, y: 78 }, { x: 56, y: 72 }, { x: 67, y: 59 }, { x: 78, y: 47 }, { x: 87, y: 28 }],
        checkpoints: makeCheckpoints('severe'), risk_segments: [{ start_mile: 0, end_mile: 104, risk_level: 'severe' }, { start_mile: 104, end_mile: 188, risk_level: 'high' }, { start_mile: 188, end_mile: 340, risk_level: 'moderate' }, { start_mile: 340, end_mile: 640, risk_level: 'low' }],
      },
    ],
    weather_frames: { wind: frames('wind'), rain: frames('rain'), snow: frames('snow') },
  };
};
