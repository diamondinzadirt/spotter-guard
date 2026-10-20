from .providers import ProviderError, ProviderNotConfigured, UnconfiguredRoutingProvider, UnconfiguredWeatherProvider


class RoutePlanningService:
    def __init__(self, routing_provider=None, weather_provider=None):
        self.routing_provider = routing_provider or UnconfiguredRoutingProvider()
        self.weather_provider = weather_provider or UnconfiguredWeatherProvider()

    def plan(self, request):
        candidates = self.routing_provider.candidates(
            request["origin"], request["destination"], request["departure_time"], request["load_weight_lb"]
        )
        if len(candidates) < 3:
            raise ProviderError(f"Only {len(candidates)} valid truck routes are available; 3 were requested")
        raise ProviderNotConfigured("Weather provider is required to assemble the existing risk-aware response contract")
