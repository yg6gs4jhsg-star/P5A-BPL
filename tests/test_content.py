import io
import struct
import zlib
from pathlib import Path

import pytest

from app import create_app
from app.models import File, Project, Theme, db
from app.projects import content
from app.projects.service import (
    ProjectError, add_file, change_status, create_project, delete_file, invite, plain, save_draft,
)
from tests.conftest import log_in, person

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = PNG_SIGNATURE + png_chunk(b"IHDR", b"\0" * 13) + png_chunk(b"eXIf", b"GPS 43.6N") + png_chunk(b"IEND", b"")
JPEG = b"\xff\xd8" + b"\xff\xe1\x00\x09ExifGPS" + b"\xff\xdb\x00\x04\x01\x02" + b"\xff\xda\x00\x02IMAGE\xff\xd9"
PDF = b"%PDF-1.7 contenu\n%%EOF\n"


def riff_chunk(kind, data):
    return kind + struct.pack("<I", len(data)) + data + b"\0" * (len(data) % 2)


WEBP_BODY = b"WEBP" + riff_chunk(b"VP8X", b"\x08" + b"\0" * 9) + riff_chunk(b"VP8 ", b"IMG") + riff_chunk(b"EXIF", b"GPS")
WEBP = b"RIFF" + struct.pack("<I", len(WEBP_BODY)) + WEBP_BODY


@pytest.fixture
def people(app):
    return {"owner": person("owner"), "collabo": person("collabo"), "client": person("client", "encadrant"),
            "encadrant": person("encadrant", "encadrant"), "exterieur": person("exterieur")}


@pytest.fixture
def project(people):
    project = create_project(people["owner"], "Drone", people["encadrant"])
    invite(people["owner"], project, "collabo@epfedu.fr", "collabo")
    invite(people["owner"], project, "client@epf.fr", "client")
    return project


def versions(project):
    return {s: content.fingerprint(content.read_section(project, "draft", s)) for s in content.SECTIONS}


def publish(project, people):
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")


# Rendu Markdown.
def test_markdown_is_cleaned():
    html = content.render("# Titre\n\n<script>alert(1)</script> [lien](javascript:alert(1)) **gras**")
    assert "<h1>Titre</h1>" in html and "<strong>gras</strong>" in html
    assert "<script" not in html and "javascript:" not in html


def test_only_uploaded_images_are_shown():
    html = content.render("![a](/fichiers/abc) ![b](https://ailleurs.com/x.png)")
    assert 'src="/fichiers/abc"' in html and "ailleurs.com" not in html


# Brouillon.
def test_save_and_read_draft(people, project):
    save_draft(people["collabo"], project, {"resume": "Bonjour", "detail": "Détails"}, versions(project))
    assert content.read_section(project, "draft", "resume") == "Bonjour"
    assert content.read_section(project, "published", "resume") == ""


def test_concurrent_edit_refused(people, project):
    opened = versions(project)
    save_draft(people["owner"], project, {"resume": "Version A"}, opened)
    with pytest.raises(ProjectError, match="a changé depuis votre ouverture"):
        save_draft(people["collabo"], project, {"resume": "Version B"}, opened)
    assert content.read_section(project, "draft", "resume") == "Version A"


@pytest.mark.parametrize("who", ["client", "exterieur"])
def test_edit_refused_without_right(people, project, who):
    with pytest.raises(ProjectError, match="droit"):
        save_draft(people[who], project, {"resume": "x"}, versions(project))


def test_draft_locked_after_submission(people, project):
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError):
        save_draft(people["owner"], project, {"resume": "x"}, versions(project))


def test_publish_copies_draft_and_old_version_stays_online(people, project):
    save_draft(people["owner"], project, {"resume": "Version 1"}, versions(project))
    publish(project, people)
    assert content.read_section(project, "published", "resume") == "Version 1"
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    save_draft(people["owner"], project, {"resume": "Version 2"}, versions(project))
    assert content.read_section(project, "published", "resume") == "Version 1"


