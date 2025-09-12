# publishing/templatetags/numfmt.py
from django import template

register = template.Library()

def _to_float(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # tolère "12 345,67" ou "12,345.67"
    s = s.replace("\xa0", " ").replace(" ", "")
    # si virgule comme séparateur décimal, convertir en point
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        try:
            return float(str(value))
        except Exception:
            return None

@register.filter(name="fr_number")
def fr_number(value, decimals="-1"):
    """
    Formate un nombre en FR :
      - séparateur milliers : espace insécable
      - séparateur décimal : virgule
    Param `decimals` :
      - "0","1","2",...  => nb de décimales fixes
      - "-1" (défaut)    => auto (0 à 3 décimales utiles)
    Non numérique => retourne tel quel.
    """
    x = _to_float(value)
    if x is None:
        return value

    # détermine le nombre de décimales
    try:
        dec = int(decimals)
    except Exception:
        dec = -1

    if dec < 0:
        # auto : garder jusqu’à 3 décimales non nulles
        s_raw = f"{x:.6f}".rstrip("0").rstrip(".")
        frac = s_raw.split(".")[1] if "." in s_raw else ""
        dec = min(3, max(0, len(frac)))

    s = f"{x:,.{dec}f}"      # ex: 12,345.67 (US)
    s = s.replace(",", " ")  # milliers -> espace
    s = s.replace(".", ",")  # décimal -> virgule
    return s
