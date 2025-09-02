from django.db import models

class SurveillanceSn(models.Model):
    ajouter_un_prelevement = models.TextField(blank=True, null=True)
    commentaire_de_la_suspicion = models.TextField(blank=True, null=True)
    commentaire_mesures_de_control = models.TextField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)
    formhub_uuid = models.TextField(blank=True, null=True)
    grp1_date_rapportage = models.DateField(blank=True, null=True)
    grp1_date_signalement = models.DateField(blank=True, null=True)
    grp2_adresse_mail = models.TextField(blank=True, null=True)
    grp2_adresse_professionnelle = models.TextField(blank=True, null=True)
    grp2_nom_agent = models.TextField(blank=True, null=True)
    grp2_statutagent = models.TextField(blank=True, null=True)
    grp2_telephone_agent = models.IntegerField(blank=True, null=True)
    grp2_titreagent = models.TextField(blank=True, null=True)
    grp3_autrefoyer = models.TextField(blank=True, null=True)
    grp3_commune = models.TextField(blank=True, null=True)
    grp3_departement = models.TextField(blank=True, null=True)
    grp3_geolocalisation = models.TextField(blank=True, null=True)
    grp3_lieususpicion = models.TextField(blank=True, null=True)
    grp3_nom_du_village = models.TextField(blank=True, null=True)
    grp3_nom_pv_service = models.TextField(blank=True, null=True)
    grp3_region = models.TextField(blank=True, null=True)
    grp4_nom_eleveur = models.TextField(blank=True, null=True)
    grp4_telephone_eleveur = models.IntegerField(blank=True, null=True)
    grp5_evolutionmaladie = models.TextField(blank=True, null=True)
    grp5_liste_lesions = models.TextField(blank=True, null=True)
    grp5_liste_signes = models.TextField(blank=True, null=True)
    grp5_qmad1 = models.TextField(blank=True, null=True)
    meta_instanceid = models.TextField(blank=True, null=True)
    meta_rootuuid = models.TextField(blank=True, null=True)
    nbre_soumission = models.IntegerField(blank=True, null=True)
    numero_dordre = models.IntegerField(blank=True, null=True)
    start = models.DateTimeField(blank=True, null=True)
    systemeelevagetroupeau = models.TextField(blank=True, null=True)
    vaccination_anterieure = models.TextField(blank=True, null=True)
    voulez_vous_ajouter_des_mesure = models.TextField(blank=True, null=True)
    instance_id = models.CharField(max_length=128, db_index=True, blank=True, null=True)
    xform_id_string = models.CharField(max_length=200, blank=True, null=True)
    submission_time = models.DateTimeField(blank=True, null=True)
    submitted_by = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    geojson = models.JSONField(blank=True, null=True)
    raw_json = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'surveillance_sn_surveillancesn'
        ordering = ('-id',)

    def __str__(self):
        return f"SurveillanceSn #{self.pk}"


class SurveillanceSnChild783b28ae(models.Model):
    parent = models.ForeignKey('SurveillanceSn', on_delete=models.CASCADE, related_name='grp6_items')
    item_index = models.IntegerField(blank=True, null=True)
    raw_json = models.JSONField(blank=True, null=True)
    calcul_animaux_morts = models.IntegerField(blank=True, null=True)
    effectif_animaux_malade = models.IntegerField(blank=True, null=True)
    effectif_animaux_morts_calcule = models.IntegerField(blank=True, null=True)
    effectif_total_troup_st_de_tot = models.IntegerField(blank=True, null=True)
    fadultes = models.IntegerField(blank=True, null=True)
    fadultes_malades = models.IntegerField(blank=True, null=True)
    fjeunes = models.IntegerField(blank=True, null=True)
    fjeunes_malades = models.IntegerField(blank=True, null=True)
    liste_anisensibles = models.TextField(blank=True, null=True)
    madultes = models.IntegerField(blank=True, null=True)
    madultesmalades = models.IntegerField(blank=True, null=True)
    mjeunes = models.IntegerField(blank=True, null=True)
    mjeunes_malades = models.IntegerField(blank=True, null=True)
    nb_femelles_adultes_mortes = models.IntegerField(blank=True, null=True)
    nb_jeunes_femelles_mortes = models.IntegerField(blank=True, null=True)
    nb_jeunes_males_morts = models.IntegerField(blank=True, null=True)
    nb_males_adultes_morts = models.IntegerField(blank=True, null=True)
    total_malade = models.IntegerField(blank=True, null=True)
    totaltroupeau = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'surveillance_sn_surveillancesnchild783b28ae'
        ordering = ('parent_id', 'item_index')
        unique_together = (('parent', 'item_index'),)

    def __str__(self):
        return f"SurveillanceSnChild783b28ae of {self.parent_id}[{self.item_index}]"
