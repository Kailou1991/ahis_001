from django.urls import path
from .views import dashboard_inspections,export_inspections_excel

urlpatterns = [
    path('dashboard/inspections/', dashboard_inspections, name='dashboard_inspections'),
    path('dashboard/inspections/export/', export_inspections_excel, name='export_inspections_excel'),

]
