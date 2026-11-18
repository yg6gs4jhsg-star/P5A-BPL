import pytest

from app import create_app
from app.models import Account, AdminEmail, db


TENANT = "tenant-test"


@pytest.fixture
def app(tmp_path):
    """Application de test : base SQLite en mémoire et dossier de contenu temporaire, vides à chaque test."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "OIDC_TENANT_ID": TENANT,
                      "CONTENT_DIR": str(tmp_path)})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()  # ferme la connexion SQLite (sinon avertissement)


@pytest.fixture
def client(app):
    return app.test_client()



def person(name, base_role="etudiant", admin=False):
    """Compte de test (adresse en @epf.fr, ou @epfedu.fr pour un étudiant)."""
    domain = "epfedu.fr" if base_role == "etudiant" else "epf.fr"
    account = Account(oid=name, email=f"{name}@{domain}", name=name, base_role=base_role)
    db.session.add(account)
    if admin:
        db.session.add(AdminEmail(email=account.email))
    db.session.commit()
    return account
