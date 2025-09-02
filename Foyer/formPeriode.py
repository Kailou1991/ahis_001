from django import forms
import datetime
from .models import Region, Maladie,Foyer

class PeriodeRapportForm(forms.Form):
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}), 
        required=False, 
        label="Choisir la Région"
    )
    maladie = forms.ModelChoiceField(
        
        queryset=Maladie.objects.filter(id__in=Foyer.objects.values('maladie')).distinct(), 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-control'}), 
        label="Choisir la Maladie"
    )

    CHOIX_PERIODE = [
        ('Hebdomadaire', 'Hebdomadaire'),
        ('Mensuel', 'Mensuel'),
        ('Trimestriel', 'Trimestriel'),
        ('Semestriel', 'Semestriel'),
        ('Annuel', 'Annuel'),
    ]
    
    periode_type = forms.ChoiceField(
        choices=CHOIX_PERIODE,
        label="Choisir la période",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    semaine = forms.IntegerField(
        label="Hebdomadaire (1-52)", 
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    mois = forms.ChoiceField(
        choices=[(i, m) for i, m in enumerate(['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                                                'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'], 1)],
        label="Mensuel",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    trimestre = forms.ChoiceField(
        choices=[(1, 'T1'), (2, 'T2'), (3, 'T3'), (4, 'T4')],
        label="Trimestriel",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    semestre = forms.ChoiceField(
        choices=[(1, 'S1'), (2, 'S2')],
        label="Semestriel",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    annee = forms.ChoiceField(
        choices=[(y, str(y)) for y in range(2018, datetime.date.today().year + 1)],
        label="Annuel",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, region_session=None, **kwargs):
        """
        Ajout d'un constructeur pour accepter region_session.
        """
        super().__init__(*args, **kwargs)
        # Filtrer les régions en fonction de region_session
        if region_session:
            self.fields['region'].queryset = Region.objects.filter(id=region_session)

    def clean(self):
        cleaned_data = super().clean()
        periode_type = cleaned_data.get('periode_type')
        semaine = cleaned_data.get('semaine')
        mois = cleaned_data.get('mois')
        trimestre = cleaned_data.get('trimestre')
        semestre = cleaned_data.get('semestre')
        annee = cleaned_data.get('annee')

        if periode_type == 'Hebdomadaire' and not semaine:
            self.add_error('semaine', 'Ce champ est requis pour une période hebdomadaire.')
        elif periode_type == 'Mensuel' and mois is None:
            self.add_error('mois', 'Ce champ est requis pour une période mensuelle.')
        elif periode_type == 'Trimestriel' and trimestre is None:
            self.add_error('trimestre', 'Ce champ est requis pour une période trimestrielle.')
        elif periode_type == 'Semestriel' and semestre is None:
            self.add_error('semestre', 'Ce champ est requis pour une période semestrielle.')
        elif periode_type == 'Annuel' and annee is None:
            self.add_error('annee', 'Ce champ est requis pour une période annuelle.')

        return cleaned_data
