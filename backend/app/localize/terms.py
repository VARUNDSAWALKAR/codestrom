"""Conservative protected spans; model output is text data, never executed."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import re

MASK_VERSION = "spans-v1-id101"
TOKEN = re.compile(r"<ID\d+>|\[T\d+\]")
ATOM = r"(?:[A-Za-z_][\w.]*[₀-₉⁰-⁹²³]*|[+-]?\d+(?:\.\d+)?)"
PATTERNS = [
    r"`[^`]+`",
    r"\b[A-Za-z_][\w.]*\((?:[^()\n]|\([^()\n]*\))*\)",
    ATOM + r"(?:\s*[=<>+−*/÷×→^]\s*" + ATOM + r")+",
    r"\b[A-Za-z]+(?:/[A-Za-z]+)+[²³⁰-⁹₀-₉]*",
    r"\b[A-Za-z]+[₀-₉⁰-⁹²³]+[A-Za-z₀-₉⁰-⁹²³]*",
    r"(?<!\w)(?:kg|mg|km|cm|mm|ms|Hz|kHz|MHz|kPa|Pa|mol)(?!\w)",
    r"(?<!\w)\d+(?:\.\d+)?\s*(?:kg|mg|km|cm|mm|ms|Hz|kHz|MHz|kPa|Pa|mol|m|s|g|N|J|W|V|A|K)(?!\w)",
    r"^\s*(?:m|s|g|N|J|W|V|A|K)\s*$",
    r"\b(?:[A-Za-z]+_[A-Za-z_0-9]+|[a-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]+\d+[A-Za-z0-9]*)\b",
    r"(?<!\w)[+-]?\d+(?:\.\d+)?(?:%|°[CF])?(?!\w)",
    TOKEN.pattern,
]


def literal_pattern(value: str) -> str:
    return (r"(?<!\w)" if value[0].isalnum() else "") + re.escape(value) + (r"(?!\w)" if value[-1].isalnum() else "")


@dataclass(frozen=True)
class Masked:
    source: str
    masked: str
    spans: tuple[str, ...]
    placeholders: tuple[str, ...]
    prose: str
    fingerprint: str

    @property
    def eligible(self) -> bool:
        return any(c.isalpha() for c in self.prose)


def mask(text: str, terms: list[str]) -> Masked:
    candidates = []
    for pattern in PATTERNS:
        candidates.extend((m.start(), m.end()) for m in re.finditer(pattern, text))
    for term in sorted(set(terms), key=len, reverse=True):
        if term:
            candidates.extend((m.start(), m.end()) for m in re.finditer(literal_pattern(term), text, re.IGNORECASE))
    selected: list[tuple[int, int]] = []
    # Merge overlapping matches: e.g. "9.8 m" and "m/s²" must protect the
    # entire unit expression rather than leaving a translated suffix behind.
    for start, end in sorted(set(candidates)):
        if selected and start < selected[-1][1]:
            selected[-1] = (selected[-1][0], max(selected[-1][1], end))
        else:
            selected.append((start, end))
    # Do not collide with literal placeholder text in a source lesson.
    first = max([100, *[int(re.search(r"\d+", m.group()).group()) for m in TOKEN.finditer(text)]]) + 1
    spans, placeholders, chunks, prose = [], [], [], []
    previous = 0
    for index, (start, end) in enumerate(selected):
        token = f"<ID{first + index}>"
        spans.append(text[start:end])
        placeholders.append(token)
        chunks.extend((text[previous:start], token))
        prose.append(text[previous:start])
        previous = end
    chunks.append(text[previous:])
    prose.append(text[previous:])
    fingerprint = hashlib.sha256(json.dumps([MASK_VERSION, spans, placeholders], ensure_ascii=False).encode()).hexdigest()
    return Masked(text, "".join(chunks), tuple(spans), tuple(placeholders), " ".join(prose), fingerprint)


def protected_verbatim(text: str, item: Masked) -> bool:
    return all(len(re.findall(literal_pattern(span), text)) == len(re.findall(literal_pattern(span), item.source))
               for span in set(item.spans))


def restore(text: str, item: Masked) -> str:
    if any(text.count(token) != 1 for token in item.placeholders):
        raise ValueError("A protected placeholder is missing or duplicated")
    if Counter(TOKEN.findall(text)) != Counter(item.placeholders):
        raise ValueError("Unexpected placeholder in translation")
    for token, span in zip(item.placeholders, item.spans):
        text = text.replace(token, span)
    if not protected_verbatim(text, item):
        raise ValueError("Protected spans changed")
    return text


def outside_protected(text: str, item: Masked) -> str:
    for span in sorted(set(item.spans), key=len, reverse=True):
        text = re.sub(literal_pattern(span), " ", text)
    return text
