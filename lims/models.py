# lims/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from Maladie.models import Maladie
from Region.models import Region
from Espece.models import Espece
from Departement.models import Departement
from Commune.models import Commune


# ---------- Helpers ----------
def user_in_groups(user, *names: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user.groups.filter(name__in=names).exists()


# -------------------------
# Référentiel laboratoire
# -------------------------
class SiteLabo(models.Model):
    nom = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.code} — {self.nom}"


class Soumissionnaire(models.Model):
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    nom_complet = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    organisation = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.nom_complet or (self.utilisateur and self.utilisateur.get_username()) or f"soumissionnaire#{self.pk}"


# -------------------------
# Demandes / Réceptions
# -------------------------
class DemandeEtat(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=120)
    ordre = models.PositiveSmallIntegerField(default=0)
    icon = models.CharField(max_length=80, blank=True)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordre", "code"]

    def __str__(self):
        return f"{self.label} ({self.code})"


class Demande(models.Model):
    PRIORITES = [("normale", "Normale"), ("urgente", "Urgente")]

    code_demande = models.CharField(max_length=30, unique=True, help_text="Identifiant de la demande")
    site_labo = models.ForeignKey(SiteLabo, on_delete=models.PROTECT)
    soumissionnaire = models.ForeignKey(Soumissionnaire, null=True, blank=True, on_delete=models.SET_NULL)

    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    localite = models.CharField(max_length=120, blank=True, help_text="Village / Localité")

    maladie_suspectee = models.ForeignKey(
        Maladie, null=True, blank=True, on_delete=models.SET_NULL, related_name="demandes_suspectees"
    )
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE, null=True,blank=True)
    effectif_troupeau = models.IntegerField(default=0)
    nbre_animaux_malades = models.IntegerField(default=0)
    nbre_animaux_morts = models.IntegerField(default=0)

    motif = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    current_etat = models.ForeignKey(
        DemandeEtat, null=True, blank=True, on_delete=models.SET_NULL, related_name="demandes_courantes"
    )

    priorite = models.CharField(max_length=10, choices=PRIORITES, default="normale", db_index=True)
    date_echeance = models.DateTimeField(null=True, blank=True)

    cree_le = models.DateTimeField(default=timezone.now, db_index=True)
    recu_le = models.DateTimeField(null=True, blank=True)

    # Conclusion / suspicion (remplie par l’analyste à la fin)
    SUSPICION = [("non_evaluee", "Non évaluée"), ("confirmee", "Confirmée"), ("infirmee", "Infirmée")]
    suspicion_statut = models.CharField(max_length=20, choices=SUSPICION, default="non_evaluee")
    suspicion_notes = models.TextField(blank=True)
    suspicion_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="demandes_conclues"
    )
    suspicion_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["priorite", "date_echeance"])]

    def __str__(self):
        return self.code_demande

    # --------- Helpers de transition ----------
    def set_etat(self, etat_code: str, by=None, note: str = "") -> "DemandeEtat":
        target = DemandeEtat.objects.get(code=etat_code)
        DemandeEtatEntry.objects.create(demande=self, etat=target, by=by, note=note)
        self.current_etat = target
        self.save(update_fields=["current_etat"])
        return target

    @property
    def etat_label(self) -> str:
        return self.current_etat.label if self.current_etat_id else "—"


