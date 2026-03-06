"""
Filtre Safe For Work — blocklist basique FR/EN.
Propriétaire : Aida

Note : c'est un filet de sécurité minimal. Le system prompt du LLM
contient aussi une instruction SFW. Les modèles open-source (z-images)
sont non-censurés, donc cette double protection est nécessaire.
"""

import re

BLOCKED_FR: list[str] = [
    "nu", "nue", "nus", "nues", "sexe", "sexuel", "sexuelle",
    "pornographique", "érotique", "prostitu",
    "violence", "violent", "meurtre", "sang", "sanglant",
    "arme", "fusil", "bombe", "explosif",
    "drogue", "nazi", "raciste", "terroriste", "génocide",
    "suicide", "torture",
]

BLOCKED_EN: list[str] = [
    "nude", "naked", "sex", "sexual", "porn", "erotic", "nsfw",
    "prostitut", "gore", "murder", "blood", "bloody",
    "weapon", "gun", "bomb", "explosive",
    "drug", "nazi", "racist", "terrorist", "genocide",
    "suicide", "torture",
]

ALL_BLOCKED: list[str] = BLOCKED_FR + BLOCKED_EN


def check_sfw(text: str) -> tuple[bool, str | None]:
    """
    Vérifie si le texte est SFW.

    Returns:
        (True, None) si le texte est ok.
        (False, mot_bloqué) si un mot interdit est détecté.
    """
    lower = text.lower()
    for word in ALL_BLOCKED:
        # \b pour éviter les faux positifs (ex: "arsenal" ne matche pas "arme")
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return False, word
    return True, None
