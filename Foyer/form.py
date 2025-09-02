from django import forms
from .models import Foyer, Maladie
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

class FoyerForm(forms.ModelForm):
    class Meta:
        model = Foyer
        fields = [
            'date_signalement','date_rapportage', 'espece', 'maladie', 'region', 'departement', 'commune',
            'localite', 'lieu_suspicion', 'nom_lieu_suspicion', 'longitude', 'latitude',
            'effectif_troupeau', 'nbre_sujets_malade', 'nbre_sujets_morts',
            'nbre_des_cas_de_morsure_humains', 'nbre_des_cas_de_morsure_animaux',
            'mesure_controle', 'nbre_sujets_traites', 'nbre_sujets_vaccines',
            'nbre_sujets_en_quarantaine', 'nbre_sujets_abattus',
            'vaccinations_recentes', 'maladie_vaccination', 'date_vaccination',
            'prelevement_envoye', 'date_envoi_prelevement', 'nature_prelevement',
            'resultat_laboratoire','resultat_analyse','date_reception_prelevement','date_resultat','nbre_echant_recu','absence_reactifs',
              'nbre_echant_inexploitable',
            'laboratoire', 'type_test_labo', 'service_labo',
            'recommandations', 'fichier_resultat',
        ]
        widgets = {
            'date_rapportage': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'date_signalement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
           
            'date_vaccination': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'date_envoi_prelevement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'date_reception_prelevement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'date_resultat': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),

            'localite': forms.TextInput(attrs={'class': 'form-control'}),
            'lieu_suspicion':forms.Select(attrs={'class': 'form-control'}),
            'nom_lieu_suspicion': forms.TextInput(attrs={'class': 'form-control'}),
            'nature_prelevement': forms.Select(attrs={'class': 'form-control'}),

            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),

            'effectif_troupeau': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_malade': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_morts': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_des_cas_de_morsure_humains': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_des_cas_de_morsure_animaux': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_traites': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_vaccines': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_en_quarantaine': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_sujets_abattus': forms.NumberInput(attrs={'class': 'form-control'}),
            'nbre_echant_recu': forms.NumberInput(attrs={'class': 'form-control'}),
             'nbre_echant_inexploitable': forms.NumberInput(attrs={'class': 'form-control'}),
            'vaccinations_recentes': forms.Select(attrs={'class': 'form-control'}),
            'prelevement_envoye': forms.Select(attrs={'class': 'form-control'}),
            'resultat_laboratoire': forms.Select(attrs={'class': 'form-control'}),
            'resultat_analye': forms.Select(attrs={'class': 'form-control'}),
            'absence_reactifs': forms.Select(attrs={'class': 'form-control'}),
            'espece': forms.Select(attrs={'class': 'form-control'}),
            'maladie': forms.Select(attrs={'class': 'form-control'}),
            'region': forms.Select(attrs={'class': 'form-control'}),
            'departement': forms.Select(attrs={'class': 'form-control'}),
            'commune': forms.Select(attrs={'class': 'form-control'}),
            'maladie_vaccination': forms.Select(attrs={'class': 'form-control'}),
            'laboratoire': forms.Select(attrs={'class': 'form-control'}),
            'type_test_labo': forms.Select(attrs={'class': 'form-control'}),
            'service_labo': forms.Select(attrs={'class': 'form-control'}),
            'recommandations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fichier_resultat': forms.FileInput(attrs={'class': 'form-control'}),
            'mesure_controle': forms.SelectMultiple(attrs={'class': 'form-control', 'id': 'mesure_controle'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.session = kwargs.pop('session', None)
        super(FoyerForm, self).__init__(*args, **kwargs)

        # Filtrage dynamique des régions, départements, communes
        region_id = self.session.get('region_id') if self.session else None
        departement_id = self.session.get('departement_id') if self.session else None

        if region_id:
            self.fields['region'].queryset = Region.objects.filter(id=region_id)
        else:
            self.fields['region'].queryset = Region.objects.all()

        if region_id:
            if departement_id:
                self.fields['departement'].queryset = Departement.objects.filter(id=departement_id, Region_id=region_id)
            else:
                self.fields['departement'].queryset = Departement.objects.filter(Region_id=region_id)
        else:
            self.fields['departement'].queryset = Departement.objects.all()

        if departement_id:
            self.fields['commune'].queryset = Commune.objects.filter(DepartementID_id=departement_id)
        else:
            self.fields['commune'].queryset = Commune.objects.all()

        # Maladie liée à l'espèce
        self.fields['maladie'].queryset = Maladie.objects.none()
        if 'espece' in self.data:
            try:
                espece_id = int(self.data.get('espece'))
                self.fields['maladie'].queryset = Maladie.objects.filter(Espece=espece_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.espece:
            self.fields['maladie'].queryset = Maladie.objects.filter(Espece=self.instance.espece)

        # ID personnalisés JS
        js_ids = [
            'espece', 'maladie', 'region', 'departement', 'commune',
            'mesure_controle',
            'nbre_des_cas_de_morsure_humains', 'nbre_des_cas_de_morsure_animaux',
            'nbre_sujets_traites', 'nbre_sujets_vaccines',
            'nbre_sujets_en_quarantaine', 'nbre_sujets_abattus'
        ]
        for field_id in js_ids:
            if field_id in self.fields:
                self.fields[field_id].widget.attrs.update({
                    'id': f'id_{field_id}',
                    'data-js-control': 'true'
                })
