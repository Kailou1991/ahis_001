from django.contrib import admin
from .models import (
    AgentInspecteur, StructureVente, InspectionEtablissement,
    ControleDocumentaireDetaillant, VerificationPhysiqueProduits,
    ConditionsDelivrance, GestionDechetsBiomedicaux,
    DescriptionLocaux, OperationsDistribution
)

admin.site.register(AgentInspecteur)
admin.site.register(StructureVente)
admin.site.register(InspectionEtablissement)
admin.site.register(ControleDocumentaireDetaillant)
admin.site.register(VerificationPhysiqueProduits)
admin.site.register(ConditionsDelivrance)
admin.site.register(GestionDechetsBiomedicaux)
admin.site.register(DescriptionLocaux)
admin.site.register(OperationsDistribution)
