import re
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from flask import current_app
from sqlalchemy import func

from app.authorization.rules import can
from app.models import HistoryEvent, Member, Project, db, utcnow

# --- Constantes ---
TITLE_MAX = 200
DEFAULT_SLUG = "projet"
CONTENT_SUBDIRS = ("draft", "published", "files")
# Action -> (droit vérifié par can, statuts de départ, statut d'arrivée). Voir § 3 du cahier des charges.
TRANSITIONS = {
    "submit": ("submit", {"brouillon"}, "en_relecture"),
    "request_changes": ("request_changes", {"en_relecture"}, "brouillon"),
    "publish": ("publish", {"en_relecture", "retire"}, "publie"),
    "unpublish": ("unpublish", {"publie"}, "retire"),
    "request_reedition": ("request_reedition", {"publie"}, "reedition_demandee"),
    "accept_reedition": ("answer_reedition", {"reedition_demandee"}, "brouillon"),
    "refuse_reedition": ("answer_reedition", {"reedition_demandee"}, "publie"),
}


class ProjectError(Exception):
    """Action refusée ; le message, en français, s'affiche tel quel."""


def require(user, action, project=None):
    if not can(user, action, project):
        raise ProjectError("Vous n'avez pas le droit de faire cette action.")


def require_supervisor_role(account):
    if account.base_role != "encadrant":
        raise ProjectError("L'encadrant choisi n'est pas un enseignant.")


def unique_slug(title):
    """Adresse lisible sans accents, numérotée si elle existe déjà (corbeille comprise)."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if not any(char.isalpha() for char in base):
        base = DEFAULT_SLUG
    slug, number = base, 1
    while Project.query.filter_by(slug=slug).first():
        number += 1
        slug = f"{base}-{number}"
    return slug


@contextmanager
def transaction():
    """Tout ce qui est écrit dans le bloc est enregistré, ou rien."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def create_project(user, title, supervisor=None):
    require(user, "create_project")
    title = (title or "").strip()
    if not title or len(title) > TITLE_MAX:
        raise ProjectError(f"Le titre est obligatoire et fait au plus {TITLE_MAX} caractères.")
    if supervisor is not None:
        require_supervisor_role(supervisor)
    project = Project(title=title, slug=unique_slug(title), supervisor=supervisor)
    with transaction():
        db.session.add_all([
            project,
            Member(project=project, account=user, role="owner"),
            HistoryEvent(project=project, author=user, new_status="brouillon"),
        ])
        db.session.flush()  # attribue l'UUID, nom du dossier
        for subdir in CONTENT_SUBDIRS:
            (Path(current_app.config["CONTENT_DIR"]) / "projects" / project.uuid / subdir).mkdir(parents=True)
    return project


def change_status(user, project, action, message=None):
    right, from_statuses, to_status = TRANSITIONS[action]
    old_status = project.status
    if old_status not in from_statuses:
        raise ProjectError("Le statut du projet a déjà changé : action impossible.")
    require(user, right, project)
    if action == "submit" and project.supervisor_id is None:
        raise ProjectError("Aucun encadrant n'est attribué : attendez son attribution pour soumettre.")
    values = {"status": to_status, "updated_at": utcnow()}
    if to_status == "publie":
        values["first_published_at"] = func.coalesce(Project.first_published_at, utcnow())
    with transaction():
        # Écriture conditionnelle : un second clic simultané ne trouve plus l'ancien statut.
        query = Project.query.filter_by(id=project.id, status=old_status)
        if not query.update(values, synchronize_session=False):
            raise ProjectError("Le statut du projet a déjà changé : action impossible.")
        db.session.add(HistoryEvent(project=project, author=user, old_status=old_status,
                                    new_status=to_status, message=message or None))
    db.session.refresh(project)


def assign_supervisor(user, project, supervisor):
    require(user, "assign_supervisor", project)
    require_supervisor_role(supervisor)
    with transaction():
        project.supervisor = supervisor


def delete_project(user, project):
    """Met le projet à la corbeille (30 jours) ; le statut ne change pas."""
    require(user, "delete_project", project)
    if project.deleted_at is not None:
        raise ProjectError("Ce projet est déjà à la corbeille.")
    with transaction():
        project.deleted_at = utcnow()
        db.session.add(HistoryEvent(project=project, author=user, old_status=project.status,
                                    new_status=project.status, message="Projet mis à la corbeille."))


def restore_project(user, project):
    require(user, "restore_project", project)
    if project.deleted_at is None:
        raise ProjectError("Ce projet n'est pas à la corbeille.")
    with transaction():
        project.deleted_at = None