class DemandeEtatEntry(models.Model):
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name="etat_entries")
    etat = models.ForeignKey(DemandeEtat, on_delete=models.PROTECT, related_name="entries")
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(default=timezone.now, db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["at", "pk"]
        indexes = [
            models.Index(fields=["demande", "at"]),
            models.Index(fields=["demande", "etat"]),
            models.Index(fields=["etat", "at"]),
        ]

    def __str__(self):
        who = getattr(self.by, "username", "—")
        return f"[{self.at:%Y-%m-%d %H:%M}] {self.etat.label} par {who}"


# -------------------------
# Échantillons
# -------------------------
class Echantillon(models.Model):
    class Matrices(models.TextChoices):
        SERUM = "serum", "Sérum"
        PLASMA = "plasma", "Plasma"
        SANG_TOTAL = "sang_total", "Sang total"
        BUFFY_COAT = "buffy_coat", "Buffy coat"
        DBS_FTA = "dbs_fta", "Sang séché (DBS/FTA)"
        OROPHARYNGE = "ecouv_oropharynge", "Écouvillon oropharyngé"
        NASAL = "ecouv_nasal", "Écouvillon nasal"
        TRACHEAL = "ecouv_tracheal", "Écouvillon trachéal"
        CLOACAL = "ecouv_cloacal", "Écouvillon cloacal"
        RECTAL = "ecouv_rectal", "Écouvillon rectal"
        ANAL = "ecouv_anal", "Écouvillon anal"
        ORAL_BUCCAL = "ecouv_buccal", "Écouvillon buccal/oral"
        CONJONCTIVAL = "ecouv_conjonctival", "Écouvillon conjonctival/oculaire"
        VAGINAL = "ecouv_vaginal", "Écouvillon vaginal"
        PREPUTIAL = "ecouv_preputial", "Écouvillon préputial"
        CUTANE = "ecouv_cutane", "Écouvillon cutané/plaie"
        CARCASSE = "ecouv_carcasse", "Écouvillon de carcasse (surface)"
        SALIVE = "salive", "Salive"
        LAIT = "lait", "Lait"
        COLOSTRUM = "colostrum", "Colostrum"
        URINE = "urine", "Urine"
        BILE = "bile", "Bile"
        LIQ_LCR = "lcr", "Liquide céphalo-rachidien"
        LIQ_PLEURAL = "liq_pleural", "Liquide pleural"
        LIQ_PERITONEAL = "liq_peritoneal", "Ascite / Liquide péritonéal"
        LIQ_SYNOVIAL = "liq_synovial", "Liquide synovial"
        SEMEN = "semen", "Sperme"
        SECRETION_NAS = "sec_nasale", "Sécrétion nasale"
        SECRETION_VAG = "sec_vaginale", "Sécrétion vaginale"
        SECRETION_UTER = "sec_uterine", "Sécrétion utérine"
        FIENTE = "fiente", "Fiente / Fèces"
        COPRO = "copro", "Copro (flottation / sédimentation)"
        TISSU_POUMON = "t_poumon", "Tissu – Poumon"
        TISSU_FOIE = "t_foie", "Tissu – Foie"
        TISSU_RATE = "t_rate", "Tissu – Rate"
        TISSU_REIN = "t_rein", "Tissu – Rein"
        TISSU_COEUR = "t_coeur", "Tissu – Cœur"
        TISSU_CERVEAU = "t_cerveau", "Tissu – Cerveau"
        TISSU_AMYGDALE = "t_amygdale", "Tissu – Amygdales"
        TISSU_GANGLION = "t_ganglion", "Tissu – Ganglion"
        TISSU_INTESTIN = "t_intestin", "Tissu – Intestin"
        TISSU_PANCREAS = "t_pancreas", "Tissu – Pancréas"
        TISSU_RATE_REIN = "t_rate_rein", "Tissu – Rate/Rein (petits ruminants/peste)"
        MUSCLE = "muscle", "Muscle"
        PEAU = "peau", "Peau"
        PLUMES = "plumes", "Plumes"
        POILS = "poils", "Poils"
        OS = "os", "Os"
        MOELLE_OSSEUSE = "moelle", "Moelle osseuse"
        FFPE = "ffpe", "Bloc/paraffine (FFPE)"
        TETE = "Tetes"
        PLACENTA = "placenta", "Placenta"
        AVORTON = "avorton", "Fœtus/avorton (pool tissus)"
        OEUF_CONTENU = "oeuf_contenu", "Œuf – contenu"
        OEUF_COQUILLE = "oeuf_coquille", "Œuf – coquille"
        EMBRYON = "embryon", "Embryon"
        POIS_REIN_ANT = "poisson_rein_ant", "Poisson – Rein antérieur"
        POIS_RATE = "poisson_rate", "Poisson – Rate"
        POIS_FOIE = "poisson_foie", "Poisson – Foie"
        POIS_COEUR = "poisson_coeur", "Poisson – Cœur"
        POIS_INTESTIN = "poisson_intestin", "Poisson – Intestin"
        POIS_BRANCHIES = "poisson_branchies", "Poisson – Branchies"
        POIS_MUCUS = "poisson_mucus", "Poisson – Mucus/Peau"
        POIS_NAGEOIRE = "poisson_nageoire", "Poisson – Nageoire"
        OEufs_POISSON = "oeufs_poisson", "Œufs de poisson"
        ABEILLES_ADULTES = "abeilles_adultes", "Abeilles adultes"
        LARVES_ABEILLES = "larves_abeilles", "Larves d’abeilles"
        MIEL = "miel", "Miel"
        TIQUES = "tiques", "Tiques / Ectoparasites"
        INSECTES = "insectes", "Insectes (pool/individus)"
        LARVES = "larves", "Larves"
        FOURRAGE = "fourrage", "Fourrage / Aliments"
        EAU = "eau", "Eau"
        SOL = "sol", "Sol / Boue / Poussières"
        AIR = "air", "Air (filtre/impacteur)"
        CULTURE_BOUILLON = "culture_bouillon", "Culture – Bouillon"
        CULTURE_GELOSE = "culture_gelose", "Culture – Gélose"
        ISOLEMENT = "isole", "Isolat (culture pure)"
        AUTRE = "autre", "Autre (préciser)"

    code_echantillon = models.CharField(max_length=40)
    demande = models.ForeignKey(Demande, related_name="echantillons", on_delete=models.CASCADE)

    matrice = models.CharField(max_length=40, choices=Matrices.choices, db_index=True)
    matrice_autre = models.CharField(max_length=120, blank=True, help_text="Si ‘Autre’, précisez")
    id_animal = models.CharField(max_length=60, blank=True,null=True)
    date_prelevement = models.DateField(null=True, blank=True)
    commentaire = models.TextField(blank=True)
    
    CONFORMITES = [("conforme", "Conforme"), ("non_conforme", "Non conforme")]
    conformite = models.CharField(max_length=20, choices=CONFORMITES, default="conforme")

    reception_externe = models.BooleanField(default=False)  # reçu d’un autre labo
    envoi_externe = models.BooleanField(default=False)  

    def __str__(self):
        return self.code_echantillon

    @property
    def matrice_label(self) -> str:
        if self.matrice == self.Matrices.AUTRE and self.matrice_autre:
            return f"Autre — {self.matrice_autre}"
        return self.get_matrice_display()


# Emplacements physiques (congélateurs, racks…)
class Emplacement(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.nom


class StockageEchantillon(models.Model):
    echantillon = models.ForeignKey(Echantillon, on_delete=models.CASCADE)
    emplacement = models.ForeignKey(Emplacement, on_delete=models.PROTECT)
    date_entree = models.DateTimeField(default=timezone.now)
    date_sortie = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_entree"]


class TraceEchantillon(models.Model):
    echantillon = models.ForeignKey(Echantillon, on_delete=models.CASCADE, related_name="traces")
    action = models.CharField(max_length=50)
    acteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    horodatage = models.DateTimeField(default=timezone.now)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-horodatage"]


# -------------------------
# Catalogue de tests
# -------------------------
class TestCatalogue(models.Model):
    SECTIONS = [
    ("APBH", "Anatomie pathologie et Biochimie hématologie"),
    ("BACP", "Bactériologie et parasitologie"),
    ("HQA",  "Hygiène et qualité des aliments"),
    ("VIRO", "Virologie"),
    ("CQVMV","Contrôle qualité des vaccins et des médicaments vétérinaires"),
    ("SMAV", "Service des maladies animales à vecteurs"),
]

    METHODES = [
        ("RT_qPCR",       "RT-qPCR"),
        ("PCR_classique", "PCR classique"),
        ("ELISA_I",       "ELISA Indirecte"),
        ("ELISA_C",       "ELISA Compétitive"),
        ("IFAT",          "IFAT"),
        ("Culture",       "Culture"),
        ("Microscopie",   "Microscopie"),
        ("Test_rapide",   "Test rapide"),
    ]

    code_test = models.CharField(max_length=40, unique=True)
    nom_test = models.CharField(max_length=200)
    section = models.CharField(max_length=20, choices=SECTIONS)
    maladie = models.ForeignKey(Maladie, null=True, blank=True, on_delete=models.SET_NULL,
                                help_text="Maladie/agent ciblé par ce test")
    cible = models.CharField(max_length=120, blank=True)
    methode = models.CharField(max_length=30, choices=METHODES, blank=False)
    unite = models.CharField(max_length=40, blank=True)
    seuil_decision = models.CharField(max_length=60, blank=True)
    from decimal import Decimal
    tarif_fcfa = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Tarif unitaire du test en FCFA"
    )

    def __str__(self):
        return f"{self.code_test} — {self.nom_test}"


# -------------------------
# Équipements / Instruments
# -------------------------
class Equipement(models.Model):
    TYPES = [("instrument", "Instrument d'analyse"), ("equipement", "Équipement général")]
    nom = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=TYPES, default="equipement")
    reference = models.CharField(max_length=60, blank=True)
    numero_serie = models.CharField(max_length=80, blank=True)
    prochaine_maintenance = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.nom


