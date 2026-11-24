"""Le seul endroit qui touche au disque : textes Markdown et fichiers d'un projet."""
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

import markdown
import nh3
from flask import current_app
from markupsafe import Markup

# --- Constantes ---
SECTIONS = {"resume": "Présentation rapide", "detail": "Page détaillée"}  # un fichier .md par section
# Texte de départ de la présentation rapide (PUB-03).
DEFAULT_TEXTS = {"resume": "## Objectifs\n\n## Description\n\n## Réalisations\n"}
FILES_URL = "/fichiers/"
EXCERPT_MAX = 200  # début de la présentation rapide sur les cartes
CLIENT_FILE = "client.json"  # client ou société et son logo (EDI-05), copiés à la publication avec les textes
FILES_LIST = "files.json"  # fichiers du projet au moment de la publication : la version publiée
# Type -> octets attendus (position, valeur) ; le type vient du contenu réel, jamais de l'extension.
SIGNATURES = {
    "image/png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "image/jpeg": ((0, b"\xff\xd8\xff"),),
    "image/webp": ((0, b"RIFF"), (8, b"WEBP")),
    "application/pdf": ((0, b"%PDF-"),),
    "video/mp4": ((4, b"ftyp"),),
}
VIDEO_TYPE = "video/mp4"
MB = 1024 * 1024
FOLDERS = ("draft", "published", "files")


def project_dir(project, folder):
    # Chemin absolu : un chemin relatif (« ./content ») serait lu par Flask depuis le dossier app/.
    return Path(current_app.config["CONTENT_DIR"]).resolve() / "projects" / project.uuid / folder


def create_folders(project):
    for folder in FOLDERS:
        project_dir(project, folder).mkdir(parents=True)
    for section, text in DEFAULT_TEXTS.items():
        write_section(project, section, text)


def read_section(project, folder, section):
    path = project_dir(project, folder) / f"{section}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_section(project, section, text):
    (project_dir(project, "draft") / f"{section}.md").write_text(text, encoding="utf-8")


def read_client(project, folder):
    path = project_dir(project, folder) / CLIENT_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"name": "", "logo": None}


def write_client(project, name, logo_uuid):
    (project_dir(project, "draft") / CLIENT_FILE).write_text(json.dumps({"name": name, "logo": logo_uuid}),
                                                             encoding="utf-8")


def copy_draft_to_published(project):
    """Publier = figer une copie du brouillon et noter les fichiers qui en font partie."""
    shutil.copytree(project_dir(project, "draft"), project_dir(project, "published"), dirs_exist_ok=True)
    (project_dir(project, "published") / FILES_LIST).write_text(json.dumps([file.uuid for file in project.files]))


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def keep_attribute(tag, attribute, value):
    """Seules les images envoyées sur BluePrintLab s'affichent (pas d'image externe)."""
    return None if tag == "img" and attribute == "src" and not value.startswith(FILES_URL) else value


def render(text, enlarge=False):
    """Markdown vers HTML, puis nettoyé contre l'injection de code (XSS).

    `enlarge` (pages publiques) : chaque image devient un lien vers son fichier, pour l'ouvrir en grand.
    """
    cleaned = nh3.clean(markdown.markdown(text), attribute_filter=keep_attribute)
    if enlarge:
        cleaned = re.sub(r'(<img [^>]*src="([^"]+)"[^>]*>)', r'<a href="\2">\1</a>', cleaned)
    return Markup(cleaned)


def summary(project):
    """Présentation rapide publiée en texte brut, sans les titres (lignes « # ») ni balises ni scripts."""
    lines = [line for line in read_section(project, "published", "resume").splitlines() if not line.startswith("#")]
    text = html.unescape(nh3.clean(markdown.markdown("\n".join(lines)), tags=set()))
    return " ".join(text.split())


def shorten(text):
    return text if len(text) <= EXCERPT_MAX else text[:EXCERPT_MAX - 1] + "…"


def detect_type(data):
    """Type reconnu et autorisé par le réglage allowed_file_types, sinon None."""
    for mime_type, parts in SIGNATURES.items():
        if all(data[start:start + len(value)] == value for start, value in parts):
            return mime_type if mime_type in current_app.config["ALLOWED_FILE_TYPES"] else None
    return None


