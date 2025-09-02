from django import template
from core_menu.models import MenuItem

register = template.Library()

@register.inclusion_tag('core_menu/menu.html', takes_context=True)
def render_menu(context):
    user = context['request'].user
    items = MenuItem.objects.filter(active=True)
    if user.is_authenticated and not user.is_superuser:
        items = items.filter(groups__in=user.groups.all()).distinct()
    return {"items": items}