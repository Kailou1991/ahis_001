# lims/admin.py
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import OuterRef, Subquery

from .models import (
    SiteLabo, Soumissionnaire, Demande, Echantillon, TestCatalogue,
    Analyse, Rapport, Equipement, LotReactif,
    Emplacement, StockageEchantillon, TraceEchantillon,
    Maintenance, GabaritRapport, PieceJointe,
    DemandeEtat, DemandeEtatEntry,
    Delegation, DemandeComment, AnalyseComment,
)

# ───────────────────────────────────────────────────────────
# Admins simples
# ───────────────────────────────────────────────────────────

@admin.register(SiteLabo)
class SiteLaboAdmin(admin.ModelAdmin):
    search_fields = ("nom", "code")
    list_display = ("code", "nom")


@admin.register(Soumissionnaire)
class SoumissionnaireAdmin(admin.ModelAdmin):
    search_fields = ("nom_complet", "email", "telephone", "organisation")
    list_display  = ("nom_complet", "telephone", "email", "organisation")


# ───────────────────────────────────────────────────────────
# Inlines
# ───────────────────────────────────────────────────────────

class EchantillonInline(admin.TabularInline):
    model = Echantillon
    extra = 0
    fields = ("code_echantillon", "matrice", "matrice_autre",
              "id_animal", "date_prelevement", "commentaire")


class DemandeEtatEntryInline(admin.TabularInline):
    """Historique des états de la demande (journal)."""
    model = DemandeEtatEntry
    extra = 0
    fields = ("etat", "by", "at", "note")
    readonly_fields = ("at",)
    autocomplete_fields = ("etat", "by")
    ordering = ("-at",)


class DelegationInline(admin.TabularInline):
    """Délégations par demande (val_tech / val_bio / saisie_resultats / analyse_exec)."""
    model = Delegation
    extra = 0
    fields = ("role", "utilisateur", "actif", "cree_le")
    autocomplete_fields = ("utilisateur",)
    readonly_fields = ("cree_le",)


class DemandeCommentInline(admin.TabularInline):
    """Commentaires rattachés à la demande (journal)."""
    model = DemandeComment
    extra = 0
    fields = ("etape", "texte", "auteur", "cree_le")
    readonly_fields = ("cree_le",)
    autocomplete_fields = ("auteur",)
    ordering = ("-cree_le",)


# ───────────────────────────────────────────────────────────
# Filtre custom sur état courant (via la dernière entry)
# ───────────────────────────────────────────────────────────

class CurrentEtatListFilter(admin.SimpleListFilter):
    title = "État actuel"
    parameter_name = "etat_actuel"

    def lookups(self, request, model_admin):
        qs = DemandeEtat.objects.all().order_by("ordre", "code").values_list("code", "label")
        return list(qs)

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        last_etat_code = Subquery(
            DemandeEtatEntry.objects
            .filter(demande=OuterRef("pk"))
            .order_by("-at")
            .values("etat__code")[:1]
        )
        return queryset.annotate(_last_code=last_etat_code).filter(_last_code=val)


# ───────────────────────────────────────────────────────────
# Demande
# ───────────────────────────────────────────────────────────

