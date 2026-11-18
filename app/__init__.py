from importlib import import_module

from flask import Flask

from app.config import load_config

# --- Constantes ---
MODULES = ("accounts", "authorization", "projects", "administration")


def create_app():
    """Crée l'application : charge la configuration et enregistre les modules."""
    app = Flask(__name__)
    app.config.update(load_config())
    for name in MODULES:
        app.register_blueprint(import_module(f"app.{name}").bp)
    return app
