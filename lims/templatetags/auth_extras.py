# core/templatetags/auth_extras.py
from django import template
register = template.Library()

@register.filter
def has_group(user, name: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=name).exists()
