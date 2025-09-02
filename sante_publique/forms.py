from django import forms
from .models import (
    RegistreAbattage,
    RegistreInspectionAnteMortem,
    RegistreSaisiesTotales,
    RegistreSaisiesOrganes,
    InspectionViande,
    Departement,
    Commune,
    Region
)
import datetime


class RegistreAbattageForm(forms.ModelForm):
    ages = forms.ChoiceField(choices=RegistreAbattage.AGE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    sexes = forms.ChoiceField(choices=RegistreAbattage.SEXE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = RegistreAbattage
        exclude = ['user', 'date_enregistrement']
        widgets = {
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['observations', 'ages', 'sexes']:
                self.fields[field].widget.attrs.update({'class': 'form-control'})
        
        self.fields['departement'].queryset = Departement.objects.none()
        self.fields['commune'].queryset = Commune.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
            except (ValueError, TypeError):
                pass

        if 'departement' in self.data:
            try:
                departement_id = int(self.data.get('departement'))
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['departement'].queryset = Departement.objects.filter(Region=self.instance.region)
            self.fields['commune'].queryset = Commune.objects.filter(DepartementID=self.instance.departement)


class RegistreInspectionAnteMortemForm(forms.ModelForm):
    anomalies = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    symptomes = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = RegistreInspectionAnteMortem
        exclude = ['user', 'date_enregistrement']
        widgets = {
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['anomalies', 'symptomes', 'observations']:
                self.fields[field].widget.attrs.update({'class': 'form-control'})
        
        self.fields['departement'].queryset = Departement.objects.none()
        self.fields['commune'].queryset = Commune.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
            except (ValueError, TypeError):
                pass
        
        if 'departement' in self.data:
            try:
                departement_id = int(self.data.get('departement'))
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['departement'].queryset = Departement.objects.filter(Region=self.instance.region)
            self.fields['commune'].queryset = Commune.objects.filter(DepartementID=self.instance.departement)


class RegistreSaisiesTotalesForm(forms.ModelForm):
    class Meta:
        model = RegistreSaisiesTotales
        exclude = ['user', 'date_enregistrement']
        widgets = {
            'motifs_saisies': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['motifs_saisies', 'observations']:
                self.fields[field].widget.attrs.update({'class': 'form-control'})

        self.fields['departement'].queryset = Departement.objects.none()
        self.fields['commune'].queryset = Commune.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
            except (ValueError, TypeError):
                pass
        
        if 'departement' in self.data:
            try:
                departement_id = int(self.data.get('departement'))
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['departement'].queryset = Departement.objects.filter(Region=self.instance.region)
            self.fields['commune'].queryset = Commune.objects.filter(DepartementID=self.instance.departement)


class RegistreSaisiesOrganesForm(forms.ModelForm):
    class Meta:
        model = RegistreSaisiesOrganes
        exclude = ['user', 'date_enregistrement']
        widgets = {
            'organes_saisis': forms.TextInput(attrs={'class': 'form-control'}),
            'motifs_saisies_organes': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['organes_saisis', 'motifs_saisies_organes', 'observations']:
                self.fields[field].widget.attrs.update({'class': 'form-control'})

        self.fields['departement'].queryset = Departement.objects.none()
        self.fields['commune'].queryset = Commune.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
            except (ValueError, TypeError):
                pass
        
        if 'departement' in self.data:
            try:
                departement_id = int(self.data.get('departement'))
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['departement'].queryset = Departement.objects.filter(Region=self.instance.region)
            self.fields['commune'].queryset = Commune.objects.filter(DepartementID=self.instance.departement)


class InspectionViandeForm(forms.ModelForm):
    class Meta:
        model = InspectionViande
        exclude = ['date_enregistrement']
        widgets = {
            'abattoir': forms.TextInput(attrs={'class': 'form-control'}),
            'date_inspection': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'inspecteur': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_lot': forms.TextInput(attrs={'class': 'form-control'}),
            'espece': forms.Select(attrs={'class': 'form-control'}),
            'autre_espece': forms.TextInput(attrs={'class': 'form-control'}),
            'etat_animal': forms.Select(attrs={'class': 'form-control'}),
            'signes_anormaux': forms.Select(attrs={'class': 'form-control'}),
            'autre_signe_anormal': forms.TextInput(attrs={'class': 'form-control'}),
            'aspect_carcasse': forms.Select(attrs={'class': 'form-control'}),
            'poumons': forms.Select(attrs={'class': 'form-control'}),
            'foie': forms.Select(attrs={'class': 'form-control'}),
            'rate': forms.Select(attrs={'class': 'form-control'}),
            'coeur': forms.Select(attrs={'class': 'form-control'}),
            'description_anomalies': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'signature_inspecteur': forms.TextInput(attrs={'class': 'form-control'}),
        }
class PeriodeRapportForm(forms.Form):
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
        label="Choisir la région"
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
        label="Type de période",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    semaine = forms.IntegerField(
        label="Semaine (1-52)",
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    mois = forms.ChoiceField(
        choices=[(i, m) for i, m in enumerate([
            'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
            'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
        ], 1)],
        label="Mois",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    trimestre = forms.ChoiceField(
        choices=[(1, '1er trimestre'), (2, '2e trimestre'), (3, '3e trimestre'), (4, '4e trimestre')],
        label="Trimestre",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    semestre = forms.ChoiceField(
        choices=[(1, '1er semestre'), (2, '2e semestre')],
        label="Semestre",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    annee = forms.ChoiceField(
        choices=[(year, year) for year in range(2018, datetime.date.today().year + 1)],
        label="Année",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, region_session=None, **kwargs):
        super().__init__(*args, **kwargs)
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
            self.add_error('semaine', 'Veuillez renseigner la semaine.')
        if periode_type == 'Mensuel' and not mois:
            self.add_error('mois', 'Veuillez renseigner le mois.')
        if periode_type == 'Trimestriel' and not trimestre:
            self.add_error('trimestre', 'Veuillez renseigner le trimestre.')
        if periode_type == 'Semestriel' and not semestre:
            self.add_error('semestre', 'Veuillez renseigner le semestre.')
        if periode_type == 'Annuel' and not annee:
            self.add_error('annee', 'Veuillez renseigner l\'année.')

        return cleaned_data
