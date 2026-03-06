# Futures War — Documentation complète

> **Projet** : Challenge B2 — La Plateforme × Agence LVLUP
> **Équipe** : Romain (orchestration/DevOps) · Rooney (frontend/prompts) · Aida (clients/tests)
> **Date** : Mars 2026

---

## Qu'est-ce que Futures War ?

Futures War est une application web interactive qui permet aux utilisateurs d'imaginer le futur de Marseille grâce à l'intelligence artificielle. Le principe est simple : l'utilisateur décrit sa vision du futur de Marseille (par la voix ou par le texte), choisit une thématique, et l'IA génère une image photoréaliste correspondant à cette vision futuriste.

L'application a été conçue dans le cadre d'un challenge créatif en collaboration avec l'Agence LVLUP. Elle s'adresse au grand public et fonctionne comme une borne interactive ou une application web accessible depuis un navigateur.


## Comment ça marche — le pipeline complet

Le cœur de l'application est un **pipeline en 5 étapes** qui transforme une idée en image. Voici le parcours complet d'une requête utilisateur :

### Étape 1 — Saisie de l'utilisateur

L'utilisateur a deux options pour exprimer sa vision :

**Option A : Par la voix** — Il clique sur le bouton "Parler", enregistre un message audio (maximum 30 secondes), puis valide. L'audio est envoyé au serveur pour transcription.

**Option B : Par le texte** — Il tape directement sa description dans la zone de texte. Par exemple : *"Je voudrais des jardins suspendus au-dessus du Vieux-Port avec des drones qui livrent des courses."*

Si l'utilisateur fournit les deux (audio + texte), l'audio est prioritaire. Si la transcription de l'audio échoue, le texte sert de fallback.

L'utilisateur doit aussi choisir une **thématique** (voir section dédiée plus bas).

### Étape 2 — Transcription vocale (si audio)

Si l'utilisateur a parlé, l'audio est envoyé au modèle **Whisper** sur le serveur GPU distant (37.26.187.4:8000) via l'endpoint `/api/speech-to-text`. Le modèle convertit la parole en texte français. Le timeout est configuré à 30 secondes. Les formats audio acceptés sont : MP3, WAV, M4A et WebM.

### Étape 3 — Filtre Safe For Work (passe 1)

Avant tout traitement, le texte brut passe par un filtre de sécurité. Ce filtre vérifie que le texte ne contient pas de mots interdits en français ou en anglais. La liste couvre les catégories suivantes : contenu sexuel, violence, armes, drogues, contenu haineux et suicide.

Le filtre utilise des limites de mots (`\b` en regex) pour éviter les faux positifs. Par exemple, le mot "arsenal" ne déclenche pas le filtre même s'il contient "arme", car le filtre cherche le mot entier.

Si un mot bloqué est détecté, la requête est refusée avec le message *"Contenu modéré. Veuillez reformuler votre description."* (code HTTP 451).

### Étape 4 — Enrichissement du prompt par le LLM

C'est l'étape clé qui transforme une description simple en français en un prompt d'image optimisé en anglais. Le texte est envoyé au modèle **llama3.1:8b** (avec fallback sur **llama3.2:1b** en cas d'échec) via l'endpoint `/v1/chat/completions` du serveur GPU.

Le LLM reçoit un **system prompt** qui lui donne des instructions précises :

- Écrire uniquement en anglais
- Produire un paragraphe de 40 à 80 mots
- Être très visuel et descriptif (lumière, couleurs, angle de caméra, atmosphère, moment de la journée)
- Toujours inclure des éléments reconnaissables de Marseille (Vieux-Port, La Canebière, Notre-Dame de la Garde, calanques, architecture méditerranéenne, vue sur la mer)
- La scène doit paraître futuriste (2050+) tout en restant ancrée dans l'identité de Marseille
- Terminer par des tags de qualité : photorealistic, 4k, cinematic lighting, detailed
- Le contenu doit être strictement Safe For Work
- Si la description de l'utilisateur contient du contenu inapproprié, le réinterpréter comme une vision positive et constructive

