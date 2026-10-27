# Task 4: offline English lesson planner

This Task 4 contract supersedes the older planner prompt/recovery defaults in
prompts.md, pipeline.md, architecture.md and AGENTS.md. No HTTP orchestration,
translation, TTS or rendering is added here (Task 5 remains separate).

## Configuration and usage

Existing config.py reads .env and environment overrides. CPU default:
`PLANNER_MODEL_CPU=qwen3:4b-instruct-2507-q4_K_M`; optional GPU:
`PLANNER_MODEL_GPU=qwen3:8b`; backup: `PLANNER_BACKUP_MODEL=llama3.2:3b`.
No automatic backup substitution or downloads. To test the backup provisionally,
explicitly pass `--model llama3.2:3b`; this is not 4B acceptance.

`python -m backend.plan_lesson "Water Cycle" --language kn --seconds 60 --out data/samples/planner/water_cycle.json`

CLI defaults to CPU; `--device` overrides it. The reusable interface is
`plan_lesson(PlanRequest(...), Settings(...)) -> PlanResult` in
backend/app/planner/ollama_client.py. Result contains request metadata, validated
English Lesson or structured error, model, attempts, generation_seconds, cached,
and notes. `request.language` retains the requested language; `lesson.language`
is always en, preventing downstream speech from mistaking English for Kannada.
Output files contain the ordinary Lesson contract. CLI prints the result envelope
and exits 1 on failure, 0 on success. Difficulty uses the existing `level` enum.

## Generation and recovery

Only localhost Ollama at port 11434; proxy environment and redirects disabled.
Each call has a 180-second timeout. Settings: temperature 0.3, keep_alive 10m,
CPU num_gpu 0, bounded 3500 output tokens, structured Pydantic JSON schema.
Qwen3 capability discovery uses /api/show; thinking-capable models receive
think:false, non-thinking instruct models explicitly record why it is omitted.
Unknown Qwen3 capabilities fail explicitly. API option/schema rejections are
returned with the server error, never silently retried with weaker settings.

Prompt p3-task4 produces title_card, diagram and code_walkthrough only, using
existing Scene/Step models. The generation schema narrows their shared fields into
renderer variants, exposing conditional step counts and required code fields that
Pydantic model validators alone cannot express in JSON schema.
Ordered processes prefer flow; no code is forced into
non-programming lessons. There are no model-provided animation controls: all
animation remains renderer-owned. Unknown fields are rejected. Flow center is
omitted and labelled center required to respect the stricter TypeScript union.

Validation includes contract bounds, label limits, nonempty narration/labels,
code highlight references and Python syntax parsing only, rough narration budget
(1.5-3 words per requested second; Ollama is asked for 110-130 words per 60 s), script checks and topic keyword overlap.
These are practical heuristics, not a factual correctness or language classifier;
Latin-script foreign text and subtle topic errors still need human review.
Target duration is advisory; actual timing remains audio-derived later.

Invalid output saves raw content plus errors only under scratch/planner, then
gets exactly one repair call. Persistent invalid output, timeout or unavailability
returns structured failure. No fallback is substituted, even for Python loops;
the existing demo may be offered separately later. This is stricter than the
allowed matching-topic-only fallback and prevents unrelated lessons being served.

Validated successes alone are cached at cache/lessons/<content-key>/plan.json.
Key includes topic, level, duration, model and prompt version; language is omitted
because the plan is English. Cache hits are revalidated and report zero generation
latency. Failed raw replies are not written to the cache. No stage wiring or job
context changes are included; Task 5 can call this interface and propagate errors.


## Task 4b
`PlanRequest.subject` (`programming|science|other`) overrides keyword classification (`planner/subject.py`). A known subject selects the matching generation-schema branch (programming: code + flow worked example; otherwise diagram scenes only), is part of the cache key, and is enforced by `validate_plan`. Repair feedback adds code-size and missing-center hints.
