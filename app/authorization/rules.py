from app.accounts.roles import is_admin
from app.models import Member

# --- Constantes ---
ALL = None  # tous les statuts


def is_public(project):
    """Visible du public : publié, réédition demandée, ou ancienne version encore en ligne. Jamais Retiré."""
    if project.status in ("publie", "reedition_demandee"):
        return True
    return project.status in ("brouillon", "en_relecture") and project.first_published_at is not None


# Action -> (rôles autorisés, statuts autorisés ou fonction qui le décide). Un seul rôle suffit.
# « owner_jamais_publie » : Owner d'un projet dont first_published_at est vide.
RULES = {
    "view_published": ({"visiteur"}, is_public),
    "read_project": ({"client", "collabo", "owner", "encadrant", "admin"}, ALL),
    "create_project": ({"etudiant"}, ALL),
    "manage_members": ({"owner", "admin"}, ALL),
    "edit_draft": ({"collabo", "owner", "encadrant", "admin"}, {"brouillon"}),
    "submit": ({"owner"}, {"brouillon"}),
    "request_changes": ({"encadrant", "admin"}, {"en_relecture"}),
    "publish": ({"encadrant", "admin"}, {"en_relecture", "retire"}),
    "unpublish": ({"encadrant", "admin"}, {"publie"}),
    "request_reedition": ({"owner"}, {"publie"}),
    "answer_reedition": ({"encadrant", "admin"}, {"reedition_demandee"}),
    "feature_project": ({"encadrant", "admin"}, {"publie"}),
    "comment": ({"client"}, ALL),
    "read_comments": ({"client", "collabo", "owner", "encadrant", "admin"}, ALL),
    "delete_project": ({"owner_jamais_publie", "admin"}, ALL),
    "restore_project": ({"admin"}, ALL),
    "transfer_ownership": ({"owner", "admin"}, ALL),
    "assign_supervisor": ({"admin"}, ALL),
    "admin_site": ({"admin"}, ALL),
}


def roles_of(user, project):
    """Tous les rôles de la personne, sur le site et dans CE projet ; ils se cumulent."""
    roles = {"visiteur"}
    if not getattr(user, "is_authenticated", False):
        return roles
    if user.base_role == "etudiant":
        roles.add("etudiant")
    if is_admin(user.email):
        roles.add("admin")
    if project is not None:
        member = Member.query.filter_by(project_id=project.id, account_id=user.id).first()
        if member:
            roles.add(member.role)
            if member.role == "owner" and project.first_published_at is None:
                roles.add("owner_jamais_publie")
        if project.supervisor_id == user.id:
            roles.add("encadrant")
    return roles


def can(user, action, project=None):
    """Oui ou non : la personne peut-elle faire cette action ? Action inconnue : KeyError."""
    allowed_roles, statuses = RULES[action]
    roles = roles_of(user, project)
    if project is not None and project.deleted_at is not None and "admin" not in roles:
        return False  # projet à la corbeille : introuvable sauf pour l'admin
    if not roles & allowed_roles:
        return False
    if project is None or statuses is ALL:
        return True
    return statuses(project) if callable(statuses) else project.status in statuses
