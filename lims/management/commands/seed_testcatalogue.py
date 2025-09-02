# lims/management/commands/seed_maladies_tests.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from Espece.models import Espece
from Maladie.models import Maladie
from lims.models import TestCatalogue

# =========================
# 1) Espèces
# =========================
ESPECES = [
    "Bovins", "Ovins", "Caprins", "Camelidés", "Équins",
    "Asins", "Porcins", "Volaille", "Canins", "Espèces aquatiques",
]

# =========================
# 2) Maladies + espèces concernées
# =========================
MALADIES_SPECES = {
    "Fièvre aphteuse": ["Bovins", "Ovins", "Caprins", "Porcins", "Équins", "Camelidés"],
    "Tuberculose bovine": ["Bovins"],
    "Dermatose nodulaire contagieuse bovine": ["Bovins"],
    "Péripneumonie contagieuse bovine": ["Bovins"],
    "Peste des petits ruminants": ["Ovins", "Caprins"],
    "Peste porcine africaine": ["Porcins"],
    "Peste équine": ["Équins", "Asins"],
    "Rage": ["Canins", "Bovins", "Ovins", "Caprins"],
    "Influenza aviaire hautement pathogène": ["Volaille"],
    "Newcastle": ["Volaille"],
    "Gumboro (IBD)": ["Volaille"],
    "Brucellose": ["Bovins", "Ovins", "Caprins", "Camelidés"],
    "Pasteurellose": ["Bovins", "Ovins", "Caprins", "Camelidés"],
    "Charbon symptomatique": ["Bovins", "Ovins"],
    "Charbon bactéridien (Anthrax)": ["Bovins", "Ovins", "Caprins", "Camelidés"],
    "Entérotoxémies (Clostridies)": ["Ovins", "Caprins", "Bovins"],
    "Salmonellose": ["Volaille", "Porcins", "Bovins"],
    "Colibacillose": ["Volaille", "Bovins", "Porcins"],
    "Coccidiose": ["Volaille", "Ovins", "Caprins", "Bovins"],
    "Gale": ["Bovins", "Ovins", "Caprins", "Canins"],
    "Fièvre de la Vallée du Rift": ["Bovins", "Ovins", "Caprins", "Camelidés"],
    "Botulisme": ["Bovins", "Ovins", "Caprins"],
    "Autre": ESPECES,
}

# =========================
# 3) Zoonoses
# =========================
ZOONOSES = {
    "Rage",
    "Tuberculose bovine",
    "Influenza aviaire hautement pathogène",
    "Fièvre de la Vallée du Rift",
    "Charbon bactéridien (Anthrax)",
    "Brucellose",
    "Salmonellose",
    "Colibacillose",
}