class Maintenance(models.Model):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    TYPES = [(PREVENTIVE, "Préventive"), (CORRECTIVE, "Corrective")]

    equipement = models.ForeignKey(Equipement, on_delete=models.CASCADE, related_name="maintenances")
    type = models.CharField(max_length=20, choices=TYPES)
    description = models.TextField(blank=True)
    realise_le = models.DateField(default=timezone.now)
    prochain_passage = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-realise_le"]


# -------------------------
# Analyses
# -------------------------
class Analyse(models.Model):
    NOUVELLE = "nouvelle"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    VALIDE_TECH = "valide_tech"
    VALIDE_BIO = "valide_bio"
    ETATS = [
        (NOUVELLE, "Nouvelle"),
        (EN_COURS, "En cours"),
        (TERMINEE, "Terminée"),
        (VALIDE_TECH, "Validée technique"),
        (VALIDE_BIO, "Validée biologique"),
    ]
    PRIORITES = [("normale", "Normale"), ("urgente", "Urgente")]

    echantillon = models.ForeignKey(Echantillon, related_name="analyses", on_delete=models.CASCADE)
    test = models.ForeignKey(TestCatalogue, on_delete=models.PROTECT)
    analyste = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    etat = models.CharField(max_length=20, choices=ETATS, default=NOUVELLE, db_index=True)
    priorite = models.CharField(max_length=10, choices=PRIORITES, default="normale", db_index=True)
    date_echeance = models.DateTimeField(null=True, blank=True)

    instrument = models.ForeignKey(
        Equipement, null=True, blank=True, on_delete=models.SET_NULL, limit_choices_to={"type": "instrument"}
    )

    # Pièces jointes liées (export d’instrument, fiche résultats…)
    pieces_jointes = GenericRelation(
        'PieceJointe',
        related_query_name="analyse",
        content_type_field="content_type",
        object_id_field="object_id",
    )

    # Marqueurs de séquence
    debute_le = models.DateTimeField(null=True, blank=True)
    termine_le = models.DateTimeField(null=True, blank=True)

    # Jalons workflow (analyste -> réceptionniste)
    brut_transmis_le = models.DateTimeField(null=True, blank=True)
    brut_transmis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="analyses_brut_transmis"
    )
    brut_saisi_le = models.DateTimeField(null=True, blank=True)
    brut_saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="analyses_brut_saisis"
    )

    # Validations
    valide_tech_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="analyses_validees_tech"
    )
    valide_tech_le = models.DateTimeField(null=True, blank=True)
    valide_bio_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="analyses_validees_bio"
    )
    valide_bio_le = models.DateTimeField(null=True, blank=True)

    reprise_de = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    annulee = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("echantillon", "test")
        indexes = [
            models.Index(fields=["etat"]),
            models.Index(fields=["termine_le"]),
            models.Index(fields=["priorite", "date_echeance"]),
        ]

    def __str__(self):
        return f"{self.echantillon} • {self.test}"

    @property
    def maladie(self):
        return self.test.maladie

    @property
    def demande(self):
        return self.echantillon.demande

    # ----- Helpers transmission (simplifiés) -----
    def has_result_attachments(self) -> bool:
        """Au moins une pièce jointe (export/fiche)."""
        return self.pieces_jointes.exists()

    def ready_for_transmission(self) -> bool:
        """Ici on considère qu’une PJ suffit pour transmettre."""
        return (
            self.etat == self.TERMINEE
            and self.brut_transmis_le is None
            and self.has_result_attachments()
        )

    # Droits d’action
    def get_actions_for(self, user) -> dict:
        is_recep = user_in_groups(user, "Réceptioniste")
        is_dir   = user_in_groups(user, "Directeur de laboratoire") or getattr(user, "is_superuser", False)
        is_anal  = user_in_groups(user, "Analyste")
        me_assigned = (self.analyste_id == getattr(user, "id", None))

        can_assign = is_dir and (self.analyste_id is None) and self.etat == Analyse.NOUVELLE

        # Analyste
        can_start  = is_anal and me_assigned and self.etat == Analyse.NOUVELLE and not self.annulee
        can_finish = is_anal and me_assigned and self.etat == Analyse.EN_COURS and not self.annulee
        can_transmit_raw = is_anal and me_assigned and self.etat == Analyse.TERMINEE and self.brut_transmis_le is None

        # Réceptionniste
        can_enter_raw = is_recep and self.etat == Analyse.TERMINEE and self.brut_transmis_le and self.brut_saisi_le is None

        # Directeur
        can_val_tech = is_dir and (self.etat == Analyse.TERMINEE) and self.brut_saisi_le is not None and self.valide_tech_le is None
        can_val_bio  = is_dir and (self.valide_tech_le is not None) and self.valide_bio_le is None

        # Délégations
        from .models import Delegation  # résolu à l’exécution
        d_qs = Delegation.objects.filter(demande=self.demande, utilisateur=user, actif=True)
        has_del_tech = d_qs.filter(role="val_tech").exists()
        has_del_bio  = d_qs.filter(role="val_bio").exists()
        has_del_res  = d_qs.filter(role="saisie_resultats").exists()
        has_del_exec = d_qs.filter(role="analyse_exec").exists()

        can_start        = can_start        or (has_del_exec and self.etat == Analyse.NOUVELLE and not self.annulee)
        can_finish       = can_finish       or (has_del_exec and self.etat == Analyse.EN_COURS  and not self.annulee)
        can_edit_result  = (is_anal and me_assigned and self.etat in (Analyse.EN_COURS, Analyse.TERMINEE) and not self.annulee) \
                           or (has_del_res and self.etat in (Analyse.EN_COURS, Analyse.TERMINEE) and not self.annulee)
        can_val_tech     = can_val_tech or (has_del_tech and self.etat == Analyse.TERMINEE and not self.annulee)
        can_val_bio      = can_val_bio  or (has_del_bio  and self.etat == Analyse.VALIDE_TECH and not self.annulee)

        # >>> AJOUT ICI : droit de conclure la suspicion (depuis l’analyse terminée)
        can_conclude = (
            ((is_anal and me_assigned) or is_dir or has_del_bio)
            and self.etat == Analyse.TERMINEE
            and not self.annulee
        )

        return {
            "can_assign": can_assign,
            "can_start": can_start,
            "can_finish": can_finish,
            "can_transmit_raw": can_transmit_raw,
            "can_enter_raw": can_enter_raw,
            "can_val_tech": can_val_tech,
            "can_val_bio": can_val_bio,
            "can_edit_result": can_edit_result,
            "can_conclude": can_conclude,  # <<< NE PAS OUBLIER DE L’AJOUTER AU RETURN
        }

