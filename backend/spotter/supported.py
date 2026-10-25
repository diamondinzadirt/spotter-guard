SUPPORTED_JOURNEYS = {
    ("denver, co", "kansas city, mo"),
    ("dallas, tx", "los angeles, ca"),
    ("seattle, wa", "portland, or"),
}


def journey_key(origin: str, destination: str):
    return origin.strip().casefold(), destination.strip().casefold()


def is_coordinate_pair(value: str):
    try:
        latitude, longitude = (part.strip() for part in value.split(","))
        float(latitude)
        float(longitude)
        return True
    except (ValueError, TypeError):
        return False
