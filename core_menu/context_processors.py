from .models import MenuItem

def menu(request):
    user = request.user
    items = MenuItem.objects.filter(active=True)
    if user.is_authenticated and not user.is_superuser:
        items = items.filter(groups__in=user.groups.all()).distinct()
    return {"menu_items": items}