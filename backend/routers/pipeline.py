"""
Pipeline router — orchestre le flux Speech/Text → Prompt enrichi → Image.
Propriétaire : Romain
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import Category, PipelineResponse
from services.image_client import generate_image
from services.llm_client import enrich_prompt
from services.sfw_filter import check_sfw
from services.stt_client import transcribe_audio

router = APIRouter(tags=["pipeline"])
logger = logging.getLogger("futures-war.pipeline")


@router.post(
    "/api/pipeline",
    response_model=PipelineResponse,
    summary="Pipeline Speech/Text → Image",
    description=(
        "Accepte un audio (speech-to-text) OU un texte brut, "
        "enrichit le prompt via LLM, génère une image via Z-Image Turbo. "
        "Au moins `audio` ou `text` doit être fourni. Si les deux sont "
        "fournis, `audio` a priorité avec fallback sur `text`."
    ),
)
async def pipeline(
    audio: UploadFile | None = File(None, description="Fichier audio (mp3, wav, m4a, webm)"),
    text: str | None = Form(None, description="Texte brut (fallback si pas d'audio)"),
    category: Category = Form(..., description="Catégorie thématique"),
):
    start = time.time()
    source = "text"

    # ──────────────────────────────────────────────
    # 1. OBTENIR LE TEXTE
    # ──────────────────────────────────────────────
    original_text = None

    if audio is not None:
        audio_bytes = await audio.read()
        if len(audio_bytes) > 0:
            try:
                original_text = await transcribe_audio(
                    audio_bytes, audio.filename or "recording.webm", audio.content_type or "audio/webm"
                )
                source = "speech"
                logger.info("Transcription réussie: %.100s", original_text)
            except Exception as e:
                logger.warning("STT échoué (%s), tentative fallback texte", e)

    if original_text is None and text:
        original_text = text.strip()
        source = "text"

    if not original_text:
        raise HTTPException(
            status_code=400,
            detail="Fournissez un fichier audio ou un texte. Les deux champs sont vides.",
        )

    # ──────────────────────────────────────────────
    # 2. FILTRE SFW — PASS 1 (texte brut)
    # ──────────────────────────────────────────────
    is_sfw, blocked_word = check_sfw(original_text)
    if not is_sfw:
        logger.warning("SFW bloqué (input): mot='%s'", blocked_word)
        raise HTTPException(status_code=451, detail="Contenu modéré. Veuillez reformuler votre description.")

    # ──────────────────────────────────────────────
    # 3. ENRICHISSEMENT DU PROMPT VIA LLM
    # ──────────────────────────────────────────────
    try:
        prompt_enriched = await enrich_prompt(original_text, category.value)
    except Exception as e:
        logger.warning("LLM enrichissement échoué (%s), utilisation du texte brut", e)
        prompt_enriched = original_text  # mode dégradé

    # ──────────────────────────────────────────────
    # 4. FILTRE SFW — PASS 2 (prompt enrichi)
    # ──────────────────────────────────────────────
    is_sfw, blocked_word = check_sfw(prompt_enriched)
    if not is_sfw:
        logger.warning("SFW bloqué (enrichi): mot='%s'", blocked_word)
        raise HTTPException(status_code=451, detail="Le prompt enrichi a été modéré. Veuillez reformuler.")

    # ──────────────────────────────────────────────
    # 5. GÉNÉRATION DE L'IMAGE
    # ──────────────────────────────────────────────
    try:
        image_b64 = await generate_image(prompt_enriched)
    except Exception as e:
        logger.error("Génération image échouée: %s", e)
        raise HTTPException(status_code=503, detail="Serveur de génération indisponible. Réessayez plus tard.")

    # ──────────────────────────────────────────────
    # 6. RÉPONSE
    # ──────────────────────────────────────────────
    elapsed = round(time.time() - start, 1)
    logger.info(
        "Pipeline terminé en %.1fs | source=%s | catégorie=%s",
        elapsed, source, category.value,
    )

    return PipelineResponse(
        image_base64=image_b64,
        prompt_original=original_text,
        prompt_enriched=prompt_enriched,
        category=category.value,
        source=source,
        generation_time_seconds=elapsed,
    )
