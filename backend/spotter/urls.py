from django.urls import path

from .views import RoutePlanView

urlpatterns = [path("routes/plan", RoutePlanView.as_view(), name="route-plan")]
