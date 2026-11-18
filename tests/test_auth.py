import pytest
from requests import ConnectionError

from app import create_app
from app.accounts.auth import account_from_claims, oauth
from app.models import Account, AdminEmail, db
from tests.conftest import TENANT


def claims(**changes):
    base = {"oid": "oid-1", "tid": TENANT, "email": "eleve@epfedu.fr", "name": "Élève", "groups": ["gg_O365e_Etudiant"]}
    return {k: v for k, v in {**base, **changes}.items() if v is not None}


def test_first_login_creates_account(app):
    account = account_from_claims(claims())
    assert (account.oid, account.email, account.base_role) == ("oid-1", "eleve@epfedu.fr", "etudiant")


def test_second_login_updates_role_without_new_account(app):
    account_from_claims(claims())
    account = account_from_claims(claims(groups=["gg_O365e_Enseignant_Non_Permanent"], name="Nouveau nom"))
    assert Account.query.count() == 1
    assert (account.base_role, account.name) == ("encadrant", "Nouveau nom")


def test_account_without_group_refused(app):
    assert account_from_claims(claims(groups=[])) is None
    assert Account.query.count() == 0


def test_token_without_groups_claim(app):
    assert account_from_claims(claims(groups=None)) is None
    assert account_from_claims(claims(email="prof@epf.fr", groups=None)).base_role == "encadrant"


def test_admin_and_supervisor(app):
    db.session.add(AdminEmail(email="admin.test@epf.fr"))
    account = account_from_claims(claims(email="Admin.Test@epf.fr", groups=None))
    assert account.base_role == "encadrant" and account.email == "admin.test@epf.fr"


def test_wrong_tenant_refused(app):
    assert account_from_claims(claims(tid="autre-organisation")) is None


@pytest.mark.parametrize("missing", ["oid", "email", "tid"])
def test_incomplete_token_refused(app, missing):
    assert account_from_claims(claims(**{missing: None})) is None


def test_my_space_requires_login(client):
    response = client.get("/mon-espace")
    assert response.status_code == 302 and response.location.startswith("/login")


def test_callback_logs_in_and_shows_my_space(client, monkeypatch):
    db.session.add(AdminEmail(email="prof@epf.fr"))
    monkeypatch.setattr(oauth.microsoft, "authorize_access_token",
                        lambda: {"userinfo": claims(email="prof@epf.fr", name="Prof")})
    assert client.get("/auth/callback").location == "/mon-espace"
    assert "Prof : encadrant · admin" in client.get("/mon-espace").text


def test_callback_refused_account_gets_message(client, monkeypatch):
    monkeypatch.setattr(oauth.microsoft, "authorize_access_token", lambda: {"userinfo": claims(groups=[])})
    response = client.get("/auth/callback")
    assert response.status_code == 403 and "pas accès" in response.text


def provider_down(*args, **kwargs):
    raise ConnectionError("fournisseur injoignable")


@pytest.mark.parametrize("url, method", [("/login", "load_server_metadata"),
                                         ("/auth/callback", "authorize_access_token")])
def test_provider_unreachable_gives_503(client, monkeypatch, url, method):
    monkeypatch.setattr(oauth.microsoft, method, provider_down)
    response = client.get(url)
    assert response.status_code == 503
    assert "Connexion impossible pour le moment" in response.text and "Retour à l'accueil" in response.text


def test_logout_closes_session(client, monkeypatch):
    monkeypatch.setattr(oauth.microsoft, "authorize_access_token", lambda: {"userinfo": claims()})
    client.get("/auth/callback")
    client.get("/logout")
    assert client.get("/mon-espace").status_code == 302


def test_session_cookie_settings(app):
    assert app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 8 * 3600
    assert app.config["SESSION_COOKIE_HTTPONLY"] and app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_refuses_default_secret_outside_development():
    with pytest.raises(RuntimeError):
        create_app({"DEBUG": False, "SECRET_KEY": "dev-only"})
