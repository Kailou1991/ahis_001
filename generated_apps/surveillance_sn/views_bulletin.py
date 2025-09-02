# -*- coding: utf-8 -*-
# generated_apps/surveillance_sn/views_bulletin.py

from __future__ import annotations

import os, re, calendar
from io import BytesIO
from datetime import date, timedelta, datetime
from collections import Counter, defaultdict

from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Value, IntegerField
from django.db.models.functions import Coalesce, TruncMonth
from django.utils.timezone import now
from data_initialization.scop import scope_q_text


from .models import (
    SurveillanceSn as SParent,
    SurveillanceSnChild783b28ae as SChild,
)

# Remplace si tu as un vrai décorateur de rôles
def group_required(*groups):
    def _decorator(view):
        return view
    return _decorator


# -------------------------
#       FORMULAIRE
# -------------------------
class PeriodeRapportForm(forms.Form):
    PERIODES = (
        ('Hebdomadaire', 'Hebdomadaire'),
        ('Mensuel', 'Mensuel'),
        ('Trimestriel', 'Trimestriel'),
        ('Semestriel', 'Semestriel'),
        ('Annuel', 'Annuel'),
    )
    annee = forms.IntegerField(
        initial=date.today().year, min_value=2000, max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    periode_type = forms.ChoiceField(
        choices=PERIODES, initial='Mensuel',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    semaine = forms.IntegerField(required=False, min_value=1, max_value=53,
                                 widget=forms.NumberInput(attrs={'class': 'form-control'}))
    mois = forms.IntegerField(required=False, min_value=1, max_value=12,
                              widget=forms.NumberInput(attrs={'class': 'form-control'}))
    trimestre = forms.IntegerField(required=False, min_value=1, max_value=4,
                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))
    semestre = forms.IntegerField(required=False, min_value=1, max_value=2,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))
    region = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes les régions")],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)        # ← AJOUTER
        super().__init__(*args, **kwargs)
        qs = SParent.objects.all()
        if request is not None:                      # ← AJOUTER
            qs = qs.filter(scope_q_text(
                request,
                region_text_field="grp3_region",
                departement_text_field="grp3_departement",
            ))
        regions = (qs.exclude(grp3_region__isnull=True)
                .exclude(grp3_region="")
                .values_list("grp3_region", flat=True)
                .distinct().order_by("grp3_region"))
        self.fields["region"].choices = [("", "Toutes les régions")] + [(r, r) for r in regions]


    def clean(self):
        cleaned = super().clean()
        p = cleaned.get('periode_type')
        if p == 'Hebdomadaire' and not cleaned.get('semaine'):
            self.add_error('semaine', "Indique la semaine (1–53).")
        if p == 'Mensuel' and not cleaned.get('mois'):
            self.add_error('mois', "Indique le mois (1–12).")
        if p == 'Trimestriel' and not cleaned.get('trimestre'):
            self.add_error('trimestre', "Indique le trimestre (1–4).")
        if p == 'Semestriel' and not cleaned.get('semestre'):
            self.add_error('semestre', "Indique le semestre (1–2).")
        return cleaned


# -------------------------
#  GÉNÉRATION DU PDF
# -------------------------
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires',
                'Administrateur Régional','Administrateur Départemental',
                'Animateur de la Surveillance','Directeur de la Santé Animale')
