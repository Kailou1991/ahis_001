from django.db import models

# Create your models here.
class Region(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True)

    Nom = models.CharField(max_length=100,null=False,blank=False)


    def __str__(self):
        return self.Nom


