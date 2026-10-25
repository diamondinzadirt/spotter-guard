from datetime import datetime, timezone
import json
import os
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from rest_framework.test import APIClient

from .geometry import checkpoints, enrich_geometry
from .providers import ProviderRequestError, RouteCandidate, RoutePoint, WeatherReading, HereRoutingProvider, ValhallaRoutingProvider, ProviderNotConfigured, _decode_here_polyline, _decode_valhalla_shape
from .services import RoutePlanningService, _risk_for_route, _weather_frames
from .weather import OfflineWeatherProvider, OpenMeteoWeatherProvider, weather_provider_for_mode
from .risk import RiskLevel, RiskReading, classify_risk, recommendation_key

# Keep the offline suite deterministic even when a developer's local .env enables Valhalla.
os.environ["SPOTTER_ROUTE_MODE"] = "demo"
os.environ["SPOTTER_ROUTING_PROVIDER"] = "demo"


class RiskClassificationTests(TestCase):
    def test_wind_thresholds(self):
        for value, expected in ((24.99, RiskLevel.LOW), (25, RiskLevel.MODERATE), (34.99, RiskLevel.MODERATE), (35, RiskLevel.HIGH), (44.99, RiskLevel.HIGH), (45, RiskLevel.SEVERE), (54.99, RiskLevel.SEVERE), (55, RiskLevel.NO_TRAVEL)):
            with self.subTest(value=value):
                self.assertEqual(classify_risk(RiskReading(value, 0, 0), 0), expected)

    def test_rain_thresholds(self):
        for value, expected in ((0.099, RiskLevel.LOW), (0.10, RiskLevel.MODERATE), (0.249, RiskLevel.MODERATE), (0.25, RiskLevel.HIGH), (0.499, RiskLevel.HIGH), (0.50, RiskLevel.SEVERE), (1.00, RiskLevel.SEVERE), (1.001, RiskLevel.NO_TRAVEL)):
            with self.subTest(value=value):
                self.assertEqual(classify_risk(RiskReading(0, value, 0), 0), expected)

    def test_snow_thresholds(self):
        for value, expected in ((0.499, RiskLevel.LOW), (0.50, RiskLevel.MODERATE), (0.999, RiskLevel.MODERATE), (1.00, RiskLevel.HIGH), (1.999, RiskLevel.HIGH), (2.00, RiskLevel.SEVERE), (3.00, RiskLevel.SEVERE), (3.001, RiskLevel.NO_TRAVEL)):
            with self.subTest(value=value):
                self.assertEqual(classify_risk(RiskReading(0, 0, value), 0), expected)

    def test_load_rules_use_strict_greater_than_boundaries(self):
        self.assertEqual(classify_risk(RiskReading(50, 0, 0), 30_000), RiskLevel.SEVERE)
        self.assertEqual(classify_risk(RiskReading(50, 0, 0), 30_001), RiskLevel.NO_TRAVEL)
        self.assertEqual(classify_risk(RiskReading(40, 0, 0), 40_000), RiskLevel.HIGH)
        self.assertEqual(classify_risk(RiskReading(40, 0, 0), 40_001), RiskLevel.SEVERE)
        self.assertEqual(classify_risk(RiskReading(55, 0, 0), 0), RiskLevel.NO_TRAVEL)

    def test_assessment_load_scenarios_38_48_and_55_mph(self):
        for load in (20_000, 42_000):
            self.assertEqual(classify_risk(RiskReading(38, 0, 0), load), RiskLevel.SEVERE if load == 42_000 else RiskLevel.HIGH)
            self.assertEqual(classify_risk(RiskReading(48, 0, 0), load), RiskLevel.NO_TRAVEL if load == 42_000 else RiskLevel.SEVERE)
            self.assertEqual(classify_risk(RiskReading(55, 0, 0), load), RiskLevel.NO_TRAVEL)

    def test_combined_conditions_use_highest_risk(self):
        self.assertEqual(classify_risk(RiskReading(20, 0.10, 2.00), 0), RiskLevel.SEVERE)

    def test_negative_load_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_risk(RiskReading(0, 0, 0), -1)


