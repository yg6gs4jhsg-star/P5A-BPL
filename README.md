# BluePrintLab

Plateforme web des projets étudiants de l'EPF Montpellier (groupe G04).

## Installer (une seule fois)

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app db upgrade
```

Premier admin (une seule fois) : `flask --app app add-admin admin.test@epf.fr`

## Lancer le site

Deux terminaux, chacun avec l'environnement activé (`source .venv/bin/activate`) :

```
python dev/fake_microsoft.py          # terminal 1 : faux Microsoft (port 8001)
flask --app app run --port 8000       # terminal 2 : le site
```

Puis ouvrir http://localhost:8000/mon-espace (toujours `localhost`, jamais `127.0.0.1`).
Arrêter avec Ctrl + C. Pour le vrai Azure : changer les 4 variables `OIDC_…` de `.env`.

## Lancer les tests

```
pytest
```
