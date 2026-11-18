import json
import os
from pathlib import Path

# --- Constantes ---
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"
# Secrets lus dans l'environnement : variable -> (nom dans la configuration, valeur de développement).
ENV_SETTINGS = {
    "SECRET_KEY": ("SECRET_KEY", "dev-only"),
    "DATABASE_URL": ("SQLALCHEMY_DATABASE_URI", "sqlite:///dev.db"),
    "CONTENT_DIR": ("CONTENT_DIR", "./content"),
}


def load_config():
    """Réglages de config.json (clés en majuscules) et secrets de l'environnement."""
    settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    config = {key.upper(): value for key, value in settings.items()}
    for variable, (key, default) in ENV_SETTINGS.items():
        config[key] = os.environ.get(variable, default)
    return config
