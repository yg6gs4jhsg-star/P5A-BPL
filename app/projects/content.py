"""Le seul endroit qui touche au disque : textes Markdown et fichiers d'un projet."""
import hashlib
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


def copy_draft_to_published(project):
    """Publier = figer une copie du brouillon."""
    shutil.copytree(project_dir(project, "draft"), project_dir(project, "published"), dirs_exist_ok=True)


def fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def keep_attribute(tag, attribute, value):
    """Seules les images envoyées sur BluePrintLab s'affichent (pas d'image externe)."""
    if tag == "img" and attribute == "src" and not value.startswith(FILES_URL):
        return None
    return value


def render(text):
    """Markdown vers HTML, puis nettoyé contre l'injection de code (XSS)."""
    return Markup(nh3.clean(markdown.markdown(text), attribute_filter=keep_attribute))


def detect_type(data):
    """Type reconnu et autorisé par le réglage allowed_file_types, sinon None."""
    for mime_type, parts in SIGNATURES.items():
        if all(data[start:start + len(value)] == value for start, value in parts):
            return mime_type if mime_type in current_app.config["ALLOWED_FILE_TYPES"] else None
    return None


def max_size(mime_type):
    key = "MAX_VIDEO_MB" if mime_type == VIDEO_TYPE else "MAX_FILE_MB"
    return current_app.config[key] * MB


def strip_jpeg_metadata(data):
    """Retire les segments APP1 (EXIF, dont la position GPS) d'un JPEG."""
    kept, position = [data[:2]], 2
    while position + 4 <= len(data) and data[position] == 0xFF:
        marker, length = data[position + 1], int.from_bytes(data[position + 2:position + 4], "big")
        if marker == 0xDA:  # début de l'image elle-même : on garde tout le reste
            break
        if marker != 0xE1:
            kept.append(data[position:position + 2 + length])
        position += 2 + length
    return b"".join(kept) + data[position:]


def strip_png_metadata(data):
    """Retire le bloc eXIf (dont la position GPS) d'un PNG."""
    kept, position = [data[:8]], 8
    while position + 8 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk = data[position:position + 12 + length]
        if chunk[4:8] != b"eXIf":
            kept.append(chunk)
        position += 12 + length
    return b"".join(kept)


def strip_webp_metadata(data):
    """Retire le bloc EXIF (dont la position GPS) d'un WebP et met à jour les tailles."""
    kept, position = [], 12
    while position + 8 <= len(data):
        size = int.from_bytes(data[position + 4:position + 8], "little")
        chunk = bytearray(data[position:position + 8 + size + size % 2])  # blocs alignés sur 2 octets
        if chunk[:4] == b"VP8X":
            chunk[8] &= ~0x08  # l'en-tête n'annonce plus d'EXIF
        if chunk[:4] != b"EXIF":
            kept.append(bytes(chunk))
        position += len(chunk)
    body = b"WEBP" + b"".join(kept)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


STRIPPERS = {"image/jpeg": strip_jpeg_metadata, "image/png": strip_png_metadata, "image/webp": strip_webp_metadata}


def clean_file(data, mime_type):
    return STRIPPERS.get(mime_type, lambda d: d)(data)


def write_file(project, file_uuid, data):
    (project_dir(project, "files") / file_uuid).write_bytes(data)


def file_path(project, file_uuid):
    return project_dir(project, "files") / file_uuid


def delete_file(project, file_uuid):
    file_path(project, file_uuid).unlink(missing_ok=True)


def is_published_file(project, file_uuid):
    """Le fichier est cité par la version validée du projet."""
    return any(FILES_URL + file_uuid in read_section(project, "published", s) for s in SECTIONS)
