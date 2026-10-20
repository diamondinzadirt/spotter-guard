from datetime import timedelta

from .geometry import enrich_geometry
from .providers import RouteCandidate, RoutePoint


def demo_routes(request):
    origin = (39.7392, -104.9903)
    destination = (39.0997, -94.5786)
    paths = [
        ("i70-central", "I-70 Central", [(39.7392, -104.9903), (39.1, -101.8), (39.05, -98.2), destination]),
        ("northern-nebraska", "Northern Nebraska", [origin, (41.1, -102.0), (40.9, -97.0), (40.2, -95.7), destination]),
        ("southern-plains", "Southern Plains", [origin, (38.3, -103.0), (37.8, -99.0), (38.2, -96.0), destination]),
    ]
    routes = []
    for route_id, name, coordinates in paths:
        geometry = tuple(RoutePoint(lat, lon, 0, 0) for lat, lon in coordinates)
        enriched = enrich_geometry(geometry, 9 * 3600)
        duration = round(enriched[-1].cumulative_miles / 62 * 60)
        enriched = enrich_geometry(geometry, duration * 60)
        routes.append(RouteCandidate(
            id=route_id, name=name, description="Offline Spotter assessment route fixture.",
            distance_miles=enriched[-1].cumulative_miles, duration_minutes=duration,
            departure_time=request["departure_time"], arrival_time=request["departure_time"] + timedelta(minutes=duration), geometry=enriched,
        ))
    return routes
