# Futures War — Speech-to-Image MVP

> Imaginez le futur de Marseille avec l'IA. Parlez ou écrivez, l'IA génère une image.

**Projet** : Challenge B2 — La Plateforme × Agence LVLUP
**Équipe** : Romain (orchestration/DevOps) · Rooney (frontend/prompts) · Aida (clients/tests)

---

## Architecture

```
[Frontend]  →  POST /api/pipeline  →  [FastAPI Backend]
                                           │
                    ┌──────────────────────┤
                    ▼                      ▼                      ▼
            /api/speech-to-text    /v1/chat/completions    /api/prompt-to-image
                (Whisper)              (llama3)              (Z-Image Turbo)
                    └──────────────────────┘
                         Serveur GPU (37.26.187.4:8000)
```

**Pipeline** : Audio/Texte → Transcription → Enrichissement prompt → Filtre SFW → Génération image

## Quick Start

### 1. Avec Docker (recommandé)

```bash
docker-compose up --build
```

Ouvrir http://localhost:3000

> **Note** : Les variables d'environnement ont des valeurs par défaut dans `docker-compose.yml`.
> Pour les personnaliser, créez un fichier `.env` à partir de `.env.example` :
> ```bash
> cp .env.example .env
> ```

### 2. Sans Docker (dev local Windows)

```bash
# Installer les dépendances
pip install -r backend/requirements.txt

# Lancer le serveur (depuis le dossier backend/)
cd backend
uvicorn main:app --reload --port 3000
```

Ouvrir http://localhost:3000

> **Note** : Le port 3000 est utilisé par défaut (le port 8080 est souvent bloqué sur Windows).
> Le frontend est servi automatiquement depuis `../frontend/` en dev local.

### 3. API Swagger

http://localhost:3000/docs

### 4. Déploiement Dockploy

Le `Dockerfile` est à la racine du repo. Dockploy le détecte automatiquement.
Les variables d'environnement peuvent être configurées dans l'interface Dockploy.

## Endpoint principal

### `POST /api/pipeline`

**Content-Type** : `multipart/form-data`

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `audio` | File | Non | Fichier audio (mp3, wav, m4a, webm) |
| `text` | string | Non | Texte brut (fallback) |
| `category` | string | **Oui** | `se_loger`, `se_deplacer`, `manger`, `se_divertir`, `acces_nature`, `travailler` |

Au moins `audio` ou `text` doit être fourni.

**Réponse (200)** :
```json
{
  "image_base64": "iVBORw0KGgo...",
  "prompt_original": "Des jardins sur les toits",
  "prompt_enriched": "Futuristic Marseille rooftop gardens...",
  "category": "acces_nature",
  "source": "text",
  "generation_time_seconds": 14.2
}
```

### Test rapide (PowerShell)

```powershell
# Texte → Image
$body = @{ text = "Des tramways solaires sur la Canebière"; category = "se_deplacer" }
Invoke-RestMethod -Uri http://localhost:3000/api/pipeline -Method Post -Form $body
```

```powershell
# Healthcheck
Invoke-RestMethod -Uri http://localhost:3000/api/health
```

## Structure du projet

```
futures-war/
├── Dockerfile              # Production (root — for Dockploy)
├── docker-compose.yml
├── .env.example
├── requirements-dev.txt    # Dev/test deps (includes backend/requirements.txt)
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py             # Settings (env vars)
│   ├── requirements.txt      # Production deps
│   ├── routers/pipeline.py   # POST /api/pipeline
│   ├── services/
│   │   ├── stt_client.py     # Speech-to-text (Whisper)
│   │   ├── llm_client.py     # LLM enrichissement
│   │   ├── image_client.py   # Génération image (Z-Image Turbo)
│   │   └── sfw_filter.py     # Filtre Safe For Work
│   ├── models/schemas.py     # Pydantic models
│   └── prompts/enrich_system.txt  # System prompt LLM
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── tests/
    ├── conftest.py           # Path setup for pytest
    └── test_clients.py
```

## Tests

```bash
# Depuis la racine du projet
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

> **Note** : Les tests LLM et Image appellent le vrai serveur GPU — ils échouent si le serveur est down.

## Configuration (.env)

| Variable | Défaut | Description |
|----------|--------|-------------|
| `GPU_URL` | `http://37.26.187.4:8000` | URL du serveur GPU |
| `GPU_TOKEN` | `tristanlovesia` | Token d'authentification |
| `LLM_MODEL` | `llama3.1:8b` | Modèle LLM principal |
| `LLM_MODEL_FALLBACK` | `llama3.2:1b` | Modèle LLM de secours |
| `IMAGE_MODEL` | `Tongyi-MAI/Z-Image-Turbo` | Modèle de génération |
| `IMAGE_WIDTH` | `1024` | Largeur image |
| `IMAGE_HEIGHT` | `1024` | Hauteur image |