Le system prompt contient aussi la **thématique choisie** par l'utilisateur (traduite en anglais), ce qui oriente le style et le contenu de l'image.

Si le LLM principal (8b) échoue (timeout ou erreur HTTP), le système bascule automatiquement sur le modèle de secours (1b). Si les deux échouent, le texte brut de l'utilisateur est utilisé tel quel comme prompt (mode dégradé).

### Étape 5 — Filtre Safe For Work (passe 2)

Le prompt enrichi passe à nouveau par le filtre SFW. Cette double vérification est nécessaire car les modèles LLM open-source ne sont pas censurés et peuvent parfois générer du contenu inapproprié malgré les instructions du system prompt.

### Étape 6 — Génération de l'image

Le prompt enrichi est envoyé au modèle **Z-Image Turbo** (Tongyi-MAI/Z-Image-Turbo) via l'endpoint `/api/prompt-to-image` du serveur GPU. Les paramètres sont :

- Résolution : 1024 × 1024 pixels
- Timeout : 90 secondes (la génération d'image est l'étape la plus longue)

Le modèle retourne une image en base64 (format PNG). Le serveur GPU est un service externe hébergé sur la machine 37.26.187.4 — il n'est pas déployé par l'équipe Futures War.

### Étape 7 — Affichage du résultat

Le frontend reçoit la réponse JSON et affiche :

