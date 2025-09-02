from rest_framework import serializers
from Departement.models import Departement
from Commune.models import Commune

class DepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departement
        fields = ['id', 'Nom']

class CommuneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commune
        fields = ['id', 'Nom']
