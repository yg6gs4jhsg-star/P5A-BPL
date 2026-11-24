"""Étape 8d : ce qui, dans la mise en page des pages publiques, dépend de la logique."""
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
