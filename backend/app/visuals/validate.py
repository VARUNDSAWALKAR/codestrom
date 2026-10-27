"""Source-aware validation. Valid JSON is not a certificate of scientific truth."""
from __future__ import annotations

import hashlib
import json
import re
from pydantic import Field, ValidationError
from ..planner.schema import Lesson, Scene
from .schema import (Boundary, VisualSpec, SceneVisual, ASSET_VERSION,
                     CAPABILITY_VERSION, PROMPT_VERSION, SEMANTICS_VERSION)

# Nothing is licensed/implemented yet. Proposed asset names are documentation only.
APPROVED_ASSETS: frozenset[str] = frozenset()
PROVISIONAL_ASSETS = ('sun_icon', 'cloud_icon', 'plant_icon')


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_fingerprint(lesson: Lesson) -> str:
    if lesson.language != 'en':
        raise ValueError('canonical_required: pass the canonical English plan')
    return fingerprint(lesson.model_dump(mode='json'))


def beats(scene: Scene) -> list[str]:
    return ([f'{scene.id}.intro'] if scene.narration.strip() else []) + [
        f'{scene.id}.step{i}' for i in range(len(scene.steps))]


class Diagnostic(Boundary):
    code: str
    scene_id: str = ''
    path: str = ''
    message: str


class ValidationResult(Boundary):
    spec: VisualSpec | None = None
    fallback: bool = True
    diagnostics: list[Diagnostic] = Field(default_factory=list)


def safe_text(text: str) -> None:
    if (re.search(r'<\s*[/!?a-zA-Z]|(?:[a-zA-Z][a-zA-Z0-9+.-]*://)|(?:data|javascript|file):|[A-Za-z]:[\\/]|\\\\|(?:^|\s)/(?:[\w.-]+/)', text)
            or re.search(r'(?:^|\s)(?:\.{1,2}[\\/]|~[\\/]|/\S)', text)
            or re.search(r'\b(?:eval|exec|compile|__import__|subprocess)\s*\(|dangerouslySetInnerHTML', text)
            or any(ord(c) < 32 for c in text)):
        raise ValueError('unsafe_text: markup, code, paths and URLs are forbidden')


def bounds(obj) -> tuple[float, float, float, float] | None:
    kind = obj.kind
    if kind == 'group':
        return None
    if kind in {'rectangle', 'text', 'highlight_region', 'asset'}:
        x, y = obj.position.x, obj.position.y
        return x-obj.width/2, y-obj.height/2, x+obj.width/2, y+obj.height/2
    if kind in {'circle', 'ellipse', 'marker'}:
        rx = obj.rx if kind == 'ellipse' else obj.radius * 460 / 1152
        ry = obj.ry if kind == 'ellipse' else obj.radius
        return obj.position.x-rx, obj.position.y-ry, obj.position.x+rx, obj.position.y+ry
    if kind == 'particles':
        xs, ys = [p.x for p in obj.positions], [p.y for p in obj.positions]
        return min(xs)-obj.radius*460/1152, min(ys)-obj.radius, max(xs)+obj.radius*460/1152, max(ys)+obj.radius
    if kind in {'line', 'arrow'}:
        points = [obj.start, obj.end]
        if obj.start == obj.end:
            raise ValueError('degenerate_geometry: zero length line')
    elif kind == 'polygon':
        points = obj.points
        if len({(p.x, p.y) for p in points}) != len(points):
            raise ValueError('degenerate_geometry: repeated polygon vertex')
        def cross(a, b, c):
            return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
        edges = list(zip(points, points[1:]+points[:1]))
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i+1 or (i == 0 and j == len(edges)-1):
                    continue
                ab = (cross(a, b, c), cross(a, b, d))
                cd = (cross(c, d, a), cross(c, d, b))
                if ab[0]*ab[1] <= 0 and cd[0]*cd[1] <= 0:
                    # Also require overlapping bounding boxes for collinear edges.
                    if (max(min(a.x,b.x),min(c.x,d.x)) <= min(max(a.x,b.x),max(c.x,d.x))
                            and max(min(a.y,b.y),min(c.y,d.y)) <= min(max(a.y,b.y),max(c.y,d.y))):
                        raise ValueError('polygon_intersection: polygon must be simple')
        area = sum(a.x*b.y-b.x*a.y for a, b in zip(points, points[1:]+points[:1]))
        if abs(area) < 1e-8:
            raise ValueError('degenerate_geometry: polygon has zero area')
    else:
        points = [obj.start]
        for segment in obj.segments:
            if segment.kind == 'cubic':
                points += [segment.control1, segment.control2]
            points.append(segment.end)
        if all(p == points[0] for p in points):
            raise ValueError('degenerate_geometry: zero length path')
    return min(p.x for p in points), min(p.y for p in points), max(p.x for p in points), max(p.y for p in points)