# Fichiers.
def test_png_gps_removed(people, project):
    stored = add_file(people["owner"], project, "photo.png", PNG)
    data = content.file_path(project, stored.uuid).read_bytes()
    assert stored.mime_type == "image/png" and b"GPS" not in data and data.endswith(png_chunk(b"IEND", b""))
    assert stored.size == len(data) and len(stored.sha256) == 64


def test_jpeg_gps_removed(people, project):
    stored = add_file(people["owner"], project, "photo.jpg", JPEG)
    data = content.file_path(project, stored.uuid).read_bytes()
    assert b"GPS" not in data and data.startswith(b"\xff\xd8\xff\xdb") and data.endswith(b"IMAGE\xff\xd9")


def test_webp_gps_removed(people, project):
    stored = add_file(people["owner"], project, "photo.webp", WEBP)
    data = content.file_path(project, stored.uuid).read_bytes()
    assert stored.mime_type == "image/webp" and b"GPS" not in data and b"VP8 " in data
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8  # taille RIFF mise à jour
    assert data[20] & 0x08 == 0  # l'en-tête VP8X n'annonce plus d'EXIF


def test_allowed_types_come_from_settings(app, people, project):
    app.config["ALLOWED_FILE_TYPES"] = ["image/png"]
    with pytest.raises(ProjectError, match="Type de fichier refusé"):
        add_file(people["owner"], project, "doc.pdf", PDF)


def test_quick_presentation_prefilled(project):
    assert content.read_section(project, "draft", "resume") == "## Objectifs\n\n## Description\n\n## Réalisations\n"


def test_file_stored_under_random_name(people, project):
    stored = add_file(people["owner"], project, "../../danger.pdf", PDF)
    assert content.file_path(project, stored.uuid).read_bytes() == PDF
    assert stored.original_name == "../../danger.pdf"  # seulement en base, jamais comme chemin


def test_fake_image_refused(people, project):
    with pytest.raises(ProjectError, match="Type de fichier refusé"):
        add_file(people["owner"], project, "faux.jpg", b"<html>pas une image</html>")


def test_too_heavy_file_refused(app, people, project):
    app.config["MAX_FILE_MB"] = 0
    with pytest.raises(ProjectError, match="trop lourd"):
        add_file(people["owner"], project, "doc.pdf", PDF)
    assert File.query.count() == 0


def test_project_quota(app, people, project):
    add_file(people["owner"], project, "doc.pdf", PDF)
    app.config["MAX_PROJECT_MB"] = 0
    with pytest.raises(ProjectError, match="limite"):
        add_file(people["owner"], project, "doc2.pdf", PDF)


def test_video_detected(people, project):
    assert add_file(people["owner"], project, "film.mp4", b"\0\0\0\x18ftypmp42" + b"\0" * 20).mime_type == "video/mp4"


def test_client_cannot_add_file(people, project):
    with pytest.raises(ProjectError, match="droit"):
        add_file(people["client"], project, "doc.pdf", PDF)


# Pages.
def test_editor_page_and_save(client, people, project):
    log_in(client, people["collabo"])
    page = client.get("/projets/drone/editer")
    assert page.status_code == 200 and "Présentation rapide" in page.text
    data = {"resume": "**Bonjour**\r\nà tous", "detail": "", **{f"version_{s}": v for s, v in versions(project).items()}}
    assert client.post("/projets/drone/editer", data=data).location == "/projets/drone/editer"
    assert content.read_section(project, "draft", "resume") == "**Bonjour**\nà tous"
    assert "<strong>Bonjour</strong>" in client.get("/projets/drone").text


def test_preview_does_not_save(client, people, project):
    log_in(client, people["owner"])
    data = {"resume": "**Essai**", "preview": "1", **{f"version_{s}": v for s, v in versions(project).items()}}
    response = client.post("/projets/drone/editer", data=data)
    assert "<strong>Essai</strong>" in response.text
    assert content.read_section(project, "draft", "resume") == content.DEFAULT_TEXTS["resume"]


def test_conflict_keeps_typed_text(client, people, project):
    log_in(client, people["owner"])
    data = {"resume": "Mon texte", **{f"version_{s}": "ancienne" for s in content.SECTIONS}}
    response = client.post("/projets/drone/editer", data=data)
    assert response.status_code == 409 and "a changé depuis votre ouverture" in response.text
    assert "Mon texte" in response.text


