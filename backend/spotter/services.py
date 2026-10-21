import os
import math
from dataclasses import replace
from datetime import timedelta

from .demo import demo_routes
from .geometry import checkpoints, enrich_geometry
from .providers import ProviderError, ProviderNotConfigured, HereRoutingProvider
from .risk import RiskLevel, RiskReading, classify_risk, recommendation_key
from .weather import weather_provider_for_mode


RISK_VALUE = {RiskLevel.LOW: 0, RiskLevel.MODERATE: 1, RiskLevel.HIGH: 2, RiskLevel.SEVERE: 3, RiskLevel.NO_TRAVEL: 4}


def _route_geometry(route):
    return [{"x": point.longitude, "y": point.latitude} for point in route.geometry]


def _risk_for_route(route, weather_provider, request):
    route_checkpoints = checkpoints(route, request["checkpoint_interval_miles"])
    readings = weather_provider.readings(route, request["departure_time"])
    if not readings:
        raise ProviderError(f"No weather readings available for route {route.id}")
    timed = []
    for item in route_checkpoints:
        nearest = min(readings, key=lambda reading: abs(reading.mile - item["mile"]))
        risk = classify_risk(RiskReading(nearest.wind_mph, nearest.rainfall_in_hr, nearest.snowfall_in_hr), request["load_weight_lb"])
        timed.append({**item, "id": f"{route.id}-{item['mile']}", "x": item["longitude"], "y": item["latitude"], "wind_mph": nearest.wind_mph, "rainfall_in_hr": nearest.rainfall_in_hr, "snowfall_in_hr": nearest.snowfall_in_hr, "risk_level": risk.value})
    segments = []
    for first, second in zip(timed, timed[1:]):
        segments.append({"start_mile": first["mile"], "end_mile": second["mile"], "risk_level": second["risk_level"]})
    severe_miles = high_miles = no_travel_miles = weighted_risk = 0.0
    for segment in segments:
        miles = segment["end_mile"] - segment["start_mile"]
        risk = RiskLevel(segment["risk_level"])
        weighted_risk += miles * RISK_VALUE[risk]
        if risk == RiskLevel.SEVERE:
            severe_miles += miles
        elif risk == RiskLevel.HIGH:
            high_miles += miles
        elif risk == RiskLevel.NO_TRAVEL:
            no_travel_miles += miles
    total_miles = timed[-1]["mile"] if timed else route.distance_miles
    max_risk = max((RiskLevel(item["risk_level"]) for item in timed), key=RISK_VALUE.__getitem__) if timed else RiskLevel.LOW
    return {
        "id": route.id, "name": route.name, "description": route.description,
        "distance_miles": route.distance_miles, "duration_minutes": route.duration_minutes,
        "departure_time": route.departure_time.isoformat(), "arrival_time": route.arrival_time.isoformat(),
        "overall_risk": max_risk.value, "severe_miles": round(severe_miles, 2), "high_miles": round(high_miles, 2),
        "no_travel_miles": round(no_travel_miles, 2), "average_risk": round(weighted_risk / total_miles, 3) if total_miles else 0,
        "recommended": False, "geometry": _route_geometry(route), "checkpoints": timed, "risk_segments": segments,
        "geojson_geometry": {"type": "LineString", "coordinates": [[point.longitude, point.latitude] for point in route.geometry]},
    }


def _weather_frames(route, weather_provider):
    forecast_reader = getattr(weather_provider, "forecast_readings", None)
    if forecast_reader:
        reading_frames = forecast_reader(route, [offset * 8 for offset in range(7)])
    else:
        reading_frames = [weather_provider.readings(route, route.departure_time)] * 7
    readings = [] if forecast_reader else weather_provider.readings(route, route.departure_time)
    frames = {"wind": [], "rain": [], "snow": []}
    for offset in range(7):
        valid_at = (route.departure_time + timedelta(hours=offset * 8)).isoformat()
        frame_readings = reading_frames[offset]
        if forecast_reader and frame_readings:
            valid_at = frame_readings[0].valid_at.isoformat()
        for metric in frames:
            points = []
            for reading in (frame_readings or readings):
                if forecast_reader:
                    value = {"wind": reading.wind_mph / 60, "rain": reading.rainfall_in_hr, "snow": reading.snowfall_in_hr / 3}[metric]
                    measurement = {"wind": reading.wind_mph, "rain": reading.rainfall_in_hr, "snow": reading.snowfall_in_hr}[metric]
                    points.append({"x": reading.x, "y": reading.y, "intensity": min(1, max(0, value)), "value": round(measurement, 3), "unit": "mph" if metric == "wind" else "in/hr"})
                    continue
                base = {"wind": reading.wind_mph / 60, "rain": reading.rainfall_in_hr / 1.0, "snow": reading.snowfall_in_hr / 3.0}[metric]
                spatial_variation = 1 + 0.22 * math.sin(reading.x * 3 + reading.y * 2 + offset)
                time_variation = 1 + 0.12 * math.sin(offset * 1.7 + reading.mile / 90)
                value = base * spatial_variation * time_variation
                measurement = {"wind": reading.wind_mph, "rain": reading.rainfall_in_hr, "snow": reading.snowfall_in_hr}[metric] * spatial_variation * time_variation
                points.append({"x": reading.x, "y": reading.y, "intensity": min(1, max(0, value)), "value": round(measurement, 3), "unit": "mph" if metric == "wind" else "in/hr"})
            frames[metric].append({"offset_hours": offset * 8, "valid_at": valid_at, "points": points})
    return frames


class RoutePlanningService:
    def __init__(self, routing_provider=None, weather_provider=None, mode=None, live_enabled=None):
        self.mode = mode or os.getenv("SPOTTER_ROUTE_MODE", "demo").lower()
        self.live_enabled = live_enabled if live_enabled is not None else os.getenv("HERE_LIVE_ENABLED", "false").lower() == "true"
        if routing_provider:
            self.routing_provider = routing_provider
        elif self.mode == "demo":
            self.routing_provider = None
        elif self.mode == "live" and self.live_enabled:
            self.routing_provider = HereRoutingProvider()
        else:
            raise ProviderNotConfigured("Live HERE routing is disabled; use SPOTTER_ROUTE_MODE=demo or explicitly enable HERE_LIVE_ENABLED")
        self.weather_provider = weather_provider or weather_provider_for_mode(self.mode, self.live_enabled)

    def plan(self, request):
        candidates = demo_routes(request) if self.mode == "demo" else self.routing_provider.candidates(request["origin"], request["destination"], request["departure_time"], request["load_weight_lb"])
        if self.mode != "demo":
            candidates = [replace(candidate, geometry=enrich_geometry(candidate.geometry, candidate.duration_minutes * 60)) for candidate in candidates]
        if not candidates:
            raise ProviderError("No valid truck routes are available")
        routes = [_risk_for_route(route, self.weather_provider, request) for route in candidates[:3]]
        if len(routes) < 3:
            raise ProviderError(f"Only {len(routes)} route alternatives are available")
        ranked = sorted(routes, key=recommendation_key)
        recommended = ranked[0]
        recommended["recommended"] = True
        unsafe = all(route["no_travel_miles"] > 0 for route in routes)
        return {
            "routes": routes, "recommended_route_id": recommended["id"],
            "recommendation_explanation": "Recommended by severe miles, high miles, average risk, then duration. No-travel sections are flagged separately.",
            "safe_route_available": not unsafe, "data_source": self.mode,
            "weather_frames": _weather_frames(candidates[0], self.weather_provider),
        }
