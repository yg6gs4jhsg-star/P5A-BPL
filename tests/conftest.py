import pytest

from app import create_app
from app.models import db


TENANT = "tenant-test"


@pytest.fixture
def app():
    """Application de test avec une base SQLite en mémoire, vide à chaque test."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "OIDC_TENANT_ID": TENANT})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()  # ferme la connexion SQLite (sinon avertissement)


@pytest.fixture
def client(app):
    return app.test_client()

