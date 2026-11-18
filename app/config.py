import json
import os
from datetime import timedelta
from pathlib import Path

# --- Constantes ---
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"
DEV_SECRET_KEY = "dev-only"
# Secrets lus dans l'environnement : variable -> (nom dans la configuration, valeur de développement).
ENV_SETTINGS = {
    "SECRET_KEY": ("SECRET_KEY", DEV_SECRET_KEY),
    "DATABASE_URL": ("SQLALCHEMY_DATABASE_URI", "sqlite:///dev.db"),
    "CONTENT_DIR": ("CONTENT_DIR", "./content"),
    "OIDC_METADATA_URL": ("OIDC_METADATA_URL", ""),
    "OIDC_CLIENT_ID": ("OIDC_CLIENT_ID", ""),
    "OIDC_TENANT_ID": ("OIDC_TENANT_ID", ""),
    "OIDC_CLIENT_SECRET": ("OIDC_CLIENT_SECRET", ""),
}
# Session de 8 heures, cookie illisible par JavaScript et non envoyé par les autres sites.
SESSION_SETTINGS = {
    "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "WTF_CSRF_TIME_LIMIT": None,  # jeton CSRF valable toute la session
}


def load_config():
    """Réglages de config.json (clés en majuscules), session et secrets de l'environnement."""
    settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    config = {key.upper(): value for key, value in settings.items()}
    config.update(SESSION_SETTINGS)
    for variable, (key, default) in ENV_SETTINGS.items():
        config[key] = os.environ.get(variable, default)
    return config
