"""Proposed VisualSpec v1. Data only; no production lesson contract changes."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = 'visual-v1'
PROMPT_VERSION = 'visual-p2'
CAPABILITY_VERSION = 'primitives-v1'
ASSET_VERSION = 'assets-v1-empty'
SEMANTICS_VERSION = 'geometry-actions-v2'
Id = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9_-]{0,31}$')]
Digest = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Text = Annotated[str, StringConstraints(min_length=1, max_length=160)]
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Size = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
Style = Literal['primary', 'secondary', 'accent', 'muted', 'warning', 'highlight']
Layout = Literal['flow_cycle', 'spatial', 'array_grid', 'graph_network',
                 'coordinate_plane', 'comparison', 'code_walkthrough']


class Boundary(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Point(Boundary):
    x: Unit
    y: Unit


class SourceText(Boundary):
    kind: Literal['source']
    field: Literal['heading', 'center', 'expression', 'code', 'text', 'note', 'output']
    step_index: int | None = Field(default=None, ge=0, le=5)


class LiteralText(Boundary):
    kind: Literal['literal']
    text: Text


Label = Annotated[SourceText | LiteralText, Field(discriminator='kind')]


class ObjectBase(Boundary):
    id: Id
    role: Text
    style: Style = 'primary'
    label: Label | None = None


class Rectangle(ObjectBase):
    kind: Literal['rectangle']
    position: Point
    width: Size
    height: Size


class Circle(ObjectBase):
    kind: Literal['circle']
    position: Point
    radius: Annotated[float, Field(gt=0, le=.5)]


class Ellipse(ObjectBase):
    kind: Literal['ellipse']
    position: Point
    rx: Annotated[float, Field(gt=0, le=.5)]
    ry: Annotated[float, Field(gt=0, le=.5)]


class Polygon(ObjectBase):
    kind: Literal['polygon']
    points: list[Point] = Field(min_length=3, max_length=12)


class Line(ObjectBase):
    kind: Literal['line', 'arrow']
    start: Point
    end: Point


class LineSegment(Boundary):
    kind: Literal['line']
    end: Point


class CubicSegment(Boundary):
    kind: Literal['cubic']
    control1: Point
    control2: Point
    end: Point


Segment = Annotated[LineSegment | CubicSegment, Field(discriminator='kind')]


class Path(ObjectBase):
    kind: Literal['path']
    start: Point
    segments: list[Segment] = Field(min_length=1, max_length=8)


class TextLabel(ObjectBase):
    kind: Literal['text']
    position: Point
    label: Label
    width: Size = .25
    height: Size = .12


class Group(ObjectBase):
    kind: Literal['group']
    children: list[Id] = Field(min_length=1, max_length=16)


class Marker(ObjectBase):
    kind: Literal['marker']
    position: Point
    radius: Annotated[float, Field(gt=0, le=.02)] = .008


class Highlight(ObjectBase):
    kind: Literal['highlight_region']
    position: Point
    width: Size
    height: Size


class Particles(ObjectBase):
    kind: Literal['particles']
    positions: list[Point] = Field(min_length=1, max_length=32)
    radius: Annotated[float, Field(gt=0, le=.02)] = .005


class Asset(ObjectBase):
    kind: Literal['asset']
    asset_id: Id
    position: Point
    width: Size
    height: Size


VisualObject = Annotated[Rectangle | Circle | Ellipse | Polygon | Line | Path |
                         TextLabel | Group | Marker | Highlight | Particles | Asset,
                         Field(discriminator='kind')]


class Relationship(Boundary):
    kind: Literal['connected_to', 'contains', 'points_toward', 'aligned_with',
                  'before', 'ordered_with', 'belongs_to', 'depends_on']
    source: Id
    target: Id


class ActionBase(Boundary):
    id: Id
    target: Id
    beat_id: Annotated[str, StringConstraints(pattern=r'^s[1-9][0-9]*\.(intro|step[0-5])$')]
    start: Unit = 0.0
    end: Unit = .6

    @model_validator(mode='after')
    def interval(self):
        if self.start >= self.end:
            raise ValueError('timing_interval: start must be below end')
        return self


class Reveal(ActionBase):
    kind: Literal['reveal']
    from_opacity: Unit = 0.0
    to_opacity: Unit = 1.0


class Draw(ActionBase):
    kind: Literal['draw']
    from_progress: Unit = 0.0
    to_progress: Unit = 1.0


class Move(ActionBase):
    kind: Literal['move']
    from_position: Point
    to_position: Point


class HighlightAction(ActionBase):
    kind: Literal['highlight']
    from_style: Style = 'primary'
    to_style: Style = 'highlight'


class Transform(ActionBase):
    kind: Literal['transform']
    from_scale: Annotated[float, Field(ge=.25, le=1)] = 1.0
    to_scale: Annotated[float, Field(ge=.25, le=1)] = .75
    from_opacity: Unit = 1.0
    to_opacity: Unit = 1.0


class Trace(ActionBase):
    kind: Literal['trace']
    path_id: Id
    from_progress: Unit = 0.0
    to_progress: Unit = 1.0


Action = Annotated[Reveal | Draw | Move | HighlightAction | Transform | Trace,
                   Field(discriminator='kind')]


class Fallback(Boundary):
    code: Literal['legacy_scene', 'unsupported_mechanism', 'source_inaccurate',
                  'invalid_candidate', 'model_unavailable', 'not_selected', 'cache_invalid']
    reason: Text


class SceneVisual(Boundary):
    scene_id: Annotated[str, StringConstraints(pattern=r'^s[1-9][0-9]*$')]
    layout: Layout | None = None
    mechanism: Text
    accuracy: Literal['illustrative', 'legacy'] = 'illustrative'
    limitations: list[Text] = Field(min_length=1, max_length=6)
    objects: list[VisualObject] = Field(default_factory=list, max_length=48)
    relationships: list[Relationship] = Field(default_factory=list, max_length=64)
    actions: list[Action] = Field(default_factory=list, max_length=64)
    fallback: Fallback | None = None

    @model_validator(mode='after')
    def mode(self):
        if self.fallback:
            if self.layout is not None or self.objects or self.relationships or self.actions or self.accuracy != 'legacy':
                raise ValueError('fallback_payload: fallback cannot publish specialized visuals')
        elif self.layout is None or not self.objects or not self.actions or self.accuracy != 'illustrative':
            raise ValueError('empty_visual: specialized scenes need objects, actions and layout')
        return self


class Provenance(Boundary):
    prompt_version: str = PROMPT_VERSION
    model: str
    model_identity: Text
    capability_version: str = CAPABILITY_VERSION
    asset_version: str = ASSET_VERSION
    semantics_version: str = SEMANTICS_VERSION
    configuration_fingerprint: Digest


class VisualSpec(Boundary):
    visual_schema_version: Literal['visual-v1'] = SCHEMA_VERSION
    lesson_id: str
    source_fingerprint: Digest
    provenance: Provenance
    scenes: list[SceneVisual] = Field(min_length=3, max_length=6)
