"""Étape 8a : accueil, liste des projets et page publique."""
from datetime import timedelta

import pytest

from app.models import Theme, db, utcnow
from app.projects.service import add_file, change_status, create_project, invite, plain, save_draft
from tests.conftest import log_in, person
from tests.test_content import PDF, PNG, versions


@pytest.fixture
def people(app):
    return {"owner": person("Olga"), "collabo": person("Colin"), "encadrant": person("Eric", "encadrant"),
            "exterieur": person("Xavier")}


def make(people, title, published=True, featured=False, days_ago=0, theme=None, resume="Présentation"):
    """Projet de test, publié il y a `days_ago` jours."""
    project = create_project(people["owner"], title, people["encadrant"])
    save_draft(people["owner"], project, {"resume": resume, "detail": f"Détail de {title}"}, versions(project),
               theme_ids=[theme.id] if theme else ())
    if published:
        change_status(people["owner"], project, "submit")
        change_status(people["encadrant"], project, "publish")
        project.first_published_at = utcnow() - timedelta(days=days_ago)
        project.is_featured = featured
        db.session.commit()
    return project


def section(text, title):
    """Le morceau de page qui suit un titre <h2>."""
    return text.split(f"<h2>{title}</h2>", 1)[1].split("<h2>", 1)[0] if f"<h2>{title}</h2>" in text else ""


# Accueil.
def test_home_headline_is_most_recent_and_featured_are_public(client, people):
    make(people, "Ancien phare", featured=True, days_ago=10)
    make(people, "Récent", days_ago=1)
    make(people, "Brouillon phare", published=False)
    retired = make(people, "Retiré phare", featured=True, days_ago=0)
    change_status(people["encadrant"], retired, "unpublish")
    text = client.get("/").text
    assert "Récent" in section(text, "Projet à la une") and "Ancien" not in section(text, "Projet à la une")
    assert "Ancien phare" in section(text, "Projets phares")
    assert "Retiré" not in text and "Brouillon phare" not in text
    assert retired.is_featured  # garde sa marque de phare
    assert 'href="/projets"' in text


def test_home_without_public_project(client, people):
    make(people, "Brouillon", published=False)
    text = client.get("/").text
    assert "Projet à la une" not in text and "Projets phares" not in text


def test_card_excerpt_is_plain_text_and_short(client, people):
    make(people, "Long", resume="## Objectifs\n\n**Gras** " + "mot " * 100 + "<script>alert(1)</script>")
    text = client.get("/projets").text
    assert "Objectifs Gras mot" in text and "<strong>" not in text and "<script" not in text and "alert" not in text
    excerpt = text.split("Objectifs Gras", 1)[1].split("</p>", 1)[0]
    assert len("Objectifs Gras" + excerpt) <= 200 and excerpt.endswith("…")


# Liste et filtre par thème.
def test_list_shows_only_public_projects_newest_first(client, people):
    make(people, "Premier", days_ago=5)
    make(people, "Second", days_ago=1)
    make(people, "Jamais publié", published=False)
    retired = make(people, "Retiré")
    change_status(people["encadrant"], retired, "unpublish")
    trashed = make(people, "Corbeille")
    trashed.deleted_at = utcnow()
    db.session.commit()
    text = client.get("/projets").text
    assert text.index("Second") < text.index("Premier")
    for hidden in ("Jamais publié", "Retiré", "Corbeille"):
        assert hidden not in text


def test_list_filter_by_theme(client, people):
    robotics = Theme(name="Robotique", normalized_name=plain("Robotique"))
    db.session.add(robotics)
    db.session.commit()
    make(people, "Robot", theme=robotics)
    make(people, "Serre")
    text = client.get(f"/projets?theme={robotics.id}").text
    assert "Robot" in text and "Serre" not in text and f'value="{robotics.id}" selected' in text
    text = client.get("/projets").text
    assert "Robot" in text and "Serre" in text and "Tous les thèmes" in text


# Page publique d'un projet.
def test_public_page_shows_published_version_during_reedition(client, people):
    project = make(people, "Drone", resume="Version publiée")
    invite(people["owner"], project, "colin@epfedu.fr", "collabo")
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    save_draft(people["owner"], project, {"resume": "Brouillon secret", "detail": "Détail secret"}, versions(project))
    for who in (None, "exterieur"):
        if who:
            log_in(client, people[who])
        text = client.get("/projets/drone").text
        assert "Version publiée" in text and "Brouillon secret" not in text
        assert "Eric" in text and "Olga · Owner" in text and "Colin · Collaborateur" in text
        assert "Voir la page détaillée" in text and "Détail de Drone" not in text  # le détail est sur l'autre page
        assert "@epf" not in text
        detail = client.get("/projets/drone/detail").text
        assert "Détail de Drone" in detail and "Détail secret" not in detail


def test_management_page_unchanged_for_team(client, people):
    make(people, "Drone")
    log_in(client, people["owner"])
    text = client.get("/projets/drone").text
    assert "Historique" in text and "Détail de Drone" in text and "Voir la page détaillée" not in text


@pytest.mark.parametrize("url", ["/projets/brouillon", "/projets/brouillon/detail", "/projets/inconnu/detail"])
def test_non_public_project_is_404(client, people, url):
    make(people, "Brouillon", published=False)
    assert client.get(url).status_code == 404


def test_detail_lists_published_files_with_video_player(client, people):
    project = make(people, "Drone", published=False)
    video = add_file(people["owner"], project, "film.mp4", b"\0\0\0\x18ftypmp42" + b"\0" * 20)
    doc = add_file(people["owner"], project, "rapport.pdf", PDF)
    hidden = add_file(people["owner"], project, "brouillon.png", PNG)
    save_draft(people["owner"], project, {"detail": f"[v](/fichiers/{video.uuid}) [d](/fichiers/{doc.uuid})"},
               versions(project))
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    text = client.get("/projets/drone/detail").text
    assert f'<video controls src="/fichiers/{video.uuid}">' in text and ">rapport.pdf</a>" in text
    assert "brouillon.png" not in text
    response = client.get(f"/fichiers/{doc.uuid}")
    assert response.status_code == 200
    response.close()
    assert client.get(f"/fichiers/{hidden.uuid}").status_code == 404  # fichier de brouillon refusé


def test_no_script_reaches_public_pages(client, people):
    make(people, "Drone", resume="<script>alert(1)</script> Bonjour")
    for url in ("/", "/projets", "/projets/drone", "/projets/drone/detail"):
        assert "<script" not in client.get(url).text and "alert(1)" not in client.get(url).text

