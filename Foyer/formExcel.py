from django import forms

class FoyerImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'})
    )
