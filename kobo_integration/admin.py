# kobo_integration/admin.py
from django import forms
from django.contrib import admin, messages
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.http import HttpResponseRedirect

from .models import KoboForm, KoboFieldMap, SyncLog, KoboConnection
from .services.kobo_api import test_connection
from .services.runtime_sync import sync_submissions  # synchro des données (fallback synchrone)

# Imports "souples" pour ne pas imposer Celery si absent
try:
    from .tasks import generate_module_task, sync_kobo_schema_task, sync_form_task
except Exception:
    generate_module_task = None
    sync_kobo_schema_task = None
    sync_form_task = None


# ---------- KoboForm ----------
@admin.register(KoboForm)
class KoboFormAdmin(admin.ModelAdmin):
    search_fields = ("name", "xform_id_string", "slug")
    filter_horizontal = ("allowed_groups",)
    actions = ["sync_selected_data"]  # action de masse (delta)

    # Champs existants dynamiquement (évite d'appeler un champ qui n'existe pas)
    def _koboform_fieldnames(self):
        return {f.name for f in KoboForm._meta.get_fields()}

    def get_list_display(self, request):
        fields = self._koboform_fieldnames()
        cols = ["name", "xform_id_string", "slug", "mode", "enabled"]
        if "connection" in fields:
            cols.append("connection")
        if "last_synced_at" in fields:
            cols.append("last_synced_at")
        cols.append("action_links")
        return cols

    def get_list_filter(self, request):
        fields = self._koboform_fieldnames()
        flt = ["enabled", "mode"]
        if "connection" in fields:
            flt.append("connection")
        return flt

    # URLs custom : génération module, sync schéma, sync données
    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "generate/<int:pk>/",
                self.admin_site.admin_view(self.generate_view),
                name=f"{opts.app_label}_{opts.model_name}_generate",
            ),
            path(
                "sync/<int:pk>/",
                self.admin_site.admin_view(self.sync_view),
                name=f"{opts.app_label}_{opts.model_name}_sync",
            ),
            path(
                "sync-data/<int:pk>/",
                self.admin_site.admin_view(self.sync_data_view),
                name=f"{opts.app_label}_{opts.model_name}_sync_data",
            ),
        ]
        return custom + urls

    # Colonne d’actions : Générer / Sync modèle / Sync données (delta/complet)
    def action_links(self, obj):
        opts = self.model._meta
        gen = reverse(f"admin:{opts.app_label}_{opts.model_name}_generate", args=[obj.pk])
        sync_schema = reverse(f"admin:{opts.app_label}_{opts.model_name}_sync", args=[obj.pk])
        sync_data = reverse(f"admin:{opts.app_label}_{opts.model_name}_sync_data", args=[obj.pk])

        # !!! IMPORTANT: accolades CSS échappées ({{ }}) pour éviter KeyError avec format_html
        return format_html(
            '''
            <div class="kobo-actions">
                <a class="ka ka-primary" href="{0}">Générer</a>
                <a class="ka" href="{1}">Sync modèle</a>
                <a class="ka ka-info" href="{2}">Sync données</a>
                <a class="ka ka-warn" href="{3}">Sync données (complet)</a>
            </div>
            <style>
            .kobo-actions {{
                display: inline-flex; gap: 6px; flex-wrap: wrap; align-items: center;
            }}
            .kobo-actions .ka {{
                display: inline-block; padding: 3px 8px; border-radius: 6px;
                background: #f0f0f0; border: 1px solid #d9d9d9; text-decoration: none;
                white-space: nowrap; font-size: 12px;
            }}
            .kobo-actions .ka:hover {{ background: #e5e5e5; }}
            .kobo-actions .ka-primary {{ background:#0a7; color:#fff; border-color:#0a7; }}
            .kobo-actions .ka-primary:hover {{ background:#086; border-color:#086; }}
            .kobo-actions .ka-info {{ background:#2b6cb0; color:#fff; border-color:#2b6cb0; }}
            .kobo-actions .ka-info:hover {{ background:#234e7a; border-color:#234e7a; }}
            .kobo-actions .ka-warn {{ background:#d97706; color:#fff; border-color:#d97706; }}
            .kobo-actions .ka-warn:hover {{ background:#b45309; border-color:#b45309; }}
            </style>
            ''',
            gen,
            sync_schema,
            sync_data,
            f"{sync_data}?full=1",
        )
    action_links.short_description = "Actions"

    # --- VUES BOUTONS ---
    def generate_view(self, request, pk):
        """
        Génère (ou régénère) l'app cible.
        - Si Celery est dispo: tâche async.
        - Sinon: fallback synchrone direct via services.generator.
        """
        if generate_module_task is not None:
            try:
                generate_module_task.delay(pk)
                messages.success(request, "Génération déclenchée (asynchrone).")
            except Exception:
                try:
                    generate_module_task(pk)  # exécution directe de la fonction (si décorateur tolère)
                    messages.success(request, "Génération exécutée (synchrone).")
                except Exception as e:
                    messages.error(request, f"Échec de la génération: {e}")
        else:
            # Fallback total: appel direct au générateur
            try:
                from .services.generator import generate_app
                app_slug, model_name, logs = generate_app(pk)
                messages.success(request, f"Génération OK: {app_slug}.{model_name}")
            except Exception as e:
                messages.error(request, f"Échec de la génération: {e}")

        opts = self.model._meta
        return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))

    def sync_view(self, request, pk):
        """
        Synchronise le **schéma** depuis Kobo (mapping / modèles).
        Nécessite idéalement une tâche dédiée; sinon on informe l’utilisateur.
        """
        if sync_kobo_schema_task is not None:
            try:
                sync_kobo_schema_task.delay(pk)
                messages.success(request, "Synchronisation du modèle Kobo déclenchée (asynchrone).")
            except Exception:
                try:
                    sync_kobo_schema_task(pk)
                    messages.success(request, "Synchronisation du modèle Kobo exécutée (synchrone).")
                except Exception as e:
                    messages.error(request, f"Échec de la synchronisation du modèle: {e}")
        else:
            messages.error(
                request,
                "Tâche indisponible : sync_kobo_schema_task introuvable. "
                "Installez/activez Celery ou implémentez un fallback."
            )
        opts = self.model._meta
        return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))

    def sync_data_view(self, request, pk):
        """
        Synchronise les **données**:
        - par défaut delta (since = last_synced_at)
        - si ?full=1 => synchronisation complète
        """
        form = KoboForm.objects.get(pk=pk)
        full = request.GET.get("full") == "1"
        since = None if full else (form.last_synced_at.isoformat() if form.last_synced_at else None)

        if sync_form_task is not None:
            try:
                task = sync_form_task.delay(form.pk, full=full)
                messages.success(request, f"Synchro des données déclenchée (asynchrone). Task ID: {task.id}")
            except Exception:
                try:
                    res = sync_submissions(form, since=since)
                    messages.success(
                        request,
                        f"Synchro exécutée (synchrone) — créés: {res['created']}, "
                        f"MAJ: {res['updated']}, ignorés: {res['skipped']}, erreurs: {res['errors']}."
                    )
                except Exception as e:
                    messages.error(request, f"Échec synchro: {e}")
        else:
            # Fallback synchrone
            try:
                res = sync_submissions(form, since=since)
                msg = (
                    f"Synchro exécutée — créés: {res['created']}, MAJ: {res['updated']}, "
                    f"ignorés: {res['skipped']}, erreurs: {res['errors']}."
                )
                if getattr(form, "last_synced_at", None):
                    msg += f" (Dernière synchro: {localtime(form.last_synced_at):%Y-%m-%d %H:%M})"
                messages.success(request, msg)
            except Exception as e:
                messages.error(request, f"Échec synchro: {e}")

        opts = self.model._meta
        return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))

    # --- Action de masse : sync données (delta) ---
    def sync_selected_data(self, request, queryset):
        total = created = updated = skipped = errors = 0
        used_async = False

        for form in queryset:
            since = form.last_synced_at.isoformat() if getattr(form, "last_synced_at", None) else None

            if sync_form_task is not None:
                try:
                    sync_form_task.delay(form.pk, full=False)
                    used_async = True
                    total += 1
                    continue
                except Exception:
                    pass  # on tombera en fallback synchrone

            # Fallback synchrone
            try:
                res = sync_submissions(form, since=since)
                created += int(res.get("created", 0))
                updated += int(res.get("updated", 0))
                skipped += int(res.get("skipped", 0))
                errors += int(res.get("errors", 0))
                total += 1
            except Exception as e:
                errors += 1
                total += 1

        if used_async:
            messages.success(request, f"Tâches de synchro (delta) envoyées pour {total} formulaire(s).")
        else:
            messages.success(
                request,
                f"Synchro exécutée — {total} formulaire(s) | "
                f"créés: {created}, MAJ: {updated}, ignorés: {skipped}, erreurs: {errors}."
            )

    sync_selected_data.short_description = "Synchroniser les données (delta) des formulaires sélectionnés"


