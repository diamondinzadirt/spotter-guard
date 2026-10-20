from .providers import ProviderNotConfigured, UnconfiguredRoutingProvider, UnconfiguredWeatherProvider


class RoutePlanningService:
    def __init__(self, routing_provider=None, weather_provider=None):
        self.routing_provider = routing_provider or UnconfiguredRoutingProvider()
        self.weather_provider = weather_provider or UnconfiguredWeatherProvider()

    def plan(self, request):
        candidates = self.routing_provider.candidates(request["origin"], request["destination"], request["departure_time"])
        if not candidates:
            raise ProviderNotConfigured("The routing provider returned no candidates")
        raise ProviderNotConfigured("Route response assembly is waiting for the weather provider integration")
