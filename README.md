# BluePrintLab

Plateforme web des projets étudiants de l'EPF Montpellier (groupe G04).

## Installer (une seule fois)

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Lancer le site

```
flask --app app run --port 8000
```

Puis ouvrir http://localhost:8000 (arrêter avec Ctrl + C).

## Lancer les tests

```
pytest
```
