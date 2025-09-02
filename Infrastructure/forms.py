from django import forms
from .models import Infrastructure, Inspection, TypeFinancement

class InfrastructureForm(forms.ModelForm):
    type_financement = forms.ModelChoiceField(
        queryset=TypeFinancement.objects.all(),
        required=False,
        label="Type de financement"
    )

    class Meta:
        model = Infrastructure
        fields = '__all__'
        widgets = {
            'date_construction': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'date_naissance_proprietaire': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        type_proprietaire = cleaned_data.get('type_proprietaire')

        if type_proprietaire == 'PRIVEE':
            required_fields = [
                'nom_proprietaire', 'telephone_proprietaire', 'email_proprietaire',
                'adresse_proprietaire', 'piece_identite_proprietaire', 'numero_piece_identite',
                'sexe_proprietaire', 'date_naissance_proprietaire'
            ]

            for field_name in required_fields:
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, "Ce champ est requis pour un propriétaire privé.")

class InspectionForm(forms.ModelForm):
    class Meta:
        model = Inspection
        exclude = ['etat_derniere_inspection']
        widgets = {
            'date_inspection': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if not isinstance(self.fields[field].widget, forms.CheckboxInput):
                self.fields[field].widget.attrs['class'] = 'form-control'
