# data_initial/models.py

from django.db import models

from django.db import models
from django.contrib.auth.models import User

class LogEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='data_initialization_log_entries', null=True,blank=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50)  # Remplacement de PositiveIntegerField par CharField
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} {self.object_id} at {self.timestamp}"
 
    
    
