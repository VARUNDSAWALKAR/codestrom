"""Deterministic, context-aware subject classification (no model, no network)."""
from __future__ import annotations

import re
from typing import Literal

RequestSubject = Literal["programming", "science", "other"]

# Unambiguous on their own.
STRONG = ("sort", "sorting", "loop", "loops", "recursion", "recursive", "array", "arrays", "stack",
          "queue", "algorithm", "algorithms", "python", "javascript", "variable", "variables",
          "pointer", "pointers", "data structure", "data structures", "binary search",
          "linear search", "for loop", "while loop")
# Also used outside computing ("tree", "list", "genetic code", "space program"), so they
# only count when no science/math context is present.
AMBIGUOUS = ("search", "list", "tree", "trees", "graph", "graphs", "function", "functions",
             "code", "program", "programs")
SCIENCE = ("water", "photosynthesis", "plant", "plants", "leaf", "leaves", "cell", "cells", "atom",
           "atoms", "molecule", "molecules", "energy", "force", "gravity", "rain", "cloud", "sun",
           "animal", "animals", "ecosystem", "planet", "oxygen", "carbon dioxide", "chemical",
           "chemistry", "physics", "biology", "genetic", "dna", "newton", "electricity", "magnet",
           "volcano", "earth", "weather", "climate", "heart", "equation", "slope", "sunlight")


def _hits(topic: str, words: tuple[str, ...]) -> int:
    pattern = r"\b(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"
    return len(re.findall(pattern, topic.lower()))


def classify_subject(topic: str) -> RequestSubject | None:
    """Return programming/science, or None when the topic is ambiguous or unmatched."""
    strong, ambiguous, science = _hits(topic, STRONG), _hits(topic, AMBIGUOUS), _hits(topic, SCIENCE)
    if strong or (ambiguous and not science):
        return "programming"
    return "science" if science else None


def effective_subject(topic: str, explicit: RequestSubject | None) -> RequestSubject | None:
    """Explicit user choice always wins over keyword classification."""
    return explicit if explicit is not None else classify_subject(topic)
