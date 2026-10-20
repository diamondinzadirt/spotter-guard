from dataclasses import replace
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from .providers import RouteCandidate, RoutePoint

EARTH_RADIUS_MILES = 3958.7613


def distance_miles(first: RoutePoint, second: RoutePoint) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (first.latitude, first.longitude, second.latitude, second.longitude))
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(value))


def enrich_geometry(points: tuple[RoutePoint, ...], total_seconds: float) -> tuple[RoutePoint, ...]:
    if not points:
        return points
    segment_distances = [distance_miles(first, second) for first, second in zip(points, points[1:])]
    total_miles = sum(segment_distances)
    output = [replace(points[0], cumulative_miles=0, cumulative_seconds=0)]
    for index, point in enumerate(points[1:]):
        segment_miles = segment_distances[index]
        cumulative_miles = output[-1].cumulative_miles + segment_miles
        fraction = cumulative_miles / total_miles if total_miles else 0
        output.append(replace(point, cumulative_miles=cumulative_miles, cumulative_seconds=total_seconds * fraction))
    return tuple(output)


def checkpoints(route: RouteCandidate, interval_miles: int) -> list[dict]:
    points = enrich_geometry(route.geometry, route.duration_minutes * 60)
    if len(points) < 2:
        return []
    targets = list(range(interval_miles, int(points[-1].cumulative_miles) + 1, interval_miles))
    targets.extend([0, points[-1].cumulative_miles])
    output = []
    for target in sorted(set(targets)):
        if target == 0:
            point = points[0]
            elapsed = 0
        else:
            before, after = points[0], points[-1]
            for candidate_before, candidate_after in zip(points, points[1:]):
                if candidate_before.cumulative_miles <= target <= candidate_after.cumulative_miles:
                    before, after = candidate_before, candidate_after
                    break
            span = after.cumulative_miles - before.cumulative_miles
            ratio = 0 if span == 0 else (target - before.cumulative_miles) / span
            point = RoutePoint(
                latitude=before.latitude + (after.latitude - before.latitude) * ratio,
                longitude=before.longitude + (after.longitude - before.longitude) * ratio,
                cumulative_miles=target,
                cumulative_seconds=before.cumulative_seconds + (after.cumulative_seconds - before.cumulative_seconds) * ratio,
            )
            elapsed = point.cumulative_seconds
        output.append({"mile": target, "latitude": point.latitude, "longitude": point.longitude, "arrival_time": route.departure_time + timedelta(seconds=elapsed)})
    return output
