from importlib import import_module

from flask import Flask
from flask_migrate import Migrate

from app.config import load_config
from app.models import db

# --- Constantes ---
MODULES = ("accounts", "authorization", "projects", "administration")


def create_app(overrides=None):
    """Crée l'application : configuration, base de données, modules.

    `overrides` remplace des réglages (utilisé par les tests).
    """
    app = Flask(__name__)
    app.config.update(load_config())
    app.config.update(overrides or {})
    db.init_app(app)
    # Mode « batch » : SQLite ne sait pas modifier une table existante autrement.
    Migrate(app, db, render_as_batch=True)
    for name in MODULES:
        app.register_blueprint(import_module(f"app.{name}").bp)
    return app
