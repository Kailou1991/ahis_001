from django.urls import path
from .views import dashboard_aibd

urlpatterns = [
    path('dashboard-aibd/', dashboard_aibd, name='dashboard_aibd'),
]