class RecommendationTests(TestCase):
    def test_recommendation_key_follows_required_priority(self):
        slower = {"severe_miles": 2, "high_miles": 1, "average_risk": 0.5, "duration_minutes": 1}
        faster = {"severe_miles": 2, "high_miles": 1, "average_risk": 0.5, "duration_minutes": 2}
        self.assertLess(recommendation_key(slower), recommendation_key(faster))

    def test_recommendation_key_checks_each_priority_in_order(self):
        base = {"severe_miles": 1, "high_miles": 2, "average_risk": 3, "duration_minutes": 4}
        for field, value in (("severe_miles", 2), ("high_miles", 3), ("average_risk", 4), ("duration_minutes", 5)):
            changed = {**base, field: value}
            self.assertLess(recommendation_key(base), recommendation_key(changed))


class RouteRiskAggregationTests(TestCase):
    def setUp(self):
        self.route = RouteCandidate(
            id="aggregation", name="Aggregation", description="Test", distance_miles=30, duration_minutes=30,
            departure_time=datetime(2026, 1, 1, tzinfo=timezone.utc), arrival_time=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            geometry=tuple(RoutePoint(39, -100 + mile / 10, mile, mile * 60) for mile in (0, 10, 20, 30)),
        )

    def test_checkpoint_risk_and_mileage_totals_are_deterministic(self):
        readings = [
            WeatherReading(self.route.departure_time, 0, 48, 0, 0, -100, 39),
            WeatherReading(self.route.departure_time, 10, 36, 0, 0, -99, 39),
            WeatherReading(self.route.departure_time, 20, 55, 0, 0, -98, 39),
            WeatherReading(self.route.departure_time, 30, 0, 0.1, 0, -97, 39),
        ]
        class FixedWeather:
            def readings(self, route, departure_time):
                return readings
        result = _risk_for_route(self.route, FixedWeather(), {"checkpoint_interval_miles": 10, "departure_time": self.route.departure_time, "load_weight_lb": 20_000})
        self.assertEqual([item["risk_level"] for item in result["checkpoints"][:4]], ["severe", "high", "no_travel", "moderate"])
        self.assertEqual(result["severe_miles"], 0)
        self.assertEqual(result["high_miles"], 10)
        self.assertEqual(result["no_travel_miles"], 10)
        self.assertEqual([segment["risk_level"] for segment in result["risk_segments"][:3]], ["high", "no_travel", "moderate"])


