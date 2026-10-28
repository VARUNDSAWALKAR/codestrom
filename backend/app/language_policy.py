"""One approval policy for production submission and advertised availability."""
from .config import Settings

# Translation capability alone does not establish voice support or human approval.
PRODUCTION_CAPABLE = frozenset({"en", "hi", "kn"})


def approved_languages(settings: Settings) -> frozenset[str]:
    capable = PRODUCTION_CAPABLE if approved_voices(settings, "kn") else PRODUCTION_CAPABLE - {"kn"}
    return frozenset(settings.approved_languages) & capable


def approved_voices(settings: Settings, language: str) -> tuple[str, ...]:
    """Kannada approval covers Suresh/21 only; Anu has no recorded approval."""
    if language in {"en", "hi"}:
        return ("female", "male")
    if (language == "kn" and settings.enable_parler and settings.parler_seed == 21
            and settings.parler_max_new_tokens == 1500):
        return ("male",)
    return ()


def voice_options(settings: Settings, *, mock: bool = False) -> dict:
    from .speech.parler_engine import SEQUENCE_POLICY
    result = {}
    for language in ("en", "hi", "kn"):
        options = []
        for voice in (("female", "male") if mock else approved_voices(settings, language)):
            if mock:
                options.append(dict(voice=voice, speaker=f"Mock {voice}", engine="mock"))
            elif language == "kn":
                options.append(dict(voice=voice, speaker="Suresh", engine="parler", seed=21, seed_policy=SEQUENCE_POLICY))
            else:
                speaker = settings.kokoro_voice_female if voice == "female" else settings.kokoro_voice_male
                options.append(dict(voice=voice, speaker=speaker, engine="kokoro"))
        result[language] = options
    return result
