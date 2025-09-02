from django.urls import path
from . import views_demandes,views_analysis,views_rapport,views,views_rapport_periodique
from . import views_dashboard as dash
  

app_name = "lims"

urlpatterns = [
    path("vlim_demandes/", views_demandes.demandes_list, name="vlims_demandes_list"),
    # détail d’une demande
    path("demandes/<int:pk>/", views_demandes.demande_detail, name="vlims_demande_detail"),

     # CRUD demandes
    path("vlims_demandes/create/", views_demandes.demande_create, name="vlims_demande_create"),
    path("demandes/<int:pk>/edit/", views_demandes.demande_update, name="demande_update"),
    path("demandes/<int:pk>/delete/", views_demandes.demande_delete, name="demande_delete"),
    # pièces jointes & commentaires
    path("demandes/<int:pk>/piece/", views_demandes.demande_add_piece_jointe, name="demande_add_piece_jointe"),
    path("demandes/<int:pk>/comment/", views_demandes.demande_add_comment, name="demande_add_comment"),

# APIs dépendances & code
    path("api/next_code/", views_demandes.api_next_code_demande, name="api_next_code_demande"),
   # urls.py
    path("api/departements/", views_demandes.api_departements_by_region, name="api_departements_by_region"),
    path("api/communes/", views_demandes.api_communes_by_departement, name="api_communes_by_departement"),

    path("api/soumissionnaire/", views_demandes.api_soumissionnaire_create, name="api_soumissionnaire_create"),

    #############affectation######################################

    path("analyses/<int:pk>/affecter/", views_demandes.demande_affecter, name="demande_affecter"),
    path("demandes/mes/", views.demandes_list_affectees, name="demandes_list_affectees"),
    ################analyses
    path("analyses/<int:pk>/start/",    views_analysis.analyse_start,        name="analyse_start"),
    path("analyses/<int:pk>/finish/",   views_analysis.analyse_finish,       name="analyse_finish"),
    path("analyse/<int:pk>/conclude/", views_analysis.analyse_conclude, name="analyse_conclude"),
    path("demandes/<int:demande_id>/rapport/generer/", views_rapport.rapport_generate, name="rapport_generate"),
     path("rapports/periodique/", views_rapport_periodique.rapport_periodique, name="rapport_periodique"),

################DashBoard

    path("lims_dashboard/", dash.dashboard, name="lims_dashboard"),

    # Graphs PNG
    path("dashboard/chart/series/",   dash.chart_series,   name="chart_series"),
    path("dashboard/chart/sections/", dash.chart_sections, name="chart_sections"),
    path("dashboard/chart/methods/",  dash.chart_methods,  name="chart_methods"),
    path("dashboard/chart/tests/",    dash.chart_top_tests, name="chart_top_tests"),
    path("dashboard/chart/analysts/", dash.chart_analysts, name="chart_analysts"),
    path("dashboard/chart/diseases/", dash.chart_diseases, name="chart_diseases"),
    path("dashboard/chart/clients/",  dash.chart_clients,  name="chart_clients"),
    path("dashboard/chart/sla/",      dash.chart_sla,      name="chart_sla"),



]