class RoutePlanApiTests(TestCase):
    def test_health_endpoint_returns_ok_without_provider_calls(self):
        response = APIClient().get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_invalid_payload_returns_contract_error(self):
        response = APIClient().post("/api/routes/plan", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_valid_payload_returns_offline_demo_response(self):
        response = APIClient().post("/api/routes/plan", {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc).isoformat(),
            "load_weight_lb": 42_000, "checkpoint_interval_miles": 25,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_source"], "demo")
        self.assertEqual(len(payload["routes"]), 3)
        self.assertIn("safe_route_available", payload)
        self.assertEqual(set(payload["weather_frames_by_route"]), {route["id"] for route in payload["routes"]})

    def test_demo_api_honors_each_checkpoint_interval(self):
        base_request = {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc).isoformat(),
            "load_weight_lb": 42_000,
        }
        for interval in (10, 25, 50):
            with self.subTest(interval=interval):
                response = APIClient().post("/api/routes/plan", {**base_request, "checkpoint_interval_miles": interval}, format="json")
                self.assertEqual(response.status_code, 200)
                for route in response.json()["routes"]:
                    miles = [checkpoint["mile"] for checkpoint in route["checkpoints"]]
                    self.assertEqual(miles[0], 0)
                    self.assertEqual(miles[1], interval)
                    self.assertEqual(miles[2], interval * 2)
                    self.assertEqual(miles[3], interval * 3)

    def test_api_passes_load_weight_to_planning_service(self):
        request = {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc).isoformat(),
            "load_weight_lb": 42_000, "checkpoint_interval_miles": 25,
        }
        with patch("spotter.views.RoutePlanningService") as service_class:
            service_class.return_value.plan.return_value = {"routes": [], "weather_frames": {}}
            response = APIClient().post("/api/routes/plan", request, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service_class.return_value.plan.call_args.args[0]["load_weight_lb"], 42_000)

    def test_demo_loads_match_when_fixture_wind_is_below_load_sensitive_bands(self):
        base_request = {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc), "checkpoint_interval_miles": 25,
        }
        light = RoutePlanningService(mode="demo").plan({**base_request, "load_weight_lb": 20_000})
        heavy = RoutePlanningService(mode="demo").plan({**base_request, "load_weight_lb": 42_000})
        self.assertEqual(light["recommended_route_id"], heavy["recommended_route_id"])
        self.assertEqual([(route["overall_risk"], route["severe_miles"], route["high_miles"], route["no_travel_miles"]) for route in light["routes"]], [(route["overall_risk"], route["severe_miles"], route["high_miles"], route["no_travel_miles"]) for route in heavy["routes"]])

    def test_demo_weather_frames_vary_by_metric_location_and_time(self):
        response = APIClient().post("/api/routes/plan", {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc).isoformat(),
            "load_weight_lb": 42_000, "checkpoint_interval_miles": 25,
        }, format="json")
        payload = response.json()
        for metric in ("wind", "rain", "snow"):
            frames = payload["weather_frames"][metric]
            self.assertEqual(len(frames), 7)
            self.assertNotEqual(frames[0]["points"], frames[3]["points"])
            self.assertNotEqual([point["value"] for point in frames[0]["points"]], [point["value"] for point in frames[3]["points"]])
            self.assertGreater(len({(point["x"], point["y"]) for point in frames[0]["points"]}), 1)
            self.assertTrue(all(-106 < point["x"] < -94 and 37 < point["y"] < 42 for point in frames[0]["points"]))

        route_points = {route_id: {(point["x"], point["y"]) for point in frames["wind"][0]["points"]} for route_id, frames in payload["weather_frames_by_route"].items()}
        self.assertGreater(len({frozenset(points) for points in route_points.values()}), 1)
        for frames in payload["weather_frames_by_route"].values():
            for metric in ("wind", "rain", "snow"):
                self.assertEqual([frame["offset_hours"] for frame in frames[metric]], [0, 8, 16, 24, 32, 40, 48])
                self.assertNotEqual(frames[metric][0]["points"], frames[metric][3]["points"])
                self.assertNotEqual(frames[metric][3]["points"], frames[metric][6]["points"])

    def test_live_candidates_are_enriched_before_weather_sampling(self):
        route = RouteCandidate(
            "live", "Live", "Test", 60, 60,
            datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            (RoutePoint(39, -105, 0, 0), RoutePoint(39, -104, 0, 0)),
        )
        captured = []

        class Routing:
            def candidates(self, *args):
                return [route, route, route]

        class Weather:
            def readings(self, candidate, departure_time):
                captured.append(candidate.geometry)
                return [WeatherReading(departure_time, 0, 10, 0, 0, -105, 39), WeatherReading(departure_time, 60, 10, 0, 0, -104, 39)]

        RoutePlanningService(mode="live", live_enabled=True, routing_provider=Routing(), weather_provider=Weather()).plan({
            "origin": "39,-105", "destination": "39,-104", "departure_time": route.departure_time,
            "load_weight_lb": 20_000, "checkpoint_interval_miles": 25,
        })
        self.assertTrue(captured)
        self.assertGreater(captured[0][-1].cumulative_miles, 0)
        self.assertGreater(captured[0][-1].cumulative_seconds, 0)

    def test_live_planning_preserves_one_two_or_three_route_counts(self):
        route = RouteCandidate(
            "variable", "Variable", "Test", 60, 60,
            datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            (RoutePoint(39, -105, 0, 0), RoutePoint(39, -104, 0, 0)),
        )

        class Weather:
            def readings(self, candidate, departure_time):
                return [WeatherReading(departure_time, 0, 10, 0, 0, -105, 39), WeatherReading(departure_time, 60, 10, 0, 0, -104, 39)]

        for count in (1, 2, 3):
            with self.subTest(count=count):
                class Routing:
                    def candidates(self, *args):
                        return [RouteCandidate(**{**route.__dict__, "id": f"variable-{index}"}) for index in range(count)]

                response = RoutePlanningService(mode="live", live_enabled=True, routing_provider=Routing(), weather_provider=Weather()).plan({
                    "origin": "39,-105", "destination": "39,-104", "departure_time": route.departure_time,
                    "load_weight_lb": 20_000, "checkpoint_interval_miles": 25,
                })
                self.assertEqual(len(response["routes"]), count)


