# Quoi afficher, quoi enregistrer ? Projets, équipes, fichiers, statuts, commentaires, recherche.
from flask import Blueprint

bp = Blueprint("projects", __name__)


@bp.route("/")
def home():
    return "BluePrintLab : le site démarre."
