import json
from importlib import import_module
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import KoboForm, SyncLog

@csrf_exempt
def webhook(request):
    if request.method != 'POST':
        return JsonResponse({"error":"Method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
        token = request.GET.get('token') or payload.get('token')
        xform = payload.get('_xform_id_string') or payload.get('xform_id_string')
        instance_id = payload.get('meta/instanceID') or payload.get('_uuid') or str(payload.get('_id'))

        form = KoboForm.objects.get(xform_id_string=xform, enabled=True)
        if token != form.secret_token:
            return HttpResponseForbidden('Invalid token')

        # Parser dynamique
        module_path, func_name = form.parser_path.rsplit(':', 1)
        parser = getattr(import_module(module_path), func_name)
        ok, msg = parser(payload)
        SyncLog.objects.create(form=form, instance_id=instance_id, status='IMPORTED' if ok else 'FAILED', message=msg)
        return JsonResponse({"status":"ok","message":msg}, status=201)
    except KoboForm.DoesNotExist:
        return JsonResponse({"error":"Unknown form"}, status=404)
    except Exception as e:
        SyncLog.objects.create(form=None, instance_id='?', status='FAILED', message=str(e))
        return JsonResponse({"error": str(e)}, status=400)
    


import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import KoboForm
from .services.importer import upsert_one

def _xform_from_payload(d: dict) -> str | None:
    return d.get("_xform_id_string") or d.get("xform_id_string") or d.get("formhub/uuid")

@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    token = request.GET.get("token")
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return HttpResponseBadRequest(f"invalid json: {e}")

    events = data if isinstance(data, list) else [data]
    total = created = updated = failed = 0

    for payload in events:
        total += 1
        xform = _xform_from_payload(payload)
        if not xform or not token:
            failed += 1
            continue
        try:
            form = KoboForm.objects.get(xform_id_string=xform, secret_token=token, enabled=True)
        except KoboForm.DoesNotExist:
            failed += 1
            continue

        try:
            was_created, iid, changed = upsert_one(form, payload)
            if was_created:
                created += 1
            else:
                updated += 1 if changed else 0
        except Exception:
            failed += 1

    return JsonResponse({"status": "ok", "total": total, "created": created, "updated": updated, "failed": failed})
