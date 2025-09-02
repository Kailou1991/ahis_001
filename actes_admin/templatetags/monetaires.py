# actes_admin/templatetags/monetaires.py
from django import template

register = template.Library()

@register.filter
def format_montant(value):
    try:
        value = float(value)
        montant = f"{value:,.2f}"  # format: 12345.67 -> 12,345.67
        montant = montant.replace(",", " ").replace(".", ",")  # Français
        return montant
    except (ValueError, TypeError):
        return "0,00"
