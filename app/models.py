import uuid
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, MetaData, UniqueConstraint

# --- Constantes ---
BASE_ROLES = ("etudiant", "encadrant")
STATUS_LABELS = {
    "brouillon": "Brouillon",
    "en_relecture": "En relecture",
    "publie": "Publié",
    "reedition_demandee": "Réédition demandée",
    "retire": "Retiré du site public",
}
STATUSES = tuple(STATUS_LABELS)
MEMBER_ROLES = ("owner", "collabo", "client")
INVITATION_ROLES = ("collabo", "client")
INVITATION_DAYS = 30
# Noms de contraintes fixes : les migrations restent identiques en SQLite et en MySQL.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING))


def utcnow():
    """Date UTC sans fuseau : SQLite et MySQL la stockent de la même façon."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def choice(values, name):
    """Colonne à valeurs fixes : une valeur inconnue est refusée avant l'écriture."""
    return Enum(*values, name=name, native_enum=False, create_constraint=True, validate_strings=True)


class Account(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    oid = db.Column(db.String(64), unique=True, nullable=False)  # identifiant Microsoft
    email = db.Column(db.String(254), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    base_role = db.Column(choice(BASE_ROLES, "base_role"), nullable=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    slug = db.Column(db.String(220), unique=True, nullable=False)  # adresse lisible
    title = db.Column(db.String(200), nullable=False)
    theme = db.Column(db.String(100))
    status = db.Column(choice(STATUSES, "status"), nullable=False, default="brouillon")
    supervisor_id = db.Column(db.ForeignKey("account.id", ondelete="SET NULL"))
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime)  # corbeille de 30 jours
    first_published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    supervisor = db.relationship("Account")
    members = db.relationship("Member", back_populates="project", cascade="all, delete-orphan")
    invitations = db.relationship("Invitation", back_populates="project", cascade="all, delete-orphan")
    history = db.relationship(
        "HistoryEvent", back_populates="project", cascade="all, delete-orphan",
        order_by="(HistoryEvent.created_at, HistoryEvent.id)",
    )


class Member(db.Model):
    __table_args__ = (UniqueConstraint("project_id", "account_id"),)
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    account_id = db.Column(db.ForeignKey("account.id"), nullable=False)
    role = db.Column(choice(MEMBER_ROLES, "member_role"), nullable=False)

    project = db.relationship("Project", back_populates="members")
    account = db.relationship("Account")


class Invitation(db.Model):
    __table_args__ = (UniqueConstraint("project_id", "email"),)
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    role = db.Column(choice(INVITATION_ROLES, "invitation_role"), nullable=False)
    expires_at = db.Column(
        db.DateTime, nullable=False, default=lambda: utcnow() + timedelta(days=INVITATION_DAYS)
    )

    project = db.relationship("Project", back_populates="invitations")


class HistoryEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    author_id = db.Column(db.ForeignKey("account.id", ondelete="SET NULL"))  # vide si compte supprimé
    old_status = db.Column(choice(STATUSES, "old_status"))  # vide à la création du projet
    new_status = db.Column(choice(STATUSES, "new_status"), nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship("Project", back_populates="history")
    author = db.relationship("Account")


class AdminEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=utcnow)
