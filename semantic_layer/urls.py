# semantic_layer/urls.py
from django.urls import path
from django.shortcuts import redirect

app_name = "semantic"

def mapping_assistant(request, dataset_id: int):
    # Fallback : ouvre la page admin du DatasetLogical
    return redirect(f"/admin/semantic_layer/datasetlogical/{dataset_id}/change/")

urlpatterns = [
    path("semantic/mapping/<int:dataset_id>/", mapping_assistant, name="mapping"),
]