def _inside(box) -> None:
    if box is not None and (min(box[:2]) < -1e-9 or max(box[2:]) > 1+1e-9):
        raise ValueError('geometry_bounds: object extends beyond content region')


def check_label(label, scene: Scene) -> None:
    if label is None:
        return
    if label.kind == 'literal':
        safe_text(label.text)
        return
    step_fields = {'text', 'note', 'output'}
    if label.field in step_fields:
        if label.step_index is None or label.step_index >= len(scene.steps):
            raise ValueError('text_reference: invalid step index')
        owner = scene.steps[label.step_index]
    else:
        if label.step_index is not None:
            raise ValueError('text_reference: scene field cannot carry step index')
        owner = scene
    value = getattr(owner, label.field)
    if not value or len(value) > (760 if label.field == 'code' else 160):
        raise ValueError('text_reference: empty or excessive source text')
    # code/expression/output remain inert source data, never parsed as markup.
    if label.field not in {'code', 'expression', 'output'}:
        safe_text(value)


def check_scene(visual: SceneVisual, scene: Scene) -> None:
    if visual.scene_id != scene.id:
        raise ValueError('scene_reference: wrong source scene')
    for text in [visual.mechanism, *visual.limitations]:
        safe_text(text)
    if visual.fallback:
        safe_text(visual.fallback.reason)
        return
    objects = {o.id: o for o in visual.objects}
    if len(objects) != len(visual.objects) or len({a.id for a in visual.actions}) != len(visual.actions):
        raise ValueError('duplicate_id: scene-local object/action IDs must be unique')
    children: dict[str, set[str]] = {k: set() for k in objects}
    parents: dict[str, str] = {}
    instances = 0
    for obj in visual.objects:
        safe_text(obj.role)
        check_label(obj.label, scene)
        _inside(bounds(obj))
        instances += len(obj.positions) if obj.kind == 'particles' else 1
        if obj.kind == 'asset' and obj.asset_id not in APPROVED_ASSETS:
            raise ValueError('asset_unapproved: no verified local asset with this ID')
        if obj.kind == 'group':
            if len(set(obj.children)) != len(obj.children):
                raise ValueError('duplicate_child: repeated group membership')
            children[obj.id].update(obj.children)
    if instances > 128:
        raise ValueError('complexity_limit: more than 128 primitive instances')
    seen_relationships = set()
    for rel in visual.relationships:
        if rel.source not in objects or rel.target not in objects or rel.source == rel.target:
            raise ValueError('relationship_reference: missing or self target')
        triple = (rel.kind, rel.source, rel.target)
        if triple in seen_relationships:
            raise ValueError('relationship_duplicate: repeated constraint')
        seen_relationships.add(triple)
        if rel.kind == 'contains':
            children[rel.source].add(rel.target)
        elif rel.kind == 'belongs_to':
            children[rel.target].add(rel.source)
    for parent, ids in children.items():
        for child in ids:
            if child not in objects or child == parent:
                raise ValueError('group_reference: missing or self child')
            if child in parents and parents[child] != parent:
                raise ValueError('multiple_parents: ambiguous containment')
            parents[child] = parent

    def visit(node: str, ancestors: tuple[str, ...]):
        if node in ancestors:
            raise ValueError('containment_cycle: recursive grouping')
        if len(ancestors) > 3:
            raise ValueError('nesting_limit: containment exceeds depth three')
        for child in children[node]:
            visit(child, (*ancestors, node))
    for node in children:
        visit(node, ())

    order = {beat: i for i, beat in enumerate(beats(scene))}
    channels: dict[tuple[str, str], list[tuple]] = {}
    for action in visual.actions:
        if action.target not in objects:
            raise ValueError('action_target: missing object')
        if action.beat_id not in order:
            raise ValueError('beat_reference: unknown scene-local narration beat')
        obj = objects[action.target]
        if obj.kind == 'group':
            raise ValueError('action_group: animate children, not containers')
        states = {}
        if action.kind == 'reveal':
            states['opacity'] = (action.from_opacity, action.to_opacity)
        elif action.kind == 'draw':
            if obj.kind not in {'line', 'arrow', 'path'}:
                raise ValueError('action_compatibility: draw requires stroked geometry')
            states['progress'] = (action.from_progress, action.to_progress)
        elif action.kind == 'move':
            if not hasattr(obj, 'position'):
                raise ValueError('action_compatibility: move requires a positioned object')
            box = bounds(obj)
            for p in (action.from_position, action.to_position):
                dx, dy = p.x-obj.position.x, p.y-obj.position.y
                _inside((box[0]+dx, box[1]+dy, box[2]+dx, box[3]+dy))
            states['position'] = (action.from_position.model_dump(), action.to_position.model_dump())
        elif action.kind == 'highlight':
            states['style'] = (action.from_style, action.to_style)
        elif action.kind == 'transform':
            states['scale'] = (action.from_scale, action.to_scale)
            states['opacity'] = (action.from_opacity, action.to_opacity)
        else:
            path = objects.get(action.path_id)
            if obj.kind != 'marker' or path is None or path.kind != 'path':
                raise ValueError('action_compatibility: trace requires marker and path')
            box = bounds(path)
            r = obj.radius
            _inside((box[0]-r*460/1152, box[1]-r, box[2]+r*460/1152, box[3]+r))
            states['position'] = ((action.path_id, action.from_progress), (action.path_id, action.to_progress))
        for channel, (start, end) in states.items():
            channels.setdefault((action.target, channel), []).append(
                (order[action.beat_id]+action.start, order[action.beat_id]+action.end, start, end))
    for intervals in channels.values():
        intervals.sort(key=lambda x: x[:2])
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                raise ValueError('action_conflict: overlapping writes to object state')
            if current[2] != previous[3]:
                raise ValueError('state_discontinuity: next start must match held final state')


