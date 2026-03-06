"""
LLM client — enrichissement du prompt via llama3.
Propriétaire : Aida
System prompt : Rooney (fichier prompts/enrich_system.txt)
"""

import logging
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger("futures-war.llm")

# Labels anglais pour les catégories (injectés dans le system prompt)
CATEGORY_LABELS: dict[str, str] = {
    "se_loger": "Housing and Urban Living",
    "se_deplacer": "Transportation and Mobility",
    "manger": "Food, Agriculture, and Dining",
    "se_divertir": "Entertainment, Leisure, and Culture",
    "acces_nature": "Nature, Green Spaces, and Environment",
    "travailler": "Work, Economy, and Innovation",
}

# Chemin vers le system prompt (écrit par Rooney)
_PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "enrich_system.txt"


def _load_system_prompt(category: str) -> str:
    """Charge le system prompt et injecte la catégorie."""
    category_label = CATEGORY_LABELS.get(category, "General")
    try:
        template = _PROMPT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Fallback si Rooney n'a pas encore écrit le fichier
        logger.warning("enrich_system.txt introuvable, utilisation du prompt par défaut")
        template = (
            "You are an expert AI image prompt engineer. "
            "Convert the following French description of a futuristic vision of Marseille "
            "into an optimized English prompt for the Z-Image Turbo model. "
            "Category: {category}. "
            "Rules: English only, one paragraph, 40-80 words, descriptive and visual, "
            "include recognizable Marseille landmarks, end with quality tags "
            "(photorealistic, 4k, cinematic lighting). Must be Safe For Work. "
            "Output ONLY the prompt, nothing else."
        )
    return template.replace("{category}", category_label)


async def enrich_prompt(text: str, category: str) -> str:
    """
    Enrichit un texte brut en prompt optimisé pour Z-Image Turbo.

    Args:
        text: description en français du futur imaginé
        category: clé de catégorie (ex: "se_deplacer")

    Returns:
        Prompt enrichi en anglais.
    """
    system_prompt = _load_system_prompt(category)
    model = settings.LLM_MODEL
    logger.info("LLM: enrichissement avec %s, catégorie=%s", model, category)

    try:
        return await _call_llm(system_prompt, text, model)
    except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
        # Si le 8b échoue, tenter le fallback 1b
        if model != settings.LLM_MODEL_FALLBACK:
            logger.warning("LLM %s échoué (%s), fallback sur %s", model, e, settings.LLM_MODEL_FALLBACK)
            return await _call_llm(system_prompt, text, settings.LLM_MODEL_FALLBACK)
        raise


async def _call_llm(system_prompt: str, user_text: str, model: str) -> str:
    """Appel bas niveau au LLM."""
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
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()

    logger.info("LLM: prompt enrichi (%d chars) via %s", len(result), model)
    return result


# --- Test standalone ---
if __name__ == "__main__":
    import asyncio

    async def _test():
        result = await enrich_prompt(
            "Je voudrais voir des tramways solaires sur la Canebière avec des arbres partout",
            "se_deplacer",
        )
        print(f"Prompt enrichi:\n{result}")

    asyncio.run(_test())
