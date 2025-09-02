# lims/forms.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory,BaseInlineFormSet
from django.contrib.auth import get_user_model

from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

from .models import (
    Demande, Echantillon, TestCatalogue, Analyse, Rapport,
    Equipement, Maintenance, LotReactif, Emplacement, StockageEchantillon,
    TraceEchantillon, GabaritRapport, PieceJointe,
    Soumissionnaire, DemandeComment, AnalyseComment, Delegation,
)

User = get_user_model()

# ======================================================================
# Helpers Bootstrap
# ======================================================================

def _is_select(widget):
    return isinstance(widget, (forms.Select, forms.SelectMultiple))

def _is_checkbox(widget):
    return isinstance(widget, forms.CheckboxInput)

class BootstrapModelForm(forms.ModelForm):
    """Ajoute automatiquement les classes Bootstrap 5 aux widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            w = field.widget
            if _is_checkbox(w):
                base = "form-check-input"
            elif _is_select(w):
                base = "form-select"
            else:
                base = "form-control"
            w.attrs["class"] = (w.attrs.get("class", "") + " " + base).strip()
            # si erreurs, marque le champ
            if name in self.errors:
                w.attrs["class"] += " is-invalid"

DATE_WIDGET = forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
DATETIME_WIDGET = forms.DateTimeInput(format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1"})

# ======================================================================
# Demande
# ======================================================================

# ... imports inchangés ...

class DemandeForm(BootstrapModelForm):
    class Meta:
        model = Demande
        fields = (
            "code_demande", "site_labo", "soumissionnaire",
            "region", "departement", "commune",
            "localite",
            "maladie_suspectee", "espece", "effectif_troupeau",
            "nbre_animaux_malades", "nbre_animaux_morts",
            "motif", "priorite", "date_echeance", "notes",
        )
        widgets = {
            "date_echeance": DATETIME_WIDGET,
            "notes": forms.Textarea(attrs={"rows": 3}),
            "motif": forms.TextInput(attrs={"placeholder": "Précisions libres (optionnel)"}),
            "localite": forms.TextInput(attrs={"placeholder": "Ex. Ngohé"}),
        }
        labels = {
            "maladie_suspectee": "Maladie suspectée",
            "motif": "Motif (commentaire libre)",
            "localite": "Localité (village)",
            "nbre_animaux_morts": "Nombre d'animaux morts",
            "effectif_troupeau": "Nombre d'animaux exposés",
            "nbre_animaux_malades": "Nombre d'animaux malades",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # >>> rendre les champs épidémiologiques non requis côté HTML
        for fname in ("espece", "effectif_troupeau", "nbre_animaux_malades", "nbre_animaux_morts"):
            if fname in self.fields:
                self.fields[fname].required = False

        # IDs explicites pour le JS (cascades)
        self.fields["region"].widget.attrs["id"] = "id_region"
        self.fields["departement"].widget.attrs["id"] = "id_departement"
        self.fields["commune"].widget.attrs["id"] = "id_commune"

        # Empty labels
        if hasattr(self.fields["region"], "empty_label"):
            self.fields["region"].empty_label = "— Sélectionner —"
        if hasattr(self.fields["departement"], "empty_label"):
            self.fields["departement"].empty_label = "— Sélectionner —"
        if hasattr(self.fields["commune"], "empty_label"):
            self.fields["commune"].empty_label = "— Sélectionner —"

        # Cascades Région → Département → Commune (inchangé)
        self.fields["departement"].queryset = Departement.objects.none()
        self.fields["commune"].queryset = Commune.objects.none()

        data = self.data if self.data else None
        instance = self.instance

        if data and data.get("region"):
            try:
                region_id = int(data.get("region"))
                self.fields["departement"].queryset = (
                    Departement.objects.filter(Region_id=region_id).order_by("Nom")
                )
            except (ValueError, TypeError):
                pass
        elif instance and instance.pk and instance.region_id:
            self.fields["departement"].queryset = (
                Departement.objects.filter(Region=instance.region).order_by("Nom")
            )

        if data and data.get("departement"):
            try:
                dep_id = int(data.get("departement"))
                self.fields["commune"].queryset = (
                    Commune.objects.filter(DepartementID_id=dep_id).order_by("Nom")
                )
            except (ValueError, TypeError):
                pass
        elif instance and instance.pk and instance.departement_id:
            self.fields["commune"].queryset = (
                Commune.objects.filter(DepartementID=instance.departement).order_by("Nom")
            )

        # Code immuable en édition
        if instance and instance.pk:
            self.fields["code_demande"].widget.attrs["readonly"] = "readonly"

    def clean_code_demande(self):
        code = self.cleaned_data.get("code_demande")
        if self.instance and self.instance.pk and code != self.instance.code_demande:
            raise ValidationError("Ce champ est immuable après création.")
        return code

    def clean(self):
        cleaned = super().clean()
        mal = cleaned.get("maladie_suspectee")

        # Normalisation des valeurs numériques
        ex = cleaned.get("effectif_troupeau")
        ma = cleaned.get("nbre_animaux_malades")
        mo = cleaned.get("nbre_animaux_morts")

        # On force 0 si laissé vide
        ex = 0 if ex in (None, "") else ex
        ma = 0 if ma in (None, "") else ma
        mo = 0 if mo in (None, "") else mo

        if not mal:
            # Pas de maladie → on “ignore” les champs épidémiologiques
            cleaned["espece"] = None
            cleaned["effectif_troupeau"] = 0
            cleaned["nbre_animaux_malades"] = 0
            cleaned["nbre_animaux_morts"] = 0
            return cleaned

        # Maladie renseignée → validations métier
        if cleaned.get("espece") is None:
            self.add_error("espece", "Ce champ est requis lorsque la maladie est renseignée.")

        # Non-négatifs
        if ex < 0:
            self.add_error("effectif_troupeau", "La valeur ne peut pas être négative.")
        if ma < 0:
            self.add_error("nbre_animaux_malades", "La valeur ne peut pas être négative.")
        if mo < 0:
            self.add_error("nbre_animaux_morts", "La valeur ne peut pas être négative.")

        # Cohérences
        if ma > ex:
            self.add_error("nbre_animaux_malades", "Le nombre d’animaux malades ne peut pas dépasser l’effectif exposé.")
        if ma + mo > ex:
            self.add_error("nbre_animaux_morts", "La somme des malades et des morts ne peut pas dépasser l’effectif exposé.")

        # Réinjecter les (potentiellement) normalisés
        cleaned["effectif_troupeau"] = ex
        cleaned["nbre_animaux_malades"] = ma
        cleaned["nbre_animaux_morts"] = mo
        return cleaned


class DemandeConclusionForm(BootstrapModelForm):
    """Confirmer / infirmer la suspicion + notes (porté par Demande)."""
    class Meta:
        model = Demande
        fields = ("suspicion_statut", "suspicion_notes")
        widgets = {
            "suspicion_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Motifs, éléments probants…"}),
        }
        labels = {
            "suspicion_statut": "Conclusion de suspicion",
            "suspicion_notes": "Notes de conclusion",
        }

# ======================================================================
# Échantillon
# ======================================================================
#DATE_WIDGET = forms.DateInput(attrs={"type": "date"})

# ----- Mixin Bootstrap -----
class BootstrapFormMixin:
    BOOTSTRAP_MAP = {
        forms.Select: "form-select",
        forms.SelectMultiple: "form-select",
        forms.CheckboxInput: "form-check-input",
    }

    def _add_class(self, widget, cls):
        base = widget.attrs.get("class", "")
        widget.attrs["class"] = (base + " " + cls).strip()

    def _bootstrapify(self):
        for name, field in self.fields.items():
            w = field.widget
            # Choix par type de widget
            applied = False
            for typ, css in self.BOOTSTRAP_MAP.items():
                if isinstance(w, typ):
                    self._add_class(w, css)
                    applied = True
                    break
            if not applied:
                # TextInput, NumberInput, DateInput, PasswordInput, Textarea, etc.
                self._add_class(w, "form-control")
            # Taille par défaut sur les textarea
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 2)


class EchantillonForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Echantillon
        fields = (
            "code_echantillon",
            "matrice", "matrice_autre",
            "id_animal", "date_prelevement", "commentaire","conformite","reception_externe","envoi_externe"
        )
        widgets = {
            "date_prelevement": DATE_WIDGET,
            "commentaire": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Bootstrap classes
        self._bootstrapify()
         # >>> ID animal jamais requis côté serveur
        if "id_animal" in self.fields:
            self.fields["id_animal"].required = False

        # Formats tolérés au POST
        self.fields["date_prelevement"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        # Aide “Autre”
        self.fields["matrice_autre"].widget.attrs.setdefault("placeholder", "Si ‘Autre’, précisez…")

        # Code en lecture seule à l'édition
        if self.instance and self.instance.pk:
            w = self.fields["code_echantillon"].widget
            w.attrs["readonly"] = "readonly"
            w.attrs["tabindex"] = "-1"
            # garde form-control et ajoute bg-light
            self._add_class(w, "bg-light")

    def clean(self):
        cleaned = super().clean()
        matrice = cleaned.get("matrice")
        matrice_autre = (cleaned.get("matrice_autre") or "").strip()
        # Si matrice == AUTRE → matrice_autre requis
        try:
            if matrice == Echantillon.Matrices.AUTRE and not matrice_autre:
                self.add_error("matrice_autre", "Merci de préciser la matrice.")
        except Exception:
            pass
        return cleaned

    def clean_code_echantillon(self):
        """
        Pas d'unicité globale ; seulement immuable en édition.
        """
        code = (self.cleaned_data.get("code_echantillon") or "").strip()
        if not code:
            return code
        if self.instance and self.instance.pk and code != self.instance.code_echantillon:
            raise ValidationError("Ce champ est immuable après création.")
        return code


class BaseEchantillonFormSet(BaseInlineFormSet):
    """
    Empêche les doublons de code dans la même page (formset),
    sans imposer d'unicité globale en base.
    """
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            code = (form.cleaned_data.get("code_echantillon") or "").strip()
            if not code:
                continue
            if code in seen:
                form.add_error("code_echantillon", "Doublon dans le formulaire.")
            seen.add(code)


# Factories création / édition
EchantillonFormSetCreate = inlineformset_factory(
    Demande, Echantillon,
    form=EchantillonForm,
    formset=BaseEchantillonFormSet,
    extra=1, can_delete=False,
)

EchantillonFormSetUpdate = inlineformset_factory(
    Demande, Echantillon,
    form=EchantillonForm,
    formset=BaseEchantillonFormSet,
    extra=0, can_delete=True,
)

# Compat : si du code ancien importe encore EchantillonFormSet
EchantillonFormSet = EchantillonFormSetCreate

# ======================================================================
# Analyse
# ======================================================================

class AnalyseForm(BootstrapModelForm):
    """Édition/gestion d’une analyse (sans champs de résultats bruts)."""
    class Meta:
        model = Analyse
        fields = (
            "echantillon", "test", "instrument", "analyste",
            "etat", "priorite", "date_echeance",
            "debute_le", "termine_le",
            "annulee", "motif_annulation",
        )
        widgets = {
            "debute_le": DATETIME_WIDGET,
            "termine_le": DATETIME_WIDGET,
            "date_echeance": DATETIME_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "instrument" in self.fields:
            self.fields["instrument"].queryset = (
                Equipement.objects.filter(type="instrument").order_by("nom")
            )

class AnalyseResultUploadForm(forms.Form):
    """
    Joindre la fiche des résultats (ou export) à une Analyse.
    """
    TYPE_CHOICES = [
        ("result_pdf", "Fiche résultats (PDF)"),
        ("raw_csv", "Export instrument (CSV)"),
        ("raw_json", "Export instrument (JSON)"),
        ("raw_xlsx", "Export instrument (XLSX)"),
        ("autre", "Autre"),
    ]
    fichier = forms.FileField(
        required=True,
        label="Fichier",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.csv,.json,.xlsx,.xls,.txt"})
    )
    type = forms.ChoiceField(choices=TYPE_CHOICES, required=False, initial="result_pdf", label="Type de pièce jointe")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("fichier"):
            raise ValidationError("Veuillez sélectionner un fichier.")
        return cleaned


class AnalyseCommentForm(BootstrapModelForm):
    """Commenter une étape d’analyse (journal)."""
    class Meta:
        model = AnalyseComment
        fields = ("etape", "texte")
        widgets = {
            "etape": forms.TextInput(attrs={"placeholder": "ex: assignation / demarrage / resultat / validation_tech / validation_bio"}),
            "texte": forms.Textarea(attrs={"rows": 3, "placeholder": "Votre commentaire…"}),
        }
        labels = {"etape": "Étape", "texte": "Commentaire"}

# ======================================================================
# Demande — commentaires & conclusion
# ======================================================================

class DemandeCommentForm(BootstrapModelForm):
    """Commenter le workflow d’une demande (journal)."""
    class Meta:
        model = DemandeComment
        fields = ("etape", "texte")
        widgets = {
            "etape": forms.TextInput(attrs={"placeholder": "ex: reception / assignation / validation_tech / ..."}),
            "texte": forms.Textarea(attrs={"rows": 3, "placeholder": "Votre commentaire…"}),
        }
        labels = {"etape": "Étape", "texte": "Commentaire"}

class AnalyseConcludeForm(forms.Form):
    """
    Utilisé par analyse_conclude :
    - conclusion de suspicion (portée par Demande)
    - note libre
    - PJ facultative (fiche résultats / export)
    """
    suspicion_statut = forms.ChoiceField(choices=Demande.SUSPICION, label="Conclusion de suspicion")
    suspicion_notes = forms.CharField(
        required=False,
        label="Notes de conclusion",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Motifs, éléments probants…"}),
    )
    result_file = forms.FileField(
        required=False,
        label="Joindre la fiche des résultats (optionnel)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.csv,.json,.xlsx,.xls,.txt"})
    )

# ======================================================================
# Divers (équipement, stocks, rapports…)
# ======================================================================

class RapportForm(BootstrapModelForm):
    class Meta:
        model = Rapport
        fields = ("demande", "version", "fichier_pdf", "gabarit", "destinaire_email", "envoye_le", "signe_par")
        widgets = {"envoye_le": DATETIME_WIDGET}

class EquipementForm(BootstrapModelForm):
    class Meta:
        model = Equipement
        fields = ("nom", "type", "reference", "numero_serie", "prochaine_maintenance")
        widgets = {"prochaine_maintenance": DATE_WIDGET}

class MaintenanceForm(BootstrapModelForm):
    class Meta:
        model = Maintenance
        fields = ("equipement", "type", "description", "realise_le", "prochain_passage")
        widgets = {
            "realise_le": DATE_WIDGET,
            "prochain_passage": DATE_WIDGET,
            "description": forms.Textarea(attrs={"rows": 2}),
        }

class LotReactifForm(BootstrapModelForm):
    class Meta:
        model = LotReactif
        fields = ("nom", "lot", "quantite", "unite", "perime_le")
        widgets = {"perime_le": DATE_WIDGET}

class EmplacementForm(BootstrapModelForm):
    class Meta:
        model = Emplacement
        fields = ("nom", "description")

class StockageEchantillonForm(BootstrapModelForm):
    class Meta:
        model = StockageEchantillon
        fields = ("echantillon", "emplacement", "date_entree", "date_sortie")
        widgets = {"date_entree": DATETIME_WIDGET, "date_sortie": DATETIME_WIDGET}

class TraceEchantillonForm(BootstrapModelForm):
    class Meta:
        model = TraceEchantillon
        fields = ("echantillon", "action", "acteur", "horodatage", "details")
        widgets = {"horodatage": DATETIME_WIDGET, "details": forms.Textarea(attrs={"rows": 2})}

class TestCatalogueForm(BootstrapModelForm):
    class Meta:
        model = TestCatalogue
        fields = ("code_test", "nom_test", "section", "maladie", "cible", "methode", "unite", "seuil_decision","tarif_fcfa")

class GabaritRapportForm(BootstrapModelForm):
    class Meta:
        model = GabaritRapport
        fields = ("nom", "slug", "template_path")

class PieceJointeForm(BootstrapModelForm):
    """
    La vue positionne content_type/object_id et calcule nom_original/taille/checksum/uploader.
    """
    class Meta:
        model = PieceJointe
        fields = (
            "content_type", "object_id", "type", "fichier",
            "nom_original", "taille_octets", "checksum_sha256", "uploader",
            "ajoute_le",
        )
        widgets = {
            "ajoute_le": DATETIME_WIDGET,
            "type": forms.TextInput(attrs={"placeholder": "result_pdf / raw_csv / raw_json / raw_xlsx …"}),
        }

class DelegationForm(BootstrapModelForm):
    class Meta:
        model = Delegation
        fields = ("role", "utilisateur", "actif")
        widgets = {
            "role": forms.Select(),
            "utilisateur": forms.Select(),
            "actif": forms.CheckboxInput(),
        }
        labels = {"role": "Rôle délégué", "utilisateur": "Utilisateur", "actif": "Actif ?"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["utilisateur"].queryset = User.objects.order_by("username")

# ======================================================================
# Soumissionnaire (ajout rapide)
# ======================================================================

class SoumissionnaireQuickForm(forms.ModelForm):
    class Meta:
        model = Soumissionnaire
        fields = ("nom_complet", "telephone", "email", "organisation")
        labels = {
            "nom_complet": "Nom complet",
            "telephone": "Téléphone",
            "email": "Email",
            "organisation": "Organisation",
        }
        widgets = {
            "nom_complet": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom complet"}),
            "telephone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Téléphone"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
            "organisation": forms.TextInput(attrs={"class": "form-control", "placeholder": "Organisation"}),
        }

    def clean_nom_complet(self):
        nom = (self.cleaned_data.get("nom_complet") or "").strip()
        if not nom:
            raise forms.ValidationError("Le nom complet est requis.")
        return nom

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email and Soumissionnaire.objects.filter(email=email).exists():
            raise forms.ValidationError("Un soumissionnaire avec cet email existe déjà.")
        return email
