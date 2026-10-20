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

## Phase 1 backend status

The Django foundation validates this request shape at `POST /api/routes/plan`. Until real routing and weather providers are configured, a valid request returns HTTP `503` with `{ "error": { "code": "provider_not_configured", "message": "..." } }`; it never presents fabricated weather or route data as live results.

## Risk implementation interpretation

The backend implements the authoritative assessment thresholds with continuous boundary conventions: wind is low `<25`, moderate `25–<35`, high `35–<45`, severe `45–<55`, and no travel `>=55` mph. Rain is low `<0.10`, moderate `0.10–<0.25`, high `0.25–<0.50`, severe `0.50–1.00`, and no travel `>1.00` in/hr. Snow is low `<0.5`, moderate `0.5–<1.0`, high `1.0–<2.0`, severe `2.0–3.0`, and no travel `>3.0` in/hr.

Load rules are limited to the specified wind overrides: wind `>=55` is always no travel; wind `>=45` and `<55` with load `>30,000 lb` is no travel; wind `>=35` and `<45` with load `>40,000 lb` is severe. Equality at 30,000 lb and 40,000 lb does not trigger an override.

When multiple weather dimensions apply, the highest classification is used. Route recommendation remains lexicographic by severe miles, high miles, average risk, then duration. The treatment of no-travel mileage in that ordering was not separately specified; the backend does not invent a new ranking criterion and currently expects no-travel segments to be represented in the existing route risk totals for product confirmation.

## Phase 2 routing status

The backend includes a HERE Routing API v8 truck adapter in `backend/spotter/providers.py`. It requests `transportMode=truck`, the submitted gross weight, departure time, and `alternatives=2` (three total routes including the primary). Address inputs are geocoded through HERE when they are not already `lat,lng` pairs. HERE Flexible Polyline geometry is decoded into timezone-aware route candidates, and `backend/spotter/geometry.py` interpolates interval checkpoints using cumulative geometry distance and route duration.

The existing plan response also requires weather-derived risk fields. Because live weather integration remains out of scope, the API continues to return a provider configuration error instead of presenting routing-only results as complete risk-aware plans. The next provider integration must supply route-time weather readings before this endpoint can safely emit the full response.

Provider requirements: set `HERE_API_KEY` in the backend environment and keep it out of Git. HERE account plan, request quotas, truck-routing availability, geocoding charges, and alternative-route limits must be confirmed against the active HERE agreement before production deployment; this repository does not assume a free tier or fixed pricing.