class GeometryTests(TestCase):
    def setUp(self):
        self.route = RouteCandidate(
            id="route-1", name="Test", description="Test", distance_miles=0, duration_minutes=60,
            departure_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            arrival_time=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            geometry=(RoutePoint(0, 0, 0, 0), RoutePoint(0, 1, 0, 0)),
        )

    def test_interpolation_and_eta_are_monotonic(self):
        enriched = enrich_geometry(self.route.geometry, 3600)
        self.assertGreater(enriched[-1].cumulative_miles, 60)
        generated = checkpoints(self.route, 25)
        self.assertEqual(generated[0]["mile"], 0)
        self.assertEqual(generated[-1]["mile"], enriched[-1].cumulative_miles)
        self.assertEqual(generated[1]["longitude"], 25 / enriched[-1].cumulative_miles)
        self.assertLess(generated[1]["arrival_time"], generated[-1]["arrival_time"])

    def test_intervals_and_short_routes(self):
        self.assertEqual([item["mile"] for item in checkpoints(self.route, 50)][1:-1], [50])
        short = RouteCandidate(**{**self.route.__dict__, "geometry": (RoutePoint(0, 0, 0, 0), RoutePoint(0, 0.001, 0, 0))})
        self.assertEqual(len(checkpoints(short, 50)), 2)


class HereProviderTests(TestCase):
    def test_flexible_polyline_decodes_official_two_dimension_example(self):
        coordinates = _decode_here_polyline("BFoz5xJ67i1B1B7PzIhaxL7Y")
        self.assertEqual(len(coordinates), 4)
        self.assertAlmostEqual(coordinates[0][0], 50.10228, places=5)
        self.assertAlmostEqual(coordinates[0][1], 8.69821, places=5)
        self.assertAlmostEqual(coordinates[-1][0], 50.09878, places=5)
        self.assertAlmostEqual(coordinates[-1][1], 8.68752, places=5)

    def test_provider_parses_three_alternatives_and_truck_parameters(self):
        payload = {"routes": [{"sections": [{"summary": {"length": 160934.4, "duration": 3600}, "polyline": "BFoz5xJ67i1B1B7PzIhaxL7Y"}]} for _ in range(3)]}
        response = MagicMock()
        response.read.return_value = __import__("json").dumps(payload).encode()
        response.__enter__.return_value = response
        provider = HereRoutingProvider(api_key="secret", opener=Mock(return_value=response))
        routes = provider.candidates("39.7,-104.9", "39.1,-94.6", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)
        self.assertEqual(len(routes), 3)
        request_url = provider.opener.call_args.args[0].full_url
        self.assertIn("transportMode=truck", request_url)
        self.assertIn("alternatives=2", request_url)
        self.assertIn("truck%5BgrossWeight%5D=19051", request_url)

    def test_provider_reports_insufficient_alternatives(self):
        response = MagicMock()
        response.read.return_value = __import__("json").dumps({"routes": []}).encode()
        response.__enter__.return_value = response
        provider = HereRoutingProvider(api_key="secret", opener=Mock(return_value=response))
        with self.assertRaises(ProviderRequestError):
            provider.candidates("39.7,-104.9", "39.1,-94.6", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)

    def test_provider_accepts_one_two_or_three_valid_alternatives(self):
        polyline = "BFoz5xJ67i1B1B7PzIhaxL7Y"
        for count in (1, 2, 3):
            with self.subTest(count=count):
                payload = {"routes": [{"sections": [{"summary": {"length": 160934.4, "duration": 3600}, "polyline": polyline}]} for _ in range(count)]}
                response = MagicMock()
                response.read.return_value = __import__("json").dumps(payload).encode()
                response.__enter__.return_value = response
                provider = HereRoutingProvider(api_key="secret", opener=Mock(return_value=response))
                self.assertEqual(len(provider.candidates("39.7,-104.9", "39.1,-94.6", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)), count)


