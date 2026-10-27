# Pipeline — Blu VisualTeacher

> Task 4 override: see [offline planner contract](planner-task4.md). Planner calls use 180 s, keep_alive 10m, one repair, failure-only raw logs, and English content with requested-language metadata. Failed requests return structured errors; no unrelated fallback. Task 5 orchestration is not implemented.

> Current Task 7 override: production orchestration is implemented. Task 6's
> checked localization cache supersedes the old translation sketch below.
> Kannada now uses local Indic Parler-TTS on CPU/configured CUDA, separately
> approval-gated; see task7-status.md and narration-languages.md. This deployment
> retains en,hi approval. All timing remains audio-derived.

Build file · What each stage does: inputs, outputs, cache, failure handling.
Contracts: `lesson-schema.md`. Coding rules: `../AGENTS.md`.

---

## 0. Stages
| # | Stage | Module | Output | PS stage |
|---|---|---|---|---|
| – | input | `web/src/app` | job request | 1 |
| 1 | `plan` | `planner/ollama_client.py`, `prompt.py` | raw JSON | 2 |
| 2 | `validate` | `planner/validate.py` | `plan.json` (English lesson) | 2 |
| 3 | `translate` | `localize/` | `<variant>/lesson.json` | 4 |
| 4 | `voice` | `speech/` | one WAV per beat | 4 |
| 5 | `timeline` | `timeline/` | `timeline.json`, `narration.wav/.m4a`, `lesson.srt` → **playable** | 3, 4 |
| 6 | `export` | `export/` + `web/render/render.mjs` | `lesson.mp4` → **done** | 5 |

The visual engine (PS stage 3) is the renderer: it runs in the browser player and inside `export`.
The job reports `playable: true` after `timeline`, so the lesson can play while the MP4 renders.

---

## 1. Input
| Field | Values | Default |
|---|---|---|
| `topic` | 3–120 chars, free text | – |
| `level` | `beginner` \| `intermediate` | `beginner` |
| `language` | core `en`, `hi`, `kn` · bonus `ta`, `te`, `bn`, `mr` | `en` |
| `target_seconds` | 30–90 (UI steps of 15) | 60 |
| `voice` | `female` \| `male` | `female` |
| `speed` | 0.85 \| 1.0 \| 1.15 (accept 0.8–1.2) | 1.0 |

Normalized topic (for the cache key): lowercase, punctuation removed, spaces collapsed.
Before running, check the cache (§8): a known topic skips `plan` and `validate`; a known variant skips straight to `playable`/`done`.

---

## 2. Plan
- `POST {OLLAMA_URL}/api/chat` with `stream: false`, `format: <lesson.schema.json>`, `keep_alive: "30m"`.
- Options: `temperature 0.3`, `top_p 0.9`, `seed 7`, `num_ctx 4096`, `num_predict 2000`. CPU profile adds `num_gpu 0`.
- Messages: system prompt + one example + the request, from `prompts.md`. The request carries topic, level, target seconds and the **word budget = round(target_seconds × 2.2)**.
- Timeout: 60 s on the GPU profile, 300 s on CPU. A timeout counts as a failure.
- Model by profile: `PLANNER_MODEL_GPU` (`qwen3:8b`, sent with `think: false`) or `PLANNER_MODEL_CPU` (`qwen3:4b-instruct-2507-q4_K_M`). If Ollama reports the model missing or fails to load it, retry once with `PLANNER_BACKUP_MODEL`.
- Save the raw reply to `cache/lessons/<id>/plan.raw.json`.
- **Calibrate the 2.2 words/s budget** after the first real lessons: actual seconds ÷ English words, logged in `test-log.md`.

## 3. Validate
`lesson-schema.md` §5: parse → Pydantic → auto-fix → hard errors → lint.
- Hard errors → **one** repair call: the same model gets its JSON back plus the error list (`prompts.md`). Then validate again.
- Still failing, or any Ollama error → fallback lesson (`lesson-schema.md` §5d). The job continues with it, so the learner still gets a lesson in their language.
- Add the meta fields and save `cache/lessons/<id>/plan.json`. Unload the LLM now (`keep_alive: 0`) when `LOW_RAM=1`, or on the `gpu` profile when the voice stage will use Parler (VRAM, `architecture.md` §5).

## 4. Translate (skipped for `en`)
- Model: IndicTrans2 en→Indic `dist-200M` with IndicTransToolkit's `IndicProcessor`.
- Language tags: `hi → hin_Deva`, `kn → kan_Knda`, `ta → tam_Taml`, `te → tel_Telu`, `bn → ben_Beng`, `mr → mar_Deva`.
- Translate the fields in `lesson-schema.md` §8, one sentence per item, all items of a lesson in **one batch** (batch size 16).
- Before: mask `keep_terms`, code-like spans and numbers with placeholders. After: restore them; if a placeholder went missing, translate that item again without masking and log it. Exact rules: `narration-languages.md`.
- Cache every translated string in `cache/translations/<lang>.json`, keyed by `sha1(text + model)`.
- Output: the localized lesson, `cache/lessons/<id>/<variant>/lesson.json`.

