# kobo_integration/urls.py
from django.urls import path
from .views import webhook

app_name = "kobo_integration"
urlpatterns = [
    path("webhook/", webhook, name="webhook"),
]
