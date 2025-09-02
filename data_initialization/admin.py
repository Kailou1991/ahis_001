# data_initial/admin.py

from django.contrib import admin
from .models import LogEntry

admin.site.register(LogEntry)