@pytest.mark.parametrize("who, status", [("client", 403), ("exterieur", 404)])
def test_editor_refused(client, people, project, who, status):
    log_in(client, people[who])
    assert client.get("/projets/drone/editer").status_code == status


def test_edit_link_only_for_editors(client, people, project):
    log_in(client, people["client"])
    assert "Modifier le brouillon" not in client.get("/projets/drone").text
    log_in(client, people["collabo"])
    assert "Modifier le brouillon" in client.get("/projets/drone").text


def test_upload_and_download(client, people, project):
    log_in(client, people["owner"])
    response = client.post("/projets/drone/fichiers", data={"file": (io.BytesIO(PDF), "rapport.pdf")})
    assert response.location == "/projets/drone/editer"
    stored = File.query.one()
    assert f"[rapport.pdf](/fichiers/{stored.uuid})" in client.get("/projets/drone/editer").text
    download = client.get(f"/fichiers/{stored.uuid}")
    assert download.data == PDF and download.mimetype == "application/pdf"
    download.close()


def test_download_with_relative_content_dir(app, client, people, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app.config["CONTENT_DIR"] = "./content"
    project = create_project(people["owner"], "Relatif")
    stored = add_file(people["owner"], project, "doc.pdf", PDF)
    log_in(client, people["owner"])
    response = client.get(f"/fichiers/{stored.uuid}")
    assert response.data == PDF
    response.close()


def test_upload_error_shown(client, people, project):
    log_in(client, people["owner"])
    response = client.post("/projets/drone/fichiers", data={"file": (io.BytesIO(b"texte"), "x.jpg")})
    assert response.status_code == 400 and "Type de fichier refusé" in response.text


def test_public_sees_only_published_files(client, people, project):
    shown = add_file(people["owner"], project, "photo.png", PNG)
    hidden = add_file(people["owner"], project, "brouillon.pdf", PDF)
    save_draft(people["owner"], project, {"resume": f"![photo](/fichiers/{shown.uuid})"}, versions(project))
    assert client.get(f"/fichiers/{shown.uuid}").status_code == 404  # pas encore publié
    publish(project, people)
    response = client.get(f"/fichiers/{shown.uuid}")
    assert response.status_code == 200
    response.close()
    assert client.get(f"/fichiers/{hidden.uuid}").status_code == 404
    assert client.get("/fichiers/inconnu").status_code == 404
    assert f'src="/fichiers/{shown.uuid}"' in client.get("/projets/drone").text


def test_visitor_sees_published_version_not_draft(client, people, project):
    save_draft(people["owner"], project, {"resume": "Version publiée"}, versions(project))
    publish(project, people)
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    save_draft(people["owner"], project, {"resume": "Travail en cours"}, versions(project))
    text = client.get("/projets/drone").text
    assert "Version publiée" in text and "Travail en cours" not in text
    log_in(client, people["owner"])
    assert "Travail en cours" in client.get("/projets/drone").text
    db.session.remove()


# Suppression d'un fichier.
def test_delete_file(people, project):
    stored = add_file(people["collabo"], project, "doc.pdf", PDF)
    path = content.file_path(project, stored.uuid)
    delete_file(people["collabo"], project, stored)
    assert File.query.count() == 0 and not path.exists()


def test_delete_file_refused_outside_draft_or_without_right(people, project):
    stored = add_file(people["owner"], project, "doc.pdf", PDF)
    with pytest.raises(ProjectError, match="droit"):
        delete_file(people["client"], project, stored)
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError, match="droit"):
        delete_file(people["owner"], project, stored)


def test_file_of_published_version_cannot_be_deleted(people, project):
    stored = add_file(people["owner"], project, "photo.png", PNG)
    save_draft(people["owner"], project, {"resume": f"![p](/fichiers/{stored.uuid})"}, versions(project))
    publish(project, people)
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    with pytest.raises(ProjectError, match="version publiée"):
        delete_file(people["owner"], project, stored)