# ---------- Commentaires d’étape d’une analyse ----------
class AnalyseComment(models.Model):
    analyse = models.ForeignKey(Analyse, related_name="comments", on_delete=models.CASCADE)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    etape = models.CharField(max_length=30, blank=True,
                             help_text="ex: assignation, demarrage, resultat, validation_tech, validation_bio")
    texte = models.TextField()
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        who = self.auteur.username if self.auteur else "—"
        return f"Commentaire {self.etape or ''} par {who}"


# -------------------------
# Rapports / COA
# -------------------------
class GabaritRapport(models.Model):
    nom = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    template_path = models.CharField(max_length=200, help_text="Chemin template HTML (ou slug)")

    def __str__(self):
        return self.nom


class Rapport(models.Model):
    demande = models.ForeignKey(Demande, related_name="rapports", on_delete=models.CASCADE)
    version = models.PositiveIntegerField(default=1)
    fichier_pdf = models.FileField(upload_to="lims/rapports/", blank=True)

    gabarit = models.ForeignKey(GabaritRapport, null=True, blank=True, on_delete=models.SET_NULL)
    destinaire_email = models.EmailField(blank=True)
    envoye_le = models.DateTimeField(null=True, blank=True)

    signe_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="rapports_signes")
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("demande", "version")
        ordering = ["-cree_le"]


