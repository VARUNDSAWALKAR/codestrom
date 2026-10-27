"""Usage: python -m backend.plan_lesson 'Water Cycle' --out data/samples/planner/water_cycle.json"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app.config import get_settings
from .app.planner.ollama_client import PlanRequest, plan_lesson


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic")
    parser.add_argument("--level", choices=["beginner", "intermediate"], default="beginner")
    parser.add_argument("--language", default="en")
    parser.add_argument("--subject", choices=["programming", "science", "other"],
                        help="Explicit subject; overrides keyword classification")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--device", choices=["cpu", "auto", "cuda"], default="cpu")
    parser.add_argument("--model", help="Explicit model override; never pulls or renames models")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    values = get_settings().model_dump()
    values["device"] = args.device
    if args.model:
        values.update(planner_model_cpu=args.model, planner_model_gpu=args.model)
    settings = type(get_settings()).model_validate(values)
    request = PlanRequest(topic=args.topic, level=args.level, language=args.language, target_seconds=args.seconds,
                          subject=args.subject)
    result = plan_lesson(request, settings)
    if result.lesson and result.error is None and args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result.lesson.model_dump_json(indent=2, exclude_unset=True), encoding="utf-8")
    print(result.model_dump_json(indent=2, exclude_unset=True))
    return 0 if result.lesson is not None and result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
