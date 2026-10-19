# Spotter Guard API Contract

## Request

`POST /api/routes/plan`

```json
{
  "origin": "Denver, CO",
  "destination": "Kansas City, MO",
  "departure_time": "2026-10-19T14:00:00-06:00",
  "load_weight_lb": 42000,
  "checkpoint_interval_miles": 25
}
```

All fields use snake_case. `departure_time` is a timezone-aware ISO 8601 timestamp. Distances are miles, duration is minutes, wind is miles per hour, and precipitation is inches per hour.

## Response

The response is a `RoutePlanResponse` with `routes`, `recommended_route_id`, and time-indexed `weather_frames`. Each route includes a GeoJSON-ready route geometry, arrival ETA, checkpoint readings, risk segments, severe/high mileage totals, average risk, and overall risk. Risk values are `low`, `moderate`, `high`, `severe`, or `no_travel`.

The frontend currently uses the mock adapter behind the same service boundary. Set `VITE_API_BASE_URL` to connect the future Django API; the HTTP adapter can replace `planRoutes` without changing views.
