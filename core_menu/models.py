from django.db import models
from django.contrib.auth.models import Group

class MenuItem(models.Model):
    label = models.CharField(max_length=100)
    url_name = models.CharField(max_length=200)  # ex: "surveillance:list"
    app_label = models.CharField(max_length=100, blank=True)
    groups = models.ManyToManyField(Group, blank=True)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order",)

    def __str__(self):
        return self.label