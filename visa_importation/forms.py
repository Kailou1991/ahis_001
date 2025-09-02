# visa_importation/forms.py

from django import forms
from .models import FactureImportationVisee


class FactureImportationForm(forms.ModelForm):
    class Meta:
        model = FactureImportationVisee
        fields = ['numero_facture', 'fichier_facture','Structure']
        widgets = {
            'numero_facture': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex : FACT-2025-001'
            }),
             'Structure': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la structure'
            }),

           
            'fichier_facture': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'numero_facture': 'Numéro de la facture',
            'fichier_facture': 'Facture visée (PDF)',
            'Structure': 'Nom de la Structure'
        }