## 5. Voice
**One clip per beat.** Beats in order: for each scene, the intro (if `narration` isn't empty), then each step.

Speech text = the localized narration after `speech/textnorm.py`: collapse whitespace, remove characters TTS can't say (brackets, `_`, `*`, `#`), make sure it ends with `.`, `?` or `!`. `keep_terms` stay in Latin letters.

**Engine per language** (`speech/engines.py`). The profile is `gpu` or `cpu` (`architecture.md` §5).
| Language | `gpu` profile | `cpu` profile | Voices: female / male |
|---|---|---|---|
| `en` | Kokoro, phonemes `en-us`* | same | `hf_alpha` / `hm_omega` (Indian-accented English) |
| `hi` | Kokoro, `hi` | same | `hf_alpha` / `hm_omega` |
| `kn` | Local Indic Parler-TTS | Local Indic Parler-TTS, CPU float32 | `Anu` / `Suresh`; explicit approval + ENABLE_PARLER required |
| `ta` (bonus) | Parler | Kokoro `ta` if it passes the listening test, else "GPU only" | Parler `Jaya` / none → male uses Kokoro |
| `te` (bonus) | Parler | as above | Parler `Lalitha` / `Prakash` |
| `bn` (bonus) | Parler | as above | Parler `Aditi` / `Arjun` |
| `mr` (bonus) | Parler | as above | Parler `Sunita` / `Sanjay` |
\* Listening test also tries `en-gb` phonemes with `hf_alpha`; pick whichever sounds more natural.

- **Kokoro** (`kokoro-onnx`, CPU): `create(text, voice, speed, lang)` → 24 kHz mono. `speed` = the learner's speed.
- **Parler** (Task 7 Kannada): lazy local model and separate local description
  tokenizer. Named moderate-pace description, isolated fixed seed per beat,
  one generation per uncached beat. Requested speed uses FFmpeg atempo, not
  only a prompt hint. Raw 44.1 kHz is processed to 24 kHz PCM. Near-token-cap
  output fails rather than silently truncating speech. No alternate engine fallback.
- If an engine fails for a beat: try the other engine for that language once, else fail the stage (→ fallback, §11).

Post-processing per clip (`speech/audio.py`): resample to 24 kHz mono, trim edge silence (below −40 dBFS, keep 50 ms), normalize RMS to about −20 dBFS with peak ≤ −1 dBFS.
Cache: `cache/audio/<sha1(speech_text|lang|engine|voice_id|speed|tempo|ENGINE_VERSION)[:16]>.wav`. A cached clip is never made again.

**Tonight's listening test (decides the `kn` row):** one 3-beat Kannada lesson excerpt in Kokoro `hf_alpha` and Parler `Anu`. Varun judges naturalness; record RTF (synth time ÷ audio length) for both on GPU and CPU in `test-log.md`. Same test for English `en-us` vs `en-gb`, and Hindi with a Latin term ("Python में loop…") in Kokoro.

## 6. Timeline (the sync rule)
The audio decides every duration. Constants (`timeline/build.py`):
| Constant | Value | Meaning |
|---|---|---|
| `FPS` | 30 | |
| `LEAD_IN` | 0.30 s | before a scene's first beat (heading animates in) |
| `BEAT_GAP` | 0.25 s | between beats in a scene |
| `SCENE_TAIL` | 0.60 s | the "short pause" after a scene's last beat |
| `TITLE_MIN` | 2.5 s | minimum title-card length |
| `MAX_LESSON` | 90 s | PS limit |

Algorithm:
```
t = 0
for scene:
    scene_start = t
    t += LEAD_IN
    for beat in scene.beats:
        beat.start = t ; beat.end = t + clip_seconds(beat) ; t = beat.end + BEAT_GAP
    t = t - BEAT_GAP + SCENE_TAIL
    t = max(t, scene_start + TITLE_MIN) if title_card
frames = round(seconds × FPS); scene durations = next start − this start (frames add up exactly)
```
- **Over 90 s:** speed up every clip by `tempo = min(1.10, speech_seconds / (90 − pause_seconds))` with FFmpeg `atempo` (cached as a new clip), rebuild. Still over → keep it, add a warning.
- **Narration track:** a silent 24 kHz buffer of the full length; paste each clip at its start sample → `narration.wav` (16-bit PCM). Then `ffmpeg -y -i narration.wav -c:a aac -b:a 64k -ac 1 narration.m4a` for the web player.
- **Captions:** each beat's localized narration split into chunks: at sentence ends first, then commas, then the space nearest the middle. Max code points per chunk: `en 90 · hi 90 · mr 90 · bn 85 · kn 80 · te 80 · ta 75` (tune when we see real renders). A chunk's time inside its beat is proportional to its length.
- **SRT:** one cue per caption chunk, UTF-8, `HH:MM:SS,mmm`.
- Write `timeline.json` (`lesson-schema.md` §6). The job is now **playable**.

## 7. Export
1. Write `props.json` (`lesson-schema.md` §7) with `mediaBase: "http://127.0.0.1:8000"` and `audioVariant: "wav"`.
2. If `props.json` has the same hash as the existing `lesson.mp4`, skip.
3. Run `node web/render/render.mjs --props <props.json> --out raw.mp4 --concurrency <RENDER_CONCURRENCY>` and turn its `{"progress":…}` lines into job progress.
   Render settings: composition `Lesson`, codec `h264`, audio `aac` 128 kbps, `crf 23`, `yuv420p`, 1280×720, `fps` from the timeline.
4. `ffmpeg -y -i raw.mp4 -c copy -movflags +faststart lesson.mp4` (starts playing before it fully loads, good for phones).
5. `ffprobe` check: 1280×720, h264, yuv420p, aac, duration within 0.2 s of the timeline. Fail → treat as an export error.
6. `lesson.srt` sits next to the MP4. The job is **done**.
- Export error → Plan B exporter (Playwright records the player in real time, FFmpeg adds the WAV; `export.md`). Both fail → the job ends without an MP4 and the UI says so; the player still works.

## 8. Cache (no lesson is ever made twice)
| What | Key | Where |
|---|---|---|
| Plan | `lesson_id = sha1(norm_topic \| level \| target_seconds \| planner model used \| PROMPT_VERSION \| SCHEMA_VERSION)[:12]` | `cache/lessons/<id>/plan.json` |
| Edited plan | `<lesson_id>-v<n>` | `cache/lessons/<id>-v<n>/plan.json` |
| Language variant | `<lang>-<voice>-<speed>`, e.g. `hi-female-1` | `cache/lessons/<id>/<variant>/` |
| Translations | `sha1(text + model)` | `cache/translations/<lang>.json` |
| Beat audio | §5 hash | `cache/audio/<hash>.wav` |
| MP4 | hash of `props.json` | `cache/lessons/<id>/<variant>/lesson.mp4` + `props.sha1` |
| Library | – | `cache/index.json`: `{lesson_id, topic, title, level, target_seconds, source, variants[], created_at}` |
| Run log | – | `cache/runs.jsonl` |

Variant folder: `lesson.json`, `timeline.json`, `narration.wav`, `narration.m4a`, `lesson.srt`, `props.json`, `props.sha1`, `lesson.mp4`, `meta.json` (engine, voice, timings, warnings).
Served as `/media/<id>/<variant>/<file>`.

## 9. Revoice and edit (bonus; the plumbing comes free)
- **Revoice** (other language, voice or speed): new variant of the same plan. Runs `translate → voice → timeline → export`; `plan` and `validate` show as "cached". Unchanged strings and clips come from the cache.
- **Edit one scene:** the teacher changes English `heading`, `narration`, step fields → a new plan `<id>-v<n>` → re-validate → run the variant again. Only strings and beats that changed are translated and voiced again; everything else is a cache hit. Export runs again (whole video, but fast).

## 10. Time budget (estimates; replace with measured numbers in `test-log.md`)
| Stage | `gpu` profile | `cpu` profile | Notes |
|---|---|---|---|
| plan | 8–20 s (`qwen3:8b`) | 60–180 s (`qwen3:4b`) | biggest CPU cost; cached per topic |
| validate | < 0.1 s (+1 plan call if repaired) | same | |
| translate | 1–3 s | 3–10 s | skipped for `en` |
| voice | Kokoro estimates unchanged; CUDA Parler unverified | Kokoro 10–30 s; Task 7 Parler voice 268.159 s for 68.011 s speech | Kannada CPU sampled process peak about 6.7 GiB; not an 8-GB-machine acceptance |
| timeline | ~1 s | ~1 s | includes the m4a encode |
| **→ playable** | **~0.5–1.5 min** | **~1.5–4 min** | |
| export | 30–90 s | 1–3 min | 1,800 frames for 60 s |

Every stage's time and peak RAM is shown in the UI and logged (bonus: "show how long each stage takes on your weakest laptop").

## 11. Failure handling
| Failure | Seen as | What happens |
|---|---|---|
| Ollama down, model missing | HTTP error at health or plan | backup model once → fallback lesson |
| Plan timeout | timeout | fallback lesson |
| Still invalid after repair | validator | fallback lesson |
| Translation error | exception or empty output | pre-rendered fallback package in that language |
| TTS error | exception | other engine for that language once → fallback package |
| Render error | exit code 1 or ffprobe check fails | Plan B exporter → "MP4 failed" banner; the player still works |
| Anything else | exception | fallback package |

**Fallback package** = the Python-loop lesson already run through our own pipeline for every language variant with the default voice (audio, timeline, MP4). Made around H+18 by generating it once per language, so it's created locally by our system and plays instantly.
Every fallback sets `fallback: true` and a one-line reason that the UI shows as a banner.
