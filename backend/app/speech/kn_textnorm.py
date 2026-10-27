"""Versioned Kannada speech-only normalization. Captions and Lesson remain untouched."""
from .textnorm import normalize_text

KN_NORMALIZATION_VERSION = "kn-speech-v1"


def normalize_kannada(text: str) -> str:
    # Parler supports mixed Indic/Latin transcripts. Do not invent phonetic
    # translations of technical terms or mathematical meaning without review.
    # The established markup cleanup is applied to speech only, as in en/hi.
    return normalize_text(text, "kn")
