"""Étape 7 : badges, message obligatoire, projets phares, historique visible, publication de bout en bout."""
import pytest

from app.models import Project, db, utcnow
from app.projects import content
from app.projects.service import (
    ProjectError, add_file, change_status, create_project, invite, save_draft, set_featured,
)
from tests.conftest import log_in, person
from tests.test_content import PNG, versions


@pytest.fixture
def people(app):
    return {"owner": person("Olga"), "collabo": person("Colin"), "client": person("Clara", "encadrant"),
            "encadrant": person("Eric", "encadrant"), "autre": person("Alain", "encadrant"),
            "admin": person("Adam", "encadrant", admin=True), "exterieur": person("Xavier")}


@pytest.fixture
def project(people):
    project = create_project(people["owner"], "Drone", people["encadrant"])
    invite(people["owner"], project, "colin@epfedu.fr", "collabo")
    invite(people["owner"], project, "clara@epf.fr", "client")
    return project


def publish(project, people):
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")


def page(client, people, who, url):
    if who != "visiteur":
        log_in(client, people[who])
    return client.get(url)


# Badges « À faire » et « À relire ».
def test_badges_count(client, people, project):
    second = create_project(people["owner"], "Robot", people["encadrant"])
    third = create_project(people["owner"], "Serre", people["encadrant"])
    change_status(people["owner"], second, "submit")
    publish(third, people)
    change_status(people["owner"], third, "request_reedition")
    trashed = create_project(people["owner"], "Corbeille")
    trashed.deleted_at = utcnow()
    db.session.commit()
    assert 'À faire <span class="badge">1</span>' in page(client, people, "owner", "/mon-espace").text  # pas la corbeille
    assert 'À faire <span class="badge">1</span>' in page(client, people, "collabo", "/mon-espace").text
    assert 'À relire <span class="badge">2</span>' in page(client, people, "encadrant", "/mon-espace").text


@pytest.mark.parametrize("who", ["client", "autre", "admin"])
def test_no_badge_without_work(client, people, project, who):
    text = page(client, people, who, "/mon-espace").text
    assert "À faire" not in text and "À relire" not in text


# « Demander des modifications » : message obligatoire, gardé dans l'historique.
@pytest.mark.parametrize("message", [None, "", "   "])
def test_request_changes_needs_message(people, project, message):
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError, match="quoi corriger"):
        change_status(people["encadrant"], project, "request_changes", message)
    assert project.status == "en_relecture"


def test_request_changes_message_in_history(client, people, project):
    change_status(people["owner"], project, "submit")
    log_in(client, people["encadrant"])
    response = client.post("/projets/drone/request_changes", data={"message": ""})
    assert response.status_code == 400 and "quoi corriger" in response.text
    client.post("/projets/drone/request_changes", data={"message": "  Ajoutez des photos  "})
    assert project.history[-1].message == "Ajoutez des photos"
    assert "Ajoutez des photos" in page(client, people, "owner", "/projets/drone").text


# Projets phares.
@pytest.mark.parametrize("who", ["encadrant", "admin"])
def test_feature_and_unfeature(client, people, project, who):
    publish(project, people)
    log_in(client, people[who])
    assert "<button>Mettre en avant</button>" in client.get("/projets/drone").text
    client.post("/projets/drone/feature")
    assert db.session.get(Project, project.id).is_featured
    assert "<button>Retirer des phares</button>" in client.get("/projets/drone").text
    client.post("/projets/drone/unfeature")
    assert not db.session.get(Project, project.id).is_featured


@pytest.mark.parametrize("who", ["owner", "collabo", "client", "autre", "exterieur"])
def test_feature_refused(client, people, project, who):
    publish(project, people)
    log_in(client, people[who])
    assert "Mettre en avant" not in client.get("/projets/drone").text
    assert client.post("/projets/drone/feature").status_code == 403
    assert not project.is_featured


def test_feature_only_when_published(people, project):
    with pytest.raises(ProjectError, match="droit"):
        set_featured(people["admin"], project, True)


# Historique visible selon le rôle.
@pytest.mark.parametrize("who, visible", [("owner", True), ("collabo", True), ("client", True), ("encadrant", True),
                                          ("admin", True), ("visiteur", False), ("exterieur", False), ("autre", False)])
def test_history_visible_by_role(client, people, project, who, visible):
    publish(project, people)
    text = page(client, people, who, "/projets/drone").text
    assert ("Historique" in text) is visible
    assert ("En relecture → Publié" in text) is visible  # ancien et nouveau statut
    assert "@epf" not in text  # jamais d'adresse e-mail


# Publication de bout en bout.
def test_publication_copies_text_files_client_and_logo(client, people, project):
    photo = add_file(people["owner"], project, "photo.png", PNG)
    logo = add_file(people["owner"], project, "logo.png", PNG)
    save_draft(people["owner"], project, {"resume": f"Version 1 ![p](/fichiers/{photo.uuid})", "detail": "Détails"},
               versions(project), "Airbus", logo)
    publish(project, people)
    assert content.read_section(project, "published", "resume").startswith("Version 1")
    assert content.read_section(project, "published", "detail") == "Détails"
    assert content.read_client(project, "published") == {"name": "Airbus", "logo": logo.uuid}
    text = client.get("/projets/drone").text
    assert "Version 1" in text and "Airbus" in text
    for stored in (photo, logo):
        response = client.get(f"/fichiers/{stored.uuid}")
        assert response.status_code == 200
        response.close()


def test_reedition_withdrawal_and_republish(client, people, project):
    save_draft(people["owner"], project, {"resume": "Version 1"}, versions(project))
    publish(project, people)
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    save_draft(people["owner"], project, {"resume": "Version 2"}, versions(project))
    text = client.get("/projets/drone").text
    assert "Version 1" in text and "Version 2" not in text  # l'ancienne version reste en ligne
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    change_status(people["encadrant"], project, "unpublish")
    assert client.get("/projets/drone").status_code == 404  # retiré du site public
    change_status(people["admin"], project, "publish")
    assert "Version 2" in client.get("/projets/drone").text  # republié
