import tempfile
from django.template.loader import render_to_string

try:
    from weasyprint import HTML
    WEASY = True
except Exception:
    WEASY = False

def generer_rapport_demande(demande):
    ctx = {
        "demande": demande,
        "echantillons": list(demande.echantillons.all()),
        "analyses": list(demande.echantillons.prefetch_related("analyses").values(
            "code_echantillon", "analyses__test__code_test", "analyses__test__nom_test", "analyses__interpretation", "analyses__resultat_brut"
        )),
    }
    html = render_to_string("lims/rapport_demande.html", ctx)
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    if WEASY:
        HTML(string=html).write_pdf(out.name)
    else:
        with open(out.name, "wb") as fh:
            fh.write(html.encode("utf-8"))
    return out.name
