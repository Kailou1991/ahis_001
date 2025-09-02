from django.utils import timezone
from django.db.models import Max
from .models import Demande

# lims/services.py
from typing import Iterable, Tuple
from django.db import transaction
from .models import Demande, Echantillon, Analyse, TestCatalogue, Equipement, Maladie
from django.contrib.auth import get_user_model

User = get_user_model()

def next_code_demande() -> str:
    """
    Génère le prochain code unique de demande.
    Format: DEM-YYYY-NNNN
    Exemple: DEM-2025-0001
    """
    year = timezone.now().year

    # Récupérer le max existant pour l'année courante
    last_code = (
        Demande.objects.filter(code_demande__startswith=f"DEM-{year}")
        .aggregate(Max("code_demande"))
        .get("code_demande__max")
    )

    if last_code:
        try:
            # Extraire le compteur à la fin
            last_number = int(last_code.split("-")[-1])
        except ValueError:
            last_number = 0
    else:
        last_number = 0

    # Incrémente le compteur
    next_number = last_number + 1

    # Retourne formaté
    return f"DEM-{year}-{next_number:04d}"



def tests_suggerees_pour_demande(demande: Demande):
    """
    Retourne le queryset des tests suggérés par la maladie suspectée de la demande.
    Si aucune maladie, retourne un queryset vide.
    """
    if not demande.maladie_suspectee_id:
        return TestCatalogue.objects.none()
    return TestCatalogue.objects.filter(maladie_id=demande.maladie_suspectee_id).order_by("code_test")


def couples_ech_tests_manquants(demande: Demande, tests_qs: Iterable[TestCatalogue]) -> Iterable[Tuple[Echantillon, TestCatalogue]]:
    """
    Pour chaque échantillon de la demande, renvoie les (échantillon, test) pour lesquels
    il N'EXISTE PAS encore d'Analyse.
    """
    tests = list(tests_qs)
    if not tests:
        return []

    # déjà existants (ech_id, test_id)
    existing = set(
        Analyse.objects.filter(echantillon__demande=demande, test__in=tests)
        .values_list("echantillon_id", "test_id")
    )

    pairs = []
    for e in demande.echantillons.all():
        for t in tests:
            if (e.id, t.id) not in existing:
                pairs.append((e, t))
    return pairs


@transaction.atomic
def creer_analyses_manquantes(
    demande: Demande,
    tests_qs: Iterable[TestCatalogue],
    *,
    analyste: User | None = None, # type: ignore
    priorite: str = "normale",
    date_echeance = None,
    instrument: Equipement | None = None,
) -> int:
    """
    Crée les Analyses manquantes (combinaisons échantillon x test) pour la demande.
    Retourne le nombre créé. Affecte éventuellement à un analyste, instrument, etc.
    """
    count = 0
    for e, t in couples_ech_tests_manquants(demande, tests_qs):
        Analyse.objects.create(
            echantillon=e,
            test=t,
            analyste=analyste,
            etat=Analyse.NOUVELLE,
            priorite=priorite,
            date_echeance=date_echeance,
            instrument=instrument,
        )
        count += 1
    return count