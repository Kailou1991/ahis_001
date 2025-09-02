from django import forms
from .models import Conge

class CongeForm(forms.ModelForm):
    class Meta:
        model = Conge
        fields = ['employe', 'type_conge', 'date_debut', 'date_fin', 'statut', 'remarque']
        widgets = {
            'employe': forms.Select(attrs={'class': 'form-control', 'id': 'id_employe'}),
            'type_conge': forms.Select(attrs={'class': 'form-control', 'id': 'id_type_conge'}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_date_debut'}, format='%Y-%m-%d'),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_date_fin'}, format='%Y-%m-%d'),
            'statut': forms.Select(attrs={'class': 'form-control', 'id': 'id_statut'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'id': 'id_remarque'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get("date_debut")
        date_fin = cleaned_data.get("date_fin")

        if date_debut and date_fin and date_fin < date_debut:
            raise forms.ValidationError("La date de fin doit être après la date de début.")

        return cleaned_data