def generer_contenu_pdf_bulletin_surv(request, buffer, s_qs, p_qs,
                                      start_date, end_date, periode_type, region_name: str | None):

    # ReportLab
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from django.conf import settings
    from django.utils.timezone import localtime

    # ---------- Police UTF-8 (optionnelle, mais recommandée) ----------
    # Si le fichier n'existe pas, on reste sur Helvetica.
    try:
        font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "DejaVuSans.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
            BASE_FONT = "DejaVuSans"
        else:
            BASE_FONT = "Helvetica"
    except Exception:
        BASE_FONT = "Helvetica"

    # ---------- Helpers ----------
    SOFT_HYPH = u"\u00AD"  # soft hyphen (apparait uniquement en fin de ligne)
    SEP_RE = re.compile(r"(\s+|/|-|,|;|\(|\)|\[|\])")

    def insert_soft_hyphens(token: str, width: int = 12) -> str:
        if len(token) <= width:
            return token
        # coupe proprement les mots très longs
        return SOFT_HYPH.join(token[i:i+width] for i in range(0, len(token), width))

    def safe_wrap(text: str, width: int = 12) -> str:
        """Ajoute des soft-hyphens dans les longs 'mots' pour éviter les carrés et forcer une césure propre."""
        if not text:
            return ""
        parts = SEP_RE.split(str(text))
        out = []
        for p in parts:
            if SEP_RE.fullmatch(p):  # séparateur / espace
                out.append(p)
            else:
                out.append(insert_soft_hyphens(p, width=width))
        return "".join(out)

    def fmt_int(v):
        try:
            return f"{int(v or 0):,}".replace(",", " ")
        except Exception:
            return "0"

    def pct(num, den):
        try:
            num = float(num or 0); den = float(den or 0)
            return round((num / den) * 100, 1) if den else 0.0
        except Exception:
            return 0.0

    def month_name_fr(y, m):
        noms = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                "juil.", "août", "sept.", "oct.", "nov.", "déc."]
        return f"{noms[m-1]} {y}"

    def wrap_para(txt, style_name="CellLeft", width=12):
        return Paragraph(safe_wrap((txt or ""), width=width), styles[style_name])

    def zebra(tbl, header_bg="#0b5ed7"):
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(header_bg)),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), BASE_FONT + '-Bold' if BASE_FONT != "Helvetica" else 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('GRID', (0,0), (-1,-1), 0.35, colors.grey),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.Color(0.98,0.98,0.98)]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

    def kpi(label, value, sub=None, bg="#f8f9fa"):
        t = Table(
            [[Paragraph(f"<b>{label}</b>", styles["KPI_Label"])],
             [Paragraph(f"{value}", styles["KPI_Value"])],
             [Paragraph(sub or "", styles["KPI_Sub"])]],
            colWidths=[5.2*cm], rowHeights=[0.8*cm, 1.2*cm, 0.6*cm]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg)),
            ('BOX', (0,0), (-1,-1), 0.7, colors.HexColor("#dee2e6")),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t
    



    def wrap_maladie(txt):
        """
        Renvoie un Paragraph qui force un retour à la ligne propre
        pour les libellés de maladie (mots longs, slashs, tirets).
        """
        t = (txt or "").strip()
        # autoriser des césures sur / et -
        t = t.replace("/", "/\u200b").replace("-", "-\u200b")

        # insérer des soft-hyphens dans les très longs tokens sans espaces
        def _soft_break(token: str, every: int = 12, min_len: int = 18) -> str:
            if len(token) <= min_len:
                return token
            parts = [token[i:i+every] for i in range(0, len(token), every)]
            return "\u00ad".join(parts)  # soft hyphen

        t = " ".join(_soft_break(w) for w in t.split())
        return Paragraph(t, styles["CellLeft"])


    # ---------- Styles ----------
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitreBleu", fontName=BASE_FONT, fontSize=16, leading=20, alignment=1, textColor=colors.darkblue))
    styles.add(ParagraphStyle(name="SousTitre", fontName=BASE_FONT, fontSize=11, leading=14, alignment=1))
    styles.add(ParagraphStyle(name="NormalSmall", fontName=BASE_FONT, fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="NormalCenter", fontName=BASE_FONT, fontSize=9, alignment=1))
    styles.add(ParagraphStyle(name="H2", fontName=BASE_FONT, fontSize=12, leading=15, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#0b5ed7")))
    styles.add(ParagraphStyle(name="H3", fontName=BASE_FONT, fontSize=10, leading=13, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#0b5ed7")))
    styles.add(ParagraphStyle(name="KPI_Label", fontName=BASE_FONT, fontSize=8, textColor=colors.HexColor("#6c757d")))
    styles.add(ParagraphStyle(name="KPI_Value", fontName=BASE_FONT, fontSize=16, leading=18, textColor=colors.HexColor("#212529")))
    styles.add(ParagraphStyle(name="KPI_Sub", fontName=BASE_FONT, fontSize=7, textColor=colors.HexColor("#6c757d")))
    # Cellules avec wrapping propre (pas de CJK)
    styles.add(ParagraphStyle(name="CellLeft", fontName=BASE_FONT, fontSize=8, leading=10, alignment=0))
    styles.add(ParagraphStyle(name="CellCenter", fontName=BASE_FONT, fontSize=8, leading=10, alignment=1))

    # ---------- Footer ----------
    def _footer(c: _canvas.Canvas, doc):
        c.saveState()
        meta = f"AHIS – Bulletin généré le {localtime(now()):%d/%m/%Y %H:%M} – Page {doc.page}"
        c.setFont(BASE_FONT if BASE_FONT != "Helvetica" else "Helvetica", 8)
        c.setFillGray(0.4)
        c.drawRightString(doc.pagesize[0]-1.0*cm, 0.8*cm, meta)
        c.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18
    )
    story = []

    # ---------- En-tête institutionnel ----------
    try:
        from parametre.models import Ministere, DirectionSV
    except Exception:
        Ministere = DirectionSV = None

    ministere_nom = ""
    direction_nom = ""
    if Ministere:
        ministere_nom = Ministere.objects.first().nom if getattr(Ministere.objects, "exists", lambda: False)() else ""
    if DirectionSV:
        direction_nom = DirectionSV.objects.first().nom if getattr(DirectionSV.objects, "exists", lambda: False)() else ""

    ministere_nom = ministere_nom or "MINISTÈRE DE L’AGRICULTURE ET DE L’ÉLEVAGE"
    direction_nom = direction_nom or "DIRECTION DES SERVICES VÉTÉRINAIRES"

    drapeau = os.path.join(settings.BASE_DIR, 'static/img/gondwana.png')
    armoirie = os.path.join(settings.BASE_DIR, 'static/img/amrgondwana.jpg')

    story.append(
        Table([[
            Image(drapeau, width=60, height=40) if os.path.exists(drapeau) else Paragraph("", styles["NormalSmall"]),
            Paragraph("<b>REPUBLIQUE DU GONDWANA<br/>UN PEUPLE – UNE TRADITION – UNE LIBERTÉ</b>", styles['NormalCenter']),
            Image(armoirie, width=60, height=60) if os.path.exists(armoirie) else Paragraph("", styles["NormalSmall"]),
        ]], colWidths=[70, 400, 70])
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph(ministere_nom.upper(), styles["TitreBleu"]))
    story.append(Paragraph(direction_nom.upper(), styles["SousTitre"]))
    story.append(Spacer(1, 4))

    zone_txt = f" – Région : {region_name}" if region_name else " – Toutes régions"
    story.append(Paragraph("BULLETIN ÉPIDÉMIOLOGIQUE – SANTÉ ANIMALE", styles["H2"]))
    story.append(Paragraph(f"Période couverte : <b>{start_date:%d/%m/%Y}</b> – <b>{end_date:%d/%m/%Y}</b>{zone_txt}", styles["NormalSmall"]))
    story.append(Paragraph("Source des données : AHIS (surveillance Kobo – formulaires « SurveillanceSn »).", styles["NormalSmall"]))
    story.append(Spacer(1, 6))

    # ---------- Agrégats ----------
    sensible_expr = Coalesce(F("totaltroupeau"), F("effectif_total_troup_st_de_tot"), Value(0), output_field=IntegerField())
    morts_expr    = Coalesce(F("effectif_animaux_morts_calcule"), F("calcul_animaux_morts"), Value(0), output_field=IntegerField())

    g = s_qs.aggregate(
        sens=Sum(sensible_expr),
        mal=Sum(Coalesce(F("total_malade"), Value(0))),
        morts=Sum(morts_expr),
    )
    total_foyers = p_qs.values("id").distinct().count()
    g_sens = int(g.get("sens") or 0)
    g_mal  = int(g.get("mal") or 0)
    g_morts= int(g.get("morts") or 0)

    # Délai médian
    deltas = []
    for p in p_qs.exclude(grp1_date_signalement__isnull=True).exclude(submission_time__isnull=True).values("grp1_date_signalement","submission_time"):
        try:
            d = (p["submission_time"].date() - p["grp1_date_signalement"]).days
            deltas.append(d)
        except Exception:
            pass
    deltas.sort()
    median_prompt = deltas[len(deltas)//2] if deltas else None

    k1 = [kpi("Foyers notifiés", fmt_int(total_foyers)),
          kpi("Animaux exposés", fmt_int(g_sens)),
          kpi("Malades", fmt_int(g_mal)),
          kpi("Morts", fmt_int(g_morts))]
    k2 = [kpi("Mortalité (%)", f"{pct(g_morts, g_sens):.1f}", "morts / exposés", "#f1f3f5"),
          kpi("Morbidité (%)", f"{pct(g_mal, g_sens):.1f}", "malades / exposés", "#f1f3f5"),
          kpi("Létalité (%)", f"{pct(g_morts, g_mal):.1f}", "morts / malades", "#f1f3f5"),
          kpi("Délai médian (j)", f"{median_prompt if median_prompt is not None else '—'}", "signalement → soumission", "#f1f3f5")]
    story.extend([Table([k1], colWidths=[5.4*cm]*4, hAlign="LEFT", spaceBefore=6, spaceAfter=3),
                  Table([k2], colWidths=[5.4*cm]*4, hAlign="LEFT"),
                  Spacer(1, 8)])

    # ---------- Résumé exécutif ----------
    top_mal = list(
        s_qs.values('parent__grp5_qmad1')
            .annotate(m=Sum(Coalesce(F('total_malade'), Value(0))))
            .order_by('-m')[:4]
    )
    hot_regs = list(
        s_qs.values('parent__grp3_region')
            .annotate(foy=Count('parent_id', distinct=True))
            .order_by('-foy')[:2]
    )
    top_txt = ", ".join([f"{(r['parent__grp5_qmad1'] or '—')} ({fmt_int(r['m'])})" for r in top_mal]) if top_mal else "—"
    hot_txt = " et ".join([f"{r['parent__grp3_region'] or '—'}" for r in hot_regs]) if hot_regs else "—"

    resume = (
        f"<b>Résumé exécutif.</b> <b>{fmt_int(total_foyers)}</b> foyers notifiés, "
        f"<b>{fmt_int(g_mal)}</b> malades et <b>{fmt_int(g_morts)}</b> décès "
        f"(exposés : {fmt_int(g_sens)}). Maladies dominantes : {safe_wrap(top_txt)}. "
        f"Points chauds : <b>{safe_wrap(hot_txt)}</b>."
    )
    story.extend([Paragraph(resume, styles["NormalSmall"]), Spacer(1, 8)])

    # ---------- 1) Par maladie ----------
    story.append(Paragraph("1) Situation par maladie prioritaire (suspicion)", styles["H3"]))
    t1_rows = [["Maladie", "Foyers", "Exposés", "Malades", "Morts", "Mortalité %", "Morbidité %", "Létalité %"]]
    stats_mal = (s_qs.values("parent__grp5_qmad1")
                    .annotate(
                        foy=Count("parent_id", distinct=True),
                        exp=Sum(sensible_expr),
                        mal=Sum(Coalesce(F("total_malade"), Value(0))),
                        dcd=Sum(morts_expr),
                    )
                    .order_by("-mal", "parent__grp5_qmad1"))
    labels, m_mor, m_morb, m_leta = [], [], [], []
    for r in stats_mal:
        mal_nom = r["parent__grp5_qmad1"] or "—"
        exp = int(r["exp"] or 0); mal=int(r["mal"] or 0); dcd=int(r["dcd"] or 0)
        mor = pct(dcd, exp); morb = pct(mal, exp); leta = pct(dcd, mal)
        t1_rows.append([wrap_para(mal_nom, width=10), fmt_int(r["foy"]), fmt_int(exp), fmt_int(mal), fmt_int(dcd),
                        f"{mor:.1f}", f"{morb:.1f}", f"{leta:.1f}"])
        labels.append(mal_nom); m_mor.append(mor); m_morb.append(morb); m_leta.append(leta)

    t1 = Table(t1_rows, hAlign="LEFT", colWidths=[5.0*cm, 1.6*cm, 2.2*cm, 2.2*cm, 2.0*cm, 2.2*cm, 2.2*cm, 2.0*cm])
    zebra(t1); story.append(t1)
    story.append(Spacer(1, 6))

    # (graph facultatif – tu peux garder/retirer)
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        x = np.arange(len(labels)); width = 0.28
        fig, ax = plt.subplots(figsize=(8.8, 3.2))
        ax.bar(x - width, m_mor,  width, label='Mortalité %')
        ax.bar(x,         m_morb, width, label='Morbidité %')
        ax.bar(x + width, m_leta, width, label='Létalité %')
        ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
        ax.set_ylabel("Taux (%)"); ax.set_title("Taux par maladie")
        ax.legend(loc="upper left", ncol=3, fontsize=8)
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        bio = BytesIO(); fig.tight_layout(); fig.savefig(bio, format='PNG', dpi=160); bio.seek(0)
        story.extend([Image(bio, width=560, height=240)])
        plt.close(fig)
    except Exception:
        pass

    story.append(Spacer(1, 8))

        # ---------- 2) Évolution temporelle (3 mois glissants) ----------
    story.append(Paragraph("2) Évolution temporelle (3 mois glissants)", styles["H3"]))

    # Fenêtre = mois M-2 .. M (fin sur end_date)
    start_m1 = end_date.replace(day=1)
    prev_m   = (start_m1 - timedelta(days=1)).replace(day=1)
    prev_m2  = (prev_m   - timedelta(days=1)).replace(day=1)
    months = [(prev_m2.year, prev_m2.month),
              (prev_m.year,   prev_m.month),
              (start_m1.year, start_m1.month)]
    month_labels = [month_name_fr(y, m) for (y, m) in months]

    # Comptage par maladie x mois (valeur = nb de parents distincts)
    from collections import defaultdict
    counts = defaultdict(lambda: [0, 0, 0])  # maladie -> [m-2, m-1, m]
    diseases = set()

    for idx, (y, m) in enumerate(months):
        base = s_qs.filter(parent__grp1_date_signalement__year=y,
                           parent__grp1_date_signalement__month=m)
        for r in (base.values("parent__grp5_qmad1")
                       .annotate(c=Count("parent_id", distinct=True))):
            mal = r["parent__grp5_qmad1"] or "—"
            counts[mal][idx] = int(r["c"] or 0)
            diseases.add(mal)

    if not diseases:
        diseases = {"—"}

    # Tri des maladies par total décroissant
    diseases_sorted = sorted(diseases, key=lambda k: sum(counts[k]), reverse=True)

    # Tableau : maladies en lignes, mois en colonnes + total
    rows_tr = [["Maladie"] + month_labels + ["Total"]]
    for mal in diseases_sorted:
        m2, m1, m0 = counts[mal]
        total = m2 + m1 + m0
        rows_tr.append([
            wrap_para(mal, width=14),
            fmt_int(m2), fmt_int(m1), fmt_int(m0),
            fmt_int(total),
        ])

    # Largeurs :  Maladie large + 3 mois + Total
    t_tr = Table(
        rows_tr, hAlign="LEFT",
        colWidths=[7.8*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.4*cm]
    )
    zebra(t_tr)
    story.append(t_tr)
    story.append(Spacer(1, 8))


    # ---------- 3) Répartition géographique ----------
    story.append(Paragraph("3) Répartition géographique", styles["H3"]))
    geo_rows = [["Région", "Foyers", "Principales maladies", "Communes touchées (exemples)"]]
    parents_by_reg = (p_qs.values("grp3_region")
                         .annotate(foy=Count("id"))
                         .order_by("-foy","grp3_region"))
    for pr in parents_by_reg:
        reg = pr["grp3_region"] or "—"
        foy = pr["foy"]
        reg_parents = p_qs.filter(grp3_region__iexact=reg)
        communes = list(reg_parents.exclude(grp3_commune__isnull=True)
                                      .exclude(grp3_commune="")
                                      .values_list("grp3_commune", flat=True)[:5])
        communes_txt = ", ".join(communes) if communes else "—"
        child_reg = s_qs.filter(parent__grp3_region__iexact=reg)
        mal_counts = (child_reg.values("parent__grp5_qmad1")
                               .annotate(c=Count("parent_id", distinct=True))
                               .order_by("-c")[:3])
        mals_txt = ", ".join([(r["parent__grp5_qmad1"] or "—") for r in mal_counts]) or "—"
        geo_rows.append([wrap_para(reg, width=10), fmt_int(foy), wrap_para(mals_txt, width=12), wrap_para(communes_txt, width=14)])
    t_geo = Table(geo_rows, hAlign="LEFT", colWidths=[4.0*cm, 2.2*cm, 7.0*cm, 10.8*cm])
    zebra(t_geo); story.append(t_geo)
    story.append(Spacer(1, 8))

    # ---------- 4) Mesures de riposte ----------
    story.append(Paragraph("4) Mesures de riposte et contrôle", styles["H3"]))
    keys = {
        "Nettoyage & désinfection": ["désinfect", "nettoy", "desinfect"],
        "Quarantaine": ["quarantaine", "restriction", "interdit", "mouvement"],
        "Vaccination (riposte)": ["vaccin", "immunis"],
        "Saisies/abattage": ["saisie", "abatt", "destruction", "euthan"],
        "Lutte anti-vectorielle": ["vector", "insect", "acaricide", "larvicide"],
        "Sensibilisation": ["sensibil", "communication", "radio", "IEC"],
    }
    counts = Counter()
    for t in p_qs.values_list("commentaire_mesures_de_control", flat=True):
        low = (t or "").lower()
        for label, words in keys.items():
            if any(w in low for w in words):
                counts[label] += 1
    rip_rows = [["Mesure", "Nombre de sites", "Observations"]]
    for label in keys.keys():
        rip_rows.append([wrap_para(label, width=16), fmt_int(counts.get(label, 0)), wrap_para("—")])
    t_rip = Table(rip_rows, hAlign="LEFT", colWidths=[7.0*cm, 3.0*cm, 13.0*cm])
    zebra(t_rip); story.append(t_rip)
    story.append(Spacer(1, 8))

    # ---------- 5) Laboratoire ----------
    story.append(Paragraph("5) Laboratoire", styles["H3"]))
    prelev_mention = sum(1 for t in p_qs.values_list("ajouter_un_prelevement", flat=True) if t and str(t).strip())
    lab_txt = f"Prélèvements mentionnés dans les fiches : <b>{fmt_int(prelev_mention)}</b>."
    story.append(Paragraph(lab_txt, styles["NormalSmall"]))
    story.append(Spacer(1, 6))

    # ---------- 6) Analyse de risques ----------
    story.append(Paragraph("6) Analyse de risques (court terme)", styles["H3"]))
    risks = []
    if hot_regs:
        regs_str = ", ".join([r['parent__grp3_region'] or "—" for r in hot_regs])
        risks.append(f"Probabilité plus élevée dans <b>{safe_wrap(regs_str)}</b> (volume de foyers récent).")
    if top_mal:
        dom = top_mal[0]['parent__grp5_qmad1'] or "—"
        risks.append(f"Impact principal attendu : pertes liées à <b>{safe_wrap(dom)}</b> dans les zones à forte densité.")
    risks.append("Période de transhumance / marchés à bétail : surveiller mouvements et points d’eau.")
    story.append(Paragraph("• " + "<br/>• ".join(risks), styles["NormalSmall"]))
    story.append(Spacer(1, 6))

    # ---------- 7) Recommandations ----------
    story.append(Paragraph("7) Recommandations opérationnelles", styles["H3"]))
    recos = [
        "Renforcer la surveillance active dans les communes avec foyers récurrents.",
        "Contrôler les mouvements d’animaux dans les zones chaudes (certificats, inspections de marchés).",
        "Accroître la communication (radio en langues locales) sur signes & notification précoce.",
        "Si disponibilité : vaccination en riposte ciblée sur les foyers et communes limitrophes.",
        "Améliorer la qualité des fiches (mesures, délais) pour fiabiliser le suivi.",
    ]
    story.append(Paragraph("• " + "<br/>• ".join(recos), styles["NormalSmall"]))
    story.append(Spacer(1, 8))

    # ---------- Annexe ----------
   # ---------- 11) Annexes ----------
    story.append(PageBreak())
    story.append(Paragraph("Annexe – Liste détaillée des foyers", styles["H3"]))

    # Pré-agrégats par parent pour l’annexe
    amap = {
        r["parent_id"]: r for r in
        (SChild.objects.filter(parent__in=p_qs)
            .values("parent_id")
            .annotate(
                exp=Sum(sensible_expr),
                mal=Sum(Coalesce(F("total_malade"), Value(0))),
                dcd=Sum(morts_expr),
            ))
    }

    headers = ["ID", "Date", "Région", "Département", "Commune", "Village", "Maladie", "Exposés", "Malades", "Morts"]
    rows = [headers]
    chunk = 0
    CHUNK = 35

    for p in p_qs.order_by("-grp1_date_signalement", "-submission_time"):
        a = amap.get(p.id, {})
        rows.append([
            str(p.id),
            p.grp1_date_signalement.strftime("%d/%m/%Y") if p.grp1_date_signalement else "-",
            wrap_para(p.grp3_region or "-"),
            wrap_para(p.grp3_departement or "-"),
            wrap_para(p.grp3_commune or "-"),
            wrap_para((p.grp3_nom_du_village or "").strip()),
            wrap_maladie(p.grp5_qmad1 or "-"),  # <<< wrap spécifique maladie
            fmt_int(a.get("exp", 0)),
            fmt_int(a.get("mal", 0)),
            fmt_int(a.get("dcd", 0)),
        ])
        chunk += 1

        if chunk % CHUNK == 0:
            t = Table(
                rows, hAlign="LEFT",
                #         ID   Date  Région  Départ. Commune Village Maladie  Exp  Mal  Morts
                colWidths=[2.0*cm, 2.0*cm, 3.0*cm,  3.2*cm, 3.6*cm, 3.6*cm,  4.8*cm, 1.8*cm, 1.8*cm, 1.8*cm]
            )
            zebra(t)
            story.append(KeepTogether([t, Spacer(1, 6)]))
            rows = [headers]  # reset pour page suivante

    # dernière page
    if len(rows) > 1:
        t = Table(
            rows, hAlign="LEFT",
            colWidths=[2.0*cm, 2.0*cm, 3.0*cm,  3.2*cm, 3.6*cm, 3.6*cm,  4.8*cm, 1.8*cm, 1.8*cm, 1.8*cm]
        )
        zebra(t)
        story.append(t)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<font size='8' color='#6c757d'>Bulletin généré automatiquement – {end_date:%d/%m/%Y}.</font>",
        styles["NormalSmall"]
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


# -------------------------
#   VUE PRINCIPALE
# -------------------------
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires',
                'Administrateur Régional','Administrateur Départemental',
                'Animateur de la Surveillance','Directeur de la Santé Animale')
def generer_bulletin_surv(request):
    #form = PeriodeRapportForm(request.POST or None)
    form = PeriodeRapportForm(request.POST or None, request=request)

    error = None

    if request.method == "POST" and form.is_valid():
        ptype = form.cleaned_data["periode_type"]
        annee = int(form.cleaned_data["annee"])
        today = date.today()
        region_name = form.cleaned_data.get("region") or ""

        def daterange():
            if ptype == "Hebdomadaire":
                w = int(form.cleaned_data["semaine"])
                start = date.fromisocalendar(annee, w, 1); end = start + timedelta(days=6)
                return start, min(end, today)
            if ptype == "Mensuel":
                m = int(form.cleaned_data["mois"])
                last = calendar.monthrange(annee, m)[1]
                start = date(annee, m, 1); end = date(annee, m, last)
                return start, min(end, today)
            if ptype == "Trimestriel":
                t = int(form.cleaned_data["trimestre"])
                m1, m2 = {1:(1,3),2:(4,6),3:(7,9),4:(10,12)}.get(t, (1,3))
                last = calendar.monthrange(annee, m2)[1]
                start = date(annee, m1, 1); end = date(annee, m2, last)
                return start, min(end, today)
            if ptype == "Semestriel":
                s = int(form.cleaned_data["semestre"])
                if s == 1:
                    last = calendar.monthrange(annee, 6)[1]; start = date(annee,1,1); end = date(annee,6,last)
                else:
                    last = calendar.monthrange(annee,12)[1]; start = date(annee,7,1); end = date(annee,12,last)
                return start, min(end, today)
            if ptype == "Annuel":
                return date(annee,1,1), min(date(annee,12,31), today)
            return None, None

        start_date, end_date = daterange()
        if not (start_date and end_date and start_date <= today):
            error = "Veuillez sélectionner une période valide."
        else:
            #p_qs = SParent.objects.filter(grp1_date_signalement__range=(start_date, end_date))
            scope = scope_q_text(
                request,
                region_text_field="grp3_region",
                departement_text_field="grp3_departement",
            )  # ← AJOUTER

            p_qs = (SParent.objects
                    .filter(scope)  # ← AJOUTER
                    .filter(grp1_date_signalement__range=(start_date, end_date)))
            
            if region_name:
                p_qs = p_qs.filter(grp3_region__iexact=region_name)
            s_qs = SChild.objects.select_related("parent").filter(parent__in=p_qs)

            response = HttpResponse(content_type="application/pdf")
            response['Content-Disposition'] = (
                f'inline; filename="bulletin_surv_{ptype}_{start_date:%Y%m%d}_{end_date:%Y%m%d}.pdf"'
            )
            buf = BytesIO()
            generer_contenu_pdf_bulletin_surv(
                request, buffer=buf, s_qs=s_qs, p_qs=p_qs,
                start_date=start_date, end_date=end_date,
                periode_type=ptype, region_name=region_name or None
            )
            pdf = buf.getvalue(); buf.close(); response.write(pdf)
            return response

    return render(request, "surveillance_sn/bulletin.html", {"form": form, "error_message": error})
