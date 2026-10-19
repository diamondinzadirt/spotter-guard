export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel';
export type WeatherMetric = 'wind' | 'rain' | 'snow';

export interface Checkpoint {
  id: string;
  mile: number;
  arrival_time: string;
  wind_mph: number;
  rainfall_in_hr: number;
  snowfall_in_hr: number;
  risk_level: RiskLevel;
  x: number;
  y: number;
}

export interface RiskSegment {
  start_mile: number;
  end_mile: number;
  risk_level: RiskLevel;
}

export interface WeatherFrame {
  offset_hours: number;
  valid_at: string;
  points: { x: number; y: number; intensity: number }[];
}

export interface RouteOption {
  id: string;
  name: string;
  description: string;
  distance_miles: number;
  duration_minutes: number;
  arrival_time: string;
  overall_risk: RiskLevel;
  severe_miles: number;
  high_miles: number;
  average_risk: number;
  recommended: boolean;
  geometry: { x: number; y: number }[];
  checkpoints: Checkpoint[];
  risk_segments: RiskSegment[];
}

export interface RoutePlanResponse {
  routes: RouteOption[];
  recommended_route_id: string;
  weather_frames: Record<WeatherMetric, WeatherFrame[]>;
}

export interface RoutePlanRequest {
  origin: string;
  destination: string;
  departure_time: string;
  load_weight_lb: number;
  checkpoint_interval_miles: 10 | 25 | 50;
}

export interface ServiceError {
  code: string;
  message: string;
}
