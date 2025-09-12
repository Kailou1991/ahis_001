# forms.py
from __future__ import annotations
from django import forms
from semantic_layer.models import DatasetLogical

class ViewWizardForm(forms.Form):
    dataset = forms.ModelChoiceField(
        queryset=DatasetLogical.objects.filter(active=True).order_by("name"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    slug = forms.SlugField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    default_group_dims = forms.CharField(
        help_text="Ex: date,region,maladie",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    default_metrics = forms.CharField(
        help_text="Ex: nb_malades:sum;nb_morts:sum",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    visible_filters = forms.CharField(
        help_text="Ex: periode,region,maladie",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
