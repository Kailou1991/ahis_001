# kobo_integration/services/dynamic_parser.py
from __future__ import annotations
from typing import Any, Dict, Tuple
from django.apps import apps
# ... (tes imports/converters existants) ...

def _resolve_model(model, app_label: str, model_name: str | None):
    """Retourne la classe de modèle. Si non fournie, on la résout dynamiquement."""
    if model is not None:
        return model
    # d'abord, si un nom explicite est donné
    if model_name:
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            # certains préfèrent le chemin 'generated_apps.<slug>'
            return apps.get_model(f"generated_apps.{app_label}", model_name)

    # sinon, on prend le 1er modèle déclaré dans l’app
    try:
        conf = apps.get_app_config(app_label)
    except LookupError:
        conf = apps.get_app_config(f"generated_apps.{app_label}")
    models = list(conf.get_models())
    if not models:
        raise LookupError(f"Aucun modèle trouvé pour l'app '{app_label}'")
    return models[0]

def parse_with_fieldmaps(
    form_slug: str,
    model=None,
    payload: Dict[str, Any] | None = None,
    app_label: str | None = None,
    model_name: str | None = None,
) -> Tuple[bool, str]:
    """
    Parse générique basé sur KoboFieldMap.
    - form_slug : slug/label du KoboForm
    - model : (optionnel) classe du modèle cible
    - app_label : (optionnel) label de l'app (par défaut = form_slug)
    - model_name : (optionnel) nom de la classe du modèle
    """
    from kobo_integration.models import KoboForm, KoboFieldMap  # import local pour éviter cycles

    if payload is None:
        payload = {}

    # Résolution du modèle si non fourni
    app_label = (app_label or form_slug)
    Model = _resolve_model(model, app_label, model_name)

    # ... ensuite, garde ton code existant qui:
    # 1) lit les FieldMaps du KoboForm(form_slug)
    # 2) convertit selon dtype
    # 3) fait update_or_create (PK = _id si présent, sinon instance_id)
    # (ne change rien au reste de la fonction)
