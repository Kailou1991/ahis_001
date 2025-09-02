from django.contrib import admin
from .models import CategorieActe, TypeActe,PieceAFournir, DemandeActe, AffectationSuivi,Justificatif, SuiviDemande,EmailNotification

admin.site.register(CategorieActe)
admin.site.register(TypeActe)
admin.site.register(DemandeActe)
admin.site.register(Justificatif)
admin.site.register(SuiviDemande)
admin.site.register(EmailNotification)
admin.site.register(AffectationSuivi)
admin.site.register(PieceAFournir)
