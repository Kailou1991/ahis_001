import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AHIS001.settings')
app = Celery('AHIS001')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()