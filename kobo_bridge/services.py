# kobo_bridge/services.py
from django.utils.dateparse import parse_datetime
from .models import KoboSource, RawSubmission
from .utils import iter_submissions  # ← auto OData ou REST JSON

def pull_source_sync(source: KoboSource):
    new_, upd_ = 0, 0
    for row in iter_submissions(source.server_url, source.asset_uid, source.token):
        iid_candidates = [
            row.get("meta/instanceID"), row.get("meta_instanceID"),
            row.get("instanceID"), row.get("_uuid"), row.get("uuid")
        ]
        instance_id = next((x for x in iid_candidates if x), None)
        if instance_id is None:
            _id = row.get("_id") or row.get("id")
            if _id is not None:
                instance_id = f"oid:{_id}"

        submitted_at = (
            row.get("_submission_time") or row.get("submission_time")
            or row.get("end") or row.get("start") or row.get("date_modified")
        )

        _, created = RawSubmission.objects.update_or_create(
            source=source, instance_id=instance_id,
            defaults=dict(
                submission_id=str(row.get("_id") or row.get("id")) if (row.get("_id") or row.get("id")) is not None else None,
                submitted_at=parse_datetime(submitted_at) if submitted_at else None,
                xform_id=row.get("_xform_id_string") or row.get("xform_id") or row.get("form_id"),
                form_version=row.get("_version") or row.get("version"),
                payload=row,
            )
        )
        new_ += int(created); upd_ += int(not created)
    return {"new": new_, "updated": upd_}
