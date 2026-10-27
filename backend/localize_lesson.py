"""Local-only translation CLI; does not plan, synthesize voice or export video."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .app.config import get_settings
from .app.cache import Cache
from .app.localize import localize_lesson
from .app.planner.schema import Lesson


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", required=True, help="English plan.json path or canonical lesson ID")
    parser.add_argument("--lang", choices=("hi", "kn"), required=True)
    parser.add_argument("--show", type=int, default=6)
    parser.add_argument("--voice", choices=("female", "male"), default="female")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    settings = get_settings()
    path = Path(args.lesson)
    if not path.is_file():
        path = Cache(settings.cache_dir).lesson_dir(args.lesson) / "plan.json"
    lesson = Lesson.model_validate_json(path.read_text(encoding="utf-8"))
    result = localize_lesson(lesson, args.lang, settings, voice=args.voice, speed=args.speed)
    print(json.dumps({"lesson_id": result.lesson.lesson_id, "language": args.lang, "cached": result.cached,
                      "localization_quality": result.localization_quality, "english_fraction": result.english_fraction,
                      "stats": result.stats, "warnings": result.warnings,
                      "pairs": [d.model_dump() for d in result.diagnostics[:max(0, args.show)]]}, ensure_ascii=False, indent=2))
    return 0 if result.english_fraction <= settings.localize_max_english_fraction else 2


if __name__ == "__main__":
    raise SystemExit(main())
