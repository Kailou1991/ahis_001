from celery import shared_task
from .models import DatasetLogical
from .services import rebuild_widerows_for_dataset
@shared_task
def rebuild_widerow(dataset_id:int):
    ds = DatasetLogical.objects.get(pk=dataset_id)
    rebuild_widerows_for_dataset(ds)
    return "ok"