# -------------------------
# Stocks (réactifs)
# -------------------------
class LotReactif(models.Model):
    nom = models.CharField(max_length=120)
    lot = models.CharField(max_length=60)
    perime_le = models.DateField()
    quantite = models.FloatField(default=0.0)
    unite = models.CharField(max_length=20, default="u")

    def __str__(self):
        return f"{self.nom} — {self.lot}"


# -------------------------
# Pièces jointes génériques
# -------------------------
class PieceJointe(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    fichier = models.FileField(upload_to="lims/pj/")
    # Catégorie: 'raw_csv', 'raw_xlsx', 'result_pdf', etc.
    type = models.CharField(max_length=50, blank=True)

    # --- audit/qualité ---
    nom_original = models.CharField(max_length=200, blank=True)
    taille_octets = models.PositiveIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pieces_uploads"
    )
    # ---------------------

    ajoute_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-ajoute_le"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["type"]),
        ]


# -------------------------
# Délégations
# -------------------------
class Delegation(models.Model):
    ROLE = [
        ("val_tech", "Validation technique"),
        ("val_bio", "Validation biologique"),
        ("saisie_resultats", "Saisie des résultats"),
        ("analyse_exec", "Exécution d’analyses"),
    ]
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name="delegations")
    role = models.CharField(max_length=30, choices=ROLE)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("demande", "role", "utilisateur")
        indexes = [models.Index(fields=["demande", "role", "actif"])]

    def __str__(self):
        return f"{self.demande} • {self.get_role_display()} • {self.utilisateur}"


# -------------------------
# Commentaires Demande
# -------------------------
class DemandeComment(models.Model):
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name="comments")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    etape = models.CharField(max_length=40, blank=True)  # ex: reception, assignation, validation_tech, validation_bio, rapport
    texte = models.TextField()
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.demande} • {self.etape or 'commentaire'}"
