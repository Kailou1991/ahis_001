from django import template
import re

register = template.Library()

@register.filter
def espece_first(value):
    if not value:
        return ""
    s = str(value).strip()
    for sep in [";", ",", "/", "|", "-"]:
        s = s.replace(sep, "/")
    parts = [p.strip() for p in s.split("/") if p.strip()]
    token = parts[0] if parts else s
    camel_parts = re.split(r'(?<=[a-z])(?=[A-Z])', token)
    token = camel_parts[0] if camel_parts else token
    return token
