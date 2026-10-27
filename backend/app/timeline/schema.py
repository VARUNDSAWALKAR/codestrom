"""Timeline v1 and render-props boundary validation (lesson-schema.md §6–7)."""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from ..config import Language
from ..planner.schema import ContractModel, Lesson, SceneType


class Caption(ContractModel):
    text: str = Field(min_length=1)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)


class Beat(ContractModel):
    beat_id: str
    step_index: int | None = Field(default=None, ge=0)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    captions: list[Caption] = Field(min_length=1)

    @model_validator(mode="after")
    def intervals(self) -> Beat:
        previous = self.start_frame
        for caption in self.captions:
            if not previous <= caption.start_frame < caption.end_frame <= self.end_frame:
                raise ValueError("Invalid caption interval")
            previous = caption.end_frame
        if self.start_frame >= self.end_frame:
            raise ValueError("Empty beat interval")
        return self


class SceneTiming(ContractModel):
    scene_id: str
    type: SceneType
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    beats: list[Beat] = Field(min_length=1)


class AudioURLs(ContractModel):
    web: str = Field(pattern=r"^/media/")
    wav: str = Field(pattern=r"^/media/")


class Voice(ContractModel):
    engine: Literal["kokoro", "parler"]
    voice_id: str
    speed: float = Field(ge=0.8, le=1.2)


class Timeline(ContractModel):
    timeline_version: Literal[1] = 1
    lesson_id: str
    language: Language
    variant: str
    fps: Literal[30] = 30
    width: Literal[1280] = 1280
    height: Literal[720] = 720
    duration_frames: int = Field(gt=0)
    audio: AudioURLs | None
    voice: Voice
    tempo: float = Field(default=1.0, ge=1.0, le=1.1)
    scenes: list[SceneTiming] = Field(min_length=1)

    @model_validator(mode="after")
    def intervals(self) -> Timeline:
        end = 0
        seen: set[str] = set()
        for scene in self.scenes:
            if scene.start_frame != end or scene.scene_id in seen:
                raise ValueError("Scenes must be unique and contiguous from frame zero")
            seen.add(scene.scene_id)
            end = scene.start_frame + scene.duration_frames
            previous = scene.start_frame
            ids: set[str] = set()
            for beat in scene.beats:
                suffix = "intro" if beat.step_index is None else f"step{beat.step_index}"
                if beat.beat_id != f"{scene.scene_id}.{suffix}" or beat.beat_id in ids:
                    raise ValueError("Invalid or duplicate beat id")
                ids.add(beat.beat_id)
                if not previous <= beat.start_frame < beat.end_frame <= end:
                    raise ValueError("Beat outside scene or overlapping")
                previous = beat.end_frame
        if end != self.duration_frames:
            raise ValueError("Scene durations do not sum to timeline duration")
        return self


class RenderProps(ContractModel):
    lesson: Lesson
    timeline: Timeline
    mediaBase: str = ""
    audioVariant: Literal["web", "wav"] = "web"
    showCaptions: bool = True

    @model_validator(mode="after")
    def matching_lesson(self) -> RenderProps:
        if (self.lesson.lesson_id != self.timeline.lesson_id or self.lesson.language != self.timeline.language
                or len(self.lesson.scenes) != len(self.timeline.scenes)):
            raise ValueError("Lesson and timeline do not match")
        for scene, timing in zip(self.lesson.scenes, self.timeline.scenes):
            expected = ([None] if scene.narration.strip() else []) + list(range(len(scene.steps)))
            if (scene.id != timing.scene_id or scene.type != timing.type
                    or [b.step_index for b in timing.beats] != expected):
                raise ValueError("Scene/beat mapping mismatch")
        return self
