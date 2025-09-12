from django.urls import path
from . import views

app_name = "publishing"

urlpatterns = [
    path("assistant/", views.assistant_view, name="assistant_view"),
    path("<slug:slug>/", views.view_detail, name="view_detail"),
    path("<slug:slug>/w/<int:widget_id>.png", views.widget_png, name="widget_png"),
    path("<slug:slug>/export/<int:export_id>/", views.export_view, name="export_view"),
    path("<slug:slug>/options/<str:dim_code>/", views.filter_options_json, name="filter_options_json"),
    
]
