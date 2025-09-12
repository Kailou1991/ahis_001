import hmac, hashlib, json
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from .models import KoboSource, RawSubmission

def _valid_signature(secret: str, body: bytes, sig_header: str) -> bool:
    try: algo, sig = sig_header.split("=", 1)
    except Exception: return False
    if algo.lower() != "sha256": return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, sig)

@csrf_exempt
def kobo_webhook(request, asset_uid: str):
    if request.method != "POST": return HttpResponseBadRequest("POST only")
    try: src = KoboSource.objects.get(asset_uid=asset_uid, active=True)
    except KoboSource.DoesNotExist: return HttpResponseForbidden("Unknown asset")
    sig = request.headers.get("X-Kobo-Signature","")
    if not _valid_signature(settings.KOBO_WEBHOOK_SECRET, request.body, sig):
        return HttpResponseForbidden("Bad signature")
    payload = json.loads(request.body.decode("utf-8"))
    instance_id = payload.get("meta",{}).get("instanceID")
    submitted_at = payload.get("_submission_time") or payload.get("end")
    RawSubmission.objects.update_or_create(
        source=src, instance_id=instance_id,
        defaults=dict(
            submission_id=str(payload.get("_id")) if payload.get("_id") is not None else None,
            submitted_at=parse_datetime(submitted_at) if submitted_at else None,
            xform_id=payload.get("_xform_id_string"), form_version=payload.get("_version"),
            payload=payload,
        ),
    )
    return JsonResponse({"status": "ok"})
