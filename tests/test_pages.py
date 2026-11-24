import re

import pytest

from app import create_app
from app.models import Project, db, utcnow
from app.projects.service import change_status, create_project, invite
from tests.conftest import log_in, person

VIEWERS = ("visiteur", "owner", "collabo", "client", "encadrant", "autre_encadrant", "admin", "exterieur")
READERS = {"owner", "collabo", "client", "encadrant", "admin"}


@pytest.fixture
def people(app):
    return {
        "visiteur": None,
        "owner": person("Olga"),
        "collabo": person("Colin"),
        "client": person("Clara", "encadrant"),
        "encadrant": person("Eric", "encadrant"),
        "autre_encadrant": person("Alain", "encadrant"),
        "admin": person("Adam", "encadrant", admin=True),
        "exterieur": person("Xavier"),
    }


@pytest.fixture
def project(people):
    project = create_project(people["owner"], "Drone autonome", people["encadrant"])
    invite(people["owner"], project, "colin@epfedu.fr", "collabo")
    invite(people["owner"], project, "clara@epf.fr", "client")
    invite(people["owner"], project, "pas.encore@epfedu.fr", "client")
    return project


def view(client, people, who, url):
    if people[who]:
        log_in(client, people[who])
    return client.get(url)


# Page d'un projet.
@pytest.mark.parametrize("who", VIEWERS)
def test_draft_page_by_role(client, people, project, who):
    response = view(client, people, who, "/projets/drone-autonome")
    if who not in READERS:
        assert response.status_code == 404 and "Page introuvable." in response.text
        return
    text = response.text
    assert response.status_code == 200
    assert "Drone autonome" in text and "Statut : Brouillon" in text and "Eric" in text
    assert "Colin · Collaborateur" in text and "Clara · Client" in text and "Olga · Owner" in text
    assert "Date (heure de Paris)" in text
    assert "colin@epfedu.fr" not in text and "olga@epfedu.fr" not in text  # jamais les adresses de l'équipe
    assert ("pas.encore@epfedu.fr" in text) is (who in ("owner", "admin"))  # invitations : manage_members


@pytest.mark.parametrize("who", ["visiteur", "autre_encadrant", "exterieur"])
def test_published_project_for_visitor(client, people, project, who):
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    text = view(client, people, who, "/projets/drone-autonome").text
    assert "Drone autonome" in text and "Eric" in text and "Olga · Owner" in text
    assert "Statut" not in text and "Historique" not in text and "pas.encore" not in text


def test_unknown_project_is_404(client):
    response = client.get("/projets/inconnu")
    assert response.status_code == 404 and "Page introuvable." in response.text


@pytest.mark.parametrize("who, status", [("admin", 200), ("owner", 404), ("visiteur", 404)])
def test_deleted_project(client, people, project, who, status):
    project.deleted_at = utcnow()
    db.session.commit()
    response = view(client, people, who, "/projets/drone-autonome")
    assert response.status_code == status
    assert ("Ce projet est à la corbeille." in response.text) is (status == 200)


# Mon espace.
def test_my_space_requires_login(client):
    assert client.get("/mon-espace").location.startswith("/login")


def test_my_space_lists_projects_by_role(client, people, project):
    deleted = create_project(people["owner"], "Vieux projet")
    deleted.deleted_at = utcnow()
    db.session.commit()
    text = view(client, people, "owner", "/mon-espace").text
    assert "<h1>Olga</h1>" in text and "olga@epfedu.fr · Étudiant" in text
    assert '<span class="pastille-pale role-owner">Owner</span>' in text and "Drone autonome</a>" in text
    assert '<span class="pastille-pale statut-brouillon">Brouillon</span>' in text
    assert "Vieux projet" not in text


@pytest.mark.parametrize("who, heading", [("collabo", "Collaborateur"), ("client", "Client"), ("encadrant", "Encadrant")])
def test_my_space_other_roles(client, people, project, who, heading):
    text = view(client, people, who, "/mon-espace").text
    assert f'<span class="pastille-pale role-{who}">{heading}</span>' in text and "Drone autonome" in text


def test_my_space_shows_admin(client, people):
    assert "adam@epf.fr · Encadrant · admin" in view(client, people, "admin", "/mon-espace").text


@pytest.mark.parametrize("who, has_form", [("exterieur", True), ("encadrant", False), ("admin", False)])
def test_create_form_only_for_students(client, people, who, has_form):
    assert ("Créer un projet" in view(client, people, who, "/mon-espace").text) is has_form


def test_create_project_from_form(client, people):
    log_in(client, people["owner"])
    response = client.post("/mon-espace", data={"title": "Robot", "supervisor_id": str(people["encadrant"].id)})
    assert response.location == "/projets/robot"
    assert Project.query.filter_by(slug="robot").one().supervisor == people["encadrant"]


def test_create_form_lists_supervisors_only(client, people):
    text = view(client, people, "owner", "/mon-espace").text
    assert "<option value=\"%d\">Eric</option>" % people["encadrant"].id in text
    assert ">Colin</option>" not in text


def test_create_project_error_keeps_title(client, people):
    log_in(client, people["owner"])
    response = client.post("/mon-espace", data={"title": "x" * 201})
    assert response.status_code == 400
    assert "Le titre est obligatoire" in response.text and 'value="' + "x" * 201 in response.text


def test_teacher_cannot_create_by_post(client, people):
    log_in(client, people["encadrant"])
    assert client.post("/mon-espace", data={"title": "Robot"}).status_code == 400
    assert Project.query.count() == 0


# Pages communes et sécurité.
def test_home_and_header(client):
    text = client.get("/").text
    assert "Se connecter" in text and "Mon espace" in text


def test_logout_is_a_post_form(client, people):
    log_in(client, people["owner"])
    assert "Se déconnecter" in client.get("/").text
    assert client.get("/logout").status_code == 405


def test_post_without_csrf_token_refused(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "CONTENT_DIR": str(tmp_path)})
    with app.app_context():
        db.create_all()
        response = app.test_client().post("/logout")
        assert response.status_code == 400 and "Le formulaire a expiré" in response.text
        db.session.remove()
        db.engine.dispose()


def test_word_collabo_never_shown(client, people, project):
    """On écrit « Collaborateur » : le mot abrégé n'apparaît sur aucune page principale."""
    pages = []
    for who in ("owner", "collabo", "admin"):
        log_in(client, people[who])
        pages += [client.get(url).text for url in ("/", "/mon-espace", "/projets/drone-autonome")]
    log_in(client, people["owner"])
    pages.append(client.get("/projets/drone-autonome/editer").text)
    pages.append(client.post("/projets/drone-autonome/invite", data={"email": "prof@epf.fr", "role": "collabo"}).text)
    pages.append(client.post("/projets/drone-autonome/transfer_ownership",
                             data={"account_id": people["client"].id}).text)
    visible = [re.sub(r"<[^>]+>", " ", page) for page in pages]  # texte lu à l'écran, sans les balises
    assert not any(re.search(r"collabo(?!rateur)", text, re.IGNORECASE) for text in visible)
    assert "Un Collaborateur doit être un étudiant." in visible[-2]
