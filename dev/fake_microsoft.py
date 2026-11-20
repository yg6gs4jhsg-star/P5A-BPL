"""Faux serveur OpenID Connect pour le développement : remplace Microsoft sur le port 8001.

Lancer : python dev/fake_microsoft.py
"""
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

from flask import Flask, abort, jsonify, redirect, render_template_string, request
from joserfc import jwt
from joserfc.jwk import RSAKey

# --- Constantes ---
PORT = 8001
ISSUER = f"http://localhost:{PORT}"
TENANT_ID = "00000000-0000-0000-0000-00000000e9f0"  # identique à OIDC_TENANT_ID de .env.example
STUDENT_GROUP = "gg_O365e_Etudiant"
EXTERNAL_TEACHER_GROUP = "gg_O365e_Enseignant_Non_Permanent"
ACCOUNTS = {
    "etudiant": {"name": "Étudiant Test", "email": "etudiant.test@epfedu.fr", "groups": [STUDENT_GROUP]},
    "enseignant": {"name": "Enseignant Test", "email": "enseignant.test@epf.fr", "groups": []},
    "externe": {"name": "Externe Test", "email": "externe.test@epfedu.fr", "groups": [EXTERNAL_TEACHER_GROUP]},
    "admin": {"name": "Admin Test", "email": "admin.test@epf.fr", "groups": []},
    "sans-groupe": {"name": "Sans Groupe", "email": "sans.groupe@epfedu.fr", "groups": []},
}
CHOOSE_PAGE = """<h1>Faux Microsoft</h1><p>Choisir un compte de test :</p><ul>
{% for key, account in accounts.items() %}
<li><a href="?{{ query }}&account={{ key }}">{{ account.name }} ({{ account.email }})</a></li>
{% endfor %}</ul>"""

app = Flask(__name__)
key = RSAKey.generate_key(2048, parameters={"kid": "fake-key"})  # nouvelle clé à chaque démarrage
codes = {}  # code à usage unique -> demande d'origine


@app.route("/.well-known/openid-configuration")
def metadata():
    return jsonify(
        issuer=ISSUER,
        authorization_endpoint=f"{ISSUER}/authorize",
        token_endpoint=f"{ISSUER}/token",
        jwks_uri=f"{ISSUER}/keys",
        response_types_supported=["code"],
        id_token_signing_alg_values_supported=["RS256"],
        code_challenge_methods_supported=["S256"],
    )


@app.route("/keys")
def keys():
    return jsonify(keys=[key.as_dict(private=False)])


@app.route("/authorize")
def authorize():
    """Page de choix du compte, puis retour vers l'application avec un code."""
    account = request.args.get("account")
    if account not in ACCOUNTS:
        query = urlencode({k: v for k, v in request.args.items() if k != "account"})
        return render_template_string(CHOOSE_PAGE, accounts=ACCOUNTS, query=query)
    code = secrets.token_urlsafe(16)
    codes[code] = dict(request.args)
    return redirect(f"{request.args['redirect_uri']}?{urlencode({'code': code, 'state': request.args['state']})}")


@app.route("/token", methods=["POST"])
def token():
    """Échange le code contre un id_token signé, comme Microsoft (avec vérification PKCE)."""
    asked = codes.pop(request.form.get("code"), None)
    verifier = request.form.get("code_verifier", "").encode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode()
    if asked is None or challenge != asked.get("code_challenge"):
        abort(400)
    account, now = ACCOUNTS[asked["account"]], int(time.time())
    claims = {
        "iss": ISSUER, "aud": asked["client_id"], "iat": now, "exp": now + 3600, "nonce": asked.get("nonce"),
        "sub": f"sub-{asked['account']}", "oid": f"oid-{asked['account']}", "tid": TENANT_ID,
        "email": account["email"], "preferred_username": account["email"], "name": account["name"],
        "groups": account["groups"],
    }
    id_token = jwt.encode({"alg": "RS256", "kid": "fake-key"}, claims, key)
    return jsonify(access_token="fake", token_type="Bearer", expires_in=3600, id_token=id_token)


if __name__ == "__main__":
    app.run(port=PORT)
