from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError

from app.accounts.auth import message
from app.accounts.roles import is_admin
from app.authorization.rules import can
from app.models import STATUS_LABELS, Account, Invitation, Member, Project, db
from app.projects import bp
from app.projects import service
from app.projects.service import TRANSITIONS, ProjectError, create_project

# --- Constantes ---
LABELS = {
    **STATUS_LABELS,
    "owner": "Owner", "collabo": "Collabo", "client": "Client",
    "encadrant": "Encadrant", "etudiant": "Étudiant",
}
ROLE_ORDER = ("owner", "collabo", "client", "encadrant")
# Action de la page projet -> (droit vérifié par can, message de confirmation).
ACTIONS = {
    "submit": ("submit", "Projet soumis à la relecture."),
    "request_changes": ("request_changes", "Modifications demandées."),
    "publish": ("publish", "Projet publié."),
    "unpublish": ("unpublish", "Projet retiré du site public."),
    "request_reedition": ("request_reedition", "Réédition demandée."),
    "accept_reedition": ("answer_reedition", "Réédition acceptée."),
    "refuse_reedition": ("answer_reedition", "Réédition refusée."),
    "delete": ("delete_project", "Projet mis à la corbeille."),
    "restore": ("restore_project", "Projet restauré."),
    "assign_supervisor": ("assign_supervisor", "Encadrant attribué."),
    "invite": ("manage_members", "Invitation enregistrée."),
    "remove_member": ("manage_members", "Membre retiré."),
    "cancel_invitation": ("manage_members", "Invitation annulée."),
    "transfer_ownership": ("transfer_ownership", "Rôle d'Owner transféré."),
}


@bp.app_template_filter("label")
def label(code):
    """Libellé en toutes lettres d'un statut ou d'un rôle."""
    return LABELS[code]


@bp.app_errorhandler(404)
def not_found(error):
    return message("Page introuvable.", 404)


@bp.app_errorhandler(403)
def forbidden(error):
    return message("Action non autorisée : vous n'avez pas ce droit, ou le statut du projet a changé.", 403)


@bp.app_errorhandler(CSRFError)
def csrf_expired(error):
    return message("Le formulaire a expiré. Rechargez la page et recommencez.", 400)


@bp.route("/")
def home():
    return render_template("home.html")


def my_projects(user):
    """Mes projets hors corbeille, classés par rôle."""
    by_role = {role: [] for role in ROLE_ORDER}
    for member in Member.query.filter_by(account_id=user.id).join(Project).filter(Project.deleted_at.is_(None)):
        by_role[member.role].append(member.project)
    by_role["encadrant"] = Project.query.filter_by(supervisor_id=user.id, deleted_at=None).all()
    return by_role


@bp.route("/mon-espace", methods=["GET", "POST"])
@login_required
def my_space():
    title, error, status = "", None, 200
    if request.method == "POST":
        title = request.form.get("title", "")
        supervisor_id = request.form.get("supervisor_id", type=int)
        try:
            project = create_project(current_user, title, db.session.get(Account, supervisor_id) if supervisor_id else None)
            return redirect(url_for("projects.project_page", slug=project.slug))
        except ProjectError as refusal:
            error, status = str(refusal), 400
    return render_template(
        "my_space.html",
        admin=is_admin(current_user.email),
        projects_by_role=my_projects(current_user),
        can_create=can(current_user, "create_project"),
        supervisors=Account.query.filter_by(base_role="encadrant").order_by(Account.name),
        title=title, error=error,
    ), status


def visible_project(slug):
    """Le projet et « lisible ou non » ; 404 s'il n'est ni lisible ni public pour la personne."""
    project = Project.query.filter_by(slug=slug).first()
    readable = project is not None and can(current_user, "read_project", project)
    if not readable and not (project is not None and can(current_user, "view_published", project)):
        abort(404)  # on ne révèle pas qu'un projet non public existe
    return project, readable


def allowed_actions(project):
    """Actions dont le bouton s'affiche : droit et statut ; supprimer ou restaurer selon la corbeille."""
    allowed = {action: can(current_user, right, project) for action, (right, _) in ACTIONS.items()}
    allowed["delete"] &= project.deleted_at is None
    allowed["restore"] &= project.deleted_at is not None
    return allowed


def show_project(project, readable, error=None, status=200):
    return render_template(
        "project.html", project=project, readable=readable, error=error,
        allowed=allowed_actions(project),
        supervisors=Account.query.filter_by(base_role="encadrant").order_by(Account.name),
    ), status


@bp.route("/projets/<slug>")
def project_page(slug):
    return show_project(*visible_project(slug))


def from_form(model, field):
    """L'objet dont l'identifiant est dans le formulaire, sinon ProjectError."""
    found = db.session.get(model, request.form.get(field, type=int) or 0)
    if found is None:
        raise ProjectError("Choix invalide : rechargez la page et recommencez.")
    return found


def run_action(action, user, project, form):
    """Appelle la fonction du service qui correspond au bouton."""
    if action in TRANSITIONS:
        return service.change_status(user, project, action, form.get("message"))
    if action == "delete":
        if not form.get("confirm"):
            raise ProjectError("Cochez la case pour confirmer la suppression.")
        return service.delete_project(user, project)
    if action == "restore":
        return service.restore_project(user, project)
    if action == "assign_supervisor":
        return service.assign_supervisor(user, project, from_form(Account, "account_id"))
    if action == "invite":
        return service.invite(user, project, form.get("email"), form.get("role"))
    if action == "remove_member":
        return service.remove_member(user, project, from_form(Account, "account_id"))
    if action == "cancel_invitation":
        return service.cancel_invitation(user, project, from_form(Invitation, "invitation_id"))
    return service.transfer_ownership(user, project, from_form(Account, "account_id"))


@bp.route("/projets/<slug>/<action>", methods=["POST"])
def project_action(slug, action):
    if action not in ACTIONS:
        abort(404)
    project, readable = visible_project(slug)
    right, confirmation = ACTIONS[action]
    if not can(current_user, right, project):
        abort(403)  # le serveur vérifie toujours, même si le bouton n'est pas affiché
    try:
        run_action(action, current_user, project, request.form)
    except ProjectError as refusal:
        return show_project(project, readable, str(refusal), 400)
    flash(confirmation)
    return redirect(url_for("projects.project_page", slug=project.slug))