def max_size(mime_type):
    key = "MAX_VIDEO_MB" if mime_type == VIDEO_TYPE else "MAX_FILE_MB"
    return current_app.config[key] * MB


class DamagedFile(ValueError):
    """Le fichier est tronqué ou abîmé : sa structure ne tient pas."""


def require_complete(condition):
    if not condition:
        raise DamagedFile


def strip_jpeg_metadata(data):
    """Retire les segments APP1 (EXIF, dont la position GPS) d'un JPEG."""
    kept, position = [data[:2]], 2
    while data[position:position + 2] != b"\xff\xda":  # jusqu'au début de l'image elle-même
        require_complete(position + 4 <= len(data) and data[position] == 0xFF)
        end = position + 2 + int.from_bytes(data[position + 2:position + 4], "big")
        require_complete(end <= len(data))
        if data[position + 1] != 0xE1:
            kept.append(data[position:end])
        position = end
    require_complete(data.endswith(b"\xff\xd9"))  # fin d'image présente
    return b"".join(kept) + data[position:]


def strip_png_metadata(data):
    """Retire le bloc eXIf (dont la position GPS) d'un PNG."""
    kept, position = [data[:8]], 8
    while position < len(data):
        end = position + 12 + int.from_bytes(data[position:position + 4], "big")
        require_complete(position + 8 <= len(data) and end <= len(data))
        if data[position + 4:position + 8] != b"eXIf":
            kept.append(data[position:end])
        position = end
    require_complete(kept[-1][4:8] == b"IEND")  # dernier bloc présent
    return b"".join(kept)


def strip_webp_metadata(data):
    """Retire le bloc EXIF (dont la position GPS) d'un WebP et met à jour les tailles."""
    require_complete(int.from_bytes(data[4:8], "little") == len(data) - 8)
    kept, position = [], 12
    while position < len(data):
        size = int.from_bytes(data[position + 4:position + 8], "little")
        chunk = bytearray(data[position:position + 8 + size + size % 2])  # blocs alignés sur 2 octets
        require_complete(position + 8 <= len(data) and position + len(chunk) <= len(data) and size + 8 <= len(chunk))
        if chunk[:4] == b"VP8X":
            chunk[8] &= ~0x08  # l'en-tête n'annonce plus d'EXIF
        if chunk[:4] != b"EXIF":
            kept.append(bytes(chunk))
        position += len(chunk)
    body = b"WEBP" + b"".join(kept)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def check_pdf(data):
    require_complete(b"%%EOF" in data[-1024:])  # marque de fin présente
    return data


def check_mp4(data):
    """Les boîtes MP4 (taille sur 4 octets, ou 8 si elle vaut 1, ou jusqu'à la fin si 0) remplissent le fichier."""
    position = 0
    while position < len(data):
        require_complete(position + 8 <= len(data))
        size = int.from_bytes(data[position:position + 4], "big")
        if size == 1:
            require_complete(position + 16 <= len(data))
            size = int.from_bytes(data[position + 8:position + 16], "big")
        size = size or len(data) - position
        require_complete(size >= 8 and position + size <= len(data))
        position += size
    return data


CLEANERS = {"image/jpeg": strip_jpeg_metadata, "image/png": strip_png_metadata, "image/webp": strip_webp_metadata,
            "application/pdf": check_pdf, "video/mp4": check_mp4}


def clean_file(data, mime_type):
    """Fichier vérifié et sans métadonnées ; DamagedFile s'il est tronqué ou abîmé."""
    return CLEANERS[mime_type](data)


def write_file(project, file_uuid, data):
    file_path(project, file_uuid).write_bytes(data)


def file_path(project, file_uuid):
    return project_dir(project, "files") / file_uuid


def delete_file(project, file_uuid):
    file_path(project, file_uuid).unlink(missing_ok=True)


def is_published_file(project, file_uuid):
    """Le fichier fait partie de la version validée du projet (cité dans le texte ou non)."""
    path = project_dir(project, "published") / FILES_LIST
    return path.exists() and file_uuid in json.loads(path.read_text())