@admin.register(Demande)
class DemandeAdmin(admin.ModelAdmin):
    def etat_actuel(self, obj):
        return obj.etat_label
    etat_actuel.short_description = "État actuel"

    list_display = (
        "code_demande", "site_labo", "soumissionnaire",
        "region", "departement", "commune", "localite",
        "maladie_suspectee", "espece",
        "nbre_animaux_morts", "effectif_troupeau", "nbre_animaux_malades",
        "priorite", "date_echeance",
        "cree_le", "recu_le", "etat_actuel",
    )
    list_filter = (
        CurrentEtatListFilter,
        "priorite", "site_labo", "region", "departement", "commune",
        "maladie_suspectee", "espece"
    )
    search_fields = ("code_demande", "motif", "notes", "soumissionnaire__nom_complet")
    date_hierarchy = "cree_le"
    inlines = [EchantillonInline, DemandeEtatEntryInline, DelegationInline, DemandeCommentInline]

    raw_id_fields = (
        "site_labo", "soumissionnaire", "region", "departement", "commune",
        "maladie_suspectee", "espece", "current_etat"
    )
    list_select_related = (
        "site_labo", "soumissionnaire", "region", "departement", "commune",
        "maladie_suspectee", "espece", "current_etat"
    )

    @admin.action(description="Marquer comme « Reçue »")
    def marquer_recue(self, request, queryset):
        now = timezone.now()
        try:
            etat_recue = DemandeEtat.objects.get(code="recue")
        except DemandeEtat.DoesNotExist:
            self.message_user(request, "État 'recue' introuvable dans le référentiel DemandeEtat.", level="error")
            return
        created = 0
        for d in queryset:
            DemandeEtatEntry.objects.create(demande=d, etat=etat_recue, by=request.user, at=now, note="")
            d.current_etat = etat_recue
            if not d.recu_le:
                d.recu_le = now
            d.save(update_fields=["current_etat", "recu_le"])
            created += 1
        self.message_user(request, f"{created} demande(s) marquée(s) « Reçue ».")
    actions = ["marquer_recue"]


# ───────────────────────────────────────────────────────────
# Échantillon / Traçabilité / Stockage
# ───────────────────────────────────────────────────────────

@admin.register(Echantillon)
class EchantillonAdmin(admin.ModelAdmin):
    def matrice_aff(self, obj):
        try:
            return obj.matrice_label
        except Exception:
            return obj.get_matrice_display() if hasattr(obj, "get_matrice_display") else obj.matrice
    matrice_aff.short_description = "Matrice"

    list_display = (
        "code_echantillon", "demande",
        "matrice_aff", "matrice_autre", "id_animal",
        "date_prelevement","conformite","reception_externe","envoi_externe"
    )
    search_fields = ("code_echantillon", "demande__code_demande", "id_animal")
    list_select_related = ("demande",)


@admin.register(Emplacement)
class EmplacementAdmin(admin.ModelAdmin):
    list_display = ("nom", "description")
    search_fields = ("nom", "description")


@admin.register(StockageEchantillon)
class StockageEchantillonAdmin(admin.ModelAdmin):
    list_display = ("echantillon", "emplacement", "date_entree", "date_sortie")
    list_filter  = ("emplacement",)
    search_fields = ("echantillon__code_echantillon",)
    raw_id_fields = ("echantillon", "emplacement")
    date_hierarchy = "date_entree"
    list_select_related = ("echantillon", "emplacement")


@admin.register(TraceEchantillon)
class TraceEchantillonAdmin(admin.ModelAdmin):
    list_display = ("echantillon", "action", "acteur", "horodatage")
    list_filter  = ("action",)
    search_fields = ("echantillon__code_echantillon", "acteur__username", "details")
    raw_id_fields = ("echantillon", "acteur")
    date_hierarchy = "horodatage"
    list_select_related = ("echantillon", "acteur")


# ───────────────────────────────────────────────────────────
# Catalogue des tests
# ───────────────────────────────────────────────────────────

@admin.register(TestCatalogue)
class TestCatalogueAdmin(admin.ModelAdmin):
    list_display = ("code_test", "nom_test", "section", "maladie", "methode", "cible", "unite", "seuil_decision","tarif_fcfa")
    list_filter  = ("section", "methode", "maladie")
    search_fields = ("code_test", "nom_test", "cible")
    raw_id_fields = ("maladie",)


# ───────────────────────────────────────────────────────────
# Équipements & Maintenance
# ───────────────────────────────────────────────────────────

