from django import forms
from .models import Employe, HistoriqueCarriere, Poste, Formation
from gestion_documents.models import Document
from django.core.exceptions import ValidationError

class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = ['matricule', 'nom', 'prenom', 'date_naissance', 'sexe', 'adresse', 'telephone', 'email', 'date_embauche', 'poste', 'position', 'grade', 'echelon']
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'date_naissance': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'sexe': forms.Select(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'date_embauche': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'poste': forms.Select(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'grade': forms.Select(attrs={'class': 'form-control'}),
            'echelon': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'instance' in kwargs and kwargs['instance']:
            # Modification d'un employé existant
            employe = kwargs['instance']
            self.fields['poste'].queryset = Poste.objects.filter(statut='vacant') | Poste.objects.filter(id=employe.poste.id)
        else:
            # Ajout d'un nouvel employé
            self.fields['poste'].queryset = Poste.objects.filter(statut='vacant')

    def save(self, commit=True):
        employe = super().save(commit=False)
        if commit:
            employe.save()
        return employe
    

class HistoriqueCarriereForm(forms.ModelForm):
    TYPE_CHOIX = [
        ('Promotion', 'Promotion'),
        ('Mutation', 'Mutation'),
        ('Réaffectation', 'Réaffectation'),
        ('Detachement', 'Detachement'),
        ('Disponibilité', 'Disponibilité'),
        ('Stage', 'Stage'),
        ('Fin de contrat', 'Fin de contrat'),
        ('Licenciement', 'Licenciement'),
        ('Démission', 'Démission'),
        ('Changement de grade', 'Changement de grade'),
        ('Changement d’échelon', 'Changement d’échelon'),
        ('Affectation temporaire', 'Affectation temporaire'),
        ('Réintégration après absence', 'Réintégration après absence'),
        ('Mise en congé longue durée', 'Mise en congé longue durée'),
    ]

    type_changement = forms.ChoiceField(
        choices=TYPE_CHOIX,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = HistoriqueCarriere
        fields = ['date_debut', 'date_fin', 'type_changement', 'remarque']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ajouter une remarque...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_fin and date_fin < date_debut:
            raise ValidationError("La date de fin doit être après la date de début.")
        return cleaned_data

    def save(self, commit=True):
        historique_carriere = super().save(commit=False)
        if commit:
            historique_carriere.save()
        return historique_carriere

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['nom', 'type_document', 'fichier']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'type_document': forms.Select(attrs={'class': 'form-control'}),
            'fichier': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = ['intitule', 'institution', 'date_debut', 'date_fin', 'diplome_obtenu']
        widgets = {
            'intitule': forms.TextInput(attrs={'class': 'form-control'}),
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'diplome_obtenu': forms.TextInput(attrs={'class': 'form-control'}),
        }

class EmployeWithHistoriqueForm(forms.Form):
    employe = EmployeForm()
    historique_carriere = HistoriqueCarriereForm()
    document = DocumentForm()
    formation = FormationForm()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.employe = EmployeForm(*args, **kwargs)
        self.historique_carriere = HistoriqueCarriereForm(*args, **kwargs)
        self.document = DocumentForm(*args, **kwargs)
        self.formation = FormationForm(*args, **kwargs)

    def is_valid(self):
        return (self.employe.is_valid() and 
                self.historique_carriere.is_valid() and 
                self.document.is_valid() and 
                self.formation.is_valid())

    def save(self):
        employe_instance = self.employe.save(commit=False)
        historique_instance = self.historique_carriere.save(commit=False)
        document_instance = self.document.save(commit=False)
        formation_instance = self.formation.save(commit=False)

        employe_instance.save()
        historique_instance.employe = employe_instance
        historique_instance.save()
        document_instance.employe = employe_instance
        document_instance.save()
        formation_instance.employe = employe_instance
        formation_instance.save()

        return employe_instance, historique_instance, document_instance, formation_instance