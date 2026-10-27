"""One approval policy for production submission and advertised availability."""
from .config import Settings

# Translation capability alone does not establish voice support or human approval.
PRODUCTION_CAPABLE = frozenset({"en", "hi", "kn"})


def approved_languages(settings: Settings) -> frozenset[str]:
    capable = PRODUCTION_CAPABLE if settings.enable_parler else PRODUCTION_CAPABLE - {"kn"}
    return frozenset(settings.approved_languages) & capable
