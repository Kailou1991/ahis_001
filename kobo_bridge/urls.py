from django.urls import path
from .views import kobo_webhook
urlpatterns = [ path("webhooks/kobo/<str:asset_uid>/", kobo_webhook, name="kobo_webhook") ]
