from rest_framework import serializers
from .models import Foyer

class FoyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Foyer
        fields = '__all__'
