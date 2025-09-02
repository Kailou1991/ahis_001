# forms.py — filtrage serveur avec gestion de session
from django import forms
from .models import DemandeActe, Justificatif, TypeActe, AffectationSuivi, Region, Departement, Commune
from django.contrib.auth.models import User

class DemandeActeForm(forms.ModelForm):
    class Meta:
        model = DemandeActe
        exclude = ['user', 'statut', 'date_soumission', 'document_final']

    def __init__(self, *args, **kwargs):
        session = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)

        # Style Bootstrap
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

        # Ajout d'IDs si besoin plus tard pour JS
        self.fields['categorie'].widget.attrs.update({'id': 'id_categorie'})
        self.fields['acte'].widget.attrs.update({'id': 'id_acte'})

        # Filtrage dynamique côté serveur
        self.fields['acte'].queryset = TypeActe.objects.none()

        if 'categorie' in self.data:
            try:
                categorie_id = int(self.data.get('categorie'))
                self.fields['acte'].queryset = TypeActe.objects.filter(categorie_id=categorie_id).order_by('nom')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.categorie:
            self.fields['acte'].queryset = self.instance.categorie.actes.order_by('nom')

        # Filtrage géographique via session
        if session:
            region_id = session.get('region_id')
            departement_id = session.get('departement_id')

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


class DocumentFinalForm(forms.ModelForm):
    class Meta:
        model = DemandeActe
        fields = ['document_final']
        labels = {'document_final': "Document signé (PDF)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document_final'].widget.attrs.update({'class': 'form-control'})


class JustificatifForm(forms.ModelForm):
    class Meta:
        model = Justificatif
        fields = ['nom', 'fichier']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class AffectationForm(forms.ModelForm):
    class Meta:
        model = AffectationSuivi
        fields = ['agent', 'commentaire']
        labels = {
            'agent': "Agent chargé du suivi",
            'commentaire': "Instructions / Commentaires",
        }

    def __init__(self, *args, **kwargs):
        demande = kwargs.pop('demande', None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        agents = User.objects.filter(groups__name="Agent de suivi de demande")
        if demande:
            agents_deja_affectes = demande.affectations.values_list('agent_id', flat=True)
            #agents = agents.exclude(id__in=agents_deja_affectes)

        #self.fields['agent'].queryset = agents
        self.fields['agent'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"
