from django import forms
from .models import DeplacementAnimal

class DeplacementAnimauxForm(forms.ModelForm):
    class Meta:
        model = DeplacementAnimal
        exclude = ['user', 'date_enregistrement']
        widgets = {
            'espece': forms.Select(attrs={'class': 'form-control'}),
            'nombre_animaux': forms.NumberInput(attrs={'class': 'form-control'}),

            # Localisation
            'region_provenance': forms.Select(attrs={'class': 'form-control'}),
            'departement_provenance': forms.Select(attrs={'class': 'form-control'}),
            'commune_provenance': forms.Select(attrs={'class': 'form-control'}),
            'region_destination': forms.Select(attrs={'class': 'form-control'}),
            'departement_destination': forms.Select(attrs={'class': 'form-control'}),
            'commune_destination': forms.Select(attrs={'class': 'form-control'}),
            'etablissement_origine': forms.TextInput(attrs={'class': 'form-control'}),
            'etablissement_destination': forms.TextInput(attrs={'class': 'form-control'}),

            # Déplacement
            'date_deplacement': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'duree_deplacement': forms.NumberInput(attrs={'class': 'form-control'}),
            'mode_transport': forms.Select(attrs={'class': 'form-control'}),
            'raison_deplacement': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),

            # Nouveaux champs remplacent les certificats
            'nombre_certificats_vaccination_controles': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_certificats_vaccination_delivres': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_laisser_passer_controles': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_laisser_passer_delivres': forms.NumberInput(attrs={'class': 'form-control'}),

            # Propriétaire
            'nom_proprietaire': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_proprietaire': forms.TextInput(attrs={'class': 'form-control'}),

            # Transporteur
            'nom_transporteur': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_transporteur': forms.TextInput(attrs={'class': 'form-control'}),

            # Coordonnées GPS du poste de contrôle
            'latitude_poste_controle': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'longitude_poste_controle': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),

            # Surveillance sanitaire
            'maladie_detectee': forms.Select(attrs={'class': 'form-control'}),
            'maladie_suspectee': forms.Select(attrs={'class': 'form-control'}),
            'nombre_animaux_malades': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_animaux_traites': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_animaux_vaccines': forms.NumberInput(attrs={'class': 'form-control'}),
            'nombre_animaux_quarantaine': forms.NumberInput(attrs={'class': 'form-control'}),
            'mesures_prises': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super(DeplacementAnimauxForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