def validate_visuals(candidate: object, source: Lesson) -> ValidationResult:
    """All-or-nothing publication boundary; never mutates the canonical source."""
    try:
        source = Lesson.model_validate(source.model_dump(mode='json'))
        expected = source_fingerprint(source)
        if isinstance(candidate, VisualSpec):
            candidate = candidate.model_dump(mode='json')  # revalidate even model_construct/copy
        raw = json.dumps(candidate, allow_nan=False)
        if len(raw) > 512_000:
            raise ValueError('complexity_limit: candidate exceeds 512 KB')
        spec = VisualSpec.model_validate(candidate)
        if spec.lesson_id != source.lesson_id or spec.source_fingerprint != expected:
            raise ValueError('source_mismatch: stale or unrelated canonical plan')
        p = spec.provenance
        for value in p.model_dump().values():
            safe_text(value)
        # Known producer versions, not a change to the VisualSpec wire schema.
        # Keep v1 authored fixtures and caches valid while isolating VQ1.1 output.
        known = {(PROMPT_VERSION, SEMANTICS_VERSION),
                 ('visual-semantic-p1', 'semantic-composer-v1')}
        if ((p.prompt_version, p.semantics_version) not in known
                or (p.capability_version, p.asset_version) != (CAPABILITY_VERSION, ASSET_VERSION)):
            raise ValueError('version_mismatch: unsupported visual provenance')
        if [s.scene_id for s in spec.scenes] != [s.id for s in source.scenes]:
            raise ValueError('scene_reference: every canonical scene required in source order')
        if sum(len(s.actions) for s in spec.scenes) > 256:
            raise ValueError('complexity_limit: too many lesson actions')
        for visual, scene in zip(spec.scenes, source.scenes):
            check_scene(visual, scene)
        diagnostics = [Diagnostic(code='accuracy_unverified', message='Illustrative geometry; subject review still required')]
        for scene in spec.scenes:
            if scene.actions and all(a.kind in {'reveal', 'highlight'} for a in scene.actions):
                diagnostics.append(Diagnostic(code='limited_visual_mechanism', scene_id=scene.scene_id,
                    message='Only reveal/emphasis actions; review whether the mechanism is actually depicted'))
        diagnostics += [Diagnostic(code=s.fallback.code, scene_id=s.scene_id, message=s.fallback.reason)
                        for s in spec.scenes if s.fallback]
        return ValidationResult(spec=spec, fallback=any(s.fallback for s in spec.scenes), diagnostics=diagnostics)
    except ValidationError as exc:
        return ValidationResult(diagnostics=[Diagnostic(code='schema_invalid', path='.'.join(map(str, e['loc'])),
                                                       message=e['msg'][:200]) for e in exc.errors()[:12]])
    except (ValueError, TypeError, RecursionError) as exc:
        message = str(exc)[:200]
        code = message.split(':', 1)[0] if ':' in message else 'invalid_candidate'
        return ValidationResult(diagnostics=[Diagnostic(code=code, message=message)])
