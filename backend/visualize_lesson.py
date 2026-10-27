"""Opt-in VQ1 development CLI. Does not translate, narrate or render anything."""
import argparse
import json
from pathlib import Path
from .app.config import get_settings
from .app.planner.schema import Lesson
from .app.visuals.planner import plan_visuals, plan_semantic_visuals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lesson', required=True, help='Canonical English plan.json path or cached lesson ID')
    parser.add_argument('--scene', action='append', help='Limit visual inference to these scene IDs')
    parser.add_argument('--legacy-intent', action='store_true', help='Use the original VQ1 shape/slot planner instead of VQ1.1')
    args = parser.parse_args()
    settings = get_settings()
    path = Path(args.lesson)
    if not path.is_file():
        from .app.cache import Cache
        path = Cache(settings.cache_dir).lesson_dir(args.lesson)/'plan.json'
    lesson = Lesson.model_validate_json(path.read_text(encoding='utf-8'))
    planner = plan_visuals if args.legacy_intent else plan_semantic_visuals
    result = planner(lesson, settings, scene_ids=args.scene)
    print(json.dumps(result.model_dump(mode='json'), ensure_ascii=False, indent=2))
    return 0 if any(s.objects for s in result.spec.scenes) else 2


if __name__ == '__main__':
    raise SystemExit(main())
