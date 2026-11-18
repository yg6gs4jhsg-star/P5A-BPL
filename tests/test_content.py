import io
import struct
import zlib

import pytest

from app.models import File, db
from app.projects import content
from app.projects.service import ProjectError, add_file, change_status, create_project, invite, save_draft
from tests.conftest import log_in, person

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = PNG_SIGNATURE + png_chunk(b"IHDR", b"\0" * 13) + png_chunk(b"eXIf", b"GPS 43.6N") + png_chunk(b"IEND", b"")
JPEG = b"\xff\xd8" + b"\xff\xe1\x00\x09ExifGPS" + b"\xff\xdb\x00\x04\x01\x02" + b"\xff\xda\x00\x02IMAGE\xff\xd9"
PDF = b"%PDF-1.7 contenu"


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
    assert "<strong>Essai</strong>" in response.text and content.read_section(project, "draft", "resume") == ""


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
