from importlib import import_module

from flask import Flask
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from app.accounts.auth import init_auth
from app.config import DEV_SECRET_KEY, load_config
from app.models import db

# --- Constantes ---
MODULES = ("accounts", "authorization", "projects", "administration")


def create_app(overrides=None):
    """Crée l'application : configuration, base de données, connexion, modules.

    `overrides` remplace des réglages (utilisé par les tests).
    """
    app = Flask(__name__)
    app.config.update(load_config())
    app.config.update(overrides or {})
    # Un envoi plus gros que la plus grande limite (vidéo) est refusé avant d'être lu.
    app.config["MAX_CONTENT_LENGTH"] = (app.config["MAX_VIDEO_MB"] + 1) * 1024 * 1024
    if not app.config["DEBUG"] and app.config["SECRET_KEY"] == DEV_SECRET_KEY:
        raise RuntimeError("SECRET_KEY doit être changée hors développement.")
    db.init_app(app)
    # Mode « batch » : SQLite ne sait pas modifier une table existante autrement.
    Migrate(app, db, render_as_batch=True)
    init_auth(app)
    CSRFProtect(app)  # jeton vérifié sur chaque formulaire qui envoie des données
    for name in MODULES:
        app.register_blueprint(import_module(f"app.{name}").bp)
    return app
