import json
import os
import math
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .providers import ProviderNotConfigured, ProviderRequestError, RouteCandidate, WeatherReading


class OfflineWeatherProvider:
    source = "demo"

    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]:
        readings = []
        for point in route.geometry:
            mile = point.cumulative_miles
            geographic_cell = math.sin(point.latitude * 0.22 + point.longitude * 0.17) + math.sin(point.longitude * 0.31 - point.latitude * 0.11)
            corridor_cell = math.sin(mile / 68 + point.latitude * 0.08)
            intensity = (geographic_cell + corridor_cell + 3) / 6
            readings.append(WeatherReading(
                valid_at=departure_time,
                mile=mile,
                wind_mph=round(16 + intensity * 17 + max(0, math.sin(mile / 180 + point.longitude)) * 7, 2),
                rainfall_in_hr=round(0.025 + intensity * 0.16, 3),
                snowfall_in_hr=round(0.04 + intensity * 0.55, 3),
                x=point.longitude,
                y=point.latitude,
            ))
        return readings


class OpenMeteoWeatherProvider:
    source = "live"

    def __init__(self, opener: Callable = urlopen, timeout: float = 15.0):
        self.opener = opener
        self.timeout = timeout

    def _request(self, latitude: float, longitude: float, arrival_times: list[datetime]) -> dict:
        if not arrival_times:
            return {}
        dates = sorted({item.astimezone(timezone.utc).date().isoformat() for item in arrival_times})
        params = urlencode({
            "latitude": latitude, "longitude": longitude,
            "hourly": "wind_speed_10m,rain,snowfall",
            "start_date": dates[0], "end_date": dates[-1], "wind_speed_unit": "mph",
            "timezone": "UTC",
        })
        try:
            with self.opener(Request(f"https://api.open-meteo.com/v1/forecast?{params}", headers={"Accept": "application/json"}), timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise ProviderRequestError(f"Open-Meteo request failed: {error}") from error

    def readings(self, route: RouteCandidate, departure_time: datetime) -> list[WeatherReading]:
        return self.forecast_readings(route, [0])[0]

    def forecast_readings(self, route: RouteCandidate, offsets: list[int]) -> list[list[WeatherReading]]:
        frames = [[] for _ in offsets]
        for point in route.geometry:
            targets = [route.departure_time + timedelta(seconds=point.cumulative_seconds, hours=offset) for offset in offsets]
            data = self._request(point.latitude, point.longitude, targets)
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            wind = hourly.get("wind_speed_10m", [])
            rain = hourly.get("rain", [])
            snow = hourly.get("snowfall", [])
            if not times or not (len(times) == len(wind) == len(rain) == len(snow)):
                raise ProviderRequestError("Open-Meteo returned an incomplete hourly forecast")
            for frame_index, target in enumerate(targets):
                index = min(range(len(times)), key=lambda item: abs(datetime.fromisoformat(times[item]).replace(tzinfo=timezone.utc).timestamp() - target.timestamp()))
                frames[frame_index].append(WeatherReading(
                    valid_at=datetime.fromisoformat(times[index]).replace(tzinfo=timezone.utc), mile=point.cumulative_miles,
                    wind_mph=float(wind[index]), rainfall_in_hr=float(rain[index]) / 25.4, snowfall_in_hr=float(snow[index]) / 2.54,
                    x=point.longitude, y=point.latitude,
                ))
        return frames


def weather_provider_for_mode(mode: str, live_enabled: bool):
    if mode == "demo":
        return OfflineWeatherProvider()
    if mode == "live" and live_enabled:
        return OpenMeteoWeatherProvider()
    raise ProviderNotConfigured("Live weather requires an explicit live mode and provider configuration")
