from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import error_response
from .serializers import RoutePlanRequestSerializer
from .services import RoutePlanningService
from .providers import ProviderError, ProviderNotConfigured


class RoutePlanView(APIView):
    def post(self, request):
        serializer = RoutePlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("invalid_request", serializer.errors, status.HTTP_400_BAD_REQUEST)
        try:
            response = RoutePlanningService().plan(serializer.validated_data)
        except ProviderNotConfigured as error:
            return error_response("provider_not_configured", str(error), status.HTTP_503_SERVICE_UNAVAILABLE)
        except ProviderError as error:
            return error_response("provider_request_failed", str(error), status.HTTP_502_BAD_GATEWAY)
        return Response(response, status=status.HTTP_200_OK)
