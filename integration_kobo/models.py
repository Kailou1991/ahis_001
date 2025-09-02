from django.db import models

class FormulaireKobo(models.Model):
    nom = models.CharField(max_length=100)
    uid = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=255,default="")
    base_url = models.URLField(default="https://kf.kobotoolbox.org")
    parser = models.CharField(max_length=100,default=None)  # ex: "parse_vaccination_data"
    modele_django = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom

class SyncLog(models.Model):
    formulaire = models.ForeignKey(FormulaireKobo, on_delete=models.CASCADE)
    date_sync = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)
    message = models.TextField()


