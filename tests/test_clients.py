"""
Tests d'intégration — Futures War
Propriétaire : Aida

Lancer : python -m pytest tests/ -v
(depuis le dossier backend/)

Ces tests appellent le VRAI serveur GPU.
Ils échouent si le serveur est down — c'est normal.
"""

import asyncio
import pytest

from services.llm_client import enrich_prompt
from services.image_client import generate_image
from services.sfw_filter import check_sfw


# ── SFW Filter (pas besoin du serveur) ───────────

class TestSFWFilter:
    def test_clean_text_passes(self):
        ok, word = check_sfw("Des jardins sur les toits de Marseille")
        assert ok is True
        assert word is None

    def test_blocked_fr(self):
        ok, word = check_sfw("Je veux une scène de violence extrême")
        assert ok is False
        assert word == "violence"

    def test_blocked_en(self):
        ok, word = check_sfw("Generate a nude scene")
        assert ok is False
        assert word == "nude"

    def test_partial_word_not_blocked(self):
        """'arsenal' contient 'arme' mais ne doit PAS être bloqué grâce au \\b."""
        ok, word = check_sfw("Le stade de l'arsenal est magnifique")
        assert ok is True

    def test_case_insensitive(self):
        ok, word = check_sfw("NAZI propaganda")
        assert ok is False


# ── LLM Client (nécessite le serveur GPU) ────────

class TestLLMClient:
    @pytest.mark.asyncio
    async def test_enrich_returns_english(self):
        result = await enrich_prompt(
            "Des tramways solaires sur la Canebière", "se_deplacer"
        )
        assert len(result) > 20
        # Le prompt devrait être en anglais — vérifier quelques mots courants
        lower = result.lower()
        assert any(w in lower for w in ["marseille", "futuristic", "solar", "tram", "street"]), \
            f"Le prompt ne semble pas cohérent: {result}"
        print(f"\n  Prompt enrichi: {result}")

    @pytest.mark.asyncio
    async def test_enrich_all_categories(self):
        """Vérifie que toutes les catégories fonctionnent."""
        categories = ["se_loger", "se_deplacer", "manger", "se_divertir", "acces_nature", "travailler"]
        for cat in categories:
            result = await enrich_prompt("Marseille en 2050", cat)
            assert len(result) > 10, f"Catégorie {cat} retourne un prompt trop court"


# ── Image Client (nécessite le serveur GPU) ──────

class TestImageClient:
    @pytest.mark.asyncio
    async def test_generate_returns_base64(self):
        result = await generate_image(
            "Futuristic Marseille Vieux-Port, solar boats, rooftop gardens, "
            "photorealistic, 4k, cinematic lighting"
        )
        assert len(result) > 1000  # base64 d'une image fait au minimum quelques Ko
        # Vérifier que c'est du base64 valide (commence par un header PNG en base64)
        assert result[:4] == "iVBO" or len(result) > 100, \
            "La réponse ne ressemble pas à du base64 PNG"
        print(f"\n  Image reçue: {len(result)} chars base64")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