@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "reference", "numero_serie", "prochaine_maintenance")
    search_fields = ("nom", "reference", "numero_serie")
    list_filter  = ("type", "prochaine_maintenance")


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ("equipement", "type", "realise_le", "prochain_passage")
    list_filter  = ("type", "realise_le")
    search_fields = ("equipement__nom", "description")
    raw_id_fields = ("equipement",)
    date_hierarchy = "realise_le"
    list_select_related = ("equipement",)


# ───────────────────────────────────────────────────────────
# Analyses
# ───────────────────────────────────────────────────────────
@admin.register(Analyse)
class AnalyseAdmin(admin.ModelAdmin):
    def methode(self, obj):
        return obj.test.methode
    methode.short_description = "Méthode"

    # --- Infos PJ (dernière pièce jointe liée à l’analyse) ---
    @admin.display(boolean=True, description="PJ présente")
    def has_pj(self, obj):
        try:
            return obj.pieces_jointes.exists()
        except Exception:
            return False

    def last_file_name(self, obj):
        pj = obj.pieces_jointes.order_by("-ajoute_le").first()
        if pj:
            if pj.nom_original:
                return pj.nom_original
            if pj.fichier:
                return pj.fichier.name.rsplit("/", 1)[-1]
        return "—"
    last_file_name.short_description = "Dernier fichier"

    def last_file_uploaded_at(self, obj):
        pj = obj.pieces_jointes.order_by("-ajoute_le").first()
        return pj.ajoute_le if pj else "—"
    last_file_uploaded_at.short_description = "Uploadé le"

    def last_file_uploader(self, obj):
        pj = obj.pieces_jointes.order_by("-ajoute_le").first()
        return getattr(pj.uploader, "username", "—") if pj and pj.uploader_id else "—"
    last_file_uploader.short_description = "Uploader"

    def suspicion(self, obj):
        d = obj.demande
        try:
            return d.get_suspicion_statut_display()
        except Exception:
            return "—"
    suspicion.short_description = "Suspicion (demande)"

    list_display = (
        "echantillon", "test", "methode", "instrument",
        "etat", "priorite", "date_echeance",
        "analyste", "debute_le", "termine_le",
        "has_pj", "suspicion", "annulee",
    )
    list_filter  = ("etat", "priorite", "test__section", "test__methode", "instrument", "annulee")
    search_fields = ("echantillon__code_echantillon", "test__code_test", "analyste__username")
    raw_id_fields = ("echantillon", "test", "analyste", "instrument")
    list_select_related = ("echantillon", "test", "analyste", "instrument")
    date_hierarchy = "debute_le"

    # Afficher en lecture seule dans la fiche (facultatif)
    readonly_fields = ("last_file_name", "last_file_uploaded_at", "last_file_uploader")

    @admin.action(description="Valider techniquement")
    def valider_tech(self, request, queryset):
        updated = queryset.update(
            etat=Analyse.VALIDE_TECH,
            valide_tech_par=request.user,
            valide_tech_le=timezone.now()
        )
        self.message_user(request, f"{updated} analyse(s) validée(s) techniquement")

    @admin.action(description="Valider biologiquement")
    def valider_bio(self, request, queryset):
        updated = queryset.update(
            etat=Analyse.VALIDE_BIO,
            valide_bio_par=request.user,
            valide_bio_le=timezone.now()
        )
        self.message_user(request, f"{updated} analyse(s) validée(s) biologiquement")

    @admin.action(description="Annuler les analyses sélectionnées")
    def annuler(self, request, queryset):
        updated = queryset.update(
            annulee=True,
            motif_annulation="Annulée depuis l’admin",
            etat=Analyse.TERMINEE
        )
        self.message_user(request, f"{updated} analyse(s) annulée(s)")

    actions = ["valider_tech", "valider_bio", "annuler"]


# ───────────────────────────────────────────────────────────
# Rapports / Gabarits
# ───────────────────────────────────────────────────────────

@admin.register(GabaritRapport)
class GabaritRapportAdmin(admin.ModelAdmin):
    list_display = ("nom", "slug", "template_path")
    search_fields = ("nom", "slug", "template_path")


