# Quoi afficher, quoi enregistrer ? Projets, équipes, fichiers, statuts, commentaires, recherche.
from flask import Blueprint

bp = Blueprint("projects", __name__)

from app.projects import pages  # noqa: E402,F401  (enregistre les routes)
