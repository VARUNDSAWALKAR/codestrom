"""Read-only source-label and narration-clock adapters for a future renderer."""
from __future__ import annotations

from ..planner.schema import Lesson
from ..timeline.schema import Timeline, RenderProps
from .schema import Boundary, VisualSpec
from .validate import validate_visuals


class BoundAction(Boundary):
    scene_id: str
    action_id: str
    beat_id: str
    start_frame: float
    end_frame: float


def check_variant(canonical: Lesson, localized: Lesson) -> None:
    def structure(lesson):
        data = lesson.model_dump(mode='json')
        data.pop('language')
        data.pop('warnings')
        data['title'] = '<text>'
        for scene in data['scenes']:
            scene['has_intro'] = bool(scene['narration'].strip())
            for field in ('heading', 'narration', 'subtitle', 'center'):
                scene[field] = '<text>'
            for step in scene['steps']:
                for field in ('text', 'note', 'narration'):
                    step[field] = '<text>'
        return data
    if structure(canonical) != structure(localized):
        raise ValueError('Localized structure or protected metadata mismatch')


def bind_timeline(spec: VisualSpec, canonical: Lesson, localized: Lesson,
                  timeline: Timeline) -> list[BoundAction]:
    if validate_visuals(spec, canonical).spec is None:
        raise ValueError('Invalid canonical visual specification')
    # Existing boundary verifies actual beat inventory and scene/step indexes.
    RenderProps(lesson=localized, timeline=timeline)
    check_variant(canonical, localized)
    if localized.lesson_id != canonical.lesson_id or len(localized.scenes) != len(canonical.scenes):
        raise ValueError('Localized identity mismatch')
    for a, b in zip(canonical.scenes, localized.scenes):
        if (a.id, a.type, len(a.steps), bool(a.narration.strip()), a.code, a.expression,
            a.code_language, a.layout) != (b.id, b.type, len(b.steps), bool(b.narration.strip()),
            b.code, b.expression, b.code_language, b.layout):
            raise ValueError('Localized structure mismatch')
        if [(s.lines, s.output) for s in a.steps] != [(s.lines, s.output) for s in b.steps]:
            raise ValueError('Localized protected fields changed')
    timings = {b.beat_id: b for scene in timeline.scenes for b in scene.beats}
    return [BoundAction(scene_id=s.scene_id, action_id=a.id, beat_id=a.beat_id,
        start_frame=timings[a.beat_id].start_frame+a.start*(timings[a.beat_id].end_frame-timings[a.beat_id].start_frame),
        end_frame=timings[a.beat_id].start_frame+a.end*(timings[a.beat_id].end_frame-timings[a.beat_id].start_frame))
        for s in spec.scenes for a in s.actions]


def resolve_labels(spec: VisualSpec, canonical: Lesson, localized: Lesson) -> tuple[dict[str, str], list[str]]:
    if validate_visuals(spec, canonical).spec is None or localized.lesson_id != canonical.lesson_id:
        raise ValueError('Invalid visual or localized identity')
    check_variant(canonical, localized)
    if [(s.id, s.type, len(s.steps)) for s in canonical.scenes] != [(s.id, s.type, len(s.steps)) for s in localized.scenes]:
        raise ValueError('Localized scene/step mapping changed')
    scenes = {s.id: s for s in localized.scenes}
    labels, warnings = {}, []
    for visual in spec.scenes:
        scene = scenes[visual.scene_id]
        for obj in visual.objects:
            label = obj.label
            if label is None:
                continue
            key = f'{scene.id}.{obj.id}'
            if label.kind == 'literal':
                labels[key] = label.text
                if localized.language != 'en':
                    warnings.append(f'{key}: English supplemental label requires review/localization')
            else:
                owner = scene if label.step_index is None else scene.steps[label.step_index]
                labels[key] = getattr(owner, label.field)
    return labels, warnings
