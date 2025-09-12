from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from .models import KoboSource, RawSubmission

# --- Bouton Pull + Probe + compteur Raw sur KoboSource ---
@admin.register(KoboSource)
class KoboSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name", "asset_uid", "mode", "active", "created_at",
        "pull_now_btn", "probe_btn", "raw_count",
    )
    search_fields = ("name", "asset_uid")
    list_filter = ("active", "mode")

    @admin.display(description="Importer maintenant")
    def pull_now_btn(self, obj):
        url = reverse("admin:kobo_pull_now", args=[obj.pk])
        return format_html('<a class="button" href="{}">Pull</a>', url)

    @admin.display(description="Tester endpoint")
    def probe_btn(self, obj):
        url = reverse("admin:kobo_probe", args=[obj.pk])
        return format_html('<a class="button" href="{}">Probe</a>', url)

    @admin.display(description="Raw")
    def raw_count(self, obj):
        return RawSubmission.objects.filter(source=obj).count()

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("pull/<int:pk>/", self.admin_site.admin_view(self.pull_now_view), name="kobo_pull_now"),
            path("probe/<int:pk>/", self.admin_site.admin_view(self.probe_view), name="kobo_probe"),
        ]
        return custom + urls

    def pull_now_view(self, request, pk):
        # Import synchrone (pas besoin de Celery)
        from .services import pull_source_sync  # nécessite kobo_bridge/services.py
        src = self.get_object(request, pk)
        res = pull_source_sync(src)
        messages.success(request, f"Import terminé : {res['new']} nouveaux, {res['updated']} mis à jour.")
        return redirect("admin:kobo_bridge_kobosource_change", pk)

    def probe_view(self, request, pk):
        # Tente OData puis REST JSON
        from .utils import odata_pick_entity, _rest_base_candidates
        import requests
        src = self.get_object(request, pk)
        headers = {"Authorization": f"Token {src.token}"}
        ok = None
        try:
            ent = odata_pick_entity(src.server_url, src.asset_uid, src.token)
            r = requests.get(ent, headers=headers, params={"$top": 1}, timeout=20)
            if r.status_code == 200:
                ok = f"OData OK: {ent}"
        except Exception:
            pass
        if not ok:
            for u in _rest_base_candidates(src.server_url, src.asset_uid):
                try:
                    r = requests.get(u, headers=headers, timeout=20)
                    if r.status_code == 200:
                        ok = f"REST OK: {u}"
                        break
                except Exception:
                    pass
        if ok:
            messages.info(request, ok)
        else:
            messages.error(request, "Aucun endpoint détecté (vérifier token/UID).")
        return redirect("admin:kobo_bridge_kobosource_change", pk)


@admin.register(RawSubmission)
class RawSubmissionAdmin(admin.ModelAdmin):
    list_display = ("source", "instance_id", "form_version", "submitted_at", "received_at")
    search_fields = ("instance_id", "submission_id")
    list_filter = ("source",)
