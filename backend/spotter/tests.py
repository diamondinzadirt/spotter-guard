from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

from django.test import TestCase
from rest_framework.test import APIClient

from .geometry import checkpoints, enrich_geometry
from .providers import ProviderRequestError, RouteCandidate, RoutePoint, HereRoutingProvider, ProviderNotConfigured
from .risk import RiskLevel, RiskReading, classify_risk, recommendation_key


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


class RoutePlanApiTests(TestCase):
    def test_invalid_payload_returns_contract_error(self):
        response = APIClient().post("/api/routes/plan", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_valid_payload_does_not_fabricate_provider_data(self):
        response = APIClient().post("/api/routes/plan", {
            "origin": "Denver, CO", "destination": "Kansas City, MO",
            "departure_time": datetime(2026, 10, 19, 20, tzinfo=timezone.utc).isoformat(),
            "load_weight_lb": 42_000, "checkpoint_interval_miles": 25,
        }, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "provider_not_configured")


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
    def test_provider_parses_three_alternatives_and_truck_parameters(self):
        # Encoded fixture is a valid two-point HERE flexible polyline.
        payload = {"routes": [{"sections": [{"summary": {"length": 160934.4, "duration": 3600}, "polyline": "BAAAU"}]} for _ in range(3)]}
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

    def test_provider_timeout_is_reported(self):
        def timeout(*args, **kwargs):
            raise TimeoutError("timed out")
        provider = HereRoutingProvider(api_key="secret", opener=timeout)
        with self.assertRaises(ProviderRequestError):
            provider.candidates("39.7,-104.9", "39.1,-94.6", datetime(2026, 1, 1, tzinfo=timezone.utc), 42_000)