def test_file_of_another_project_refused(people, project):
    other = create_project(people["collabo"], "Autre")
    stored = add_file(people["collabo"], other, "doc.pdf", PDF)
    with pytest.raises(ProjectError, match="ne concerne pas"):
        delete_file(people["owner"], project, stored)


def test_delete_file_from_editor(client, people, project):
    stored = add_file(people["owner"], project, "doc.pdf", PDF)
    log_in(client, people["owner"])
    assert client.post("/projets/drone/fichiers/supprimer", data={"file_id": stored.id}).location == "/projets/drone/editer"
    assert File.query.count() == 0
    log_in(client, people["client"])
    assert client.post("/projets/drone/fichiers/supprimer", data={"file_id": 1}).status_code == 403


# Client ou société avec logo (EDI-05).
def test_client_name_and_logo(people, project):
    logo = add_file(people["owner"], project, "logo.png", PNG)
    save_draft(people["owner"], project, {}, versions(project), "  Airbus  ", logo)
    assert content.read_client(project, "draft") == {"name": "Airbus", "logo": logo.uuid}
    delete_file(people["owner"], project, logo)
    assert content.read_client(project, "draft") == {"name": "Airbus", "logo": None}


@pytest.mark.parametrize("bad", ["pdf", "other_project"])
def test_logo_must_be_an_image_of_the_project(people, project, bad):
    if bad == "pdf":
        logo = add_file(people["owner"], project, "doc.pdf", PDF)
    else:
        logo = add_file(people["collabo"], create_project(people["collabo"], "Autre"), "logo.png", PNG)
    with pytest.raises(ProjectError, match="logo"):
        save_draft(people["owner"], project, {}, versions(project), "Airbus", logo)


def test_client_name_too_long(people, project):
    with pytest.raises(ProjectError, match="client"):
        save_draft(people["owner"], project, {}, versions(project), "x" * 201)


def test_client_from_editor_and_public_logo(client, people, project):
    logo = add_file(people["owner"], project, "logo.png", PNG)
    log_in(client, people["owner"])
    data = {"client_name": "Airbus", "client_logo": logo.uuid, **{f"version_{s}": v for s, v in versions(project).items()}}
    client.post("/projets/drone/editer", data=data)
    assert 'value="Airbus"' in client.get("/projets/drone/editer").text
    publish(project, people)
    client.post("/logout")
    page = client.get("/projets/drone").text
    assert "Client :" in page and "Airbus" in page and f"/fichiers/{logo.uuid}" in page
    response = client.get(f"/fichiers/{logo.uuid}")
    assert response.status_code == 200
    response.close()



def test_client_change_during_reedition_not_public_before_publication(client, people, project):
    old_logo, new_logo = (add_file(people["owner"], project, name, PNG) for name in ("ancien.png", "nouveau.png"))
    save_draft(people["owner"], project, {}, versions(project), "Ancien client", old_logo)
    publish(project, people)
    change_status(people["owner"], project, "request_reedition")
    change_status(people["encadrant"], project, "accept_reedition")
    save_draft(people["owner"], project, {}, versions(project), "Nouveau client", new_logo)
    page = client.get("/projets/drone").text
    assert "Ancien client" in page and old_logo.uuid in page
    assert "Nouveau client" not in page and new_logo.uuid not in page
    with pytest.raises(ProjectError, match="version publiée"):
        delete_file(people["owner"], project, old_logo)  # logo encore en ligne
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    page = client.get("/projets/drone").text
    assert "Nouveau client" in page and new_logo.uuid in page


# NFS-04 avec de vrais fichiers (tests/fixtures, créés par Pillow avec une position GPS à Montpellier).
FIXTURES = Path(__file__).parent / "fixtures"
REAL_IMAGES = {"gps.jpg": "image/jpeg", "gps.png": "image/png", "gps.webp": "image/webp"}


@pytest.mark.parametrize("name", REAL_IMAGES)
def test_real_photo_comes_out_without_gps(people, project, name):
    original = (FIXTURES / name).read_bytes()
    assert b"Appareil Test" in original and b"\x88\x25" in original  # bloc EXIF avec sa partie GPS (balise 0x8825)
    stored = add_file(people["owner"], project, name, original)
    cleaned = content.file_path(project, stored.uuid).read_bytes()
    assert stored.mime_type == REAL_IMAGES[name]
    assert b"Appareil Test" not in cleaned and b"\x88\x25" not in cleaned
    assert content.clean_file(cleaned, stored.mime_type) == cleaned  # structure intacte, plus rien à retirer


