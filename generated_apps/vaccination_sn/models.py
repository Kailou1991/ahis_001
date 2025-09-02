from django.db import models

class VaccinationSn(models.Model):
    campagne = models.TextField(blank=True, null=True)
    commentaire = models.TextField(blank=True, null=True)
    datesaisie = models.DateField(blank=True, null=True)
    end = models.TextField(blank=True, null=True)
    formhub_uuid = models.TextField(blank=True, null=True)
    grp4_departement = models.TextField(blank=True, null=True)
    grp4_region = models.TextField(blank=True, null=True)
    meta_instanceid = models.TextField(blank=True, null=True)
    meta_rootuuid = models.TextField(blank=True, null=True)
    start = models.TextField(blank=True, null=True)
    type_de_campagne = models.TextField(blank=True, null=True)
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
        db_table = 'vaccination_sn_vaccinationsn'
        ordering = ('-id',)

    def __str__(self):
        return f"VaccinationSn #{self.pk}"


class VaccinationSnChild0c8ff1d1(models.Model):
    parent = models.ForeignKey('VaccinationSn', on_delete=models.CASCADE, related_name='grp5_items')
    item_index = models.IntegerField(blank=True, null=True)
    raw_json = models.JSONField(blank=True, null=True)
    calculation = models.IntegerField(blank=True, null=True)
    commune = models.TextField(blank=True, null=True)
    maladie_masse = models.TextField(blank=True, null=True)
    marque_prive = models.IntegerField(blank=True, null=True)
    marque_public = models.IntegerField(blank=True, null=True)
    total_marque = models.IntegerField(blank=True, null=True)
    vaccine_prive = models.IntegerField(blank=True, null=True)
    vaccine_public = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'vaccination_sn_vaccinationsnchild0c8ff1d1'
        ordering = ('parent_id', 'item_index')
        unique_together = (('parent', 'item_index'),)

    def __str__(self):
        return f"VaccinationSnChild0c8ff1d1 of {self.parent_id}[{self.item_index}]"
