from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError

from app.accounts.auth import message
from app.accounts.roles import is_admin
from app.authorization.rules import can
from app.models import STATUS_LABELS, Account, File, Invitation, Member, Project, Theme, db
from app.projects import bp, content, service
from app.projects.service import TRANSITIONS, ProjectError, create_project

# --- Constantes ---
LABELS = {
    **STATUS_LABELS,
    "owner": "Owner", "collabo": "Collaborateur", "client": "Client",
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


@bp.app_errorhandler(413)
def too_large(error):
    return message("Fichier trop lourd.", 413)


@bp.app_errorhandler(CSRFError)
def csrf_expired(error):
    return message("Le formulaire a expiré. Rechargez la page et recommencez.", 400)


@bp.route("/")
def home():
    return render_template("home.html")


def offered_themes(current=()):
    """Thèmes proposés en cases à cocher : les actifs, et ceux que le projet a déjà."""
    return sorted({*Theme.query.filter_by(active=True), *current}, key=lambda theme: theme.normalized_name)


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
    checked = request.form.getlist("theme_ids", type=int)
    if request.method == "POST":
        title = request.form.get("title", "")
        supervisor_id = request.form.get("supervisor_id", type=int)
        try:
            supervisor = db.session.get(Account, supervisor_id) if supervisor_id else None
            project = create_project(current_user, title, supervisor, checked, request.form.get("new_theme", ""))
            return redirect(url_for("projects.project_page", slug=project.slug))
        except ProjectError as refusal:
            error, status = str(refusal), 400
    return render_template(
        "my_space.html",
        admin=is_admin(current_user.email),
        projects_by_role=my_projects(current_user),
        can_create=can(current_user, "create_project"),
        supervisors=Account.query.filter_by(base_role="encadrant").order_by(Account.name),
        themes=offered_themes(), checked=checked, title=title, error=error,
    ), status


def visible_project(slug):
    """Le projet et « lisible ou non » ; 404 s'il n'est ni lisible ni public pour la personne."""
    project = Project.query.filter_by(slug=slug).first() or abort(404)
    readable = can(current_user, "read_project", project)
    if not readable and not can(current_user, "view_published", project):
        abort(404)  # on ne révèle pas qu'un projet non public existe
    return project, readable


def allowed_actions(project):
    """Actions dont le bouton s'affiche : droit et statut ; supprimer ou restaurer selon la corbeille."""
    allowed = {action: can(current_user, right, project) for action, (right, _) in ACTIONS.items()}
    allowed["delete"] &= project.deleted_at is None
    allowed["restore"] &= project.deleted_at is not None
    return allowed


def show_project(project, readable, error=None, status=200):
    # L'équipe voit le brouillon ; le public voit la dernière version validée.
    folder = "draft" if readable else "published"
    texts = {section: content.render(content.read_section(project, folder, section)) for section in content.SECTIONS}
    return render_template(
        "project.html", project=project, readable=readable, error=error, texts=texts,
        client=content.read_client(project, folder),
        sections=content.SECTIONS, can_edit=can(current_user, "edit_draft", project),
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


def editable_project(slug):
    """Projet modifiable : 404 s'il n'est pas visible, 403 sans le droit ou hors brouillon."""
    project, _ = visible_project(slug)
    if not can(current_user, "edit_draft", project):
        abort(403)
    return project


def show_editor(project, texts=None, versions=None, client=None, checked=None, preview=False, error=None, status=200):
    """Éditeur ; sans textes donnés, ceux du disque et leurs empreintes d'ouverture."""
    if texts is None:
        texts = {s: content.read_section(project, "draft", s) for s in content.SECTIONS}
        versions = {s: content.fingerprint(t) for s, t in texts.items()}
    return render_template(
        "editor.html", project=project, sections=content.SECTIONS, texts=texts, versions=versions,
        client=client or content.read_client(project, "draft"),
        images=[file for file in project.files if file.mime_type.startswith("image/")],
        themes=offered_themes(project.themes),
        checked=checked if checked is not None else [theme.id for theme in project.themes],
        previews={s: content.render(t) for s, t in texts.items()} if preview else None, error=error,
    ), status


@bp.route("/projets/<slug>/editer", methods=["GET", "POST"])
@login_required
def edit_draft(slug):
    project = editable_project(slug)
    if request.method == "GET":
        return show_editor(project)
    texts = {s: request.form.get(s, "").replace("\r\n", "\n") for s in content.SECTIONS}
    versions = {s: request.form.get(f"version_{s}") for s in content.SECTIONS}
    client = {"name": request.form.get("client_name", ""), "logo": request.form.get("client_logo") or None}
    checked = request.form.getlist("theme_ids", type=int)
    if request.form.get("preview"):
        return show_editor(project, texts, versions, client, checked, preview=True)
    try:
        logo = File.query.filter_by(uuid=client["logo"]).first() if client["logo"] else None
        service.save_draft(current_user, project, texts, versions, client["name"], logo, checked,
                           request.form.get("new_theme", ""))
    except ProjectError as refusal:
        return show_editor(project, texts, versions, client, checked, error=str(refusal), status=409)
    flash("Brouillon enregistré.")
    return redirect(url_for("projects.edit_draft", slug=slug))


@bp.route("/projets/<slug>/apercu", methods=["POST"])
def preview(slug):
    """Fragment HTML de l'aperçu en direct (HTMX) : même rendu nettoyé que la page publique."""
    editable_project(slug)
    return content.render(next((request.form[s] for s in content.SECTIONS if s in request.form), ""))


@bp.route("/projets/<slug>/fichiers", methods=["POST"])
@login_required
def upload_file(slug):
    project = editable_project(slug)
    upload = request.files.get("file")
    try:
        if not upload or not upload.filename:
            raise ProjectError("Choisissez un fichier.")
        service.add_file(current_user, project, upload.filename, upload.read())
    except ProjectError as refusal:
        return show_editor(project, error=str(refusal), status=400)
    flash("Fichier ajouté.")
    return redirect(url_for("projects.edit_draft", slug=slug))


@bp.route("/projets/<slug>/fichiers/supprimer", methods=["POST"])
@login_required
def remove_file(slug):
    project = editable_project(slug)
    try:
        service.delete_file(current_user, project, from_form(File, "file_id"))
    except ProjectError as refusal:
        return show_editor(project, error=str(refusal), status=400)
    flash("Fichier supprimé.")
    return redirect(url_for("projects.edit_draft", slug=slug))


@bp.route("/fichiers/<file_uuid>")
def download_file(file_uuid):
    """Mêmes droits que la page du projet ; le public ne voit que le logo et les fichiers de la version validée."""
    stored = File.query.filter_by(uuid=file_uuid).first() or abort(404)
    project, readable = visible_project(stored.project.slug)
    if not readable and not content.is_published_file(project, file_uuid):
        abort(404)
    return send_file(content.file_path(project, file_uuid), mimetype=stored.mime_type,
                     download_name=stored.original_name)
