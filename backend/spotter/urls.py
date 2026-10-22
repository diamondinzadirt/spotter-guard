from django.urls import path

from .views import RoutePlanView, health

urlpatterns = [
    path("health", health, name="health"),
    path("routes/plan", RoutePlanView.as_view(), name="route-plan"),
]
