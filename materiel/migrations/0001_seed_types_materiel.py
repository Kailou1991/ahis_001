from django.db import migrations

TYPES_MATERIEL = [
    "Pince de marquage",
    "Enregistreur de température",
    "Glaciére électrique",
    "Glaciére petit modéle",
    "Réfrigérateur_300L",
    "Congélateur_500L",
    "Frigo Solaire",
    "Glaciére 22L",
    "Glaciére 12L",
    "Glaciére 11L",
    "Aiguiles sous cutané bovin",
    "Aiguilles sous cutanée ovin",
    "Aiguilles intra-musculaire bovin",
    "Aiguilles intra musculaire ovin",
    "Compte goutte",
    "Fiche de vaccination",
    "Séringues révolver",
    "Séringues avec curseur",
]

def forwards(apps, schema_editor):
    TypeMateriel = apps.get_model("materiel", "TypeMateriel")
    for nom in TYPES_MATERIEL:
        TypeMateriel.objects.get_or_create(nom=nom)

def backwards(apps, schema_editor):
    TypeMateriel = apps.get_model("materiel", "TypeMateriel")
    TypeMateriel.objects.filter(nom__in=TYPES_MATERIEL).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("materiel", "0001_initial"),  # assure-toi que ce numéro correspond bien
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
