from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    NO_TRAVEL = "no_travel"


@dataclass(frozen=True)
class RiskReading:
    wind_mph: float
    rainfall_in_hr: float
    snowfall_in_hr: float


RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.SEVERE: 3,
    RiskLevel.NO_TRAVEL: 4,
}


def _wind_risk(wind_mph: float) -> RiskLevel:
    if wind_mph >= 55:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= 45:
        return RiskLevel.SEVERE
    if wind_mph >= 35:
        return RiskLevel.HIGH
    if wind_mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _rain_risk(rainfall_in_hr: float) -> RiskLevel:
    if rainfall_in_hr > 1.00:
        return RiskLevel.NO_TRAVEL
    if rainfall_in_hr >= 0.50:
        return RiskLevel.SEVERE
    if rainfall_in_hr >= 0.25:
        return RiskLevel.HIGH
    if rainfall_in_hr >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _snow_risk(snowfall_in_hr: float) -> RiskLevel:
    if snowfall_in_hr > 3.00:
        return RiskLevel.NO_TRAVEL
    if snowfall_in_hr >= 2.00:
        return RiskLevel.SEVERE
    if snowfall_in_hr >= 1.00:
        return RiskLevel.HIGH
    if snowfall_in_hr >= 0.50:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_risk(reading: RiskReading, load_weight_lb: float) -> RiskLevel:
    """Classify one arrival-weather reading using the assessment rules.

    The weather dimensions are combined by taking the highest applicable
    classification. Load rules only add the specified wind-based overrides.
    """
    if load_weight_lb < 0:
        raise ValueError("load_weight_lb cannot be negative")
    wind_risk = _wind_risk(reading.wind_mph)
    load_risk = RiskLevel.LOW
    if 45 <= reading.wind_mph < 55 and load_weight_lb > 30_000:
        load_risk = RiskLevel.NO_TRAVEL
    elif 35 <= reading.wind_mph < 45 and load_weight_lb > 40_000:
        load_risk = RiskLevel.SEVERE
    risks = (wind_risk, _rain_risk(reading.rainfall_in_hr), _snow_risk(reading.snowfall_in_hr), load_risk)
    return max(risks, key=RISK_ORDER.__getitem__)


def recommendation_key(route: dict) -> tuple[float, float, float, float]:
    """Return the exact requested recommendation ordering."""
    return (route["severe_miles"], route["high_miles"], route["average_risk"], route["duration_minutes"])
