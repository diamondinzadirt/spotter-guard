from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RouteCandidate:
    id: str
    name: str
    description: str
    distance_miles: float
    duration_minutes: int
    geometry: list[dict[str, float]]


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
    def candidates(self, origin: str, destination: str, departure_time: datetime) -> list[RouteCandidate]: ...


class WeatherProvider(Protocol):
    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]: ...


class ProviderNotConfigured(Exception):
    pass


class UnconfiguredRoutingProvider:
    def candidates(self, origin: str, destination: str, departure_time: datetime) -> list[RouteCandidate]:
        raise ProviderNotConfigured("A routing provider has not been configured")


class UnconfiguredWeatherProvider:
    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]:
        raise ProviderNotConfigured("A weather provider has not been configured")
