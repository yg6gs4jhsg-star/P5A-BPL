import click

from app.accounts import bp
from app.models import AdminEmail, db

# --- Constantes ---
STAFF_DOMAIN = "epf.fr"
STUDENT_DOMAIN = "epfedu.fr"
EXTERNAL_TEACHER_GROUP = "gg_O365e_Enseignant_Non_Permanent"
STUDENT_GROUP = "gg_O365e_Etudiant"


def normalize_email(email):
    """Adresse sans espaces autour ni majuscules."""
    return (email or "").strip().lower()


def domain_of(email):
    """Domaine exact après le « @ », ou None si l'adresse n'a pas de partie avant le « @ »."""
    local, at, domain = normalize_email(email).rpartition("@")
    return domain if at and local else None


def compute_base_role(email, groups):
    """Rôle de base depuis le compte Microsoft : « encadrant », « etudiant » ou None (refusé)."""
    domain, groups = domain_of(email), set(groups or ())
    if domain == STAFF_DOMAIN or (domain == STUDENT_DOMAIN and EXTERNAL_TEACHER_GROUP in groups):
        return "encadrant"
    if domain == STUDENT_DOMAIN and STUDENT_GROUP in groups:
        return "etudiant"
    return None


def is_admin(email):
    """Pouvoir admin, en plus du rôle de base : l'adresse est dans la liste blanche."""
    return db.session.query(AdminEmail.query.filter_by(email=normalize_email(email)).exists()).scalar()


@bp.cli.command("add-admin")
@click.argument("email")
def add_admin(email):
    """Ajoute une adresse à la liste blanche des admins (seul moyen de créer le premier admin)."""
    email = normalize_email(email)
    if "@" not in email:
        raise click.ClickException(f"Adresse invalide : {email}")
    if is_admin(email):
        raise click.ClickException(f"Déjà dans la liste blanche : {email}")
    db.session.add(AdminEmail(email=email))
    db.session.commit()
    click.echo(f"Admin ajouté : {email}")
