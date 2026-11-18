from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import Account, HistoryEvent, Invitation, Member, Project, db, utcnow


def add(*objects):
    db.session.add_all(objects)
    db.session.commit()
    return objects if len(objects) > 1 else objects[0]


def account(n=1, role="etudiant"):
    return Account(oid=f"oid-{n}", email=f"p{n}@epfedu.fr", name=f"Personne {n}", base_role=role)


def project(slug="drone"):
    return Project(slug=slug, title="Drone")


def test_project_defaults(app):
    p = add(project())
    assert p.status == "brouillon"
    assert len(p.uuid) == 36
    assert p.is_featured is False
    assert p.deleted_at is None and p.first_published_at is None
    assert p.created_at and p.updated_at


def test_supervisor_can_be_empty(app):
    assert add(project()).supervisor is None


def test_unknown_status_refused(app):
    db.session.add(Project(slug="x", title="X", status="inconnu"))
    with pytest.raises(StatementError):
        db.session.commit()


def test_unknown_base_role_refused(app):
    db.session.add(account(role="admin"))
    with pytest.raises(StatementError):
        db.session.commit()


@pytest.mark.parametrize("duplicate", [
    lambda: (account(1), Account(oid="oid-1", email="autre@epfedu.fr", name="A", base_role="etudiant")),
    lambda: (account(1), Account(oid="autre", email="p1@epfedu.fr", name="A", base_role="etudiant")),
    lambda: (project("drone"), project("drone")),
], ids=["oid", "adresse", "adresse_projet"])
def test_duplicates_refused(app, duplicate):
    db.session.add_all(duplicate())
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_same_person_once_per_project(app):
    p, a = add(project(), account())
    db.session.add_all([Member(project=p, account=a, role="owner"), Member(project=p, account=a, role="collabo")])
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_same_email_invited_once_per_project(app):
    p = add(project())
    db.session.add_all([Invitation(project=p, email="x@epfedu.fr", role="client"),
                        Invitation(project=p, email="x@epfedu.fr", role="collabo")])
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_invitation_expires_after_30_days(app):
    before = utcnow()
    invitation = add(Invitation(project=project(), email="x@epfedu.fr", role="client"))
    assert before + timedelta(days=30) <= invitation.expires_at <= utcnow() + timedelta(days=30)


def test_history_in_chronological_order(app):
    p = add(project())
    now = utcnow()
    add(HistoryEvent(project=p, new_status="en_relecture", created_at=now),
        HistoryEvent(project=p, new_status="brouillon", created_at=now - timedelta(hours=1)))
    db.session.expire_all()
    assert [e.new_status for e in db.session.get(Project, p.id).history] == ["brouillon", "en_relecture"]


def test_project_deletion_cascades(app):
    p, a = add(project(), account())
    add(Member(project=p, account=a, role="owner"),
        Invitation(project=p, email="x@epfedu.fr", role="client"),
        HistoryEvent(project=p, author=a, new_status="brouillon"))
    db.session.delete(p)
    db.session.commit()
    assert Member.query.count() == Invitation.query.count() == HistoryEvent.query.count() == 0
    assert Account.query.count() == 1
