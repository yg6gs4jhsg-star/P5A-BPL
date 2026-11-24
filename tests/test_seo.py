"""Étape 8c : référencement, partage, images agrandies, heure de Paris."""
import re
from datetime import datetime

import pytest

from app.models import HistoryEvent, db, utcnow
from app.projects import content
from app.projects.service import add_file, change_status, save_draft
from tests.conftest import log_in
from tests.test_content import PNG, versions
from tests.test_public import make, people  # noqa: F401  (fixture des comptes)

SITE = "http://localhost:8000"


def meta(text, name):
    found = re.search(rf'<meta (?:name|property)="{name}" content="([^"]*)">', text)
    return found.group(1) if found else None


def public_project(people, title="Drone", image=False):
    project = make(people, title, published=False, resume="Un drone qui vole tout seul.")
    if image:
        photo = add_file(people["owner"], project, "photo.png", PNG)
        save_draft(people["owner"], project, {"resume": f"Il vole. ![photo](/fichiers/{photo.uuid})"},
                   versions(project))
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    return project


PAGES = ["/", "/projets", "/informations", "/projets/drone", "/projets/drone/detail"]


def test_each_public_page_has_own_title_description_and_full_addresses(client, people):
    public_project(people)
    titles = set()
    for url in PAGES:
        text = client.get(url).text
        title = re.search(r"<title>(.*)</title>", text).group(1)
        titles.add(title)
        assert '<html lang="fr">' in text and meta(text, "description")
        assert f'<link rel="canonical" href="{SITE}{url}">' in text
        assert meta(text, "og:title") == title and meta(text, "og:url") == SITE + url
        assert meta(text, "og:description") == meta(text, "description") and meta(text, "og:type")
        assert 'name="robots"' not in text
    assert len(titles) == len(PAGES)


def test_project_description_is_title_and_start_of_presentation(client, people):
    public_project(people)
    text = client.get("/projets/drone").text
    assert meta(text, "description") == "Drone : Un drone qui vole tout seul."
    assert meta(text, "og:type") == "article"


def test_og_image_only_with_published_image(client, people):
    public_project(people, "Drone")
    assert meta(client.get("/projets/drone").text, "og:image") is None
    project = public_project(people, "Robot", image=True)
    image = meta(client.get("/projets/robot").text, "og:image")
    assert image == f"{SITE}/fichiers/{project.files[0].uuid}"


def test_robots_txt(client):
    response = client.get("/robots.txt")
    assert response.mimetype == "text/plain"
    for path in ("/mon-espace", "/login", "/logout", "/auth"):
        assert f"Disallow: {path}\n" in response.text
    assert f"Sitemap: {SITE}/sitemap.xml" in response.text and "User-agent: *" in response.text


def test_sitemap_lists_only_public_projects(client, people):
    public_project(people, "Publié")
    make(people, "Brouillon", published=False)
    retired = public_project(people, "Retiré")
    change_status(people["encadrant"], retired, "unpublish")
    trashed = public_project(people, "Corbeille")
    trashed.deleted_at = utcnow()
    db.session.commit()
    response = client.get("/sitemap.xml")
    assert response.mimetype == "application/xml"
    urls = re.findall(r"<loc>(.*)</loc>", response.text)
    assert urls == [f"{SITE}/", f"{SITE}/projets", f"{SITE}/informations", f"{SITE}/projets/publie"]


def test_noindex_on_private_pages(client, people):
    public_project(people)
    log_in(client, people["owner"])
    for url in ("/mon-espace", "/projets/drone"):  # Mon espace, et la page de gestion pour l'équipe
        assert '<meta name="robots" content="noindex">' in client.get(url).text


def test_share_links_on_public_page_only(client, people):
    public_project(people)
    text = client.get("/projets/drone").text
    assert ('href="https://www.linkedin.com/sharing/share-offsite/?url=http%3A%2F%2Flocalhost%3A8000%2Fprojets%2Fdrone"'
            ' target="_blank" rel="noopener">') in text and "Partager sur LinkedIn</a>" in text
    assert f'data-copy="{SITE}/projets/drone">' in text and "Copier le lien</button>" in text and "/static/share.js" in text
    log_in(client, people["owner"])
    assert "LinkedIn" not in client.get("/projets/drone").text  # page de gestion


def test_no_share_on_non_public_project(client, people):
    make(people, "Brouillon", published=False)
    assert client.get("/projets/brouillon").status_code == 404
    log_in(client, people["owner"])
    text = client.get("/projets/brouillon").text
    assert "LinkedIn" not in text and "Copier le lien" not in text and "share.js" not in text


def test_images_enlarged_on_public_pages_only(client, people):
    project = public_project(people, image=True)
    uuid = project.files[0].uuid
    link = f'<a href="/fichiers/{uuid}"><img alt="photo" src="/fichiers/{uuid}"></a>'
    assert link in client.get("/projets/drone").text
    assert "<a href" not in content.render(f"![photo](/fichiers/{uuid})")  # aperçu et éditeur
    assert "<script" not in content.render("![x](/fichiers/a) <script>alert(1)</script>", enlarge=True)


@pytest.mark.parametrize("utc, shown", [(datetime(2026, 7, 14, 12, 0), "14/07/2026 14:00"),   # été : UTC+2
                                        (datetime(2026, 1, 15, 12, 0), "15/01/2026 13:00")])  # hiver : UTC+1
def test_dates_shown_in_paris_time(client, people, utc, shown):
    project = make(people, "Drone", published=False)
    db.session.add(HistoryEvent(project=project, new_status="brouillon", created_at=utc, message="Repère"))
    db.session.commit()
    log_in(client, people["owner"])
    text = client.get("/projets/drone").text
    assert f"<td>{shown}</td>" in text and "Date (heure de Paris)" in text and "UTC" not in text