class ValhallaProviderTests(TestCase):
    @staticmethod
    def encode_shape(coordinates):
        previous = [0, 0]
        encoded = []
        for coordinate in coordinates:
            for index, number in enumerate(coordinate):
                scaled = round(number * 1_000_000)
                delta = scaled - previous[index]
                previous[index] = scaled
                value = (delta << 1) ^ (delta >> 31)
                while value >= 0x20:
                    encoded.append(chr(((value & 0x1F) | 0x20) + 63))
                    value >>= 5
                encoded.append(chr(value + 63))
        return "".join(encoded)

    def test_valhalla_decoder_and_provider_accept_two_alternatives(self):
        shape = self.encode_shape([(32.7767, -96.7970), (33.5, -105.0), (34.0522, -118.2437)])
        alternate_shape = self.encode_shape([(32.7767, -96.7970), (34.0, -110.0), (34.0522, -118.2437)])
        payload = {"trip": {"summary": {"length": 1435, "time": 90000}, "legs": [{"shape": shape}]}, "alternates": [{"trip": {"summary": {"length": 1450, "time": 92000}, "legs": [{"shape": alternate_shape}]}}]}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        provider = ValhallaRoutingProvider(base_url="https://valhalla.test", opener=Mock(return_value=response))
        routes = provider.candidates("Dallas, TX", "Los Angeles, CA", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)
        self.assertEqual(len(routes), 2)
        self.assertAlmostEqual(_decode_valhalla_shape(shape)[0][0], 32.7767, places=5)
        request = provider.opener.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data)["costing"], "truck")
        self.assertEqual(json.loads(request.data)["alternates"], 2)
        self.assertEqual(request.headers["X-client-id"], "spotter-guard-local")

    def test_valhalla_rejects_invalid_or_empty_routes(self):
        response = MagicMock()
        response.read.return_value = b'{"trip": {"summary": {}, "legs": []}}'
        response.__enter__.return_value = response
        provider = ValhallaRoutingProvider(opener=Mock(return_value=response))
        with self.assertRaises(ProviderRequestError):
            provider.candidates("Seattle, WA", "Portland, OR", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)


class PhaseThreeSafetyTests(TestCase):
    def test_live_weather_requires_explicit_enablement(self):
        with self.assertRaises(ProviderNotConfigured):
            weather_provider_for_mode("live", False)

    def test_live_here_is_disabled_even_when_key_exists(self):
        request = {"origin": "Denver, CO", "destination": "Kansas City, MO", "departure_time": datetime(2026, 1, 1, tzinfo=timezone.utc), "load_weight_lb": 42_000, "checkpoint_interval_miles": 25}
        with patch.dict(os.environ, {"SPOTTER_ROUTE_MODE": "live", "SPOTTER_ROUTING_PROVIDER": "demo", "HERE_LIVE_ENABLED": "false", "HERE_API_KEY": "configured"}):
            with self.assertRaises(ProviderNotConfigured):
                RoutePlanningService().plan(request)

    def test_demo_plan_contains_risk_mileage_and_source(self):
        request = {"origin": "Denver, CO", "destination": "Kansas City, MO", "departure_time": datetime(2026, 1, 1, tzinfo=timezone.utc), "load_weight_lb": 42_000, "checkpoint_interval_miles": 10}
        response = RoutePlanningService(mode="demo").plan(request)
        self.assertEqual(response["data_source"], "demo")
        for route in response["routes"]:
            self.assertIn("no_travel_miles", route)
            self.assertIn("geojson_geometry", route)
            self.assertGreaterEqual(len(route["checkpoints"]), 2)
        self.assertEqual(len(response["weather_frames"]["wind"]), 7)
        self.assertNotEqual(response["weather_frames"]["wind"][0]["valid_at"], response["weather_frames"]["wind"][1]["valid_at"])


