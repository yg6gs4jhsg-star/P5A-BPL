from markupsafe import escape

import pytest

from app import create_app
from app.models import Account, Invitation, Member, Project, db
from app.projects.service import change_status, create_project, invite
from tests.conftest import log_in, person

URL = "/projets/drone/"


@pytest.fixture
def people(app):
    return {
        "owner": person("owner"),
        "collabo": person("collabo"),
        "client": person("client", "encadrant"),
        "encadrant": person("encadrant", "encadrant"),
        "autre": person("autre", "encadrant"),
        "admin": person("admin", "encadrant", admin=True),
        "exterieur": person("exterieur"),
    }


@pytest.fixture
def project(people):
    project = create_project(people["owner"], "Drone", people["encadrant"])
    invite(people["owner"], project, "collabo@epfedu.fr", "collabo")
    invite(people["owner"], project, "client@epf.fr", "client")
    return project


def post(client, people, who, action, **data):
    log_in(client, people[who])
    return client.post(URL + action, data=data)


def move(project, people, *actions):
    for who, action in actions:
        change_status(people[who], project, action)


SUBMITTED = [("owner", "submit")]
PUBLISHED = SUBMITTED + [("encadrant", "publish")]
REEDITION = PUBLISHED + [("owner", "request_reedition")]

# Action -> (qui la fait, étapes avant, statut attendu après).
STATUS_ACTIONS = {
    "submit": ("owner", [], "en_relecture"),
    "request_changes": ("encadrant", SUBMITTED, "brouillon"),
    "publish": ("admin", SUBMITTED, "publie"),
    "unpublish": ("encadrant", PUBLISHED, "retire"),
    "request_reedition": ("owner", PUBLISHED, "reedition_demandee"),
    "accept_reedition": ("encadrant", REEDITION, "brouillon"),
    "refuse_reedition": ("admin", REEDITION, "publie"),
}


@pytest.mark.parametrize("action", STATUS_ACTIONS)
def test_status_action_by_right_role(client, people, project, action):
    who, before, expected = STATUS_ACTIONS[action]
    move(project, people, *before)
    response = post(client, people, who, action, message="Merci")
    assert response.location == URL.rstrip("/")
    db.session.expire_all()
    assert project.status == expected and project.history[-1].message == "Merci"
    assert "class=\"confirmation\"" in client.get(response.location).text


def test_republish(client, people, project):
    move(project, people, *PUBLISHED, ("encadrant", "unpublish"))
    post(client, people, "encadrant", "publish")
    db.session.expire_all()
    assert project.status == "publie"


def test_member_actions(client, people, project):
    post(client, people, "owner", "invite", email="nouveau@epfedu.fr", role="client")
    invitation = Invitation.query.one()
    post(client, people, "owner", "cancel_invitation", invitation_id=invitation.id)
    assert Invitation.query.count() == 0
    post(client, people, "owner", "remove_member", account_id=people["client"].id)
    post(client, people, "owner", "transfer_ownership", account_id=people["collabo"].id)
    roles = {m.account.name: m.role for m in Member.query.all()}
    assert roles == {"owner": "collabo", "collabo": "owner"}


def test_assign_supervisor(client, people, project):
    post(client, people, "admin", "assign_supervisor", account_id=people["autre"].id)
    assert project.supervisor == people["autre"]


def test_delete_needs_confirmation_then_restore(client, people, project):
    response = post(client, people, "owner", "delete")
    assert response.status_code == 400 and "Cochez la case" in response.text
    post(client, people, "owner", "delete", confirm="on")
    assert project.deleted_at is not None
    assert client.get(URL.rstrip("/")).status_code == 404  # l'Owner ne le voit plus
    post(client, people, "admin", "restore")
    db.session.expire_all()
    assert project.deleted_at is None


def test_service_error_shown_on_page(client, people, project):
    response = post(client, people, "owner", "invite", email="x@gmail.com", role="client")
    assert response.status_code == 400 and "Adresse invalide" in response.text and "Drone" in response.text


def test_submit_without_supervisor_explained(client, people):
    create_project(people["owner"], "Seul")
    log_in(client, people["owner"])
    response = client.post("/projets/seul/submit")
    assert response.status_code == 400 and "attendez" in response.text


def test_invalid_choice_is_an_error_not_a_crash(client, people, project):
    response = post(client, people, "owner", "remove_member", account_id="abc")
    assert response.status_code == 400 and "Choix invalide" in response.text


@pytest.mark.parametrize("who, action", [
    ("collabo", "submit"), ("client", "submit"), ("encadrant", "submit"),
    ("owner", "publish"), ("collabo", "invite"), ("client", "invite"), ("encadrant", "invite"),
    ("owner", "assign_supervisor"), ("owner", "restore"), ("collabo", "delete"),
])
def test_wrong_role_gets_403(client, people, project, who, action):
    assert post(client, people, who, action).status_code == 403


