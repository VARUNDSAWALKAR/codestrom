"""Independent, checksummed, atomically replaced visual envelopes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from uuid import uuid4
from ..planner.schema import Lesson
from .schema import VisualSpec, Provenance
from .validate import fingerprint, validate_visuals


class CacheInvalid(ValueError):
    pass


class VisualCache:
    def __init__(self, root: Path):
        self.root = (root / 'visuals').resolve()

    def path(self, key: str) -> Path:
        if not re.fullmatch('[0-9a-f]{64}', key):
            raise ValueError('Invalid visual cache key')
        path = (self.root / f'{key}.json').resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Visual cache path escaped root')
        return path

    def read(self, key: str, source: Lesson, provenance: Provenance) -> VisualSpec | None:
        path = self.path(key)
        if not path.is_file():
            return None
        try:
            if path.stat().st_size > 600_000:
                raise ValueError('excessive visual cache size')
            envelope = json.loads(path.read_text(encoding='utf-8'))
            if set(envelope) != {'key', 'spec', 'checksum'} or envelope['key'] != key:
                raise ValueError('visual envelope identity mismatch')
            if fingerprint(envelope['spec']) != envelope['checksum']:
                raise ValueError('visual checksum mismatch')
            checked = validate_visuals(envelope['spec'], source)
            if checked.spec is None or checked.spec.provenance != provenance:
                raise ValueError('visual provenance or validation mismatch')
            return checked.spec
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            raise CacheInvalid(str(exc)) from exc

    def write(self, key: str, spec: VisualSpec, source: Lesson) -> None:
        checked = validate_visuals(spec, source)
        if checked.spec is None:
            raise ValueError('Refusing invalid visual publication')
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        value = checked.spec.model_dump(mode='json')
        envelope = dict(key=key, spec=value, checksum=fingerprint(value))
        temporary = path.with_name(f'.{key}.{uuid4().hex}.tmp')
        try:
            with temporary.open('w', encoding='utf-8') as stream:
                json.dump(envelope, stream, ensure_ascii=False, allow_nan=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
