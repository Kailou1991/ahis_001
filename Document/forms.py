from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['type_document', 'libelle', 'date_de_mise_en_application', 'date_de_publication', 
                  'autorite_emission', 'version', 'fichier', 'mots_cles', 'description', 'valide']
        widgets = {
            'date_de_mise_en_application': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_de_publication': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fichier': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'libelle': forms.TextInput(attrs={'class': 'form-control'}),
            'autorite_emission': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'mots_cles': forms.TextInput(attrs={'class': 'form-control'}),
            'type_document': forms.Select(attrs={'class': 'form-control'}),
            'valide': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
