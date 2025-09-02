from django import forms
from .models import Campagne

class CampagneForm(forms.ModelForm):
    class Meta:
        model = Campagne
        fields = ['Campagne', 'type_campagne']
        labels = {
            'Campagne': 'Période de la campagne (ex: 2024-2025)',
            'type_campagne': 'Type de campagne'
        }
        widgets = {
            'Campagne': forms.TextInput(attrs={'class': 'form-control'}),
            'type_campagne': forms.Select(attrs={'class': 'form-control'})
        }
