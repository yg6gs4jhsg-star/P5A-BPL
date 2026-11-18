from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError

from app.accounts.auth import message
from app.accounts.roles import is_admin
from app.authorization.rules import can
from app.models import STATUS_LABELS, Account, Member, Project, db
from app.projects import bp
from app.projects.service import ProjectError, create_project

# --- Constantes ---
LABELS = {
    **STATUS_LABELS,
    "owner": "Owner", "collabo": "Collabo", "client": "Client",
    "encadrant": "Encadrant", "etudiant": "Étudiant",
}
ROLE_ORDER = ("owner", "collabo", "client", "encadrant")


@bp.app_template_filter("label")
def label(code):
    """Libellé en toutes lettres d'un statut ou d'un rôle."""
    return LABELS[code]


@bp.app_errorhandler(404)
def not_found(error):
    return message("Page introuvable.", 404)


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


@bp.route("/projets/<slug>")
def project_page(slug):
    project = Project.query.filter_by(slug=slug).first()
    readable = project is not None and can(current_user, "read_project", project)
    if not readable and not (project is not None and can(current_user, "view_published", project)):
        abort(404)  # on ne révèle pas qu'un projet non public existe
    return render_template(
        "project.html", project=project, readable=readable,
        show_invitations=can(current_user, "manage_members", project),
    )
