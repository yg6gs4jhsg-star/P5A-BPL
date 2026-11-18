# BluePrintLab : consignes pour Claude

Plateforme web des projets étudiants de l'EPF Montpellier (groupe G04).
On avance **étape par étape** : une étape à la fois, on s'arrête quand les tests passent, on ne code pas la suivante.

## Documents de référence (dossier docs/)
Cahier des charges fonctionnel (V3.1), dossier d'architecture (2.1) et `matrice_droits.md` (copie du § 2.2 du cahier des charges). En cas de doute, ils font foi. Si le code doit s'en écarter, on le dit avant.

## Technologies (décidées)
- Python 3.12 ou plus récent (3.13 sur le Mac de Perrine), Flask (blueprints : accounts, authorization, projects, administration)
- Jinja2 + HTMX. JavaScript seulement dans le navigateur, seulement si utile. Jamais de JavaScript côté serveur.
- Base de données : MySQL (SQLAlchemy + Flask-Migrate). SQLite seulement en développement : écrire des modèles qui marchent aux deux endroits (rien de propre à SQLite).
- Connexion : OpenID Connect avec Microsoft Azure (Entra ID), via Authlib. Aucun mot de passe chez nous. Flask-Login pour la session.
- Sécurité : Flask-WTF (CSRF), `markdown` + `nh3` (nettoyage du HTML).
- Textes des projets : fichiers Markdown sur le disque (`CONTENT_DIR/projects/<uuid>/{draft,published,files}`). La base garde personnes, rôles, équipes, statuts, droits.
- Tests : pytest. Un test par ligne de la matrice des droits.
- Mise en ligne : Docker, nginx, gunicorn (étape finale).

## Authentification (à respecter dès le premier fichier)
- Toutes les pages protégées passent par Flask-Login. Jamais de page « sans connexion à brancher plus tard ».
- Rôle de base calculé à chaque connexion dans UNE seule fonction (module accounts) :
  - `@epf.fr` -> encadrant
  - `@epfedu.fr` + groupe `gg_O365e_Enseignant_Non_Permanent` -> encadrant
  - `@epfedu.fr` + groupe `gg_O365e_Etudiant` -> étudiant
  - ni l'un ni l'autre -> connexion refusée, même si l'adresse est dans la liste blanche
- Admin = pouvoir en plus du rôle de base (pas un rôle qui le remplace). Il vient de la liste blanche (admins seulement).
- Les droits sont vérifiés côté serveur, dans un seul module (authorization), jamais dans les gabarits.
- Client ID, Tenant ID et secret : variables d'environnement, jamais dans le code ni dans Git.
- En local : mêmes routes /login et /auth/callback, mais le fournisseur est un faux serveur OpenID avec des comptes de test (un par rôle). Passer au vrai Azure = changer des variables d'environnement.

## Façon de travailler (instructions de Perrine)
- Faire au plus simple. Le moins de lignes possible.
- Ne rien installer qui ne sert pas tout de suite. Une nouvelle bibliothèque : une phrase pour la justifier, puis l'ajouter à `requirements.txt`.
- Code irréprochable et clair : noms explicites, une fonction = une seule chose, commentaire court qui dit pourquoi, pas de code mort, aucune fonctionnalité non demandée.
- Anticiper les erreurs avant de dire « c'est fini » : lancer `pytest` (la commande exacte, pas `python -m pytest`), tester aussi les cas d'erreur, vérifier que `flask --app app run --port 8000` démarre.
- À la fin de chaque étape, dire à Perrine en langage simple : les fichiers créés, les commandes à lancer (par exemple `pip install -r requirements.txt` si `requirements.txt` a changé), et ce qu'elle doit voir à l'écran.
- **Aucune initiative** : ne rien ajouter qui ne soit pas écrit dans le cahier des charges ou dans la consigne de l'étape. Si un point n'est pas tranché par les documents, poser la question avant de coder et attendre la réponse.
- À la fin de chaque étape (tests verts) : `git commit` puis `git push` sur la branche de travail, avec le nom de l'étape comme message. Ne supprimer aucun fichier.
- Une étape à la fois. Ne pas commencer la suivante.

## Règles de code
- Code simple et court, utile par rapport au cahier des charges. Pas de bibliothèque « parce qu'elle est populaire ».
- Environ 600 lignes utiles, commentaires non comptés.
- Constantes isolées dans un bloc clairement marqué en haut du fichier.
- Réglages (adresse du site, poids max des fichiers, mode développement) dans `config.json`. Les secrets n'y sont jamais.
- Vocabulaire simple dans les textes affichés à l'écran (français).

## Statuts d'un projet
Brouillon, En relecture, Publié, Réédition demandée, Retiré du site public (republiable). Historique conservé. Pas d'e-mails : badges « À faire » / « À relire ».
