"""
Speech-to-Text client — appelle le serveur Whisper.
Propriétaire : Aida
"""

import logging

import httpx

from config import settings

logger = logging.getLogger("futures-war.stt")


async def transcribe_audio(audio_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Envoie un fichier audio au serveur Whisper.

    Args:
        audio_bytes: contenu brut du fichier audio
        filename: nom du fichier (ex: "recording.webm")
        content_type: MIME type (ex: "audio/webm", "audio/mp4", "audio/mpeg")

    Returns:
        Le texte transcrit.

    Raises:
        httpx.TimeoutException: si le serveur ne répond pas dans les temps
        httpx.HTTPStatusError: si le serveur retourne une erreur HTTP
    """
    logger.info("STT: envoi de %d bytes (%s, %s)", len(audio_bytes), filename, content_type)

    async with httpx.AsyncClient(timeout=settings.STT_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.GPU_URL}/api/speech-to-text",
            headers={"Authorization": f"Bearer {settings.GPU_TOKEN}"},
            files={"file": (filename, audio_bytes, content_type)},
        )
        resp.raise_for_status()
        text = resp.json()["text"]

    logger.info("STT: transcription reçue (%d caractères)", len(text))
    return text


# --- Test standalone ---
if __name__ == "__main__":
    import asyncio
    import sys

    async def _test():
        if len(sys.argv) < 2:
            print("Usage: python stt_client.py <audio_file>")
            print("Exemple: python stt_client.py test.m4a")
            return
        filepath = sys.argv[1]
        # Déduire le MIME type
        ext = filepath.rsplit(".", 1)[-1].lower()
        mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "webm": "audio/webm"}
        content_type = mime_map.get(ext, f"audio/{ext}")
        with open(filepath, "rb") as f:
            data = f.read()
        result = await transcribe_audio(data, filepath, content_type)
        print(f"Transcription: {result}")

    asyncio.run(_test())