@pytest.mark.parametrize("name", [*REAL_IMAGES, "pdf"])
def test_truncated_file_refused_without_error_500(client, people, project, name):
    data = PDF if name == "pdf" else (FIXTURES / name).read_bytes()
    log_in(client, people["owner"])
    response = client.post("/projets/drone/fichiers", data={"file": (io.BytesIO(data[:len(data) // 2]), name)})
    assert response.status_code == 400 and "Fichier abîmé ou incomplet" in response.text
    assert File.query.count() == 0


def test_corrupted_png_refused(people, project):
    data = (FIXTURES / "gps.png").read_bytes()
    corrupted = data[:8] + b"\xff\xff\xff\xff" + data[12:]  # taille du premier bloc impossible
    with pytest.raises(ProjectError, match="abîmé"):
        add_file(people["owner"], project, "gps.png", corrupted)


def test_fake_png_file_refused(client, people, project):
    log_in(client, people["owner"])
    fake = (FIXTURES / "faux.png").read_bytes()
    response = client.post("/projets/drone/fichiers", data={"file": (io.BytesIO(fake), "faux.png")})
    assert response.status_code == 400 and "Type de fichier refusé" in response.text
    assert File.query.count() == 0


# Étape 6b : aperçu en direct (HTMX) et barre d'outils.
def test_live_preview_is_cleaned(client, people, project):
    log_in(client, people["collabo"])
    response = client.post("/projets/drone/apercu", data={"detail": "**Gras** <script>alert(1)</script>"})
    assert response.status_code == 200 and "<strong>Gras</strong>" in response.text
    assert "<script" not in response.text and "<html" not in response.text  # un fragment, pas une page


@pytest.mark.parametrize("who, status", [("client", 403), ("exterieur", 404)])
def test_live_preview_refused_without_right(client, people, project, who, status):
    log_in(client, people[who])
    assert client.post("/projets/drone/apercu", data={"resume": "x"}).status_code == status


def test_live_preview_refused_once_submitted(client, people, project):
    change_status(people["owner"], project, "submit")
    log_in(client, people["owner"])
    assert client.post("/projets/drone/apercu", data={"resume": "x"}).status_code == 403


def test_live_preview_requires_csrf_token(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "CONTENT_DIR": str(tmp_path)})
    with app.app_context():
        db.create_all()
        owner = person("owner")
        create_project(owner, "Drone")
        client = app.test_client()
        log_in(client, owner)
        assert client.post("/projets/drone/apercu", data={"resume": "x"}).status_code == 400
        db.session.remove()
        db.engine.dispose()


def test_editor_has_toolbar_and_htmx(client, people, project):
    add_file(people["owner"], project, "photo.png", PNG)
    log_in(client, people["owner"])
    text = client.get("/projets/drone/editer").text
    for tool in ("titre", "gras", "liste", "image"):
        assert f'data-outil="{tool}"' in text
    assert ">photo.png</option>" in text
    assert 'hx-post="/projets/drone/apercu"' in text and 'hx-params="detail,csrf_token"' in text
    assert "/static/htmx-2.0.4.min.js" in text and "/static/editor.js" in text
    assert "https://" not in text  # aucun script venu d'un site externe
    assert 'name="preview"' in text  # le bouton Aperçu reste si le JavaScript est coupé


def test_htmx_only_on_editor(client, people, project):
    log_in(client, people["owner"])
    assert "<script" not in client.get("/projets/drone").text


# Étape 6c : thèmes (EDI-06).
def themes_of(project):
    return [theme.name for theme in project.themes]


@pytest.fixture
def themes(app):
    found = [Theme(name=name, normalized_name=plain(name)) for name in ("Robotique", "Énergie", "Santé")]
    found[2].active = False
    db.session.add_all(found)
    db.session.commit()
    return found


def test_check_one_or_several_existing_themes(people, project, themes):
    save_draft(people["collabo"], project, {}, versions(project), theme_ids=[themes[0].id])
    assert themes_of(project) == ["Robotique"]
    save_draft(people["collabo"], project, {}, versions(project), theme_ids=[themes[0].id, themes[1].id])
    assert themes_of(project) == ["Énergie", "Robotique"]


def test_propose_new_theme_created_active_and_checked(people, project, themes):
    save_draft(people["owner"], project, {}, versions(project), theme_ids=[themes[0].id], new_theme="  Aéro   spatial ")
    created = Theme.query.filter_by(normalized_name="aero spatial").one()
    assert created.name == "Aéro spatial" and created.active
    assert themes_of(project) == ["Aéro spatial", "Robotique"]


@pytest.mark.parametrize("proposed", ["energie", "  ÉNERGIE ", "Energie"])
def test_duplicate_theme_reused(people, project, themes, proposed):
    save_draft(people["owner"], project, {}, versions(project), theme_ids=[themes[1].id], new_theme=proposed)
    assert Theme.query.count() == 3 and themes_of(project) == ["Énergie"]


def test_inactive_theme_not_offered(client, people, project, themes):
    log_in(client, people["owner"])
    page = client.get("/projets/drone/editer").text
    assert "Robotique" in page and "Énergie" in page and "Santé" not in page
    save_draft(people["owner"], project, {}, versions(project), theme_ids=[themes[2].id])
    assert themes_of(project) == []  # un thème inactif ne peut pas être coché


def test_themes_refused_outside_draft(people, project, themes):
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError, match="droit"):
        save_draft(people["owner"], project, {}, versions(project), new_theme="Nouveau")
    assert Theme.query.count() == 3


def test_themes_from_editor_shown_on_project_page(client, people, project, themes):
    log_in(client, people["owner"])
    data = {"theme_ids": [themes[0].id], "new_theme": "Aéronautique",
            **{f"version_{s}": v for s, v in versions(project).items()}}
    client.post("/projets/drone/editer", data=data)
    assert "Thèmes : Aéronautique, Robotique" in client.get("/projets/drone").text


# 6c bis : thèmes à la création du projet (PRJ-01).
def test_create_project_with_existing_theme(people, themes):
    assert themes_of(create_project(people["owner"], "Robot", theme_ids=[themes[0].id])) == ["Robotique"]


def test_create_project_with_new_theme(people, themes):
    project = create_project(people["owner"], "Robot", theme_ids=[themes[0].id], new_theme="Aéronautique")
    assert themes_of(project) == ["Aéronautique", "Robotique"] and Theme.query.count() == 4


@pytest.mark.parametrize("proposed", ["energie", " ÉNERGIE "])
def test_create_project_with_duplicate_theme_reuses_it(people, themes, proposed):
    assert themes_of(create_project(people["owner"], "Robot", new_theme=proposed)) == ["Énergie"]
    assert Theme.query.count() == 3


def test_create_project_without_theme(people, themes):
    assert themes_of(create_project(people["owner"], "Robot")) == []


@pytest.mark.parametrize("who, title", [("owner", ""), ("encadrant", "Robot")])
def test_refused_creation_creates_no_theme(people, themes, who, title):
    with pytest.raises(ProjectError):
        create_project(people[who], title, new_theme="Nouveau thème")
    assert Theme.query.count() == 3 and Project.query.count() == 0


def test_create_form_offers_themes_and_keeps_them_on_error(client, people, themes):
    log_in(client, people["exterieur"])
    page = client.get("/mon-espace").text
    assert "Robotique" in page and "Énergie" in page and "Santé" not in page and 'name="new_theme"' in page
    response = client.post("/mon-espace", data={"title": "", "theme_ids": [themes[1].id]})
    assert response.status_code == 400 and f'value="{themes[1].id}" checked' in response.text
    response = client.post("/mon-espace", data={"title": "Robot", "theme_ids": [themes[1].id], "new_theme": "IA"})
    assert response.location == "/projets/robot"
    assert themes_of(Project.query.filter_by(slug="robot").one()) == ["Énergie", "IA"]
