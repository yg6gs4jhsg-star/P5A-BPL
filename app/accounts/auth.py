from authlib.integrations.flask_client import OAuth, OAuthError
from flask import current_app, redirect, render_template_string, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from joserfc.errors import JoseError
from requests import RequestException

from app.accounts import bp
from app.accounts.roles import compute_base_role, is_admin
from app.models import Account, Invitation, Member, db, utcnow

# --- Constantes ---
SCOPES = "openid profile email"
# Le fournisseur est injoignable, répond une erreur ou renvoie un jeton invalide.
PROVIDER_ERRORS = (RequestException, OAuthError, JoseError)
UNAVAILABLE = "Connexion impossible pour le moment, réessayez plus tard."
REFUSED = "Votre compte n'a pas accès à l'espace de rédaction."
PAGE = '<p>{{ text }}</p><p><a href="{{ url_for(\'projects.home\') }}">Retour à l\'accueil</a></p>'

oauth = OAuth()
login_manager = LoginManager()
login_manager.login_view = "accounts.login"


def init_auth(app):
    """Branche le fournisseur OpenID (adresse lue dans l'environnement) et la session."""
    oauth.init_app(app)
    oauth.register(
        "microsoft",
        server_metadata_url=app.config["OIDC_METADATA_URL"],
        client_id=app.config["OIDC_CLIENT_ID"],
        client_secret=app.config["OIDC_CLIENT_SECRET"],
        client_kwargs={"scope": SCOPES, "code_challenge_method": "S256"},  # PKCE
    )
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(account_id):
    return db.session.get(Account, int(account_id))


def account_from_claims(claims):
    """Crée ou met à jour le compte depuis un jeton vérifié ; None si la connexion est refusée."""
    email = claims.get("email") or claims.get("preferred_username")
    if claims.get("tid") != current_app.config["OIDC_TENANT_ID"] or not claims.get("oid") or not email:
        return None
    base_role = compute_base_role(email, claims.get("groups"))
    if base_role is None:
        return None
    account = Account.query.filter_by(oid=claims["oid"]).first() or Account(oid=claims["oid"])
    account.email, account.name, account.base_role = email.strip().lower(), claims.get("name", email), base_role
    db.session.add(account)
    join_invited_projects(account)
    db.session.commit()
    return account


def join_invited_projects(account):
    """Les invitations valables deviennent des membres (même transaction que le compte).

    Une invitation « collabo » attend si la personne est encadrante : un Collabo est un étudiant.
    """
    for invitation in Invitation.query.filter(Invitation.email == account.email, Invitation.expires_at > utcnow()):
        if invitation.role == "collabo" and account.base_role != "etudiant":
            continue
        db.session.add(Member(project_id=invitation.project_id, account=account, role=invitation.role))
        db.session.delete(invitation)


def message(text, status):
    return render_template_string(PAGE, text=text), status


@bp.route("/login")
def login():
    try:
        return oauth.microsoft.authorize_redirect(url_for("accounts.callback", _external=True))
    except PROVIDER_ERRORS:
        return message(UNAVAILABLE, 503)


@bp.route("/auth/callback")
def callback():
    try:
        claims = oauth.microsoft.authorize_access_token()["userinfo"]
    except PROVIDER_ERRORS:
        return message(UNAVAILABLE, 503)
    account = account_from_claims(claims)
    if account is None:
        return message(REFUSED, 403)
    login_user(account)
    session.permanent = True  # expire après PERMANENT_SESSION_LIFETIME
    return redirect(url_for("accounts.my_space"))


@bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("projects.home"))


@bp.route("/mon-espace")
@login_required
def my_space():
    admin = " · admin" if is_admin(current_user.email) else ""
    return render_template_string(
        "<p>{{ name }} : {{ role }}{{ admin }}</p><p><a href=\"{{ url_for('accounts.logout') }}\">Se déconnecter</a></p>",
        name=current_user.name, role=current_user.base_role, admin=admin,
    )
