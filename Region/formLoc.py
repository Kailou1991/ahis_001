from django import forms
from .models import Region, Departement, Commune, Titre, Entite

class RegionForm(forms.ModelForm):
    class Meta:
        model = Region
        fields = ['Nom', 'user']

class DepartementForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ['Nom', 'Region', 'user']

class CommuneForm(forms.ModelForm):
    class Meta:
        model = Commune
        fields = ['Nom', 'DepartementID', 'user']

class TitreForm(forms.ModelForm):
    class Meta:
        model = Titre
        fields = ['nom']

class EntiteForm(forms.ModelForm):
    class Meta:
        model = Entite
        fields = ['nom']
