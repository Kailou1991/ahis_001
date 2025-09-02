from django import forms
from .models import ObjectifSn

class ObjectifSnForm(forms.ModelForm):
    class Meta:
        model = ObjectifSn
        fields = '__all__'
