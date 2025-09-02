from django.urls import include, path
from .registry import discover_apps

urlpatterns = [
    path(f"{name}/", include(f"generated_apps.{name}.urls")) for name in discover_apps()
]