def test_second_click_gets_403(client, people, project):
    post(client, people, "owner", "submit")
    assert post(client, people, "owner", "submit").status_code == 403


@pytest.mark.parametrize("who", ["autre", "exterieur"])
def test_no_access_gets_404(client, people, project, who):
    assert post(client, people, who, "submit").status_code == 404


def test_visitor_of_published_project_gets_403(client, people, project):
    move(project, people, *PUBLISHED)
    assert client.post(URL + "unpublish").status_code == 403
    assert post(client, people, "autre", "unpublish").status_code == 403


def test_anonymous_on_draft_gets_404(client, project):
    assert client.post(URL + "submit").status_code == 404


def test_unknown_action_is_404(client, people, project):
    assert post(client, people, "owner", "voler").status_code == 404


# Boutons visibles seulement pour les bons rôles et statuts.
BUTTONS = {
    "Soumettre à la relecture": "submit", "Demander des modifications": "request_changes",
    "Valider et publier": "publish", "Retirer du site public": "unpublish",
    "Demander une réédition": "request_reedition", "Accepter la réédition": "accept_reedition",
    "Refuser la réédition": "refuse_reedition", "Supprimer le projet": "delete",
    "Attribuer l'encadrant": "assign_supervisor", "Inviter": "invite",
    "Transférer le rôle d'Owner": "transfer_ownership",
}


@pytest.mark.parametrize("before, who, expected", [
    ([], "owner", {"submit", "delete", "invite", "transfer_ownership"}),
    ([], "collabo", set()),
    ([], "client", set()),
    ([], "encadrant", set()),
    ([], "admin", {"delete", "invite", "transfer_ownership", "assign_supervisor"}),
    (SUBMITTED, "owner", {"delete", "invite", "transfer_ownership"}),
    (SUBMITTED, "encadrant", {"request_changes", "publish"}),
    (PUBLISHED, "owner", {"request_reedition", "invite", "transfer_ownership"}),
    (PUBLISHED, "encadrant", {"unpublish"}),
    (REEDITION, "encadrant", {"accept_reedition", "refuse_reedition"}),
])
def test_buttons_by_role_and_status(client, people, project, before, who, expected):
    move(project, people, *before)
    log_in(client, people[who])
    text = client.get(URL.rstrip("/")).text
    shown = {action for label, action in BUTTONS.items() if f"<button>{escape(label)}</button>" in text}
    assert shown == expected


def test_republish_button_on_withdrawn_project(client, people, project):
    move(project, people, *PUBLISHED, ("encadrant", "unpublish"))
    log_in(client, people["encadrant"])
    text = client.get(URL.rstrip("/")).text
    assert "<button>Republier</button>" in text and "Valider et publier" not in text


def test_restore_button_only_on_deleted_project_for_admin(client, people, project):
    project.deleted_at = db.func.now()
    db.session.commit()
    log_in(client, people["admin"])
    text = client.get(URL.rstrip("/")).text
    assert "<button>Restaurer</button>" in text and "Supprimer le projet" not in text


def test_action_without_csrf_token_refused(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "CONTENT_DIR": str(tmp_path)})
    with app.app_context():
        db.create_all()
        owner = person("owner")
        create_project(owner, "Drone")
        client = app.test_client()
        log_in(client, owner)
        assert client.post(URL + "delete", data={"confirm": "on"}).status_code == 400
        assert Project.query.one().deleted_at is None
        db.session.remove()
        db.engine.dispose()


def test_full_journey(client, people):
    """Création, invitation d'un Collabo, soumission, publication, réédition demandée puis acceptée."""
    def as_(who):
        log_in(client, people[who])
        return client

    as_("owner").post("/mon-espace", data={"title": "Drone", "supervisor_id": people["encadrant"].id})
    as_("owner").post(URL + "invite", data={"email": "collabo@epfedu.fr", "role": "collabo"})
    as_("owner").post(URL + "submit")
    as_("encadrant").post(URL + "request_changes", data={"message": "Ajoutez des photos"})
    as_("owner").post(URL + "submit")
    as_("encadrant").post(URL + "publish")
    as_("owner").post(URL + "request_reedition")
    as_("encadrant").post(URL + "accept_reedition")
    project = Project.query.one()
    assert project.status == "brouillon" and project.first_published_at is not None
    assert {m.account.name for m in project.members} == {"owner", "collabo"}
    assert [e.new_status for e in project.history] == [
        "brouillon", "en_relecture", "brouillon", "en_relecture", "publie", "reedition_demandee", "brouillon"]
    assert client.get("/projets/drone").status_code == 200
    client.post("/logout")
    assert client.get("/projets/drone").status_code == 200  # l'ancienne version reste publique
    assert Account.query.count() == 7
