import json
import os
from pathlib import Path

# --- Constantes ---
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"
# Secrets lus dans l'environnement, avec leur valeur par défaut de développement.
ENV_DEFAULTS = {
    "SECRET_KEY": "dev-only",
    "DATABASE_URL": "sqlite:///dev.db",
    "CONTENT_DIR": "./content",
}


def load_config():
    """Réglages de config.json (clés en majuscules) et secrets de l'environnement."""
    settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    config = {key.upper(): value for key, value in settings.items()}
    config.update({key: os.environ.get(key, default) for key, default in ENV_DEFAULTS.items()})
    return config
