from rest_framework.response import Response


def error_response(code: str, message: str, status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=status)
