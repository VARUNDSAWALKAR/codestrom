"""Foundation API response models; lesson models belong in planner/schema.py."""

from typing import Literal

from pydantic import BaseModel, Field

from .config import DeviceProfile, Language


class Readiness(BaseModel):
    ready: bool = False


class NamedReadiness(Readiness):
    name: str


class ParlerReadiness(Readiness):
    enabled: bool


class ModelHealth(BaseModel):
    planner: NamedReadiness
    translator: NamedReadiness
    tts_kokoro: Readiness = Field(default_factory=Readiness)
    tts_parler: ParlerReadiness


class RendererHealth(BaseModel):
    bundle_ready: bool


class HealthResponse(BaseModel):
    ok: bool
    device_profile: DeviceProfile
    offline: bool
    models: ModelHealth
    renderer: RendererHealth
    queue_length: int = Field(ge=0)


class LanguageOption(BaseModel):
    code: Language
    name: str
    native: str
    tier: Literal["core", "bonus"]
    available: bool = False


class LengthOptions(BaseModel):
    min: int = 30
    max: int = 90
    step: int = 15
    default: int = 60


class Defaults(BaseModel):
    language: Language = "en"
    level: Literal["beginner", "intermediate"] = "beginner"
    voice: Literal["female", "male"] = "female"
    speed: float = 1.0


class ConfigResponse(BaseModel):
    languages: list[LanguageOption]
    levels: list[Literal["beginner", "intermediate"]] = ["beginner", "intermediate"]
    target_seconds: LengthOptions
    voices: list[Literal["female", "male"]] = ["female", "male"]
    speeds: list[float] = [0.85, 1.0, 1.15]
    defaults: Defaults


LANGUAGES: tuple[LanguageOption, ...] = (
    LanguageOption(code="en", name="English", native="English", tier="core"),
    LanguageOption(code="hi", name="Hindi", native="हिन्दी", tier="core"),
    LanguageOption(code="kn", name="Kannada", native="ಕನ್ನಡ", tier="core"),
    LanguageOption(code="ta", name="Tamil", native="தமிழ்", tier="bonus"),
    LanguageOption(code="te", name="Telugu", native="తెలుగు", tier="bonus"),
    LanguageOption(code="bn", name="Bengali", native="বাংলা", tier="bonus"),
    LanguageOption(code="mr", name="Marathi", native="मराठी", tier="bonus"),
)
