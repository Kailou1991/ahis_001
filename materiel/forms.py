
# materiel/forms.py
from django import forms
from .models import Dotation
from .models import DotationDoseVaccin


class DateInput(forms.DateInput):
    input_type = "date"

class DotationForm(forms.ModelForm):
    class Meta:
        model = Dotation
        fields = ("campagne", "region", "type_materiel", "quantite", "date_dotation", "piece_jointe", "observations")
        labels = {
            "campagne": "Campagne de vaccination",
            "region": "Région",
            "type_materiel": "Type de matériel",
            "quantite": "Quantité",
            "date_dotation": "Date de dotation",
            "piece_jointe": "Pièce jointe (bon/PV)",
            "observations": "Observations",
        }
        widgets = {
            "campagne": forms.Select(attrs={"class": "form-select"}),
            "region": forms.Select(attrs={"class": "form-select"}),
            "type_materiel": forms.Select(attrs={"class": "form-select"}),
            "quantite": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "date_dotation": DateInput(attrs={"class": "form-control" }, format='%Y-%m-%d'),
            "piece_jointe": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            for name, field in self.fields.items():
                if self.errors.get(name):
                    field.widget.attrs["class"] = (field.widget.attrs.get("class", "") + " is-invalid").strip()



class DateInput(forms.DateInput):
    input_type = "date"

class DotationDoseVaccinForm(forms.ModelForm):
    class Meta:
        model = DotationDoseVaccin
        fields = ("campagne", "maladie", "quantite_doses", "date_dotation", "piece_jointe", "observations")
        labels = {
            "campagne": "Campagne",
            "maladie": "Maladie",
            "quantite_doses": "Quantité (doses)",
            "date_dotation": "Date de dotation",
            "piece_jointe": "Pièce jointe (bon/PV)",
            "observations": "Observations",
        }
        widgets = {
            "campagne": forms.Select(attrs={"class": "form-select"}),
            "maladie": forms.Select(attrs={"class": "form-select"}),
            "quantite_doses": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "date_dotation": DateInput(attrs={"class": "form-control"}, format='%Y-%m-%d'),
            "piece_jointe": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            for name, field in self.fields.items():
                if self.errors.get(name):
                    field.widget.attrs["class"] = (field.widget.attrs.get("class","") + " is-invalid").strip()
