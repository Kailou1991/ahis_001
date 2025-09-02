from django import forms
from .models import (
    AgentInspecteur, StructureVente, InspectionEtablissement,
    ControleDocumentaireDetaillant, VerificationPhysiqueProduits,
    ConditionsDelivrance, GestionDechetsBiomedicaux,
    DescriptionLocaux, OperationsDistribution
)

class AgentInspecteurForm(forms.ModelForm):
    class Meta:
        model = AgentInspecteur
        fields = '__all__'


class StructureVenteForm(forms.ModelForm):
    class Meta:
        model = StructureVente
        fields = '__all__'


class InspectionEtablissementForm(forms.ModelForm):
    class Meta:
        model = InspectionEtablissement
        fields = '__all__'


class ControleDocumentaireDetaillantForm(forms.ModelForm):
    class Meta:
        model = ControleDocumentaireDetaillant
        fields = '__all__'


class VerificationPhysiqueProduitsForm(forms.ModelForm):
    class Meta:
        model = VerificationPhysiqueProduits
        fields = '__all__'


class ConditionsDelivranceForm(forms.ModelForm):
    class Meta:
        model = ConditionsDelivrance
        fields = '__all__'


class GestionDechetsBiomedicauxForm(forms.ModelForm):
    class Meta:
        model = GestionDechetsBiomedicaux
        fields = '__all__'


class DescriptionLocauxForm(forms.ModelForm):
    class Meta:
        model = DescriptionLocaux
        fields = '__all__'


class OperationsDistributionForm(forms.ModelForm):
    class Meta:
        model = OperationsDistribution
        fields = '__all__'
