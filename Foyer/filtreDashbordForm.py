from django import forms
from .models import Maladie, Periode, Region

class FiltreTableauForm(forms.Form):
    # Maladie : choix parmi les maladies disponibles
    maladie = forms.ModelChoiceField(queryset=Maladie.objects.all(), required=False, label="Choisir la Maladie")
    
    # Période : choix parmi les périodes (Hebdomadaire, Mensuel, Trimestriel, etc.)
    periode_choices = [
        ('Hebdomadaire', 'Hebdomadaire'),
        ('Mensuel', 'Mensuel'),
        ('Trimestriel', 'Trimestriel'),
        ('Semestriel', 'Semestriel'),
        ('Annuel', 'Annuel'),
    ]
    periode = forms.ChoiceField(choices=periode_choices, required=False, label="Choisir la Période")
    
    # Région : choix parmi les régions disponibles
    region = forms.ModelChoiceField(queryset=Region.objects.all(), required=False, label="Choisir la Région")
