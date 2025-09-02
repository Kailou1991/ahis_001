# data_initial/forms.py

from django import forms
from Maladie.models import Maladie
from Campagne.models import Campagne

class FiltreStatistiquesForm(forms.Form):
    maladie = forms.ModelChoiceField(
        queryset=Maladie.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'placeholder': 'Sélectionnez une maladie'}),
        label="Sélectionnez une maladie"
    )
    campagne = forms.ModelChoiceField(
        queryset=Campagne.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'placeholder': 'Sélectionnez une campagne'}),
        label="Sélectionnez une campagne"
    )
