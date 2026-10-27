"""Prepare narration for speech without changing the caption text."""
import re
from ..config import Language


def normalize_text(text: str, language: Language) -> str:
    text = re.sub(r'[()\[\]{}<>_*#`|"]', ' ', text)
    text = " ".join(text.split())
    if not text or not any(c.isalnum() for c in text):
        raise ValueError("Narration is empty after normalization")
    if text[-1] not in ".?!।":
        text += "।" if language in {"hi", "mr"} else "."
    return text
