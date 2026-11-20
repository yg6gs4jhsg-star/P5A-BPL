# Qui es-tu ? Connexion Microsoft, création du compte, calcul du rôle.
from flask import Blueprint

# cli_group=None : les commandes s'écrivent « flask --app app add-admin », sans préfixe.
bp = Blueprint("accounts", __name__, cli_group=None)

from app.accounts import auth, roles  # noqa: E402,F401  (enregistre les routes et la commande)