# =========================
# 4) Tests par maladie (sections Burkina)
# Sections attendues dans TestCatalogue.SECTIONS :
#   APBH, BACP, HQA, VIRO, CQVMV, SMAV
# Méthodes autorisées:
#   RT_qPCR, PCR_classique, ELISA_I, ELISA_C, IFAT, Culture, Microscopie, Test_rapide
# =========================
TESTS_PAR_MALADIE = {
    # ----- VIRO -----
    "Fièvre aphteuse": [
        {"code_test": "PCR-FMD-RTqPCR", "nom_test": "Fièvre aphteuse — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "3Dpol"},
        {"code_test": "ELISA-FMD-NSP",  "nom_test": "Fièvre aphteuse — ELISA NSP", "section": "VIRO", "methode": "ELISA_I", "cible": "NSP", "unite": "S/P %", "seuil_decision": "Selon kit"},
    ],
    "Dermatose nodulaire contagieuse bovine": [
        {"code_test": "PCR-LSD-RTqPCR", "nom_test": "Dermatose nodulaire contagieuse — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "Capripox (GPCR)"},
    ],
    "Peste des petits ruminants": [
        {"code_test": "PCR-PPR-RTqPCR", "nom_test": "PPR — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "N"},
        {"code_test": "ELISA-PPR-C",    "nom_test": "PPR — ELISA Compétitive", "section": "VIRO", "methode": "ELISA_C", "cible": "Anticorps anti-PPRV", "unite": "PI %", "seuil_decision": "≥ 50 % (kit)"},
    ],
    "Peste porcine africaine": [
        {"code_test": "PCR-ASF", "nom_test": "Peste porcine africaine — PCR", "section": "VIRO", "methode": "PCR_classique", "cible": "p72 (VP72)"},
    ],
    "Peste équine": [
        {"code_test": "PCR-AHS-RTqPCR", "nom_test": "Peste équine — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "Segment 10 (NS3)"},
        {"code_test": "ELISA-AHS-C",    "nom_test": "Peste équine — ELISA Compétitive", "section": "VIRO", "methode": "ELISA_C", "cible": "VP7", "unite": "PI %"},
    ],
    "Rage": [
        {"code_test": "IFAT-RABIES",        "nom_test": "Rage — IFAT (dFAT)", "section": "VIRO", "methode": "IFAT", "cible": "Antigène rabique"},
        {"code_test": "PCR-RABIES-RTqPCR",  "nom_test": "Rage — RT-qPCR",     "section": "VIRO", "methode": "RT_qPCR", "cible": "N"},
    ],
    "Influenza aviaire hautement pathogène": [
        {"code_test": "PCR-IAHP-RTqPCR", "nom_test": "Influenza aviaire HP — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "Segment M / H5/H7"},
    ],
    "Newcastle": [
        {"code_test": "PCR-ND-RTqPCR", "nom_test": "Newcastle — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "F"},
        {"code_test": "HI-ND",         "nom_test": "Newcastle — Inhibition de l’hémagglutination", "section": "VIRO", "methode": "Test_rapide", "cible": "Ac NDV", "unite": "Titre"},
    ],
    "Gumboro (IBD)": [
        {"code_test": "PCR-IBD-RTqPCR", "nom_test": "Gumboro (IBD) — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "VP2"},
        {"code_test": "ELISA-IBD-I",    "nom_test": "Gumboro (IBD) — ELISA Indirecte", "section": "VIRO", "methode": "ELISA_I", "cible": "Ac IBDV", "unite": "S/P %"},
    ],
    "Fièvre de la Vallée du Rift": [
        {"code_test": "PCR-RVF-RTqPCR", "nom_test": "FVR — RT-qPCR", "section": "VIRO", "methode": "RT_qPCR", "cible": "Segment S"},
        {"code_test": "ELISA-RVF-IgM",  "nom_test": "FVR — ELISA IgM", "section": "VIRO", "methode": "ELISA_I", "cible": "IgM RVFV", "unite": "S/P %"},
        {"code_test": "ELISA-RVF-IgG",  "nom_test": "FVR — ELISA IgG", "section": "VIRO", "methode": "ELISA_I", "cible": "IgG RVFV", "unite": "S/P %"},
    ],

    # ----- BACP -----
    "Tuberculose bovine": [
        {"code_test": "PCR-TB-IS6110", "nom_test": "Tuberculose bovine — PCR", "section": "BACP", "methode": "PCR_classique", "cible": "IS6110 / régions M. bovis"},
    ],
    "Péripneumonie contagieuse bovine": [
        {"code_test": "ELISA-CBPP-C", "nom_test": "CBPP — ELISA Compétitive", "section": "BACP", "methode": "ELISA_C", "cible": "Anticorps Mmm", "unite": "PI %", "seuil_decision": "Selon kit"},
        {"code_test": "PCR-CBPP",     "nom_test": "CBPP — PCR",               "section": "BACP", "methode": "PCR_classique", "cible": "lppQ/Mycoplasma"},
    ],
    "Brucellose": [
        {"code_test": "ELISA-BRU-I", "nom_test": "Brucellose — ELISA Indirecte", "section": "BACP", "methode": "ELISA_I", "cible": "Ac anti-Brucella", "unite": "S/P %", "seuil_decision": "Selon kit"},
        {"code_test": "RBT-BRU",     "nom_test": "Brucellose — Rose Bengal Test", "section": "BACP", "methode": "Test_rapide", "cible": "Ac anti-Brucella"},
    ],
    "Pasteurellose": [
        {"code_test": "CULT-PAST", "nom_test": "Pasteurellose — Culture", "section": "BACP", "methode": "Culture", "cible": "P. multocida/M. haemolytica"},
        {"code_test": "PCR-PAST",  "nom_test": "Pasteurellose — PCR",     "section": "BACP", "methode": "PCR_classique", "cible": "kmt1 / autres"},
    ],
    "Charbon symptomatique": [
        {"code_test": "PCR-BLACKLEG", "nom_test": "Charbon symptomatique — PCR", "section": "BACP", "methode": "PCR_classique", "cible": "Clostridium chauvoei"},
    ],
    "Charbon bactéridien (Anthrax)": [
        {"code_test": "PCR-ANTHRAX",  "nom_test": "Anthrax — PCR",    "section": "BACP", "methode": "PCR_classique", "cible": "pagA/cap"},
        {"code_test": "CULT-ANTHRAX", "nom_test": "Anthrax — Culture","section": "BACP", "methode": "Culture", "cible": "B. anthracis"},
    ],
    "Entérotoxémies (Clostridies)": [
        {"code_test": "ELISA-CLOSTR-TOX", "nom_test": "Entérotoxémies — ELISA toxines", "section": "BACP", "methode": "ELISA_I", "cible": "Toxines Clostridium"},
    ],
    "Salmonellose": [
        {"code_test": "CULT-SALM", "nom_test": "Salmonella — Culture", "section": "BACP", "methode": "Culture", "cible": "Salmonella spp."},
        {"code_test": "PCR-SALM",  "nom_test": "Salmonella — PCR",     "section": "BACP", "methode": "PCR_classique", "cible": "invA / ttr"},
    ],
    "Colibacillose": [
        {"code_test": "CULT-ECOLI", "nom_test": "E. coli — Culture",                         "section": "BACP", "methode": "Culture", "cible": "E. coli"},
        {"code_test": "PCR-ECOLI",  "nom_test": "E. coli — PCR (facteurs de virulence)",     "section": "BACP", "methode": "PCR_classique", "cible": "stx, eae, etc."},
    ],
    "Coccidiose": [
        {"code_test": "PAR-COCCI-MIC", "nom_test": "Coccidiose — Coproscopie (OPG)", "section": "BACP", "methode": "Microscopie", "cible": "Oocystes", "unite": "OPG"},
    ],
    "Gale": [
        {"code_test": "PAR-GALE-MIC", "nom_test": "Gale — Microscopie", "section": "BACP", "methode": "Microscopie", "cible": "Sarcoptes/psoroptes"},
    ],
    "Botulisme": [
        {"code_test": "ELISA-BOT-TOX", "nom_test": "Botulisme — Détection toxines", "section": "BACP", "methode": "ELISA_I", "cible": "Toxines botuliques"},
    ],

    # ----- APBH -----
    "Autre": [
        {"code_test": "HISTO-LESIONS", "nom_test": "Histopathologie — lésions générales", "section": "APBH", "methode": "Microscopie"},
    ],
}

# =========================
# 4-bis) Tests SANS MALADIE (HQA, CQVMV)
# =========================
TESTS_SANS_MALADIE = [
    # --- HQA : Hygiène & Qualité des Aliments ---
    {"code_test": "HQA-AFLA-ELISA",   "nom_test": "Aflatoxines totales — ELISA",         "section": "HQA",   "methode": "ELISA_I",      "cible": "Aflatoxines", "unite": "ppb", "seuil_decision": "Selon norme"},
    {"code_test": "HQA-SALM-CULT",    "nom_test": "Salmonella (aliments) — Culture",     "section": "HQA",   "methode": "Culture",      "cible": "Salmonella spp."},
    {"code_test": "HQA-RESI-CHL-ELI", "nom_test": "Résidus Chloramphénicol — ELISA",     "section": "HQA",   "methode": "ELISA_I",      "cible": "Chloramphénicol", "unite": "ppb"},
    {"code_test": "HQA-EAU-FC-CULT",  "nom_test": "Eaux : Coliformes fécaux — Culture",  "section": "HQA",   "methode": "Culture",      "cible": "CF", "unite": "UFC/100 mL"},

    # --- CQVMV : Contrôle Qualité Vaccins & Médicaments Vét. ---
    {"code_test": "CQV-STERIL-CULT",  "nom_test": "Vaccins — Essai de stérilité",        "section": "CQVMV", "methode": "Culture",      "cible": "Stérilité"},
    {"code_test": "CQV-IDENT-PCR",    "nom_test": "Vaccins — Identité (PCR)",            "section": "CQVMV", "methode": "PCR_classique","cible": "Gène/Antigène cible"},
    {"code_test": "CQV-POT-ELISA",    "nom_test": "Vaccins — Teneur antigénique (ELISA)","section": "CQVMV", "methode": "ELISA_I",      "cible": "Antigène", "unite": "S/P %"},
]

# =========================
# 5) Tarifs par méthode
# =========================
TARIF_PAR_METHODE = {
    "RT_qPCR": Decimal("15000.00"),
    "PCR_classique": Decimal("12000.00"),
    "ELISA_I": Decimal("8000.00"),
    "ELISA_C": Decimal("9000.00"),
    "IFAT": Decimal("7000.00"),
    "Culture": Decimal("5000.00"),
    "Microscopie": Decimal("4000.00"),
    "Test_rapide": Decimal("3000.00"),
}

# =========================
# 6) Command
# =========================
class Command(BaseCommand):
    help = "Seed Espèces, Maladies (avec type), liaisons Maladie↔Espèce et Tests (dont HQA/CQVMV sans maladie)."

    @transaction.atomic
    def handle(self, *args, **opts):
        # 1) Espèces
        self.stdout.write(self.style.SUCCESS("==> Espèces"))
        sp_map = {}
        for label in ESPECES:
            sp, _ = Espece.objects.get_or_create(Espece=label)
            sp_map[label] = sp
            self.stdout.write(f"  - {label}")

        # 2) Maladies + liaisons espèces
        self.stdout.write(self.style.SUCCESS("\n==> Maladies & liaisons aux espèces"))
        mal_map = {}
        for mal_name, esp_list in MALADIES_SPECES.items():
            typ = "Zoonotique" if mal_name in ZOONOSES else "Animale"
            mal, _ = Maladie.objects.get_or_create(Maladie=mal_name, defaults={"Type": typ})
            if getattr(mal, "Type", None) != typ:
                mal.Type = typ
                mal.save(update_fields=["Type"])
            mal.Espece.set([sp_map[e] for e in esp_list])
            mal_map[mal_name] = mal
            self.stdout.write(f"  - {mal_name} [{typ}] → {', '.join(esp_list)}")

        # 3) Tests — liés à une maladie
        self.stdout.write(self.style.SUCCESS("\n==> Tests de laboratoire (liés aux maladies)"))
        created = updated = 0
        for mal_name, tests in TESTS_PAR_MALADIE.items():
            maladie = mal_map.get(mal_name)
            for t in tests:
                methode = t["methode"]
                tarif = TARIF_PAR_METHODE.get(methode, Decimal("0.00"))
                defaults = {
                    "nom_test": t["nom_test"],
                    "section": t["section"],  # APBH/BACP/HQA/VIRO/CQVMV/SMAV
                    "maladie": maladie,
                    "cible": t.get("cible", "") or "",
                    "methode": methode,
                    "unite": t.get("unite", "") or "",
                    "seuil_decision": t.get("seuil_decision", "") or "",
                    "tarif_fcfa": tarif,
                }
                obj, created_flag = TestCatalogue.objects.update_or_create(
                    code_test=t["code_test"], defaults=defaults
                )
                if created_flag:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"  + {obj.code_test} — {obj.nom_test} ({obj.section}/{obj.methode})"))
                else:
                    updated += 1
                    self.stdout.write(f"  = {obj.code_test} — MAJ")

        # 4) Tests — SANS maladie (HQA/CQVMV)
        self.stdout.write(self.style.SUCCESS("\n==> Tests de laboratoire (HQA / CQVMV sans maladie)"))
        for t in TESTS_SANS_MALADIE:
            methode = t["methode"]
            tarif = TARIF_PAR_METHODE.get(methode, Decimal("0.00"))
            defaults = {
                "nom_test": t["nom_test"],
                "section": t["section"],
                "maladie": None,  # <<< pas de maladie liée
                "cible": t.get("cible", "") or "",
                "methode": methode,
                "unite": t.get("unite", "") or "",
                "seuil_decision": t.get("seuil_decision", "") or "",
                "tarif_fcfa": tarif,
            }
            obj, created_flag = TestCatalogue.objects.update_or_create(
                code_test=t["code_test"], defaults=defaults
            )
            if created_flag:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {obj.code_test} — {obj.nom_test} ({obj.section}/{obj.methode})"))
            else:
                updated += 1
                self.stdout.write(f"  = {obj.code_test} — MAJ")

        self.stdout.write(self.style.SUCCESS(f"\nSeed terminé ✅  (Tests créés: {created} • MAJ: {updated})"))