# ---------- KoboFieldMap ----------
@admin.register(KoboFieldMap)
class KoboFieldMapAdmin(admin.ModelAdmin):
    list_display = ("form", "kobo_name", "model_field", "dtype", "required")
    list_filter = ("form", "dtype")
    search_fields = ("kobo_name", "model_field")


# ---------- SyncLog ----------
@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("form", "instance_id", "status", "created_at")
    list_filter = ("form", "status", "created_at")
    search_fields = ("instance_id", "message")


# ---------- Connexions Kobo ----------
class KoboConnectionForm(forms.ModelForm):
    api_token = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        help_text="Token API Kobo (sera stocké en base)."
    )
    class Meta:
        model = KoboConnection
        fields = "__all__"


@admin.register(KoboConnection)
class KoboConnectionAdmin(admin.ModelAdmin):
    form = KoboConnectionForm
    list_display = ("name", "api_base", "is_default", "updated_at", "test_link")
    list_filter = ("is_default",)
    search_fields = ("name", "api_base")

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "test/<int:pk>/",
                self.admin_site.admin_view(self.test_view),
                name=f"{opts.app_label}_{opts.model_name}_test",
            ),
        ]
        return custom + urls

    def test_link(self, obj):
        opts = self.model._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_test", args=[obj.pk])
        return format_html('<a class="button" href="{}">Tester</a>', url)
    test_link.short_description = "Connexion"

    def test_view(self, request, pk):
        obj = KoboConnection.objects.get(pk=pk)
        try:
            ok = test_connection(obj.api_base, obj.api_token, verify=obj.verify_ssl)
            if ok:
                messages.success(request, "Connexion OK : authentification réussie.")
            else:
                messages.error(request, "La connexion a répondu mais n'a pas été validée.")
        except Exception as e:
            messages.error(request, f"Échec de la connexion : {e}")
        opts = self.model._meta
        return HttpResponseRedirect(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"))
