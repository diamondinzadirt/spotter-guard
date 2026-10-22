import math

from rest_framework import serializers


class RoutePlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0)
    checkpoint_interval_miles = serializers.ChoiceField(choices=(10, 25, 50))

    def validate_origin(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Origin is required.")
        return value

    def validate_destination(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Destination is required.")
        return value

    def validate_load_weight_lb(self, value):
        if not math.isfinite(value) or value <= 0:
            raise serializers.ValidationError("Load weight must be a finite value greater than zero.")
        return value

    def validate(self, attrs):
        if attrs["origin"].casefold() == attrs["destination"].casefold():
            raise serializers.ValidationError({"destination": "Destination must differ from origin."})
        return attrs