- L'image générée
- La description originale de l'utilisateur
- Le prompt optimisé en anglais (pour que l'utilisateur voie la transformation)
- La source utilisée (voix ou texte)
- La thématique choisie
- Le temps total de génération


## Les 6 thématiques

Les thématiques sont au cœur du concept Futures War. Elles représentent les grands axes de réflexion sur le futur de Marseille, inspirés du brief de l'Agence LVLUP. Chaque thématique oriente le LLM vers un type de vision futuriste spécifique.

### Se loger (`se_loger`)

**En anglais pour le LLM** : *Housing and Urban Living*

Cette thématique concerne l'habitat et la vie urbaine du futur à Marseille. Elle pousse le LLM à imaginer des bâtiments innovants, des logements écologiques, de l'architecture futuriste, des espaces de vie communautaires, des quartiers réinventés. On parle ici de comment les Marseillais vivront dans leurs habitations en 2050+ : immeubles végétalisés, habitats flottants sur la Méditerranée, quartiers autonomes en énergie, etc.

**Exemples de descriptions possibles** : *"Des immeubles en bois avec des jardins à chaque étage dans le quartier de la Joliette"*, *"Des maisons flottantes dans le Vieux-Port alimentées par l'énergie solaire"*.

### Se déplacer (`se_deplacer`)

**En anglais pour le LLM** : *Transportation and Mobility*

Cette thématique explore les transports et la mobilité du futur. Le LLM est orienté vers des visions de tramways solaires, de véhicules autonomes, de réseaux de transport innovants, de pistes cyclables aériennes, de navettes maritimes électriques, etc. L'idée est de repenser comment les gens se déplaceront dans Marseille en 2050+.

**Exemples de descriptions possibles** : *"Des tramways solaires sur la Canebière"*, *"Des télécabines reliant les collines au Vieux-Port"*, *"Des drones taxis au-dessus de la mer"*.

### Manger (`manger`)

**En anglais pour le LLM** : *Food, Agriculture, and Dining*

Cette thématique s'intéresse à l'alimentation, l'agriculture et la restauration du futur. Le LLM imagine des fermes verticales, des marchés high-tech, des restaurants automatisés, de l'agriculture urbaine sur les toits, des systèmes de distribution alimentaire innovants, etc. Le rapport des Marseillais à la nourriture et à la gastronomie est repensé pour 2050+.

**Exemples de descriptions possibles** : *"Des fermes verticales sur le cours Julien"*, *"Un marché du futur aux Capucins avec des hologrammes qui montrent la provenance des aliments"*, *"Des restaurants robotisés avec vue sur les calanques"*.

### Se divertir (`se_divertir`)

**En anglais pour le LLM** : *Entertainment, Leisure, and Culture*

Cette thématique explore les loisirs, le divertissement et la culture du futur. Le LLM est poussé vers des visions de concerts en réalité augmentée, de musées immersifs, de stades du futur, d'espaces de loisirs technologiques, de cinémas holographiques, etc. La vie culturelle et festive de Marseille est réimaginée.

**Exemples de descriptions possibles** : *"Un concert holographique au Stade Vélodrome"*, *"Un musée immersif dans le MuCEM avec des projections IA"*, *"Des jeux de réalité virtuelle géants sur la plage du Prado"*.

### Accès Nature (`acces_nature`)

**En anglais pour le LLM** : *Nature, Green Spaces, and Environment*

Cette thématique est centrée sur la nature, les espaces verts et l'environnement. C'est la thématique sélectionnée par défaut dans l'interface. Le LLM imagine des parcs urbains futuristes, la biodiversité retrouvée, des calanques préservées avec des technologies vertes, des forêts urbaines, la reconquête de la nature en ville, etc.

**Exemples de descriptions possibles** : *"Des jardins suspendus au-dessus du Vieux-Port"*, *"Des corridors écologiques reliant les parcs de Marseille avec des passerelles végétales"*, *"Les calanques avec des récifs coralliens artificiels visibles depuis des sous-marins en verre"*.

### Travailler (`travailler`)

**En anglais pour le LLM** : *Work, Economy, and Innovation*

Cette thématique concerne le travail, l'économie et l'innovation. Le LLM imagine des espaces de coworking futuristes, des technopoles, des quartiers d'affaires réinventés, le télétravail augmenté, l'économie circulaire, des startups et incubateurs du futur, etc.

**Exemples de descriptions possibles** : *"Un quartier d'affaires à Euroméditerranée avec des tours solaires et des bureaux dans les arbres"*, *"Des espaces de coworking flottants dans le port de Marseille"*, *"Une usine de recyclage automatisée dans la vallée de l'Huveaune"*.

### Ce qui différencie les thématiques entre elles

Les thématiques ne changent pas le modèle d'IA utilisé ni les paramètres techniques de génération. Ce qui change, c'est le **contexte injecté dans le system prompt du LLM**. Concrètement, le label anglais de la thématique (par exemple "Transportation and Mobility") est inséré dans le system prompt à l'emplacement `{category}`. Cela oriente le LLM pour qu'il enrichisse le prompt en fonction du domaine choisi.

Par exemple, pour la même description *"Marseille en 2050"* :

- Avec **Se loger**, le LLM pourrait générer un prompt parlant de tours végétalisées et d'habitats modulaires
- Avec **Se déplacer**, le même texte donnerait un prompt centré sur les véhicules autonomes et les voies de transport
- Avec **Manger**, on obtiendrait des fermes verticales et des marchés futuristes

La thématique est donc un filtre créatif qui guide l'imagination de l'IA dans une direction spécifique.


## Architecture technique

### Vue d'ensemble

```
┌─────────────────────────────────┐
│          FRONTEND               │
│  (HTML/CSS/JS — statique)       │
│  Servi par FastAPI StaticFiles  │
└────────────┬────────────────────┘
             │ POST /api/pipeline (multipart/form-data)
             ▼
┌─────────────────────────────────┐
│       BACKEND (FastAPI)         │
│  Port 3000 — uvicorn            │
│                                 │
│  1. Transcription (si audio)    │
│  2. Filtre SFW (passe 1)       │
│  3. Enrichissement LLM          │
│  4. Filtre SFW (passe 2)       │
│  5. Génération image            │
└────────────┬────────────────────┘
             │ HTTP (httpx)
             ▼
┌─────────────────────────────────┐
│    SERVEUR GPU (externe)        │
│    37.26.187.4:8000             │
│                                 │
│  /api/speech-to-text  (Whisper) │
│  /v1/chat/completions (llama3)  │
│  /api/prompt-to-image (Z-Image) │
└─────────────────────────────────┘
```

### Stack technique

- **Backend** : Python 3.12, FastAPI, uvicorn, httpx, pydantic-settings
- **Frontend** : HTML5 + CSS3 + JavaScript vanilla (pas de framework)
- **Modèles IA** (sur le serveur GPU distant) :
  - **Whisper** pour la transcription vocale
  - **llama3.1:8b** (avec fallback llama3.2:1b) pour l'enrichissement de prompts
  - **Z-Image Turbo** (Tongyi-MAI) pour la génération d'images
- **Déploiement** : Docker, Dockploy (depuis GitHub)

### Endpoints API

**`POST /api/pipeline`** — L'endpoint principal. Accepte un formulaire multipart avec :

- `audio` (fichier, optionnel) : fichier audio à transcrire
- `text` (string, optionnel) : texte brut en fallback
- `category` (string, obligatoire) : une des 6 thématiques

Retourne un JSON avec l'image en base64, les prompts (original et enrichi), la catégorie, la source et le temps de génération.

**`GET /api/health`** — Vérifie que le serveur GPU est joignable. Retourne `"ok"` si le GPU répond, `"degraded"` sinon. Utile pour le monitoring.

**`GET /docs`** — Documentation Swagger automatique générée par FastAPI.


## Le frontend en détail

L'interface est simple et pensée pour être utilisable comme une borne interactive.

**Éléments principaux :**

- Un sélecteur de thématique (dropdown avec les 6 options, "Accès Nature" sélectionné par défaut)
- Une zone de texte pour décrire sa vision
- Un bouton "Parler" pour enregistrer un audio (utilise l'API MediaRecorder du navigateur, max 30s)
- Un bouton "Imaginer le futur" pour lancer le pipeline
- Un loader animé qui montre les étapes en cours ("Préparation…", "Transcription de l'audio…", "Enrichissement du prompt…", "Génération de l'image…")
- Un affichage du résultat avec l'image, les métadonnées et les prompts
- Gestion d'erreurs avec messages en français

**Design** : palette teal + dark + blanc, inspirée du brief LVLUP. Interface responsive (max-width 640px, centré).


## Le filtre Safe For Work en détail

Le filtre SFW est une couche de sécurité indispensable car les modèles IA utilisés (llama3 et Z-Image Turbo) sont des modèles open-source non censurés. Sans filtre, ils pourraient générer du contenu inapproprié.

Le filtre fonctionne avec une liste de mots interdits en français et en anglais. Il est appliqué deux fois : une première fois sur le texte brut de l'utilisateur, une deuxième fois sur le prompt enrichi par le LLM.

**Mots bloqués (français)** : nu, nue, nus, nues, sexe, sexuel, sexuelle, pornographique, érotique, prostitu(é/tion), violence, violent, meurtre, sang, sanglant, arme, fusil, bombe, explosif, drogue, nazi, raciste, terroriste, génocide, suicide, torture.

**Mots bloqués (anglais)** : nude, naked, sex, sexual, porn, erotic, nsfw, prostitut(e/ion), gore, murder, blood, bloody, weapon, gun, bomb, explosive, drug, nazi, racist, terrorist, genocide, suicide, torture.

Le filtre utilise des regex avec `\b` (word boundary) pour ne matcher que les mots entiers. Cela évite les faux positifs comme "arsenal" (qui contient "arme") ou "vinaigrette" (qui contient "vin").


## Configuration et variables d'environnement

L'application se configure via des variables d'environnement, gérées par pydantic-settings. Toutes ont des valeurs par défaut, donc l'app fonctionne sans fichier `.env`.

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `GPU_URL` | `http://37.26.187.4:8000` | URL du serveur GPU distant |
| `GPU_TOKEN` | `tristanlovesia` | Token d'authentification pour le GPU |
| `LLM_MODEL` | `llama3.1:8b` | Modèle LLM principal pour l'enrichissement |
| `LLM_MODEL_FALLBACK` | `llama3.2:1b` | Modèle de secours si le principal échoue |
| `IMAGE_MODEL` | `Tongyi-MAI/Z-Image-Turbo` | Modèle de génération d'images |
| `IMAGE_WIDTH` | `1024` | Largeur de l'image générée (pixels) |
| `IMAGE_HEIGHT` | `1024` | Hauteur de l'image générée (pixels) |
| `STT_TIMEOUT` | `30.0` | Timeout pour la transcription vocale (secondes) |
| `LLM_TIMEOUT` | `30.0` | Timeout pour l'enrichissement LLM (secondes) |
| `IMAGE_TIMEOUT` | `90.0` | Timeout pour la génération d'image (secondes) |


## Structure des fichiers

```
futures-war/
├── Dockerfile                   ← Dockerfile production (racine, pour Dockploy)
├── docker-compose.yml           ← Orchestration Docker
├── .env.example                 ← Template de configuration
├── requirements-dev.txt         ← Dépendances de développement/test
├── README.md                    ← Guide de démarrage rapide
├── DOCUMENTATION.md             ← Ce fichier
│
├── backend/
│   ├── main.py                  ← Point d'entrée FastAPI, monte les fichiers statiques
│   ├── config.py                ← Chargement des variables d'env (pydantic-settings)
│   ├── requirements.txt         ← Dépendances Python production
│   ├── routers/
│   │   └── pipeline.py          ← Route POST /api/pipeline (orchestrateur)
│   ├── services/
│   │   ├── stt_client.py        ← Client Speech-to-Text (Whisper)
│   │   ├── llm_client.py        ← Client LLM (enrichissement prompt)
│   │   ├── image_client.py      ← Client génération image (Z-Image Turbo)
│   │   └── sfw_filter.py        ← Filtre Safe For Work
│   ├── models/
│   │   └── schemas.py           ← Modèles Pydantic (Category, PipelineResponse, etc.)
│   └── prompts/
│       └── enrich_system.txt    ← System prompt pour le LLM (écrit par Rooney)
│
├── frontend/
│   ├── index.html               ← Page principale
│   ├── style.css                ← Styles (palette teal LVLUP)
│   └── app.js                   ← Logique frontend (enregistrement, appel API, affichage)
│
└── tests/
    ├── conftest.py              ← Configuration pytest (path backend)
    └── test_clients.py          ← Tests d'intégration (SFW, LLM, Image)
```


## Modes de fonctionnement

### Dev local (sans Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 3000
```

En mode local, `main.py` détecte que le dossier `static/` n'existe pas et utilise automatiquement `../frontend/` à la place. Le flag `--reload` permet le rechargement automatique quand le code change.

### Docker (docker-compose)

```bash
docker-compose up --build
```

Le Dockerfile est à la racine du repo. Il copie `backend/` dans `/app/` et `frontend/` dans `/app/static/`. L'image est autonome et n'a pas besoin de volumes. Les variables d'environnement sont injectées avec des valeurs par défaut dans `docker-compose.yml`.

### Production (Dockploy)

Dockploy détecte le `Dockerfile` à la racine, build l'image et la déploie. Les variables d'environnement peuvent être configurées dans l'interface Dockploy. Pas besoin de fichier `.env` — les defaults suffisent pour fonctionner.


## Tests

Les tests sont dans `tests/test_clients.py`. Ils se lancent avec :

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

**Tests locaux (toujours passants)** : La classe `TestSFWFilter` teste le filtre SFW avec des cas comme un texte propre, des mots bloqués en français et anglais, la casse insensible, et les faux positifs (mot partiel comme "arsenal").

**Tests d'intégration (nécessitent le serveur GPU)** : Les classes `TestLLMClient` et `TestImageClient` appellent réellement le serveur GPU. Ils vérifient que l'enrichissement retourne un prompt cohérent en anglais et que la génération d'image retourne du base64 valide. Ces tests échouent si le serveur GPU est down — c'est normal.


## Gestion des erreurs

L'application gère les erreurs à chaque étape du pipeline :

- **Transcription échouée** → fallback sur le texte saisi manuellement
- **Filtre SFW déclenché** → HTTP 451 avec message en français
- **LLM principal échoué** → fallback sur le modèle de secours (1b)
- **LLM secours échoué** → utilisation du texte brut comme prompt
- **Génération image échouée** → HTTP 503 avec message d'erreur
- **Aucune saisie** → HTTP 400

Le frontend affiche des messages d'erreur en français dans un bandeau rouge en dessous du formulaire.
