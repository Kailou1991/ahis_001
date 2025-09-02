from rest_framework.decorators import api_view
from rest_framework.response import Response
from Departement.models import Departement
from Commune.models import Commune
from .serializers import DepartementSerializer, CommuneSerializer

@api_view(['GET'])
def get_departements_by_region(request):
    region_id = request.GET.get('region_id')
    if region_id:
        departements = Departement.objects.filter(Region=region_id).order_by('Nom')
        serializer = DepartementSerializer(departements, many=True)
        return Response(serializer.data)
    return Response([])

@api_view(['GET'])
def get_communes_by_departement(request):
    departement_id = request.GET.get('departement_id')
    if departement_id:
        communes = Commune.objects.filter(DepartementID=departement_id).order_by('Nom')
        serializer = CommuneSerializer(communes, many=True)
        return Response(serializer.data)
    return Response([])
