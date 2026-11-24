"""Étape 8d : ce qui, dans la mise en page des pages publiques, dépend de la logique."""
import re

import pytest

from app.models import Theme, db
from app.projects import pages
from app.projects.service import add_file, change_status, plain, save_draft
from tests.conftest import log_in
from tests.test_content import PNG, versions
from tests.test_public import make, people  # noqa: F401  (fixture des comptes)


def card_of(text, title):
    return next(card for card in text.split('<article class="carte">')[1:] if title in card)


def test_card_without_image_has_color_background(client, people):
    make(people, "Sans image")
    card = card_of(client.get("/projets").text, "Sans image")
    assert '<div class="carte-photo"></div>' in card


def test_card_shows_first_published_image(client, people):
    project = make(people, "Avec image", published=False)
    first, second = (add_file(people["owner"], project, name, PNG) for name in ("a.png", "b.png"))
    save_draft(people["owner"], project, {"resume": "Texte"}, versions(project))
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    card = card_of(client.get("/").text, "Avec image")
    assert f'<img src="/fichiers/{first.uuid}" alt="" loading="lazy">' in card and second.uuid not in card


def test_same_theme_always_same_color(client, people):
    assert pages.theme_color("Robotique") == pages.theme_color("Robotique") in pages.THEME_COLORS
    robotics = Theme(name="Robotique", normalized_name=plain("Robotique"))
    db.session.add(robotics)
    db.session.commit()
    make(people, "Robot", theme=robotics)
    make(people, "Bras", theme=robotics)
    pill = f'<span class="pastille" style="background: {pages.theme_color("Robotique")}">Robotique</span>'
    assert client.get("/projets").text.count(pill) == 2


def test_information_page_has_four_steps(client):
    text = client.get("/informations").text
    steps = text.split('<ol class="etapes">')[1].split("</ol>")[0]
    assert steps.count("<li>") == 4 and "compte Microsoft de l'EPF" in steps and "visible par tout le monde" in steps
    assert "Qui peut faire quoi" in text


@pytest.mark.parametrize("contact, shown", [("", False), ("Etienne Gibaud, campus de Montpellier", True)])
def test_contact_block_only_when_filled(client, monkeypatch, contact, shown):
    monkeypatch.setattr(pages, "CONTACT", contact)
    text = client.get("/informations").text
    assert ("<h2>Contact</h2>" in text) is shown and (contact in text if shown else True)


def test_connected_pages_still_respond(client, people):
    make(people, "Drone", published=False)
    log_in(client, people["owner"])
    for url in ("/mon-espace", "/projets/drone", "/projets/drone/editer"):
        assert client.get(url).status_code == 200


# Étape 8e : pages connectées.
def test_one_pale_pill_color_per_status():
    from pathlib import Path
    from app.models import STATUSES
    css = (Path(pages.__file__).parents[1] / "static" / "style.css").read_text()
    backgrounds = {re.search(rf"\.statut-{status} {{ background: (var\(--[a-z-]+\))", css).group(1) for status in STATUSES}
    assert len(backgrounds) == len(STATUSES)  # une couleur différente par statut
    assert set(pages.STATUS_HINTS) == set(STATUSES)  # une phrase de bandeau par statut


def sections(text):
    """Titres des sections de Mon espace et titres des projets qu'elles contiennent."""
    found = {}
    for part in text.split("<h2>")[1:]:
        title = part.split("<", 1)[0].strip()
        found[title] = re.findall(r'<(?:strong|h3><a [^>]*)>([^<]+)<', part.split("<h2>")[0])
    return found


@pytest.fixture
def space(people):
    from app.projects.service import create_project, invite
    from tests.conftest import person
    people["client"] = person("Clara", "encadrant")
    draft = create_project(people["owner"], "Brouillon", people["encadrant"])
    invite(people["owner"], draft, "colin@epfedu.fr", "collabo")
    invite(people["owner"], draft, "clara@epf.fr", "client")
    reviewed = create_project(people["owner"], "Relecture", people["encadrant"])
    change_status(people["owner"], reviewed, "submit")
    make(people, "Publié")
    withdrawn = make(people, "Retiré")
    change_status(people["encadrant"], withdrawn, "unpublish")
    return people


@pytest.mark.parametrize("who, expected", [
    ("owner", {"À faire": ["Brouillon"], "Mes projets en cours": ["Brouillon", "Relecture"],
               "Mes projets validés": ["Publié", "Retiré"]}),
    ("collabo", {"À faire": ["Brouillon"], "Mes projets en cours": ["Brouillon"]}),
    ("client", {"Mes projets en cours": ["Brouillon"]}),
    ("encadrant", {"À relire": ["Relecture"], "Mes projets en cours": ["Brouillon", "Relecture"],
                   "Mes projets validés": ["Publié", "Retiré"]}),
])
def test_my_space_sections(client, space, who, expected):
    log_in(client, space[who])
    found = {title: sorted(set(names)) for title, names in sections(client.get("/mon-espace").text).items()
             if title != "Créer un projet"}
    assert found == {title: sorted(names) for title, names in expected.items()}


@pytest.mark.parametrize("who, shown", [("owner", True), ("collabo", False)])
def test_editor_submit_button_follows_rights(client, people, who, shown):
    from app.projects.service import create_project, invite
    project = create_project(people["owner"], "Drone", people["encadrant"])
    invite(people["owner"], project, "colin@epfedu.fr", "collabo")
    log_in(client, people[who])
    text = client.get("/projets/drone/editer").text
    assert ("<button>Soumettre à la relecture</button>" in text) is shown and 'form="editeur">Enregistrer' in text


def test_status_banner_on_management_page(client, people):
    project = make(people, "Drone", published=False)
    change_status(people["owner"], project, "submit")
    log_in(client, people["owner"])
    assert '<p class="bandeau-statut statut-en_relecture">En relecture : en attente de l&#39;encadrant.</p>' in \
        client.get("/projets/drone").text


def test_error_page_in_a_block(client):
    text = client.get("/projets/inconnu").text
    assert '<section class="bloc message">' in text and "Page introuvable." in text and "Retour à l'accueil" in text
