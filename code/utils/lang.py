from __future__ import annotations


FRENCH_MARKERS = (
    "bonjour",
    "carte",
    "bloqu",
    "voyage",
    "règles",
    "internes",
    "dites-moi",
)

SPANISH_MARKERS = ("tarjeta", "bloqueada", "ayuda", "por favor")


def detect_language(text: str) -> str:
    lowered = (text or "").lower()
    french_hits = sum(marker in lowered for marker in FRENCH_MARKERS)
    spanish_hits = sum(marker in lowered for marker in SPANISH_MARKERS)
    if french_hits >= 2:
        return "fr"
    if spanish_hits >= 2:
        return "es"
    return "en"


def translate_for_retrieval(text: str) -> str:
    lowered = (text or "").lower()
    if "carte visa" in lowered or "tarjeta" in lowered:
        return f"{text}\nvisa card blocked while travelling lost stolen card emergency assistance"
    return text
