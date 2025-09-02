from django import forms
from .models import Region, Departement, Commune, Titre, Entite,Personnel

class RegionForm(forms.ModelForm):
    class Meta:
        model = Region
        fields = ['Nom']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        session = kwargs.pop('session', None)
        super(RegionForm, self).__init__(*args, **kwargs)
        if user:
            region_id = session.get('region_id') if session else None
            if region_id:
                self.fields['Nom'].queryset = Region.objects.filter(id=region_id)
            else:
                self.fields['Nom'].queryset = Region.objects.all()

class DepartementForm(forms.ModelForm):
    class Meta:
        model = Departement
        fields = ['Nom', 'Region']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        session = kwargs.pop('session', None)
        super(DepartementForm, self).__init__(*args, **kwargs)
        if user:
            region_id = session.get('region_id') if session else None
            if region_id:
                self.fields['Region'].queryset = Region.objects.filter(id=region_id)
            else:
                self.fields['Region'].queryset = Region.objects.all()

class CommuneForm(forms.ModelForm):
    class Meta:
        model = Commune
        fields = ['Nom', 'DepartementID']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        session = kwargs.pop('session', None)
        super(CommuneForm, self).__init__(*args, **kwargs)
        if user:
            departement_id = session.get('departement_id') if session else None
            if departement_id:
                self.fields['DepartementID'].queryset = Departement.objects.filter(id=departement_id)
            else:
                self.fields['DepartementID'].queryset = Departement.objects.all()


class TitreForm(forms.ModelForm):
    class Meta:
        model = Titre
        fields = ['nom']

class EntiteForm(forms.ModelForm):
    class Meta:
        model = Entite
        fields = ['nom']

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = '__all__'  # Inclut tous les champs du modèle
        widgets = {
            'user': forms.HiddenInput(),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'entite_administrative': forms.Select(attrs={'class': 'form-control'}),
            'titre': forms.Select(attrs={'class': 'form-control'}),
            'nbre': forms.NumberInput(attrs={'class': 'form-control'}),
            'region': forms.Select(attrs={'class': 'form-control','id':'region'}),
            'departement': forms.Select(attrs={'class': 'form-control','id':'departement'}),
            'commune': forms.Select(attrs={'class': 'form-control','id':'commune'}),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
           
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        session = kwargs.pop('session', None)
        super(PersonnelForm, self).__init__(*args, **kwargs)

        if user:
            region_id = session.get('region_id') if session else None
            departement_id = session.get('departement_id') if session else None

            # Administrateur régional : Filtrer les régions et départements en fonction de la région de l'utilisateur
            if user.is_superuser:
                self.fields['region'].queryset = Region.objects.all()
                self.fields['departement'].queryset = Departement.objects.all()
                self.fields['commune'].queryset = Commune.objects.all()
            elif region_id:
                self.fields['region'].queryset = Region.objects.filter(id=region_id)
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID__Region_id=region_id)
            elif departement_id:
                # Administrateur départemental : Filtrer seulement le département et les communes
                self.fields['departement'].queryset = Departement.objects.filter(id=departement_id, Region_id=region_id)
                self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)

