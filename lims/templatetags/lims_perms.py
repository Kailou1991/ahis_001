# lims/templatetags/lims_perms.py
from django import template

register = template.Library()

# Clé menu -> groupes autorisés
MENU_GROUPS = {
    "reception": {
        "Administrateur Système",
        "Directeur de laboratoire",
        "Réceptioniste",
    },
    "planif": {
        "Administrateur Système",
        "Directeur de laboratoire",
        "Superviseur technique",
        "Responsable Qualité",
        "Superviseur Réseau labo",
    },
    "exec": {
        "Analyste",
        "Superviseur technique",
        "Responsable Qualité",
        "Directeur de laboratoire",
        "Administrateur Système",
    },
    "valtech": {
        "Responsable Qualité",
        "Superviseur technique",
        "Directeur de laboratoire",
        "Administrateur Système",
    },
    "valbio": {
        "Responsable Qualité",
        "Directeur de laboratoire",
        "Administrateur Système",
    },
    "rapports": {
        "Responsable Qualité",
        "Directeur de laboratoire",
        "Administrateur Système",
        "Superviseur Réseau labo",
        "Gestionnaire de finance",
    },
    "stocks": {
        "Gestionnaire de stock",
        "Administrateur Système",
        "Responsable Qualité",  # lecture
    },
    "equip": {
        "Superviseur technique",
        "Administrateur Système",
        "Directeur de laboratoire",
    },
    "setup": {
        "Administrateur Système",
        "Responsable Qualité",
        "Directeur de laboratoire",
    },
}

@register.simple_tag(takes_context=True)
def has_menu(context, key: str) -> bool:
    """
    Usage dans base.html : {% has_menu 'planif' as show_planif %} {% if show_planif %} ... {% endif %}
    """
    user = context.get("user")
    if not user or not user.is_authenticated:
        return False
    # superuser voit tout
    if user.is_superuser:
        return True
    allowed = MENU_GROUPS.get(key, set())
    if not allowed:
        return False
    # récupère les noms de groupes de l'utilisateur
    user_groups = set(user.groups.values_list("name", flat=True))
    return bool(user_groups & allowed)
