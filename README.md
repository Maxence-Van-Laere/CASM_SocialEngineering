# CASM — Outil d'analyse et de collecte de données de réseaux sociaux

Un Cognitive Surface Attack Mapper est un outil d’analyse qui identifie et cartographie les leviers psychologiques présents dans un message et susceptibles d’être exploités dans des scénarios de social engineering.​
Son objectif est de transformer les intéractions sur ses réseaux sociaux d'un individu en signaux mesurables​ et de fournir ensuite une évaluation, pour qu'il ait conscience de ses faiblesses et comment elles pourraient être exploitées à son encontre, tout en étant respectueux de la vie privée de l'individu tout le long du processus.

**Résumé**
- Ce dépôt rassemble : collecteurs (scrapers), pipeline d'analyse (`analyse_biais_IA`), front-end minimal et historiques d'analyses.

**Arborescence (extrait)**
- `server.py` : point d'entrée backend léger.
- `requirement.txt` : dépendances Python.
- `frontend/` : interface utilisateur (HTML/JS/CSS).
- `social_media_scrapping/` : scripts de collecte (Twitter, Mastodon, Bluesky pour l'instant). - Chaque scraper nécessite des clés API, token d'accès, ...  
- `analyse_biais_IA/` : modules d'analyse, pipeline, résultats.

**Prérequis**
- Python 3.10+ (ou 3.8+ selon votre environnement).
- Un environnement virtuel recommandé (`venv`, `conda`).

**Installation**
1. Créez et activez un environnement virtuel :

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1  # PowerShell
# ou
.\.venv\Scripts\activate.bat   # cmd
```

2. Installez les dépendances :

```bash
pip install -r requirement.txt
```

**Exécution — backend**
- Lancer le serveur (API/point d'entrée) :

```bash
python server.py
```

- Le serveur expose selon la configuration interne — vérifier `server.py` pour endpoints disponibles.

**Exécution — frontend**
- Ouvrir `frontend/index.html` dans un navigateur pour une interface statique.
- Ou servir le dossier `frontend` localement :

```bash
# depuis le dossier frontend
python -m http.server 8000
# puis ouvrir http://localhost:8000
```


**Analyse et pipeline**
- Le dossier `analyse_biais_IA/` contient :
  - `pipeline.py` : orchestration de l'analyse.
  - `analyzer.py`, `cognitive_engine.py`, `hf_emotions.py` : composants d'analyse.
  - `privacy.py` : fonctions d'anonymisation.

- Les résultats des métriques d'émotions sont écrits dans `analyse_biais_IA/output/schema.json` et un rapport final JSON correspondant se trouve dans `analyse_biais_IA/output/final_report.json`.


**Contribuer**
- Forkez le dépôt, créez une branche feature, testez localement et ouvrez une pull request.
- Ajoutez des instructions précises pour toute dépendance externe (API keys, fichiers de configuration).
- Ne committez jamais de clés API ou de données sensibles.
