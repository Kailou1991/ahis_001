from django import forms
from .models import Produit, Enregistrement, Partenaire, Structure


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        exclude = ['user']
        widgets = {
            'user': forms.HiddenInput(),
            'type_produit': forms.Select(attrs={'class': 'form-control', 'id': 'type_produit'}),  # ✅ important
            'nom_du_produit': forms.TextInput(attrs={'class': 'form-control', 'id': 'nom_du_produit'}),
            'classe_therapeutique': forms.Select(attrs={'class': 'form-control', 'id': 'classe_therapeutique'}),
            'familles_antibiotiques': forms.Select(attrs={'class': 'form-control', 'id': 'familles_antibiotiques'}),
            'forme_pharmaceutique': forms.TextInput(attrs={'class': 'form-control', 'id': 'forme_pharmaceutique'}),
            'substances_actives': forms.TextInput(attrs={'class': 'form-control', 'id': 'substances_actives'}),
            'numero_autorisation_AMM': forms.TextInput(attrs={'class': 'form-control', 'id': 'numero_autorisation_AMM'}),
            'date_delivrance_AMM': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'date_delivrance_AMM'}, format='%Y-%m-%d'),
            'numero_decision_AMM': forms.TextInput(attrs={'class': 'form-control', 'id': 'numero_decision_AMM'}),
            'status_AMM': forms.Select(attrs={'class': 'form-control', 'id': 'status_AMM'}),
        }


class EnregistrementForm(forms.ModelForm):
    class Meta:
        model = Enregistrement
        exclude = ['user']
        widgets = {
            'user': forms.HiddenInput(),
            'type_enregistrement': forms.Select(attrs={'class': 'form-control', 'id': 'id_type_enregistrement'}),
            'produit': forms.Select(attrs={'class': 'form-control', 'id': 'produit-select'}),  # ✅ utilisé dans JS
            'quantité_de_la_dotation': forms.NumberInput(attrs={'class': 'form-control', 'id': 'quantité_de_la_dotation'}),
            'partenaire_de_dotation': forms.Select(attrs={'class': 'form-control', 'id': 'partenaire_de_dotation'}),
            'date_dotation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'date_dotation'}, format='%Y-%m-%d'),
            'adresse_partenaire_dotation': forms.TextInput(attrs={'class': 'form-control', 'id': 'adresse_partenaire_dotation'}),

            'quantité_fabriquée': forms.NumberInput(attrs={'class': 'form-control', 'id': 'quantité_fabriquée'}),
            'firme_de_fabrication': forms.Select(attrs={'class': 'form-control', 'id': 'firme_de_fabrication'}),
            'pays_de_fabrication': forms.Select(attrs={'class': 'form-control', 'id': 'pays_fabrication'}),
            'date_de_fabrication': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'date_de_fabrication'}, format='%Y-%m-%d'),

            'quantité_importée': forms.NumberInput(attrs={'class': 'form-control', 'id': 'quantité_importée'}),
            'structure_importatrice': forms.Select(attrs={'class': 'form-control', 'id': 'structure_importatrice'}),
            'addresse_importateur': forms.TextInput(attrs={'class': 'form-control', 'id': 'addresse_importateur'}),
            'date_importation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'date_importation'}, format='%Y-%m-%d'),
            'pays_importation': forms.Select(attrs={'class': 'form-control', 'id': 'pays_importation'}),

            'quantité_exportée': forms.NumberInput(attrs={'class': 'form-control', 'id': 'quantité_exportée'}),
            'structure_exportatrice': forms.Select(attrs={'class': 'form-control', 'id': 'structure_exportatrice'}),
            'addresse_exportateur': forms.TextInput(attrs={'class': 'form-control', 'id': 'addresse_exportateur'}),
            'date_exportation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'id': 'date_exportation'}, format='%Y-%m-%d'),
            'pays_exportation': forms.Select(attrs={'class': 'form-control', 'id': 'pays_exportation'}),

            'valeur_financiere': forms.NumberInput(attrs={'class': 'form-control', 'id': 'valeur_financiere'}),
            'unité_de_la_quantité': forms.TextInput(attrs={'class': 'form-control', 'id': 'unité_de_la_quantité'}),
        }


class PartenaireForm(forms.ModelForm):
    class Meta:
        model = Partenaire
        exclude = ['user']

        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'id': 'nom_partenaire'}),
        }


class StructureForm(forms.ModelForm):
    class Meta:
        model = Structure
        exclude = ['user']
        widgets = {
            'structure': forms.TextInput(attrs={'class': 'form-control', 'id': 'structure'}),
        }
