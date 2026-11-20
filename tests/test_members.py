from datetime import timedelta

import pytest

from app.accounts.auth import account_from_claims
from app.models import Invitation, Member, db, utcnow
from app.projects.service import (
    ProjectError, cancel_invitation, create_project, invite, remove_member, transfer_ownership,
)
from tests.conftest import TENANT, person


@pytest.fixture
def people(app):
    return {
        "owner": person("owner"),
        "eleve": person("eleve"),
        "prof": person("prof", "encadrant"),
        "admin": person("admin", "encadrant", admin=True),
    }


@pytest.fixture
def project(people):
    return create_project(people["owner"], "Drone", people["prof"])


def team(project):
    return {(m.account.name, m.role) for m in project.members}


def login(email, groups):
    return account_from_claims({"oid": f"oid-{email}", "tid": TENANT, "email": email, "name": email, "groups": groups})


# Invitations.
def test_invite_existing_account_joins_now(people, project):
    invite(people["owner"], project, " Eleve@EPFEDU.fr ", "collabo")
    assert ("eleve", "collabo") in team(project) and Invitation.query.count() == 0


def test_invite_unknown_address_creates_invitation(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "collabo")
    invitation = Invitation.query.one()
    assert (invitation.email, invitation.role) == ("nouveau@epfedu.fr", "collabo")
    assert invitation.expires_at > utcnow() + timedelta(days=29)


@pytest.mark.parametrize("email", ["owner@epfedu.fr", "eleve@epfedu.fr"])
def test_member_cannot_be_invited_again(people, project, email):
    invite(people["owner"], project, "eleve@epfedu.fr", "client")
    with pytest.raises(ProjectError, match="déjà partie"):
        invite(people["owner"], project, email, "collabo")


def test_pending_invitation_cannot_be_duplicated(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "client")
    with pytest.raises(ProjectError, match="déjà invitée"):
        invite(people["owner"], project, "nouveau@epfedu.fr", "collabo")


def test_expired_invitation_ignored_then_replaced(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "client")
    Invitation.query.one().expires_at = utcnow() - timedelta(days=1)
    db.session.commit()
    login("nouveau@epfedu.fr", ["gg_O365e_Etudiant"])
    assert len(project.members) == 1  # expirée : ignorée à la connexion
    invite(people["owner"], project, "autre@epfedu.fr", "collabo")
    invite(people["owner"], project, "inconnu@epfedu.fr", "client")
    Invitation.query.filter_by(email="inconnu@epfedu.fr").one().expires_at = utcnow() - timedelta(days=1)
    db.session.commit()
    invite(people["owner"], project, "inconnu@epfedu.fr", "collabo")
    replaced = Invitation.query.filter_by(email="inconnu@epfedu.fr").one()
    assert replaced.role == "collabo" and replaced.expires_at > utcnow()


@pytest.mark.parametrize("email", ["prof@epf.fr", "inconnu@epf.fr"])
def test_collabo_must_be_a_student(people, project, email):
    with pytest.raises(ProjectError, match="étudiant"):
        invite(people["owner"], project, email, "collabo")


@pytest.mark.parametrize("email", ["client@gmail.com", "x@epf.fr.autre.com", "epf.fr", ""])
def test_bad_address_refused(people, project, email):
    with pytest.raises(ProjectError, match="Adresse invalide"):
        invite(people["owner"], project, email, "client")


def test_client_can_be_any_epf_address(people, project):
    invite(people["owner"], project, "prof@epf.fr", "client")
    invite(people["owner"], project, "jousset@epf.fr", "client")
    assert ("prof", "client") in team(project) and Invitation.query.one().email == "jousset@epf.fr"


def test_unknown_role_refused(people, project):
    with pytest.raises(ProjectError):
        invite(people["owner"], project, "eleve@epfedu.fr", "owner")


@pytest.mark.parametrize("role", ["collabo", "client", "prof"])
def test_only_owner_and_admin_manage_members(people, project, role):
    invite(people["owner"], project, "eleve@epfedu.fr", "collabo")
    invite(people["owner"], project, "client@epfedu.fr", "client")
    login("client@epfedu.fr", ["gg_O365e_Etudiant"])
    actor = {"collabo": people["eleve"], "client": Member.query.filter_by(role="client").one().account,
             "prof": people["prof"]}[role]
    with pytest.raises(ProjectError, match="droit"):
        invite(actor, project, "x@epfedu.fr", "client")
    with pytest.raises(ProjectError, match="droit"):
        remove_member(actor, project, people["eleve"])
    invite(people["admin"], project, "x@epfedu.fr", "client")


# Retrait, annulation.
def test_remove_member(people, project):
    invite(people["owner"], project, "eleve@epfedu.fr", "collabo")
    remove_member(people["owner"], project, people["eleve"])
    assert team(project) == {("owner", "owner")}


def test_owner_cannot_be_removed(people, project):
    with pytest.raises(ProjectError, match="Owner"):
        remove_member(people["admin"], project, people["owner"])


def test_cancel_invitation(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "client")
    cancel_invitation(people["owner"], project, Invitation.query.one())
    assert Invitation.query.count() == 0


def test_cancel_invitation_of_another_project_refused(people, project):
    other = create_project(people["eleve"], "Autre")
    invite(people["eleve"], other, "nouveau@epfedu.fr", "client")
    with pytest.raises(ProjectError):
        cancel_invitation(people["owner"], project, Invitation.query.one())


# Transfert du rôle d'Owner.
@pytest.mark.parametrize("target", ["owner", "prof", "client"])
def test_transfer_refused_to_non_collabo(people, project, target):
    invite(people["owner"], project, "prof@epf.fr", "client")
    targets = {"owner": people["owner"], "prof": people["prof"], "client": people["prof"]}
    with pytest.raises(ProjectError, match="Collaborateur"):
        transfer_ownership(people["owner"], project, targets[target])


@pytest.mark.parametrize("actor", ["owner", "admin"])
def test_transfer_succeeds(people, project, actor):
    invite(people["owner"], project, "eleve@epfedu.fr", "collabo")
    transfer_ownership(people[actor], project, people["eleve"])
    assert team(project) == {("eleve", "owner"), ("owner", "collabo")}


def test_collabo_cannot_transfer(people, project):
    invite(people["owner"], project, "eleve@epfedu.fr", "collabo")
    with pytest.raises(ProjectError, match="droit"):
        transfer_ownership(people["eleve"], project, people["eleve"])


# Première connexion d'un invité.
def test_first_login_of_invited_student(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "collabo")
    account = login("Nouveau@epfedu.fr", ["gg_O365e_Etudiant"])
    assert ("Nouveau@epfedu.fr", "collabo") in team(project) and account.email == "nouveau@epfedu.fr"
    assert Invitation.query.count() == 0


def test_external_teacher_invited_as_collabo_stays_pending(people, project):
    invite(people["owner"], project, "externe@epfedu.fr", "collabo")
    login("externe@epfedu.fr", ["gg_O365e_Enseignant_Non_Permanent"])
    assert len(project.members) == 1 and Invitation.query.count() == 1


def test_external_teacher_invited_as_client_joins(people, project):
    invite(people["owner"], project, "externe@epfedu.fr", "client")
    login("externe@epfedu.fr", ["gg_O365e_Enseignant_Non_Permanent"])
    assert ("externe@epfedu.fr", "client") in team(project) and Invitation.query.count() == 0


def test_refused_login_keeps_invitation(people, project):
    invite(people["owner"], project, "nouveau@epfedu.fr", "client")
    assert login("nouveau@epfedu.fr", []) is None
    assert Invitation.query.count() == 1
