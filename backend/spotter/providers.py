import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
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

    def read_unsigned() -> int:
        nonlocal index
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
            if chunk < 0x20:
                return value
            shift += 5

    version = read_unsigned()
    if version != 1:
        raise ProviderRequestError(f"Unsupported HERE polyline version: {version}")
    header = read_unsigned()
    precision = header & 0xF
    third_dimension = (header >> 4) & 0x7
    third_precision = (header >> 7) & 0xF
    deltas: list[int] = []
    while index < len(encoded):
        value = read_unsigned()
        deltas.append(-(value + 1) // 2 if value & 1 else value // 2)

    dimension = 3 if third_dimension else 2
    if len(deltas) % dimension:
        raise ProviderRequestError("Invalid HERE polyline coordinate tuple")
    lat = lon = 0
    result = []
    for value_index in range(0, len(deltas), dimension):
        lat += deltas[value_index]
        lon += deltas[value_index + 1]
        result.append((lat / (10**precision), lon / (10**precision)))
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
        if not routes:
            raise ProviderRequestError("HERE returned no valid truck routes")
        return routes[:3]


VALHALLA_JOURNEY_ENDPOINTS = {
    ("dallas, tx", "los angeles, ca"): ((32.7767, -96.7970), (34.0522, -118.2437)),
    ("seattle, wa", "portland, or"): ((47.6062, -122.3321), (45.5152, -122.6784)),
}


def _decode_valhalla_shape(encoded: str) -> list[tuple[float, float]]:
    """Decode Valhalla's precision-6 encoded latitude/longitude shape."""
    if not encoded:
        raise ProviderRequestError("Valhalla returned an empty route shape")
    coordinates = []
    index = 0
    latitude = longitude = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            value = shift = 0
            while True:
                if index >= len(encoded):
                    raise ProviderRequestError("Invalid Valhalla route shape")
                chunk = ord(encoded[index]) - 63
                index += 1
                value |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20:
                    break
            deltas.append(-(value >> 1) if value & 1 else value >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        coordinates.append((latitude / 1_000_000, longitude / 1_000_000))
    return coordinates


class ValhallaRoutingProvider:
    """Valhalla truck adapter for the two non-fixture assessment journeys."""

    def __init__(self, base_url: Optional[str] = None, opener: Callable = urlopen, timeout: float = 20.0, client_id: Optional[str] = None, geocoder=None):
        self.base_url = (base_url or os.getenv("VALHALLA_BASE_URL", "https://valhalla1.openstreetmap.de")).rstrip("/")
        self.opener = opener
        self.timeout = timeout
        self.client_id = client_id or os.getenv("VALHALLA_CLIENT_ID", "spotter-guard-local")
        self.geocoder = geocoder or PhotonGeocoder(opener=opener, timeout=timeout, client_id=self.client_id)

    def _request_json(self, payload: dict) -> dict:
        request = Request(
            f"{self.base_url}/route", data=json.dumps(payload).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json", "X-Client-Id": self.client_id}, method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                detail = error.read().decode("utf-8", errors="replace")
                parsed = json.loads(detail)
                message = parsed.get("error", {}).get("message") or parsed.get("error") or detail
            except (OSError, UnicodeError, json.JSONDecodeError):
                message = str(error)
            raise ProviderRequestError(f"Valhalla routing request failed ({error.code}): {message}") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ProviderRequestError(f"Valhalla routing request failed: {error}") from error

    def candidates(self, origin: str, destination: str, departure_time: datetime, load_weight_lb: float) -> list[RouteCandidate]:
        key = (origin.strip().casefold(), destination.strip().casefold())
        endpoints = VALHALLA_JOURNEY_ENDPOINTS.get(key)
        if not endpoints:
            endpoints = (self.geocoder.resolve(origin), self.geocoder.resolve(destination))
        start, end = endpoints
        data = self._request_json({
            "locations": [{"lat": start[0], "lon": start[1]}, {"lat": end[0], "lon": end[1]}],
            "costing": "truck", "alternates": 2, "units": "miles",
        })
        trips = [data.get("trip", {})] + [item.get("trip", item) for item in data.get("alternates", [])]
        routes = []
        route_signatures = set()
        for index, trip in enumerate(trips[:3]):
            try:
                summary = trip["summary"]
                coordinates = _decode_valhalla_shape(trip["legs"][0]["shape"])
                if len(coordinates) < 2:
                    continue
                first, last = coordinates[0], coordinates[-1]
                if any((abs(first[0] - start[0]) > 1, abs(first[1] - start[1]) > 1, abs(last[0] - end[0]) > 1, abs(last[1] - end[1]) > 1)):
                    continue
                if any(not (24 <= latitude <= 50 and -125 <= longitude <= -66) for latitude, longitude in coordinates):
                    continue
                signature = tuple((round(latitude, 5), round(longitude, 5)) for latitude, longitude in coordinates[::max(1, len(coordinates) // 20)])
                if signature in route_signatures:
                    continue
                route_signatures.add(signature)
                duration_seconds = int(summary["time"])
                routes.append(RouteCandidate(
                    id=f"valhalla-{index + 1}", name=f"Valhalla truck route {index + 1}",
                    description="Truck route returned by Valhalla using OpenStreetMap data.",
                    distance_miles=float(summary["length"]), duration_minutes=round(duration_seconds / 60),
                    departure_time=departure_time, arrival_time=departure_time + timedelta(seconds=duration_seconds),
                    geometry=tuple(RoutePoint(latitude=lat, longitude=lon, cumulative_miles=0, cumulative_seconds=0) for lat, lon in coordinates),
                ))
            except (IndexError, KeyError, TypeError, ValueError, ProviderRequestError):
                continue
        if not routes:
            raise ProviderRequestError("Valhalla returned no valid truck routes")
        return routes


class PhotonGeocoder:
    """Submit-time Photon geocoder with strict US locality/state matching."""

    def __init__(self, base_url: Optional[str] = None, opener: Callable = urlopen, timeout: float = 10.0, client_id: Optional[str] = None):
        self.base_url = (base_url or os.getenv("PHOTON_BASE_URL", "https://photon.komoot.io")).rstrip("/")
        self.opener = opener
        self.timeout = timeout
        self.client_id = client_id or os.getenv("VALHALLA_CLIENT_ID", "spotter-guard-local")

    def resolve(self, value: str) -> tuple[float, float]:
        parts = [part.strip() for part in value.rsplit(",", 1)]
        if len(parts) != 2 or not all(parts):
            raise ProviderRequestError(f"We couldn't identify {value!r} as a city and state")
        city, state = parts
        request = Request(
            f"{self.base_url}/api/?q={quote(f'{city}, {state}, USA')}&limit=5",
            headers={"Accept": "application/json", "User-Agent": self.client_id},
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ProviderRequestError("Location service is temporarily unavailable") from error
        state_name = state.casefold()
        for feature in data.get("features", []):
            properties = feature.get("properties", {})
            country = str(properties.get("country", "")).casefold()
            returned_state = str(properties.get("state", "")).casefold()
            returned_code = str(properties.get("statecode", properties.get("state_code", ""))).casefold()
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if country in {"united states", "us", "usa"} and (returned_state == state_name or returned_state.endswith(f" {state_name}") or returned_code == state_name) and len(coordinates) >= 2:
                longitude, latitude = coordinates[:2]
                if -125 <= float(longitude) <= -66 and 24 <= float(latitude) <= 50:
                    return float(latitude), float(longitude)
        raise ProviderRequestError(f"We couldn't find {city}, {state} in the United States")