@admin.register(Rapport)
class RapportAdmin(admin.ModelAdmin):
    def lien_pdf(self, obj):
        if obj.fichier_pdf:
            return format_html('<a href="{}" target="_blank">Télécharger</a>', obj.fichier_pdf.url)
        return "—"
    lien_pdf.short_description = "PDF"

    list_display = ("demande", "version", "gabarit", "destinaire_email", "envoye_le", "lien_pdf", "cree_le", "signe_par")
    search_fields = ("demande__code_demande", "signe_par__username", "destinaire_email")
    raw_id_fields = ("demande", "signe_par", "gabarit")
    list_select_related = ("demande", "signe_par", "gabarit")
    date_hierarchy = "cree_le"


# ───────────────────────────────────────────────────────────
# Réactifs & Lots
# ───────────────────────────────────────────────────────────

@admin.register(LotReactif)
class LotReactifAdmin(admin.ModelAdmin):
    list_display = ("nom", "lot", "perime_le", "quantite", "unite")
    search_fields = ("nom", "lot")
    list_filter  = ("perime_le",)


# ───────────────────────────────────────────────────────────
# Pièces jointes
# ───────────────────────────────────────────────────────────

@admin.register(PieceJointe)
class PieceJointeAdmin(admin.ModelAdmin):
    def lien(self, obj):
        if obj.fichier:
            return format_html('<a href="{}" target="_blank">ouvrir</a>', obj.fichier.url)
        return "—"
    lien.short_description = "Fichier"

    list_display = (
        "content_type", "object_id", "type",
        "nom_original", "taille_octets", "checksum_sha256",
        "uploader", "ajoute_le", "lien",
    )
    list_filter  = ("type", "content_type")
    search_fields = ("type", "nom_original", "checksum_sha256")
    raw_id_fields = ("uploader",)
    date_hierarchy = "ajoute_le"


# ───────────────────────────────────────────────────────────
# Commentaires (Analyse & Demande)
# ───────────────────────────────────────────────────────────

@admin.register(AnalyseComment)
class AnalyseCommentAdmin(admin.ModelAdmin):
    list_display = ("analyse", "etape", "auteur", "cree_le")
    list_filter  = ("etape", "auteur")
    search_fields = ("analyse__echantillon__code_echantillon", "texte", "auteur__username")
    raw_id_fields = ("analyse", "auteur")
    date_hierarchy = "cree_le"
    list_select_related = ("analyse", "auteur")


@admin.register(DemandeComment)
class DemandeCommentAdmin(admin.ModelAdmin):
    list_display = ("demande", "etape", "auteur", "cree_le")
    list_filter  = ("etape", "auteur")
    search_fields = ("demande__code_demande", "texte", "auteur__username")
    raw_id_fields = ("demande", "auteur")
    date_hierarchy = "cree_le"
    list_select_related = ("demande", "auteur")


# ───────────────────────────────────────────────────────────
# Référentiel d’états & Journal
# ───────────────────────────────────────────────────────────

@admin.register(DemandeEtat)
class DemandeEtatRefAdmin(admin.ModelAdmin):
    """Admin du référentiel des états (pas le journal)."""
    list_display = ("code", "label", "ordre", "icon", "is_terminal")
    list_filter  = ("is_terminal",)
    search_fields = ("code", "label")
    ordering = ("ordre", "code")


@admin.register(DemandeEtatEntry)
class DemandeEtatEntryAdmin(admin.ModelAdmin):
    """Admin du journal des états."""
    list_display = ("demande", "etat", "by", "at", "note")
    list_filter  = ("etat", "by")
    search_fields = ("demande__code_demande", "etat__code", "etat__label", "note")
    raw_id_fields = ("demande", "etat", "by")
    date_hierarchy = "at"
    list_select_related = ("demande", "etat", "by")
