"""Caption splitting and proportional timing within measured audio beats."""
import re
from ..config import Language
from .schema import Caption

LIMITS = {"en": 90, "hi": 90, "mr": 90, "bn": 85, "kn": 80, "te": 80, "ta": 75}


def chunks(text: str, language: Language) -> list[str]:
    text = " ".join(text.split())
    limit = LIMITS[language]
    if not text:
        raise ValueError("Cannot caption empty narration")
    if len(text) <= limit:
        return [text]
    for pattern in (r"(?<=[.!?।])\s+", r"(?<=,)\s+"):
        pieces = re.split(pattern, text)
        if len(pieces) > 1:
            return [part for piece in pieces for part in chunks(piece, language)]
    spaces = [i for i, c in enumerate(text) if c.isspace()]
    if not spaces:
        raise ValueError("Caption contains a word longer than its script limit")
    split = min(spaces, key=lambda i: abs(i - len(text) / 2))
    return chunks(text[:split], language) + chunks(text[split + 1:], language)


def build_captions(text: str, language: Language, start: int, end: int) -> list[Caption]:
    parts = chunks(text, language)
    duration = end - start
    if duration < len(parts):
        raise ValueError("Beat has too few frames for nonempty captions")
    total = sum(map(len, parts))
    used = 0
    previous = start
    result = []
    for i, part in enumerate(parts):
        used += len(part)
        boundary = end if i == len(parts) - 1 else min(end - (len(parts) - i - 1),
                    max(previous + 1, start + round(duration * used / total)))
        result.append(Caption(text=part, start_frame=previous, end_frame=boundary))
        previous = boundary
    return result
