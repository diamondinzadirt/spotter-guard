import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(Exception):
    """Base error for an external routing or weather provider."""


class ProviderNotConfigured(ProviderError):
    pass


class ProviderRequestError(ProviderError):
    pass


@dataclass(frozen=True)
class RoutePoint:
    latitude: float
    longitude: float
    cumulative_miles: float
    cumulative_seconds: float


@dataclass(frozen=True)
class RouteCandidate:
    id: str
    name: str
    description: str
    distance_miles: float
    duration_minutes: int
    departure_time: datetime
    arrival_time: datetime
    geometry: tuple[RoutePoint, ...]


@dataclass(frozen=True)
class WeatherReading:
    valid_at: datetime
    mile: float
    wind_mph: float
    rainfall_in_hr: float
    snowfall_in_hr: float
    x: float
    y: float


class RoutingProvider(Protocol):
    def candidates(self, origin: str, destination: str, departure_time: datetime, load_weight_lb: float) -> list[RouteCandidate]: ...


class WeatherProvider(Protocol):
    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]: ...


class UnconfiguredRoutingProvider:
    def candidates(self, origin: str, destination: str, departure_time: datetime, load_weight_lb: float) -> list[RouteCandidate]:
        raise ProviderNotConfigured("A routing provider has not been configured")


class UnconfiguredWeatherProvider:
    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]:
        raise ProviderNotConfigured("A weather provider has not been configured")


def _decode_here_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode HERE Flexible Polyline into (latitude, longitude) pairs."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    lookup = {character: index for index, character in enumerate(alphabet)}
    index = 0
    lat = lon = 0
    precision = third_dimension = third_precision = 0
    header = 0
    values: list[int] = []
    while index < len(encoded):
        value = 0
        shift = 0
        while True:
            if index >= len(encoded):
                raise ProviderRequestError("Invalid HERE polyline")
            chunk = lookup.get(encoded[index])
            index += 1
            if chunk is None:
                raise ProviderRequestError("Invalid HERE polyline character")
            value |= (chunk & 0x1F) << shift
            shift += 5
            if chunk < 0x20:
                break
        values.append(value)
        if len(values) == 1:
            header = value
            precision = header & 15
            third_dimension = (header >> 4) & 7
            third_precision = (header >> 7) & 15
    if not values:
        return []
    values = values[1:]
    result = []
    value_index = 0
    while value_index + 1 < len(values):
        encoded_lat, encoded_lon = values[value_index], values[value_index + 1]
        value_index += 2
        lat += -(encoded_lat >> 1) if encoded_lat & 1 else encoded_lat >> 1
        lon += -(encoded_lon >> 1) if encoded_lon & 1 else encoded_lon >> 1
        result.append((lat / (10**precision), lon / (10**precision)))
        if third_dimension:
            value_index += 1
    return result


class HereRoutingProvider:
    """HERE Routing API v8 truck adapter.

    The opener is injectable so HTTP responses can be tested without network
    access. The provider requests two alternatives in addition to the primary
    route, and never manufactures missing alternatives.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://router.hereapi.com/v8/routes", opener: Callable = urlopen, timeout: float = 15.0):
        self.api_key = api_key or os.getenv("HERE_API_KEY")
        self.base_url = base_url
        self.opener = opener
        self.timeout = timeout

    def _request_json(self, url: str) -> dict:
        try:
            with self.opener(Request(url, headers={"Accept": "application/json"}), timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ProviderRequestError(f"HERE routing request failed: {error}") from error

    def _resolve_location(self, value: str) -> str:
        if "," in value:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) == 2:
                try:
                    float(parts[0]); float(parts[1])
                    return f"{parts[0]},{parts[1]}"
                except ValueError:
                    pass
        if not self.api_key:
            raise ProviderNotConfigured("HERE_API_KEY is required for address geocoding")
        query = urlencode({"q": value, "apiKey": self.api_key, "limit": 1})
        data = self._request_json(f"https://geocode.search.hereapi.com/v1/geocode?{query}")
        try:
            position = data["items"][0]["position"]
            return f"{position['lat']},{position['lng']}"
        except (KeyError, IndexError) as error:
            raise ProviderRequestError(f"HERE returned no geocoding result for {value!r}") from error

    def candidates(self, origin: str, destination: str, departure_time: datetime, load_weight_lb: float) -> list[RouteCandidate]:
        if not self.api_key:
            raise ProviderNotConfigured("HERE_API_KEY is required")
        params = {
            "apiKey": self.api_key,
            "transportMode": "truck",
            "origin": self._resolve_location(origin),
            "destination": self._resolve_location(destination),
            "departureTime": departure_time.isoformat(),
            "alternatives": 2,
            "return": "polyline,summary",
            "truck[grossWeight]": round(load_weight_lb * 0.45359237),
        }
        data = self._request_json(f"{self.base_url}?{urlencode(params)}")
        routes = []
        for index, route in enumerate(data.get("routes", [])):
            try:
                section = route["sections"][0]
                summary = section["summary"]
                coordinates = _decode_here_polyline(section["polyline"])
                if len(coordinates) < 2:
                    continue
                duration_seconds = int(summary["duration"])
                distance_meters = float(summary["length"])
                routes.append(RouteCandidate(
                    id=f"here-{index + 1}", name=f"HERE truck route {index + 1}",
                    description="Truck route returned by HERE Routing API v8.",
                    distance_miles=distance_meters / 1609.344,
                    duration_minutes=round(duration_seconds / 60),
                    departure_time=departure_time,
                    arrival_time=departure_time + timedelta(seconds=duration_seconds),
                    geometry=tuple(RoutePoint(latitude=lat, longitude=lon, cumulative_miles=0, cumulative_seconds=0) for lat, lon in coordinates),
                ))
            except (KeyError, TypeError, ValueError, ProviderRequestError):
                continue
        if len(routes) < 3:
            raise ProviderRequestError(f"HERE returned {len(routes)} valid truck routes; 3 alternatives were requested")
        return routes[:3]
