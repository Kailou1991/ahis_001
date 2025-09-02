from django import forms
from .models import VaccinationSn

class VaccinationSnForm(forms.ModelForm):
    class Meta:
        model = VaccinationSn
        fields = '__all__'
