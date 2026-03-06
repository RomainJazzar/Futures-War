"""
Image generation client — appelle Z-Image Turbo via le serveur GPU.
Propriétaire : Aida
"""

import logging

import httpx

from config import settings

logger = logging.getLogger("futures-war.image")


async def generate_image(prompt: str) -> str:
    """
    Génère une image à partir d'un prompt.

    Args:
        prompt: prompt optimisé en anglais

    Returns:
        Image encodée en base64 (PNG).

    Raises:
        httpx.TimeoutException: si la génération dépasse IMAGE_TIMEOUT
        httpx.HTTPStatusError: si le serveur retourne une erreur
    """
    logger.info("IMAGE: génération en cours (prompt: %.80s...)", prompt)

    async with httpx.AsyncClient(timeout=settings.IMAGE_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.GPU_URL}/api/prompt-to-image",
            headers={
                "Authorization": f"Bearer {settings.GPU_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "model": settings.IMAGE_MODEL,
                "width": settings.IMAGE_WIDTH,
                "height": settings.IMAGE_HEIGHT,
            },
        )
        resp.raise_for_status()
        image_b64 = resp.json()["images"][0]

    logger.info("IMAGE: reçue (%d chars base64)", len(image_b64))
    return image_b64


# --- Test standalone ---
if __name__ == "__main__":
    import asyncio
    import base64

    async def _test():
        b64 = await generate_image(
            "Futuristic Marseille Vieux-Port with solar-powered boats, "
            "rooftop gardens on surrounding buildings, Notre-Dame de la Garde "
            "glowing in golden hour light, photorealistic, 4k, cinematic lighting"
        )
        # Sauvegarder l'image pour vérification visuelle
        img_data = base64.b64decode(b64)
        with open("test_output.png", "wb") as f:
            f.write(img_data)
        print(f"Image sauvegardée: test_output.png ({len(img_data)} bytes)")

    asyncio.run(_test())
