from rest_framework import status
from rest_framework.views import APIView

from .errors import error_response
from .serializers import RoutePlanRequestSerializer
from .services import RoutePlanningService
from .providers import ProviderNotConfigured


class RoutePlanView(APIView):
    def post(self, request):
        serializer = RoutePlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("invalid_request", serializer.errors, status.HTTP_400_BAD_REQUEST)
        try:
            response = RoutePlanningService().plan(serializer.validated_data)
        except ProviderNotConfigured as error:
            return error_response("provider_not_configured", str(error), status.HTTP_503_SERVICE_UNAVAILABLE)
        return response