class WeatherProviderTests(TestCase):
    def test_atlanta_weather_is_deterministic_varied_and_ranked_by_actual_risk(self):
        departure = datetime(2026, 1, 1, tzinfo=timezone.utc)
        coordinates = [
            ((33.749, -84.388), (34.6, -85.2), (35.15, -90.05)),
            ((33.749, -84.388), (34.9, -85.8), (35.15, -90.05)),
            ((33.749, -84.388), (34.2, -86.7), (35.15, -90.05)),
        ]
        provider = OfflineWeatherProvider()
        routes = []
        for index, path in enumerate(coordinates):
            geometry = tuple(RoutePoint(latitude, longitude, mile * 100, mile * 3600) for mile, (latitude, longitude) in enumerate(path))
            routes.append(RouteCandidate(f"atlanta-{index}", f"Route {index}", "", 200, 200, departure, departure, geometry))
        first_readings = provider.readings(routes[0], departure)
        repeat_readings = provider.readings(routes[0], departure)
        self.assertEqual(first_readings, repeat_readings)
        self.assertNotEqual(provider.readings(routes[1], departure)[1].wind_mph, first_readings[1].wind_mph)
        request = {"checkpoint_interval_miles": 50, "load_weight_lb": 20_000, "departure_time": departure}
        analyzed = [_risk_for_route(route, provider, request) for route in routes]
        self.assertTrue(any(route["overall_risk"] != RiskLevel.SEVERE.value for route in analyzed))
        ranked = sorted(analyzed, key=recommendation_key)
        self.assertEqual(ranked[0]["id"], min(analyzed, key=recommendation_key)["id"])

    def test_open_meteo_converts_mm_and_cm_to_inches_and_selects_hour(self):
        payload = {"hourly": {"time": ["2026-01-01T12:00", "2026-01-01T13:00"], "wind_speed_10m": [25, 30], "rain": [2.54, 5.08], "snowfall": [2.54, 5.08]}}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        route = RouteCandidate("r", "r", "r", 10, 60, datetime(2026, 1, 1, 12, 40, tzinfo=timezone.utc), datetime(2026, 1, 1, 13, 40, tzinfo=timezone.utc), (RoutePoint(39, -105, 0, 0), RoutePoint(39, -104, 10, 1800)))
        readings = OpenMeteoWeatherProvider(opener=Mock(return_value=response)).readings(route, route.departure_time)
        self.assertEqual(readings[0].wind_mph, 30)
        self.assertAlmostEqual(readings[0].rainfall_in_hr, 0.2)
        self.assertAlmostEqual(readings[0].snowfall_in_hr, 2.0)

    def test_open_meteo_forecast_frames_select_distinct_hours(self):
        payload = {"hourly": {"time": ["2026-01-01T12:00", "2026-01-01T13:00"], "wind_speed_10m": [25, 40], "rain": [2.54, 7.62], "snowfall": [2.54, 5.08]}}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        route = RouteCandidate("r", "r", "r", 10, 60, datetime(2026, 1, 1, 12, tzinfo=timezone.utc), datetime(2026, 1, 1, 13, tzinfo=timezone.utc), (RoutePoint(39, -105, 0, 0), RoutePoint(39, -104, 10, 1800)))
        frames = OpenMeteoWeatherProvider(opener=Mock(return_value=response)).forecast_readings(route, [0, 1])
        self.assertEqual(frames[0][0].wind_mph, 25)
        self.assertEqual(frames[1][0].wind_mph, 40)
        self.assertNotEqual(frames[0][0].valid_at, frames[1][0].valid_at)

    def test_malformed_forecast_is_rejected(self):
        response = MagicMock()
        response.read.return_value = b'{"hourly": {}}'
        response.__enter__.return_value = response
        route = RouteCandidate("r", "r", "r", 10, 60, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc), (RoutePoint(39, -105, 0, 0), RoutePoint(39, -104, 10, 1800)))
        with self.assertRaises(ProviderRequestError):
            OpenMeteoWeatherProvider(opener=Mock(return_value=response)).readings(route, route.departure_time)

    def test_provider_timeout_is_reported(self):
        def timeout(*args, **kwargs):
            raise TimeoutError("timed out")
        provider = HereRoutingProvider(api_key="secret", opener=timeout)
        with self.assertRaises(ProviderRequestError):
            provider.candidates("39.7,-104.9", "39.1,-94.6", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)
