from django.urls import path
from . import views
from . import views_doses
urlpatterns = [
    # Types de matériel
    path("types/", views.type_list, name="type_list"),
    path("types/nouveau/", views.type_create, name="type_create"),
    path("types/<int:pk>/modifier/", views.type_update, name="type_update"),
    path("types/<int:pk>/supprimer/", views.type_delete, name="type_delete"),

    # Dotations
    path("dotations/", views.dotation_list, name="dotation_list"),
    path("dotations/nouveau/", views.dotation_create, name="dotation_create"),
    path("dotations/<int:pk>/modifier/", views.dotation_update, name="dotation_update"),
    path("dotations/<int:pk>/supprimer/", views.dotation_delete, name="dotation_delete"),
    ###doses
     path("doses/", views_doses.dotation_dose_list, name="dose_list"),
    path("doses/nouveau/", views_doses.dotation_dose_create, name="dose_create"),
    path("doses/<int:pk>/modifier/", views_doses.dotation_dose_update, name="dose_update"),
    path("doses/<int:pk>/supprimer/", views_doses.dotation_dose_delete, name="dose_delete"),
]

