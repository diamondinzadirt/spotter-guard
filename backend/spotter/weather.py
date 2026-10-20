import json
import os
from datetime import datetime, timezone
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
            readings.append(WeatherReading(
                valid_at=departure_time,
                mile=mile,
                wind_mph=22 + (mile % 140) / 10,
                rainfall_in_hr=0.04 + (mile % 100) / 1000,
                snowfall_in_hr=0.1,
                x=15 + min(72, mile / max(route.distance_miles, 1) * 72),
                y=50,
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
        result = []
        cache = {}
        for point in route.geometry:
            cache_key = (round(point.latitude, 5), round(point.longitude, 5))
            if cache_key not in cache:
                cache[cache_key] = self._request(point.latitude, point.longitude, [route.departure_time])
            data = cache[cache_key]
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            wind = hourly.get("wind_speed_10m", [])
            rain = hourly.get("rain", [])
            snow = hourly.get("snowfall", [])
            if not times or not (len(times) == len(wind) == len(rain) == len(snow)):
                raise ProviderRequestError("Open-Meteo returned an incomplete hourly forecast")
            target = point.cumulative_seconds
            index = min(range(len(times)), key=lambda item: abs(datetime.fromisoformat(times[item]).replace(tzinfo=timezone.utc).timestamp() - (route.departure_time.timestamp() + target)))
            result.append(WeatherReading(
                valid_at=datetime.fromisoformat(times[index]).replace(tzinfo=timezone.utc), mile=point.cumulative_miles,
                wind_mph=float(wind[index]), rainfall_in_hr=float(rain[index]) / 25.4, snowfall_in_hr=float(snow[index]) / 2.54,
                x=point.longitude, y=point.latitude,
            ))
        return result


def weather_provider_for_mode(mode: str, live_enabled: bool):
    if mode == "demo":
        return OfflineWeatherProvider()
    if mode == "live" and live_enabled:
        return OpenMeteoWeatherProvider()
    raise ProviderNotConfigured("Live weather requires an explicit live mode and provider configuration")
