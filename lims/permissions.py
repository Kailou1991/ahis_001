# lims/permissions.py (NOUVEAU fichier recommandé)

def is_in_groups(user, names: tuple[str, ...]) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=names).exists()

# Groupes (reprend les tiens)
ROLE_ASSIGN   = ("Administrateur Système", "Superviseur technique", "Réceptioniste", "Directeur de laboratoire")
ROLE_EXEC     = ("Analyste", "Responsable Qualité", "Administrateur Système", "Directeur de laboratoire")
ROLE_RESULT   = ("Réceptioniste", "Administrateur Système", "Directeur de laboratoire")  # saisie résultats
ROLE_VAL_TECH = ("Responsable Qualité", "Administrateur Système", "Directeur de laboratoire")
ROLE_VAL_BIO  = ("Directeur de laboratoire", "Administrateur Système")

def delegated(user, demande, role_key: str) -> bool:
    # l’utilisateur est-il délégataire actif pour ce rôle sur cette demande ?
    return demande.delegations.filter(role=role_key, utilisateur=user, actif=True).exists()

def can_assign(user) -> bool:
    return is_in_groups(user, ROLE_ASSIGN)

def can_exec(user) -> bool:
    return is_in_groups(user, ROLE_EXEC)

def can_enter_results(user, demande) -> bool:
    return is_in_groups(user, ROLE_RESULT) or delegated(user, demande, "saisie_resultats")

def can_val_tech(user, demande) -> bool:
    return is_in_groups(user, ROLE_VAL_TECH) or delegated(user, demande, "val_tech")

def can_val_bio(user, demande) -> bool:
    return is_in_groups(user, ROLE_VAL_BIO) or delegated(user, demande, "val_bio")
