from django import forms
from .models import SurveillanceSn

class SurveillanceSnForm(forms.ModelForm):
    class Meta:
        model = SurveillanceSn
        fields = '__all__'
