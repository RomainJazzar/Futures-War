# Futures War — Guide Technique Complet

> **Objectif de ce document** : permettre à chaque membre de l'équipe (Romain, Rooney, Aida) de comprendre en profondeur le code de l'ensemble du projet — pas seulement sa partie, mais aussi celles des autres. Ce guide explique chaque fichier, chaque fonction, chaque choix technique, et les pièges à éviter.

---

## Table des matières

1. [Vue d'ensemble de l'architecture](#1-vue-densemble-de-larchitecture)
2. [Les technologies utilisées et pourquoi](#2-les-technologies-utilisées-et-pourquoi)
3. [Partie Romain — Orchestration et DevOps](#3-partie-romain--orchestration-et-devops)
4. [Partie Rooney — Frontend et Prompts](#4-partie-rooney--frontend-et-prompts)
5. [Partie Aida — Clients GPU, Filtre SFW et Tests](#5-partie-aida--clients-gpu-filtre-sfw-et-tests)
6. [Comment les parties se connectent entre elles](#6-comment-les-parties-se-connectent-entre-elles)
7. [Flux complet d'une requête — du clic au pixel](#7-flux-complet-dune-requête--du-clic-au-pixel)
8. [Pièges, bugs courants et points d'attention](#8-pièges-bugs-courants-et-points-dattention)

---

## 1. Vue d'ensemble de l'architecture

```
┌──────────────────────────────────────────────┐
│           NAVIGATEUR (utilisateur)            │
│                                               │
│  index.html + style.css + app.js              │
│  Rooney : interface, enregistrement audio,    │
│           appel API, affichage résultat       │
└───────────────────┬──────────────────────────┘
                    │  POST /api/pipeline
                    │  (multipart/form-data)
                    ▼
┌──────────────────────────────────────────────┐
│              SERVEUR FastAPI                  │
│              (port 3000)                      │
│                                               │
│  main.py (Romain) : point d'entrée,          │
│    CORS, static files, health check           │
│                                               │
│  pipeline.py (Romain) : orchestre les 5       │
│    étapes du pipeline                         │
│                                               │
│  config.py (Romain) : charge les variables    │
│    d'environnement                            │
│                                               │
│  schemas.py (Romain) : modèles de données     │
│                                               │
│  stt_client.py (Aida) : appelle Whisper       │
│  llm_client.py (Aida) : appelle llama3        │
│  image_client.py (Aida) : appelle Z-Image     │
│  sfw_filter.py (Aida) : filtre de sécurité    │
│                                               │
│  enrich_system.txt (Rooney) : system prompt    │
└───────────────────┬──────────────────────────┘
                    │  HTTP (httpx)
                    ▼
┌──────────────────────────────────────────────┐
│          SERVEUR GPU EXTERNE                  │
│          37.26.187.4:8000                     │
│                                               │
│  /api/speech-to-text   → Whisper              │
│  /v1/chat/completions  → llama3.1:8b / 3.2:1b│
│  /api/prompt-to-image  → Z-Image Turbo        │
│  /api/system-stats     → monitoring            │
└──────────────────────────────────────────────┘
```

L'application suit un modèle simple : le frontend est un site statique (HTML/CSS/JS) servi directement par FastAPI. Quand l'utilisateur clique sur "Imaginer le futur", le JavaScript envoie un POST au backend, qui orchestre une chaîne d'appels au serveur GPU, puis renvoie le résultat au frontend.

Il n'y a pas de base de données, pas de système d'authentification côté utilisateur, pas de cache. C'est un MVP minimaliste.

---

## 2. Les technologies utilisées et pourquoi

### Python 3.12

Choisi parce que c'est le standard pour le ML/IA et que le serveur GPU expose des APIs HTTP classiques. Python 3.12 apporte la syntaxe `X | Y` pour les types union (utilisée partout dans le code, par exemple `str | None`), ce qui évite d'importer `Optional` de `typing`.

### FastAPI

Framework web Python choisi pour plusieurs raisons :

- **Async natif** : les appels au serveur GPU (STT, LLM, image) sont des opérations I/O qui prennent du temps (jusqu'à 90s pour une image). FastAPI utilise `async/await`, ce qui permet au serveur de gérer d'autres requêtes pendant qu'il attend la réponse du GPU. Si on avait utilisé Flask (synchrone), le serveur serait bloqué pendant chaque génération.
- **Validation automatique** : grâce à Pydantic, les paramètres du formulaire sont validés automatiquement. Si l'utilisateur envoie une catégorie invalide, FastAPI renvoie une erreur 422 sans qu'on ait besoin d'écrire du code de validation.
- **Swagger auto** : FastAPI génère automatiquement la page `/docs` avec un formulaire interactif pour tester l'API. C'est très utile en développement.
- **StaticFiles** : FastAPI peut servir des fichiers statiques directement, ce qui évite d'avoir un serveur séparé (Nginx, etc.) pour le frontend.

### httpx

Bibliothèque HTTP asynchrone pour Python. Choisie à la place de `requests` parce que `requests` est synchrone — il bloquerait la boucle `async` de FastAPI. httpx est compatible `async/await` et a une API presque identique à `requests`, donc c'est un remplacement naturel.

### pydantic-settings

Extension de Pydantic qui charge les variables d'environnement automatiquement. On déclare une classe `Settings` avec des champs typés et des valeurs par défaut, et pydantic-settings remplit ces champs depuis les variables d'environnement ou un fichier `.env`. C'est beaucoup plus propre que de faire `os.getenv()` partout.

### python-multipart

Dépendance nécessaire pour que FastAPI puisse recevoir des données `multipart/form-data` (formulaires avec fichiers). Sans cette bibliothèque, les endpoints avec `File()` et `Form()` ne fonctionnent pas — FastAPI lève une erreur au démarrage.

### uvicorn

Serveur ASGI (Asynchronous Server Gateway Interface) qui fait tourner l'application FastAPI. C'est le serveur recommandé par FastAPI. En dev on l'utilise avec `--reload` (redémarrage automatique quand le code change), en production sans.

### JavaScript vanilla (pas de framework)

Le frontend n'utilise ni React, ni Vue, ni aucun framework. C'est un choix délibéré pour un MVP : l'interface est simple (un formulaire, un bouton, un résultat), un framework ajouterait de la complexité sans bénéfice. Pas de build step, pas de node_modules, pas de bundler. Le JS est chargé directement par le navigateur.

### Docker

Utilisé pour le déploiement via Dockploy. Le Dockerfile est à la racine du repo et crée une image autonome qui contient à la fois le backend et le frontend. Dockploy détecte ce Dockerfile et déploie automatiquement.

---

## 3. Partie Romain — Orchestration et DevOps

Romain est responsable de la structure du projet, du point d'entrée de l'application, de l'orchestration du pipeline, et du déploiement. Ses fichiers sont : `main.py`, `config.py`, `routers/pipeline.py`, `models/schemas.py`, `Dockerfile`, `docker-compose.yml`.

### 3.1. `backend/config.py` — Le chargement de la configuration

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GPU_URL: str = "http://37.26.187.4:8000"
    GPU_TOKEN: str = "tristanlovesia"
    LLM_MODEL: str = "llama3.1:8b"
    LLM_MODEL_FALLBACK: str = "llama3.2:1b"
    IMAGE_MODEL: str = "Tongyi-MAI/Z-Image-Turbo"
    IMAGE_WIDTH: int = 1024
    IMAGE_HEIGHT: int = 1024
    STT_TIMEOUT: float = 30.0
    LLM_TIMEOUT: float = 30.0
    IMAGE_TIMEOUT: float = 90.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Comment ça marche :**

`BaseSettings` de pydantic-settings fonctionne ainsi : quand on instancie `Settings()`, il cherche d'abord les variables d'environnement du système (par exemple `GPU_URL=...`), puis regarde dans le fichier `.env`, et enfin utilise la valeur par défaut définie dans la classe. L'ordre de priorité est : variable d'environnement > fichier .env > valeur par défaut.

L'objet `settings` est instancié **une seule fois au niveau du module** (ligne 19). En Python, quand un module est importé pour la première fois, le code au niveau du module est exécuté. Les imports suivants réutilisent le même objet. Donc `from config import settings` dans n'importe quel fichier donne accès au même singleton.

**`model_config`** : c'est la configuration de Pydantic v2 (qui a remplacé l'ancienne `class Config`). `env_file` indique le chemin du fichier `.env` à charger. `env_file_encoding` est nécessaire sous Windows parce que les fichiers texte peuvent être encodés en UTF-16 par certains éditeurs.

**Pourquoi les types sont importants** : `GPU_URL: str` n'est pas juste de la documentation. Pydantic valide et convertit les types. Si on met `IMAGE_WIDTH=abc` dans le `.env`, Pydantic lèvera une erreur au démarrage plutôt que de planter plus tard dans le code.

**Points d'attention** :

- Le fichier `.env` est relatif au **répertoire de travail** (CWD), pas au fichier `config.py`. En dev local, il faut lancer `uvicorn` depuis `backend/`, donc le `.env` doit être dans `backend/` ou il ne sera pas trouvé. En Docker, le CWD est `/app/` (le `WORKDIR` du Dockerfile).
- Si le `.env` n'existe pas, pydantic-settings ne plante pas — il utilise les valeurs par défaut. C'est voulu : en production Dockploy injecte les variables d'environnement directement.

### 3.2. `backend/models/schemas.py` — Les modèles de données

```python
from enum import Enum
from pydantic import BaseModel


class Category(str, Enum):
    SE_LOGER = "se_loger"
    SE_DEPLACER = "se_deplacer"
    MANGER = "manger"
    SE_DIVERTIR = "se_divertir"
    ACCES_NATURE = "acces_nature"
    TRAVAILLER = "travailler"
```

**Pourquoi `(str, Enum)` et pas juste `Enum` :**

`Category` hérite de `str` ET de `Enum`. C'est un pattern Python qui fait que chaque membre de l'enum est aussi une chaîne de caractères. Conséquences :

- `Category.MANGER == "manger"` retourne `True`
- `Category.MANGER.value` retourne `"manger"`
- On peut utiliser `category.value` directement dans du JSON sans conversion

Sans le `str`, FastAPI ne saurait pas comment sérialiser l'enum en JSON et poserait problème dans les réponses.

**Pourquoi un Enum et pas juste une string :**

Quand l'endpoint `pipeline()` déclare `category: Category = Form(...)`, FastAPI valide automatiquement que la valeur envoyée fait partie de l'enum. Si un utilisateur envoie `category=pizza`, FastAPI renvoie une erreur 422 avec la liste des valeurs acceptées. Sans l'enum, n'importe quelle string passerait et pourrait planter dans `llm_client.py`.

```python
class PipelineResponse(BaseModel):
    image_base64: str
    prompt_original: str
    prompt_enriched: str
    category: str
    source: str  # "speech" or "text"
    generation_time_seconds: float
```

**`PipelineResponse`** définit la structure exacte de la réponse JSON de l'API. FastAPI utilise ce modèle pour :

1. **Valider** la réponse côté serveur (si on oublie un champ, erreur)
2. **Sérialiser** automatiquement en JSON
3. **Documenter** dans Swagger (la page `/docs` montre le schéma de réponse)

```python
class HealthResponse(BaseModel):
    status: str
    gpu_server_reachable: bool
    gpu_stats: dict | None = None
```

`gpu_stats: dict | None = None` signifie : ce champ est optionnel, sa valeur par défaut est `None`, et s'il est présent c'est un dictionnaire. Le `dict` non typé est utilisé parce qu'on ne contrôle pas la structure exacte de la réponse du serveur GPU.

### 3.3. `backend/main.py` — Le point d'entrée

Ce fichier fait 4 choses : configurer le logging, créer l'application FastAPI, définir le healthcheck, et monter les fichiers statiques.

**Le logging :**

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("futures-war")
```

`logging.basicConfig` configure le logging pour TOUTE l'application (c'est global). `%(name)-25s` affiche le nom du logger sur 25 caractères (aligné à gauche avec le `-`), ce qui donne des logs bien alignés en colonnes :

```
14:23:01 | futures-war.pipeline      | INFO  | Pipeline terminé en 12.3s
14:23:01 | futures-war.llm           | INFO  | LLM: prompt enrichi (245 chars)
```

Chaque module crée son propre logger avec `logging.getLogger("futures-war.xxx")`. Le préfixe `futures-war.` crée une hiérarchie : tous ces loggers héritent de la configuration du logger racine défini dans `main.py`.

**L'application FastAPI :**

```python
app = FastAPI(
    title="Futures War — Speech-to-Image",
    description=(...),
    version="0.1.0",
)
```

`title`, `description`, `version` ne sont pas cosmétiques — ils apparaissent dans la page Swagger (`/docs`). C'est la documentation interactive de l'API.

**Le CORS :**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS (Cross-Origin Resource Sharing) est une sécurité des navigateurs. Si le frontend était servi depuis `http://localhost:5500` (par exemple avec Live Server de VS Code) et que le backend est sur `http://localhost:3000`, le navigateur bloquerait les requêtes AJAX entre les deux domaines. Ce middleware dit au navigateur "accepte les requêtes de n'importe quelle origine".

`allow_origins=["*"]` est permissif (accepte tout). C'est OK pour un MVP, mais en production il faudrait restreindre aux domaines réels.

**Pourquoi le middleware est déclaré même si le frontend est servi par le même serveur :** En production (même origine, même port), CORS n'est pas nécessaire. Mais en dev, Rooney pourrait ouvrir `index.html` directement dans le navigateur (protocole `file://`) ou utiliser Live Server, et dans ces cas CORS serait bloquant. Le middleware est là par sécurité.

**Le router :**

```python
app.include_router(pipeline_router)
```

`include_router` attache les routes définies dans `pipeline.py` à l'application principale. C'est un pattern de séparation : au lieu de tout mettre dans `main.py`, on découpe en "routers" thématiques. Ici il n'y en a qu'un, mais si on ajoutait un router `gallery` ou `admin`, on ferait pareil.

**Le healthcheck :**

```python
@app.get("/api/health", response_model=HealthResponse, tags=["monitoring"])
async def health():
    gpu_ok = False
    gpu_stats = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.GPU_URL}/api/system-stats",
                headers={"Authorization": f"Bearer {settings.GPU_TOKEN}"},
            )
            if resp.status_code == 200:
                gpu_ok = True
                gpu_stats = resp.json()
    except Exception:
        pass
```

Ce endpoint est crucial pour le monitoring. Dockploy (ou n'importe quel orchestrateur) peut l'appeler régulièrement pour vérifier que le service est vivant. Il ne teste pas juste si FastAPI répond, mais aussi si le serveur GPU est joignable.

**Le `try/except Exception: pass`** — normalement un anti-pattern (avaler les erreurs silencieusement), mais ici c'est intentionnel. Si le GPU est down, on ne veut pas que le healthcheck plante. On veut qu'il retourne `"degraded"`. Toute exception (timeout, DNS, connexion refusée) est traitée de la même façon : le GPU n'est pas joignable.

**Le `timeout=5.0`** est plus court que les autres timeouts (30s, 90s) parce que le healthcheck doit répondre vite.

**Le montage des fichiers statiques :**

```python
_static_dir = Path("static")
if not _static_dir.is_dir():
    _static_dir = Path(__file__).resolve().parent.parent / "frontend"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
else:
    logger.warning("No static/frontend directory found — frontend will not be served.")
```

C'est le mécanisme qui permet au même code de fonctionner en Docker ET en dev local :

- **En Docker** : le Dockerfile copie `frontend/` dans `/app/static/`. Le CWD est `/app/`. Donc `Path("static")` pointe vers `/app/static/` qui existe → on l'utilise.
- **En dev local** : on lance `uvicorn` depuis `backend/`. Il n'y a pas de dossier `backend/static/`. Donc on utilise `Path(__file__).resolve().parent.parent / "frontend"` qui remonte d'un niveau (de `backend/` à la racine du projet) puis entre dans `frontend/`.

**`html=True`** dans `StaticFiles` active le mode "Single Page App" : quand on demande `/`, FastAPI sert `index.html` automatiquement. Sans ça, il faudrait aller à `/index.html` explicitement.

**ATTENTION — Pourquoi c'est monté EN DERNIER :** `app.mount("/", ...)` capture TOUTES les URLs qui n'ont pas été matchées par les routes précédentes. Si on le mettait avant `include_router(pipeline_router)`, le `POST /api/pipeline` serait intercepté par StaticFiles et retournerait une erreur 404 (pas de fichier `/api/pipeline` dans le dossier). FastAPI évalue les routes dans l'ordre de déclaration, donc les routes API doivent être déclarées AVANT le mount statique.

### 3.4. `backend/routers/pipeline.py` — L'orchestrateur

C'est le fichier le plus important du backend. Il orchestre les 5 étapes du pipeline en séquence.

**La signature de la fonction :**

```python
async def pipeline(
    audio: UploadFile | None = File(None, description="Fichier audio (mp3, wav, m4a, webm)"),
    text: str | None = Form(None, description="Texte brut (fallback si pas d'audio)"),
    category: Category = Form(..., description="Catégorie thématique"),
):
```

Décortiquons :

- `async def` : cette fonction est asynchrone. Quand elle fait `await transcribe_audio(...)`, Python "pause" cette fonction et peut traiter d'autres requêtes en attendant la réponse du GPU.
- `audio: UploadFile | None = File(None)` : paramètre optionnel (défaut `None`). `UploadFile` est un type FastAPI qui représente un fichier envoyé en multipart. `File(None)` dit à FastAPI que ce paramètre vient du body multipart (pas du query string) et qu'il est optionnel.
- `text: str | None = Form(None)` : idem pour un champ texte de formulaire.
- `category: Category = Form(...)` : les `...` (Ellipsis) signifient "obligatoire". Si le client n'envoie pas `category`, FastAPI retourne 422.

**Pourquoi `File()` et `Form()` et pas juste des paramètres normaux :** FastAPI doit savoir si le paramètre vient du query string (`?text=...`), du body JSON, ou d'un formulaire multipart. `File()` et `Form()` le spécifient explicitement. Un même endpoint ne peut pas mélanger du JSON et du multipart — c'est une limitation du protocole HTTP.

**Étape 1 — Obtenir le texte (lignes 44-66) :**

```python
original_text = None

if audio is not None:
    audio_bytes = await audio.read()
    if len(audio_bytes) > 0:
        try:
            original_text = await transcribe_audio(...)
            source = "speech"
        except Exception as e:
            logger.warning("STT échoué (%s), tentative fallback texte", e)

if original_text is None and text:
    original_text = text.strip()
    source = "text"
```

L'algorithme de fallback est le suivant :

1. Si un audio est envoyé ET qu'il n'est pas vide (taille > 0), on tente la transcription
2. Si la transcription réussit, `original_text` est rempli et `source = "speech"`
3. Si la transcription échoue (exception), `original_text` reste `None`
4. Si `original_text` est encore `None` ET qu'un texte a été envoyé, on utilise le texte
5. Si ni l'audio ni le texte n'ont donné de résultat, erreur 400

**Pourquoi `await audio.read()`** : `UploadFile` est un objet de type fichier asynchrone. `read()` charge tout le contenu en mémoire. Pour des fichiers audio courts (< 30s), c'est OK. Pour des fichiers volumineux, il faudrait du streaming, mais ce n'est pas nécessaire ici.

**Pourquoi `if len(audio_bytes) > 0`** : le navigateur peut envoyer un champ `audio` vide (par exemple si l'utilisateur a cliqué sur le bouton micro par erreur). On vérifie qu'il y a vraiment des données.

**Étape 2 — Filtre SFW passe 1 (lignes 71-74) :**

```python
is_sfw, blocked_word = check_sfw(original_text)
if not is_sfw:
    raise HTTPException(status_code=451, detail="Contenu modéré. Veuillez reformuler votre description.")
```

Le code HTTP 451 signifie "Unavailable For Legal Reasons" (RFC 7725). C'est le code approprié pour la censure de contenu. Le frontend affiche le `detail` dans le bandeau d'erreur.

`check_sfw` retourne un tuple `(bool, str | None)` — c'est le pattern "success/error" en Python : au lieu de lever une exception, on retourne un indicateur de succès et une valeur d'erreur.

**Étape 3 — Enrichissement LLM (lignes 79-83) :**

```python
try:
    prompt_enriched = await enrich_prompt(original_text, category.value)
except Exception as e:
    logger.warning("LLM enrichissement échoué (%s), utilisation du texte brut", e)
    prompt_enriched = original_text  # mode dégradé
```

**Point crucial** : si le LLM échoue, on ne plante PAS la requête. On utilise le texte brut de l'utilisateur comme prompt. L'image sera moins bonne (texte français non optimisé), mais l'utilisateur obtient quand même un résultat. C'est le pattern "graceful degradation".

`category.value` extrait la string de l'enum : `Category.SE_DEPLACER.value` donne `"se_deplacer"`.

**Étape 4 — Filtre SFW passe 2 (lignes 88-91) :**

Le prompt enrichi passe aussi par le filtre. C'est nécessaire parce que le LLM est un modèle open-source (llama3) qui n'est pas censuré. Même avec un system prompt qui dit "SFW only", il peut parfois générer du contenu inapproprié, surtout avec des descriptions ambiguës.

**Étape 5 — Génération d'image (lignes 96-100) :**

```python
try:
    image_b64 = await generate_image(prompt_enriched)
except Exception as e:
    raise HTTPException(status_code=503, detail="Serveur de génération indisponible.")
```

Contrairement au LLM, ici on n'a PAS de fallback. Si le serveur d'images est down, on ne peut pas générer l'image — il n'y a pas d'alternative. Le code 503 (Service Unavailable) est approprié : c'est une erreur temporaire côté serveur.

**Le chronométrage :**

```python
start = time.time()
# ... tout le pipeline ...
elapsed = round(time.time() - start, 1)
```

`time.time()` retourne le timestamp Unix en secondes (avec décimales). `round(..., 1)` arrondit à une décimale. Ce temps est affiché dans le frontend comme badge "12.3s".

**Attention** : `time.time()` mesure le temps "wall clock" (temps réel écoulé), pas le temps CPU. C'est ce qu'on veut ici : on mesure l'expérience utilisateur, pas la charge serveur.

### 3.5. `Dockerfile` — Le build de production

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./static/

EXPOSE 3000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
```

Ligne par ligne :

- **`FROM python:3.12-slim`** : image de base Python minimale (~150 Mo au lieu de ~900 Mo pour l'image complète). "slim" enlève les outils de compilation, la doc, etc. Suffisant pour notre cas (pas de bibliothèques C à compiler).
- **`WORKDIR /app`** : toutes les commandes suivantes s'exécutent dans `/app/`. Comme `main.py` est dans `backend/`, et qu'on fait `COPY backend/ .`, `main.py` se retrouve à `/app/main.py`.
- **`COPY backend/requirements.txt .`** puis **`RUN pip install`** : on copie le requirements AVANT le code source. Pourquoi ? Docker met en cache chaque couche. Si on change le code mais pas les dépendances, Docker réutilise le cache du `pip install` et le build est beaucoup plus rapide. `--no-cache-dir` évite de stocker le cache pip dans l'image (on gagne quelques Mo).
- **`COPY backend/ .`** : copie tout le dossier `backend/` dans `/app/`. Les sous-dossiers `routers/`, `services/`, `models/`, `prompts/` sont inclus.
- **`COPY frontend/ ./static/`** : copie le frontend dans `/app/static/`. C'est ce que `main.py` cherche en premier (`Path("static")`).
- **`EXPOSE 3000`** : documentation — indique quel port le conteneur utilise. N'ouvre pas réellement le port (c'est `docker-compose` qui fait ça avec `ports:`).
- **`CMD [...]`** : la commande exécutée au lancement du conteneur. Pas de `--reload` en production (ça relancerait le serveur à chaque changement de fichier, inutile et risqué). `--host 0.0.0.0` est nécessaire pour que le conteneur accepte les connexions depuis l'extérieur (par défaut uvicorn écoute seulement sur `127.0.0.1`).

**Le Dockerfile est à la RACINE du repo** (pas dans `backend/`). C'est parce que Dockploy cherche le Dockerfile à la racine par défaut, et parce que le `COPY frontend/ ./static/` a besoin d'accéder au dossier `frontend/` qui est au même niveau que `backend/`.

### 3.6. `docker-compose.yml` — L'orchestration locale

```yaml
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      GPU_URL: ${GPU_URL:-http://37.26.187.4:8000}
      # ...
    env_file:
      - path: .env
        required: false
    restart: unless-stopped
```

- **`build: .`** : build le Dockerfile dans le répertoire courant (la racine du repo).
- **`ports: "3000:3000"`** : mappe le port 3000 du conteneur au port 3000 de la machine hôte. Format : `hôte:conteneur`.
- **`${GPU_URL:-http://37.26.187.4:8000}`** : syntaxe shell pour "utilise la variable d'environnement `GPU_URL` si elle existe, sinon utilise la valeur par défaut". Cela permet à Dockploy de fonctionner sans fichier `.env`.
- **`env_file: path: .env, required: false`** : charge le `.env` s'il existe, ne plante pas s'il n'existe pas. C'est la syntaxe docker-compose v2.
- **`restart: unless-stopped`** : redémarre automatiquement le conteneur s'il plante, sauf si on l'arrête manuellement.

---

## 4. Partie Rooney — Frontend et Prompts

Rooney est responsable de l'interface utilisateur (HTML, CSS, JavaScript) et du system prompt qui guide le LLM.

### 4.1. `frontend/index.html` — La structure de la page

```html
<!DOCTYPE html>
<html lang="fr">
```

`lang="fr"` est important pour l'accessibilité : les lecteurs d'écran savent que le contenu est en français. Ça aide aussi les moteurs de recherche.

**La structure HTML suit un pattern simple :**

```
<div class="container">
    <header>       → titre + sous-titre
    <main>
        .form-group   → sélecteur de thématique
        .form-group   → textarea
        .actions       → boutons (micro + générer)
        #mic-status    → indicateur d'enregistrement (caché par défaut)
        #loader        → spinner (caché par défaut)
        #error         → message d'erreur (caché par défaut)
        #result        → image + métadonnées (caché par défaut)
    <footer>       → crédits
</div>
```

**Le select des thématiques :**

```html
<select id="category">
    <option value="se_loger">Se loger</option>
    <option value="se_deplacer">Se déplacer</option>
    <option value="manger">Manger</option>
    <option value="se_divertir">Se divertir</option>
    <option value="acces_nature" selected>Accès Nature</option>
    <option value="travailler">Travailler</option>
</select>
```

Les `value` DOIVENT correspondre exactement aux valeurs de l'enum `Category` dans `schemas.py`. Si Rooney écrit `value="se-loger"` (tiret au lieu d'underscore), FastAPI retournera une erreur 422. L'attribut `selected` sur "acces_nature" en fait la valeur par défaut.

**Les éléments cachés :**

`#mic-status`, `#loader`, `#error` et `#result` ont tous la classe `hidden`. Ils sont affichés/cachés dynamiquement par `app.js` en ajoutant/retirant cette classe. C'est un pattern classique : tout le HTML est dans la page, le JS contrôle la visibilité.

**Le script en fin de body :**

```html
<script src="app.js"></script>
```

Le `<script>` est placé APRÈS tout le HTML, juste avant `</body>`. C'est important : si on le met dans `<head>`, le JS s'exécute avant que le HTML soit chargé, et les `document.getElementById(...)` retournent `null` (les éléments n'existent pas encore).

### 4.2. `frontend/style.css` — Le design

**Les variables CSS :**

```css
:root {
    --color-primary: #00b4d8;      /* teal clair — boutons, focus */
    --color-primary-dark: #0096b7;  /* teal foncé — hover, titre */
    --color-bg: #f5f7fa;            /* gris très clair — fond de page */
    --color-surface: #ffffff;       /* blanc — cartes, inputs */
    --color-text: #1e293b;          /* bleu-noir — texte principal */
    --color-text-muted: #64748b;    /* gris — texte secondaire */
    --color-error: #ef4444;         /* rouge — erreurs */
    --color-success: #10b981;       /* vert — succès (non utilisé pour l'instant) */
    --radius: 12px;                 /* coins arrondis */
    --shadow: 0 2px 12px rgba(0, 0, 0, 0.08);  /* ombre légère */
}
```

Les variables CSS (custom properties) sont déclarées dans `:root` (l'élément `<html>`) et accessibles partout avec `var(--nom)`. L'avantage : si Rooney veut changer la couleur principale, il modifie UNE seule ligne et tout le site suit.

**Le reset universel :**

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}
```

`* { margin: 0; padding: 0; }` supprime les marges par défaut du navigateur (chaque navigateur a des marges différentes sur `<h1>`, `<p>`, `<body>`, etc.). `box-sizing: border-box` fait que la propriété `width` inclut le padding et le border. Sans ça, un `input` avec `width: 100%` et `padding: 10px` dépasserait de son conteneur.

**Le conteneur centré :**

```css
.container {
    max-width: 640px;
    margin: 0 auto;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
```

`max-width: 640px` + `margin: 0 auto` centre le conteneur horizontalement et le limite à 640px de large (format mobile/tablette). `min-height: 100vh` + `flex` + `flex-direction: column` permettent au footer de rester en bas de la page même si le contenu est court (le `main` a `flex: 1` et prend tout l'espace disponible).

**L'animation du bouton micro :**

```css
.btn-mic.recording {
    border-color: var(--color-error);
    background: #fef2f2;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
```

Quand le JS ajoute la classe `recording` au bouton micro, il passe en rouge pâle avec une animation de pulsation. `@keyframes` définit l'animation : l'opacité oscille entre 100% et 70% en boucle infinie. L'indicateur `.rec-dot` utilise la même animation.

**Le spinner de chargement :**

```css
.spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #e2e8f0;
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
```

C'est un cercle (`border-radius: 50%`) avec une bordure grise sauf le côté haut qui est teal. L'animation `spin` fait tourner le cercle. C'est la technique CSS classique pour faire un spinner sans SVG ni image.

**La classe utilitaire `hidden` :**

```css
.hidden {
    display: none !important;
}
```

Le `!important` est nécessaire ici pour que `hidden` prenne le dessus sur n'importe quel autre style. Par exemple, `.mic-status` a `display: flex`, mais quand on ajoute `.hidden`, on veut que `display: none` gagne.

### 4.3. `frontend/app.js` — La logique frontend

**Les références DOM (lignes 9-26) :**

```javascript
const btnGenerate = document.getElementById("btn-generate");
const btnMic = document.getElementById("btn-mic");
// ... etc
```

Toutes les références DOM sont récupérées UNE SEULE FOIS au chargement du script et stockées dans des constantes. C'est une bonne pratique : `document.getElementById()` parcourt l'arbre DOM à chaque appel. Appeler ça dans une boucle ou à chaque clic serait inefficace.

**Les variables d'état (lignes 29-34) :**

```javascript
let mediaRecorder = null;
let audioChunks = [];
let audioBlob = null;
let timerInterval = null;
let recordingSeconds = 0;
const MAX_RECORDING_SECONDS = 30;
```

- `mediaRecorder` : l'objet natif du navigateur qui gère l'enregistrement audio
- `audioChunks` : un tableau qui accumule les morceaux d'audio pendant l'enregistrement (le navigateur envoie les données par morceaux)
- `audioBlob` : le fichier audio complet, assemblé quand l'enregistrement s'arrête
- `timerInterval` : l'ID du `setInterval` pour le compteur de secondes (nécessaire pour pouvoir l'arrêter avec `clearInterval`)
- `MAX_RECORDING_SECONDS = 30` : limite de sécurité. Au-delà, le fichier audio serait trop lourd et la transcription trop longue

**L'enregistrement audio (lignes 38-92) :**

```javascript
btnMic.addEventListener("click", async () => {
    // ...
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
```

`navigator.mediaDevices.getUserMedia({ audio: true })` est une API du navigateur qui demande l'accès au microphone. Le navigateur affiche un popup de permission. C'est un appel asynchrone (`await`) parce que l'utilisateur doit accepter.

`MediaRecorder` est l'API native pour enregistrer un flux media. On ne choisit pas le format — le navigateur décide (Chrome utilise WebM/Opus, Firefox aussi, Safari utilise MP4/AAC). C'est pour ça qu'on récupère `mediaRecorder.mimeType` pour l'envoyer au serveur.

**L'accumulation des chunks :**

```javascript
mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
};
```

Le `MediaRecorder` ne génère pas le fichier d'un coup. Il envoie des morceaux (chunks) via l'événement `ondataavailable`. On les accumule dans un tableau.

**L'assemblage quand l'enregistrement s'arrête :**

```javascript
mediaRecorder.onstop = () => {
    audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
    stream.getTracks().forEach((t) => t.stop());
    clearInterval(timerInterval);
};
```

`new Blob(audioChunks, { type: ... })` assemble tous les morceaux en un seul objet binaire (Blob). `stream.getTracks().forEach(t => t.stop())` est CRUCIAL : sans ça, le micro reste allumé (l'indicateur rouge dans le navigateur reste visible) même après l'arrêt de l'enregistrement. `clearInterval(timerInterval)` arrête le compteur.

**La sécurité : auto-stop à 30 secondes :**

```javascript
timerInterval = setInterval(() => {
    recordingSeconds++;
    if (recordingSeconds >= MAX_RECORDING_SECONDS) {
        stopRecording();
    }
}, 1000);
```

Sans cette limite, un utilisateur pourrait enregistrer 10 minutes d'audio, ce qui causerait un timeout côté Whisper ou un fichier trop lourd.

**L'appel au pipeline (lignes 106-168) :**

```javascript
async function runPipeline() {
    const formData = new FormData();
    formData.append("category", category);

    if (hasAudio) {
        const mimeType = audioBlob.type || "audio/webm";
        const ext = mimeType.includes("mp4") ? "m4a" : mimeType.includes("webm") ? "webm" : "wav";
        formData.append("audio", audioBlob, `recording.${ext}`);
    }
```

`FormData` est l'objet JavaScript pour construire un formulaire multipart. On y ajoute les champs un par un. Pour le fichier audio, le 3ème argument de `append()` est le nom de fichier — le serveur Whisper en a besoin pour déduire le format.

La détection de l'extension (`mimeType.includes("mp4") ? ...`) est un hack pragmatique. L'idéal serait de parser le MIME type proprement, mais pour un MVP c'est suffisant.

```javascript
const response = await fetch("/api/pipeline", {
    method: "POST",
    body: formData,
});
```

`fetch` est l'API native du navigateur pour les requêtes HTTP. On n'utilise PAS `axios` ou `jQuery.ajax` — pas de dépendance externe. L'URL `/api/pipeline` est relative, donc elle fonctionne quel que soit le domaine (localhost:3000 ou le domaine de production).

**Pourquoi on ne met pas `Content-Type: multipart/form-data` dans les headers :** le navigateur le fait automatiquement quand le body est un `FormData`, et il ajoute aussi le "boundary" (séparateur entre les champs). Si on le met manuellement, on écrase le boundary et la requête échoue.

**La gestion d'erreur côté frontend :**

```javascript
if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Erreur inconnue" }));
    throw new Error(err.detail || `Erreur ${response.status}`);
}
```

`.catch(() => ({ detail: "Erreur inconnue" }))` gère le cas où la réponse d'erreur n'est pas du JSON valide (par exemple un timeout du reverse proxy qui renvoie du HTML). Sans ça, on aurait une erreur de parsing JSON qui masquerait l'erreur originale.

**Le nettoyage dans `finally` :**

```javascript
finally {
    hideLoader();
    btnGenerate.disabled = false;
    audioBlob = null;
    textInput.placeholder = "Ex : Je voudrais des jardins suspendus...";
}
```

`finally` s'exécute que la requête réussisse ou échoue. On remet l'UI dans un état propre : loader caché, bouton réactivé, audio effacé. `audioBlob = null` force l'utilisateur à ré-enregistrer pour la prochaine génération (on ne réutilise pas le même audio).

**L'affichage du résultat :**

```javascript
function showResult(data) {
    resultImage.src = `data:image/png;base64,${data.image_base64}`;
```

L'image est affichée via un Data URI : au lieu de pointer vers une URL, on intègre les données directement dans l'attribut `src`. Le format est `data:image/png;base64,<données>`. C'est possible parce que le serveur retourne l'image en base64 dans le JSON.

**Point d'attention** : une image 1024x1024 en base64 fait environ 2-4 Mo de texte. C'est beaucoup plus lourd qu'un fichier image binaire (le base64 ajoute ~33% de taille). Pour un MVP c'est OK, mais en production il faudrait stocker l'image sur le serveur et renvoyer une URL.

### 4.4. `backend/prompts/enrich_system.txt` — Le cerveau du pipeline

```
You are an expert AI image prompt engineer specializing in the Z-Image Turbo model.

Your task: transform a French description of an imagined future for Marseille
into an optimized image generation prompt IN ENGLISH.

Theme category: {category}

Rules:
- Write in ENGLISH only
- One single paragraph, 40 to 80 words
- Be highly visual and descriptive: describe lighting, colors, camera angle,
  atmosphere, time of day
- Always include recognizable Marseille elements (Vieux-Port, La Canebière,
  Notre-Dame de la Garde, calanques, Mediterranean architecture, sea views)
- The scene must feel FUTURISTIC (2050+) while remaining grounded in
  Marseille's identity
- End with quality tags: photorealistic, 4k, cinematic lighting, detailed
- Content must be strictly Safe For Work
- If the user description contains inappropriate content, reinterpret it as
  a positive, constructive vision
- Do NOT add quotes, explanations, or commentary — output ONLY the prompt
```

Ce fichier est le "cerveau" du pipeline. C'est lui qui détermine la qualité des images générées. Chaque règle a un rôle précis :

- **"Write in ENGLISH only"** : Z-Image Turbo comprend mieux l'anglais que le français pour les descriptions visuelles. Les modèles de génération d'images sont entraînés principalement sur des données anglophones.
- **"40 to 80 words"** : trop court = image vague. Trop long = le modèle se perd dans les détails contradictoires. 40-80 mots est le sweet spot pour Z-Image Turbo.
- **"describe lighting, colors, camera angle, atmosphere, time of day"** : les modèles de génération d'images sont très sensibles à ces éléments. Un prompt qui dit "golden hour light, aerial view, warm Mediterranean tones" donne des résultats bien meilleurs qu'un prompt vague.
- **"Always include recognizable Marseille elements"** : ancre l'image dans Marseille. Sans ça, le LLM pourrait générer un prompt générique "futuristic city" sans identité locale.
- **"End with quality tags"** : les tags comme "photorealistic, 4k, cinematic lighting" sont des "boosters" de qualité pour les modèles de diffusion. Ils activent certains patterns appris pendant l'entraînement.
- **"output ONLY the prompt"** : sans ça, le LLM ajouterait des commentaires comme "Here's the prompt:" ou "I hope this helps!" qui pollueraient le prompt d'image.

**Le placeholder `{category}`** est remplacé dynamiquement par le label anglais de la thématique dans `llm_client.py` (par exemple "Transportation and Mobility"). C'est un simple `str.replace()`, pas un template engine. Ça marche parce qu'il n'y a qu'un seul placeholder.

**Point d'attention pour Rooney** : si tu modifies ce fichier, le LLM peut se comporter très différemment. Un petit changement de formulation peut avoir un grand impact. Teste toujours avec plusieurs descriptions et catégories après chaque modification.

---

## 5. Partie Aida — Clients GPU, Filtre SFW et Tests

Aida est responsable des clients qui communiquent avec le serveur GPU (STT, LLM, Image), du filtre de sécurité, et des tests d'intégration.

### 5.1. `backend/services/stt_client.py` — Le client Speech-to-Text

```python
async def transcribe_audio(audio_bytes: bytes, filename: str, content_type: str) -> str:
    async with httpx.AsyncClient(timeout=settings.STT_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.GPU_URL}/api/speech-to-text",
            headers={"Authorization": f"Bearer {settings.GPU_TOKEN}"},
            files={"file": (filename, audio_bytes, content_type)},
        )
        resp.raise_for_status()
        text = resp.json()["text"]
    return text
```

**`async with httpx.AsyncClient(...) as client`** : crée un client HTTP asynchrone avec un context manager. Le `async with` garantit que la connexion est fermée proprement après l'appel, même en cas d'erreur. Le `timeout=settings.STT_TIMEOUT` (30s) s'applique à toute la requête (connexion + envoi + attente de réponse).

**`files={"file": (filename, audio_bytes, content_type)}`** : envoie le fichier en multipart/form-data. Le tuple `(filename, data, mime_type)` est le format attendu par httpx. Le nom du champ est `"file"` parce que c'est ce que l'API Whisper du serveur GPU attend.

**`resp.raise_for_status()`** : si le serveur retourne un code d'erreur (400, 500, etc.), cette ligne lève une exception `httpx.HTTPStatusError`. Sans ça, on continuerait avec une réponse d'erreur et `resp.json()["text"]` planterait avec un `KeyError`.

**`resp.json()["text"]`** : parse la réponse JSON et extrait le champ `"text"`. Le format de réponse dépend de l'API Whisper du serveur GPU. Si le serveur change son format de réponse (par exemple `"transcription"` au lieu de `"text"`), il faudra adapter cette ligne.

**Le test standalone (lignes 47-66) :**

```python
if __name__ == "__main__":
    # ...
    asyncio.run(_test())
```

`if __name__ == "__main__"` permet d'exécuter le fichier directement avec `python stt_client.py test.m4a` pour tester sans lancer tout le serveur FastAPI. `asyncio.run()` lance la boucle d'événements pour exécuter la coroutine asynchrone. Ce pattern est présent dans les 3 clients et c'est très utile pour tester isolément.

### 5.2. `backend/services/llm_client.py` — Le client LLM

**Le dictionnaire de catégories :**

```python
CATEGORY_LABELS: dict[str, str] = {
    "se_loger": "Housing and Urban Living",
    "se_deplacer": "Transportation and Mobility",
    "manger": "Food, Agriculture, and Dining",
    "se_divertir": "Entertainment, Leisure, and Culture",
    "acces_nature": "Nature, Green Spaces, and Environment",
    "travailler": "Work, Economy, and Innovation",
}
```

Ce dictionnaire traduit les clés de l'enum `Category` en labels anglais descriptifs. Ces labels sont injectés dans le system prompt à la place de `{category}`. Le choix d'utiliser des labels longs et descriptifs (plutôt que juste le nom) aide le LLM à comprendre le contexte thématique.

**Le chargement du system prompt :**

```python
_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "enrich_system.txt"

def _load_system_prompt(category: str) -> str:
    category_label = CATEGORY_LABELS.get(category, "General")
    try:
        template = _PROMPT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("enrich_system.txt introuvable, utilisation du prompt par défaut")
        template = "..."  # fallback hardcodé
    return template.replace("{category}", category_label)
```

`Path(__file__).parent.parent / "prompts" / "enrich_system.txt"` construit le chemin relatif au fichier actuel : `__file__` = `services/llm_client.py`, `.parent` = `services/`, `.parent` = `backend/`, `/ "prompts"` = `backend/prompts/`. C'est plus robuste que `"../prompts/enrich_system.txt"` parce que ça ne dépend pas du CWD.

**Le fallback hardcodé** : si `enrich_system.txt` n'existe pas (par exemple si Rooney n'a pas encore committé son fichier), le code ne plante pas. Il utilise un prompt par défaut. Ce pattern protège contre les problèmes de synchronisation dans l'équipe.

**`.get(category, "General")`** : si la catégorie n'existe pas dans le dictionnaire (ne devrait pas arriver grâce à l'enum, mais sécurité), on utilise "General".

**Le mécanisme de fallback du LLM :**

```python
async def enrich_prompt(text: str, category: str) -> str:
    system_prompt = _load_system_prompt(category)
    model = settings.LLM_MODEL  # llama3.1:8b

    try:
        return await _call_llm(system_prompt, text, model)
    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
        if model != settings.LLM_MODEL_FALLBACK:
            logger.warning("LLM %s échoué, fallback sur %s", model, settings.LLM_MODEL_FALLBACK)
            return await _call_llm(system_prompt, text, settings.LLM_MODEL_FALLBACK)
        raise
```

L'algorithme : on essaie d'abord le modèle principal (llama3.1:8b, plus puissant). S'il échoue (timeout ou erreur HTTP), on essaie le fallback (llama3.2:1b, plus rapide mais moins bon). Si le fallback échoue aussi, on propage l'exception au pipeline (qui utilisera le texte brut, voir section 3.4).

**Pourquoi on ne catch que `httpx.TimeoutException` et `httpx.HTTPStatusError`** : ce sont les deux types d'erreur qui signifient "le serveur GPU a un problème temporaire". D'autres exceptions (comme `ConnectionError`) signifieraient un problème plus grave (réseau coupé) et on les laisse remonter.

**La condition `if model != settings.LLM_MODEL_FALLBACK`** : empêche une boucle infinie. Si les deux modèles sont configurés avec la même valeur, on ne tente pas le fallback (ce serait la même requête).

**L'appel HTTP au LLM :**

```python
async def _call_llm(system_prompt: str, user_text: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.GPU_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GPU_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.7,
                "max_tokens": 300,
            },
        )
```

L'endpoint `/v1/chat/completions` suit le format de l'API OpenAI. Le serveur GPU expose cette API (probablement via vLLM ou Ollama). Le format `messages` avec `system` et `user` est standard pour les LLMs conversationnels :

- **`system`** : les instructions (le system prompt de Rooney). Le LLM le traite comme des règles à suivre.
- **`user`** : le texte de l'utilisateur (la description en français).

**`temperature: 0.7`** : contrôle la "créativité" du LLM. 0 = déterministe (toujours la même réponse), 1 = très créatif (réponses variées mais parfois incohérentes). 0.7 est un bon équilibre pour de la rédaction de prompts : assez créatif pour des descriptions visuelles variées, pas trop pour rester cohérent.

**`max_tokens: 300`** : limite la longueur de la réponse. Un prompt de 40-80 mots fait environ 60-120 tokens. 300 tokens laissent une marge confortable. Sans cette limite, le LLM pourrait générer un texte très long.

**L'extraction de la réponse :**

```python
result = resp.json()["choices"][0]["message"]["content"].strip()
```

Le format de réponse OpenAI est :

```json
{
  "choices": [
    {
      "message": {
        "content": "le texte généré ici..."
      }
    }
  ]
}
```

`["choices"][0]` prend la première (et seule) réponse. `["message"]["content"]` extrait le texte. `.strip()` enlève les espaces et retours à la ligne en début/fin.

### 5.3. `backend/services/image_client.py` — Le client de génération d'image

```python
async def generate_image(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=settings.IMAGE_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.GPU_URL}/api/prompt-to-image",
            json={
                "prompt": prompt,
                "model": settings.IMAGE_MODEL,
                "width": settings.IMAGE_WIDTH,
                "height": settings.IMAGE_HEIGHT,
            },
        )
        resp.raise_for_status()
        image_b64 = resp.json()["images"][0]
    return image_b64
```

Le timeout est plus long ici (90s vs 30s) parce que la génération d'image est l'opération la plus coûteuse. Le modèle Z-Image Turbo est un modèle de diffusion qui génère des images pixel par pixel.

**`resp.json()["images"][0]`** : l'API retourne une liste d'images (on pourrait demander plusieurs variantes), on prend la première. L'image est en base64, donc c'est une string qui représente les données binaires PNG encodées.

**Le test standalone :**

```python
img_data = base64.b64decode(b64)
with open("test_output.png", "wb") as f:
    f.write(img_data)
```

Le test décode le base64 et sauvegarde le fichier PNG pour vérification visuelle. `base64.b64decode` convertit la string en bytes, puis on écrit les bytes dans un fichier. C'est utile pour vérifier que l'API fonctionne sans avoir à lancer tout le frontend.

### 5.4. `backend/services/sfw_filter.py` — Le filtre de sécurité

```python
import re

BLOCKED_FR: list[str] = [
    "nu", "nue", "nus", "nues", "sexe", "sexuel", "sexuelle",
    "pornographique", "érotique", "prostitu",
    "violence", "violent", "meurtre", "sang", "sanglant",
    "arme", "fusil", "bombe", "explosif",
    "drogue", "nazi", "raciste", "terroriste", "génocide",
    "suicide", "torture",
]
```

**Pourquoi des listes séparées FR/EN :** le texte d'entrée est en français (saisi par l'utilisateur), mais le prompt enrichi est en anglais (généré par le LLM). Le filtre est appliqué sur les deux, donc il faut couvrir les deux langues.

**Pourquoi `"prostitu"` et pas `"prostitution"` :** le préfixe `"prostitu"` capture toutes les formes : prostitution, prostitué, prostituée, prostituées, etc. Combiné avec `\b` (word boundary), ça matche `"prostitu"` comme début de mot.

Même logique pour `"prostitut"` côté anglais qui matche prostitute, prostitution, etc.

**L'algorithme de détection :**

```python
def check_sfw(text: str) -> tuple[bool, str | None]:
    lower = text.lower()
    for word in ALL_BLOCKED:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return False, word
    return True, None
```

Ligne par ligne :

1. `lower = text.lower()` : convertit en minuscules pour une comparaison insensible à la casse ("NAZI" = "nazi")
2. `for word in ALL_BLOCKED` : parcourt chaque mot interdit
3. `re.escape(word)` : échappe les caractères spéciaux regex dans le mot (par exemple `é` n'a pas besoin d'échappement, mais c'est une bonne pratique)
4. `r"\b" + re.escape(word) + r"\b"` : construit un pattern regex avec des limites de mot. `\b` est un "word boundary" : il matche la frontière entre un caractère de mot `[a-zA-Z0-9_]` et un caractère de non-mot
5. `re.search(...)` : cherche le pattern n'importe où dans le texte (pas seulement au début)
6. Si trouvé : retourne `(False, mot)` — le texte est bloqué, et on sait quel mot a causé le blocage
7. Si rien trouvé après tous les mots : retourne `(True, None)` — le texte est safe

**Le piège de `\b` avec les caractères accentués :** `\b` en Python considère que les lettres accentuées (é, è, ê, etc.) sont des caractères de mot. Donc `\bérotique\b` matche "érotique" mais PAS "nérotique" (si ça existait), ce qui est le comportement voulu.

**ATTENTION :** `\b` ne fonctionne PAS avec les apostrophes. En français, "l'arme" contient "arme" mais l'apostrophe est un word boundary. Donc `\barme\b` matche dans "l'arme". C'est le comportement souhaité ici.

**Pourquoi ce filtre n'est PAS suffisant seul :** c'est une blocklist basique. Un utilisateur malin pourrait contourner avec des fautes d'orthographe ("v1olence"), du leet speak ("s3xe"), ou des synonymes. Le system prompt du LLM contient aussi une instruction SFW, ce qui ajoute une deuxième couche. En production, un filtre ML (comme le modèle de modération d'OpenAI) serait plus robuste.

### 5.5. `tests/test_clients.py` — Les tests

**Le conftest.py :**

```python
# tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
```

Ce fichier est exécuté automatiquement par pytest avant les tests. Il ajoute le dossier `backend/` au `sys.path` Python, ce qui permet d'écrire `from services.llm_client import ...` sans préfixe. Sans ça, Python ne trouverait pas le module `services` parce que les tests sont dans `tests/` et pas dans `backend/`.

**`sys.path.insert(0, ...)` avec l'index 0 :** le `0` signifie "ajouter au DÉBUT du path". Python cherche les modules dans l'ordre du path. En mettant `backend/` en premier, on s'assure que nos modules sont trouvés avant d'éventuels modules système du même nom.

**Les tests SFW (toujours passants) :**

```python
class TestSFWFilter:
    def test_clean_text_passes(self):
        ok, word = check_sfw("Des jardins sur les toits de Marseille")
        assert ok is True
        assert word is None

    def test_partial_word_not_blocked(self):
        ok, word = check_sfw("Le stade de l'arsenal est magnifique")
        assert ok is True
```

Ces tests sont **purement locaux** — ils n'appellent aucun serveur. Ils vérifient la logique du filtre. Le test `test_partial_word_not_blocked` est particulièrement important : il vérifie que le `\b` fonctionne correctement et que "arsenal" n'est pas bloqué par "arme".

**Les tests LLM et Image (nécessitent le GPU) :**

```python
class TestLLMClient:
    @pytest.mark.asyncio
    async def test_enrich_returns_english(self):
        result = await enrich_prompt(
            "Des tramways solaires sur la Canebière", "se_deplacer"
        )
        assert len(result) > 20
        lower = result.lower()
        assert any(w in lower for w in ["marseille", "futuristic", "solar", "tram", "street"])
```

**`@pytest.mark.asyncio`** : nécessaire pour les tests async. Sans ce décorateur, pytest ne sait pas qu'il faut exécuter la fonction avec `asyncio`. C'est fourni par le package `pytest-asyncio`.

Le test vérifie que :

1. La réponse fait plus de 20 caractères (pas vide)
2. La réponse contient au moins un mot attendu (preuve que le LLM a bien compris le contexte)

**`any(w in lower for w in [...])` :** c'est un générateur Python qui vérifie si AU MOINS UN des mots est présent dans le résultat. `any()` court-circuite : dès qu'il trouve un `True`, il s'arrête.

**Point d'attention :** ces tests d'intégration appellent le VRAI serveur GPU. Ils échouent si le serveur est down, lent, ou si le token a changé. Ce n'est pas un bug, c'est voulu — ce sont des tests d'intégration, pas des tests unitaires. Pour les lancer : `python -m pytest tests/ -v` depuis la racine du projet.

---

## 6. Comment les parties se connectent entre elles

### Rooney → Romain

Le frontend (Rooney) appelle le backend (Romain) via `fetch("/api/pipeline", { method: "POST", body: formData })`. Le contrat d'interface est :

- **Entrée** : `FormData` avec les champs `category` (obligatoire), `audio` (optionnel), `text` (optionnel)
- **Sortie** : JSON conforme au schéma `PipelineResponse`
- **Erreurs** : JSON avec un champ `detail` (format FastAPI par défaut)

Si Rooney change le nom d'un champ dans le `FormData` (par exemple `"cat"` au lieu de `"category"`), le backend retourne 422. Si Romain change le schéma de la réponse, le JS de Rooney n'affichera plus les bonnes données (mais ne plantera pas grâce à `data.xxx || "fallback"`).

Les valeurs du `<select>` HTML ("se_loger", "se_deplacer"...) doivent correspondre EXACTEMENT aux valeurs de l'enum `Category` dans `schemas.py`. C'est le point de couplage le plus fragile.

### Romain → Aida

Le pipeline (Romain) appelle les services (Aida) via des fonctions Python directes :

- `await transcribe_audio(audio_bytes, filename, content_type)` → retourne `str`
- `await enrich_prompt(text, category)` → retourne `str`
- `check_sfw(text)` → retourne `tuple[bool, str | None]`
- `await generate_image(prompt)` → retourne `str` (base64)

Le contrat est simple : chaque fonction prend des strings/bytes et retourne des strings. Les erreurs sont propagées via des exceptions (que le pipeline gère avec try/except).

### Rooney → Aida (indirect)

Le system prompt de Rooney (`enrich_system.txt`) est utilisé par le client LLM d'Aida. Le lien est le placeholder `{category}` qui est remplacé par `llm_client.py`. Si Rooney change le placeholder (par exemple `{{category}}` avec doubles accolades), le `str.replace()` dans `llm_client.py` ne fonctionnera plus.

### Le dictionnaire CATEGORY_LABELS

Ce dictionnaire dans `llm_client.py` est un point de synchronisation entre les 3 parties :

- Les clés ("se_loger", etc.) doivent correspondre à l'enum de Romain
- Les valeurs ("Housing and Urban Living", etc.) sont injectées dans le prompt de Rooney
- Le tout est utilisé par le code d'Aida

Si quelqu'un ajoute une catégorie, il faut modifier : l'enum dans `schemas.py`, le dictionnaire dans `llm_client.py`, le `<select>` dans `index.html`, et le `CATEGORY_NAMES` dans `app.js`.

---

## 7. Flux complet d'une requête — du clic au pixel

Voici le voyage complet d'une requête, avec les fichiers et fonctions traversés :

```
1. L'utilisateur tape "Des tramways solaires" et choisit "Se déplacer"
   📂 frontend/app.js → runPipeline()

2. Le JS construit un FormData et fait un fetch POST
   📂 frontend/app.js → fetch("/api/pipeline", { body: formData })

3. FastAPI reçoit la requête et la route vers le pipeline
   📂 backend/main.py → app.include_router(pipeline_router)
   📂 backend/routers/pipeline.py → async def pipeline(audio, text, category)

4. Le texte est extrait (pas d'audio ici)
   📂 backend/routers/pipeline.py → original_text = text.strip()

5. Filtre SFW passe 1 — texte OK
   📂 backend/services/sfw_filter.py → check_sfw("Des tramways solaires")
   → (True, None)

6. Enrichissement via LLM
   📂 backend/services/llm_client.py → enrich_prompt("Des tramways solaires", "se_deplacer")
   📂 backend/services/llm_client.py → _load_system_prompt("se_deplacer")
   📂 backend/prompts/enrich_system.txt → template avec {category} = "Transportation and Mobility"
   📂 backend/services/llm_client.py → _call_llm(system_prompt, text, "llama3.1:8b")
   → HTTP POST vers 37.26.187.4:8000/v1/chat/completions
   → Réponse: "Futuristic Marseille La Canebière boulevard with sleek solar-powered
     trams gliding along tree-lined tracks, photorealistic, 4k, cinematic lighting"

7. Filtre SFW passe 2 — prompt enrichi OK
   📂 backend/services/sfw_filter.py → check_sfw("Futuristic Marseille...")
   → (True, None)

8. Génération de l'image
   📂 backend/services/image_client.py → generate_image("Futuristic Marseille...")
   → HTTP POST vers 37.26.187.4:8000/api/prompt-to-image
   → Réponse: "iVBORw0KGgo..." (base64 PNG, ~2 Mo de texte)

9. Construction de la réponse
   📂 backend/routers/pipeline.py → PipelineResponse(
       image_base64="iVBORw0KGgo...",
       prompt_original="Des tramways solaires",
       prompt_enriched="Futuristic Marseille...",
       category="se_deplacer",
       source="text",
       generation_time_seconds=14.2
   )

10. Le JS reçoit le JSON et affiche le résultat
    📂 frontend/app.js → showResult(data)
    → resultImage.src = "data:image/png;base64,iVBORw0KGgo..."
    → L'image s'affiche dans le navigateur
```

Temps total typique : 10-20 secondes (dont ~2s pour le LLM et ~10-15s pour l'image).

---

## 8. Pièges, bugs courants et points d'attention

### Pour tout le monde

**Le serveur GPU peut être down.** L'IP 37.26.187.4 est un serveur externe qu'on ne contrôle pas. Si les tests échouent ou si l'app ne fonctionne pas, vérifier d'abord le healthcheck : `curl http://localhost:3000/api/health`. Si `gpu_server_reachable: false`, le problème n'est pas dans notre code.

**Le fichier `.env` est relatif au CWD.** Si on lance `uvicorn` depuis la racine du projet au lieu de `backend/`, pydantic-settings ne trouvera pas le `.env` (il cherche dans le CWD). Toujours lancer depuis `backend/` en dev local, ou mettre le `.env` à la racine et dans `backend/`.

**Les catégories sont couplées en 4 endroits.** Si on ajoute/modifie une catégorie, il faut synchroniser : `schemas.py` (enum), `llm_client.py` (CATEGORY_LABELS), `index.html` (select options), `app.js` (CATEGORY_NAMES).

### Pour Romain

**Le mount statique DOIT être le dernier.** Si tu ajoutes un nouveau router, mets-le AVANT le `app.mount("/", ...)` dans `main.py`. Sinon les nouvelles routes seront interceptées par StaticFiles.

**`--reload` ne doit PAS être en production.** Le flag `--reload` de uvicorn surveille les changements de fichiers et redémarre le serveur. En production ça consomme des ressources inutilement et peut causer des interruptions.

**Le CORS `allow_origins=["*"]` est trop permissif.** Pour la production, il faudrait mettre le domaine exact de l'application.

**`docker-compose` v2 vs v3.** La syntaxe `env_file: - path: .env, required: false` est spécifique à docker-compose v2+. Si quelqu'un a une ancienne version, ça peut planter.

### Pour Rooney

**Les valeurs du `<select>` sont le contrat avec le backend.** Ne jamais les changer sans synchroniser avec `schemas.py`. Un underscore oublié casse le formulaire.

**L'image en base64 est lourde.** Une image 1024x1024 en base64 fait 2-4 Mo dans le JSON. Si tu ajoutes un gallery mode ou un historique, ça va manger la RAM du navigateur très vite.

**`MediaRecorder` n'a pas le même codec sur tous les navigateurs.** Chrome produit du WebM/Opus, Safari du MP4/AAC. Le backend (Whisper) doit supporter les deux. Si un utilisateur a un problème de transcription sur Safari, c'est probablement un problème de codec.

**Le `fetch` n'a pas de timeout.** Si le serveur GPU met 2 minutes à répondre, l'utilisateur voit le spinner tourner sans fin. Il faudrait ajouter un `AbortController` avec un timeout de ~60s.

**Attention au double-clic.** Le bouton est désactivé pendant la requête (`btnGenerate.disabled = true`), mais entre le clic et la désactivation, un double-clic rapide pourrait lancer deux requêtes. En pratique ce n'est pas grave (le serveur gère), mais pour un produit fini il faudrait un debounce.

### Pour Aida

**`httpx.AsyncClient` crée une nouvelle connexion à chaque appel.** Chaque `async with httpx.AsyncClient(...) as client:` ouvre et ferme une connexion TCP. Pour un MVP c'est OK, mais en production il faudrait un client partagé (singleton) qui réutilise les connexions (HTTP keep-alive). Ça réduirait la latence d'environ 50-100ms par appel.

**Le timeout est pour TOUTE la requête.** `timeout=90.0` dans le client image inclut : connexion TCP, envoi de la requête, attente de la réponse, et réception du body. Si le serveur GPU met 85s pour générer l'image, il reste seulement 5s pour le transfert du résultat.

**Le filtre SFW parcourt la liste entière à chaque appel.** Avec ~40 mots, c'est instantané. Mais si on ajoute 10 000 mots, il faudrait passer à un set ou un pattern regex compilé unique (au lieu de `re.search` en boucle).

**Les tests d'intégration sont non-déterministes.** Le LLM peut donner des réponses différentes à chaque appel (temperature=0.7). Un test qui passe aujourd'hui peut échouer demain si le LLM donne une réponse inhabituelle. Le `assert any(w in lower for w in [...])` est volontairement large pour gérer cette variabilité.

**`resp.json()["images"][0]` plantera si le format change.** Si le serveur GPU change son API (par exemple `"image"` au lieu de `"images"`, ou un objet au lieu d'un tableau), cette ligne lèvera un `KeyError` ou `IndexError`. Il faudrait ajouter une validation plus robuste ou utiliser Pydantic pour parser la réponse.

---

*Ce guide a été rédigé en mars 2026 pour le MVP Phase 1 de Futures War.*
