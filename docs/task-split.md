# Task split — Blu VisualTeacher

Associated file · Who builds what, hour by hour, for 2 people in 24 hours.
Milestones match `architecture.md` §10 and the PS's suggested plan (gate 1 at H+5, feature freeze at H+20).
**H+0 = the moment coding starts. Fill in the clock time: H+0 = ____**

---

## 1. Roles
| | Satwik | Varun |
|---|---|---|
| **Owns** | Backend: planner, validation, fallback, translation, TTS, timeline, cache, export orchestration, API | Web: Remotion composition + scene components, render CLI, the app (input, progress, player), fonts, phone check, test runs |
| **Files** | `backend/` | `web/`, `data/` |
| **Read first** | `pipeline.md`, `lesson-schema.md`, `prompts.md`, `narration-languages.md`, `export.md` §4 | `lesson-schema.md` §6–7, `data/samples/`, `scene-components.md`, `ui-flow.md`, `export.md` §2–3 |
| **Demo laptop** | Yes (GPU, models, Ollama) | Develops the web app against Satwik's backend over Wi-Fi |

---

## 2. Before H+0
- Tonight checklist: `risks-fallbacks.md` §1 (Kokoro and IndicTrans2 already pass offline).
- **Varun's laptop:** Node + npm, the prefetch from `architecture.md` §9, fonts. If he'll run the CPU timing test, also Python + Ollama + the 4B model.
- Settle tonight: the Kannada voice (Kokoro vs Parler) and English phonemes (`en-us` vs `en-gb`) by listening (`pipeline.md` §5).

---

## 3. Hour by hour
| When | Satwik | Varun | Must work by the end |
|---|---|---|---|
| **H+0–0.5** | **Both:** repo + `.gitignore` + `.env`, copy `data/` and `docs/` in, `AGENTS.md`/`CLAUDE.md` at the root · `ollama ps` · decide H+0 clock time | ← | |
| **H+0.5–2** | FastAPI skeleton: `config.py` (profiles, offline env vars), `/api/health`, `/api/config`, job runner with stage list + timings + `runs.jsonl`, `/media` static, `cache.py` | Vite + React + TS + Remotion; fonts in `public/fonts`, `fonts.ts`; `types.ts` from `lesson-schema.md`; composition `Lesson` with `calculateMetadata`; `StepHeading`, `CaptionBar`, `ProgressBar`; `TitleCard` | **H+2:** `/api/health` answers; `python_loop.props.json` plays in Remotion Studio |
| **H+2–3.5** | `speech/`: Kokoro engine (en, hi), text norm, clip post-processing, beat cache · `timeline/`: build, captions, SRT, narration wav/m4a · run on `python_loop.en.json` → real `timeline.json` | `render.mjs` (selectComposition + renderMedia, JSON progress lines) → MP4 from the mock props · `npx remotion bundle` | Mock props → MP4 |
| **H+3.5–5** | `export/`: write props, call `render.mjs`, faststart, ffprobe check · stage chain for a fixed lesson | `CodeWalkthrough` (highlight bar, annotation, output panel) | **H+5 GATE: fallback lesson, English, real audio → MP4** |
| **H+5–7.5** | `planner/`: Ollama client (model by profile, `think: false` for `qwen3:8b`, `format` schema, timeouts, backup model), prompt p1 (`prompts.md`), `validate.py` (`lesson-schema.md` §5), repair call, fallback · run the prompt check | `Diagram` (flow, cycle, labelled; boxes + arrows reveal per step) | |
| **H+7.5–8** | `POST /api/lessons` + `GET /api/jobs` + `GET /api/lessons/{id}`; run 5 test topics | `Formula` (highlight parts + meanings) · `Recap` | **H+8:** typed topic → English MP4; broken plan → fallback |
| **H+8–10** | `localize/`: IndicTrans2 batch translate, term + code masking, restore checks, translation cache → Hindi and Kannada | App: input page (topic, level, language, length, voice, speed), progress view (stages + times, polls the job), player page (Remotion Player, play/pause, next/prev scene, replay, download MP4 + SRT) | |
| **H+10–12** | Parler engine (GPU profile), engine registry by language + profile + voice, voice choice + speed | Indic rendering: fonts per script, caption line height and chunk fit, long-label shrinking — check with Satwik's real hi + kn outputs | **H+12:** hi + kn lessons in sync, right script, MP4 each |
| **H+12–14** | Revoice endpoint, cache library (`index.json`, `GET /api/lessons`), 90-s tempo rule | Language switch (revoice) in the player · library list · fallback banner · stage-time panel | |
| **H+14–16** | CPU-only run (`DEVICE=cpu`, GPU hidden): timings + peak RAM per stage; `LOW_RAM` mode · fixes | Phone check: player on a real phone over Wi-Fi + Chrome DevTools 4× CPU throttle; page weight · fixes | **H+16:** core complete; CPU-only timed |
| **H+16–18** | Bonus languages (ta, te, bn, mr) smoke test · edit-one-scene endpoint · fallback package generation (python loop, every language) | Quiz scene (bonus) · edit-scene panel · run `data/test_topics.json` and log pass rate + times | |
| **H+18–20** | **Both:** offline test with Wi-Fi off, full demo dry run twice, bug fixes | ← | **H+20: FEATURE FREEZE** |
| **H+20–22** | **Both:** make the 2 submission MP4s (judges' topic + ours, English + one Indian language) · repo README: setup, models/voices + licences, laptop specs | ← | **H+22:** submission files ready |
| **H+22–24** | **Both:** buffer, sleep, final rehearsal (5-min demo + Q&A), submit | ← | |

---

## 4. Handoffs
| What | From → to | Needed by | Defined in |
|---|---|---|---|
| `types.ts` mirrors `schema.py` | Varun ↔ Satwik | H+1 | `lesson-schema.md` §2–7 |
| Mock render props (3 lessons) | ready now | H+0 | `data/samples/*.props.json` |
| `render.mjs` CLI | Varun → Satwik | H+3.5 | `AGENTS.md` → Contracts |
| Real `timeline.json` + `narration.wav` for the fallback lesson | Satwik → Varun | H+3.5 | `lesson-schema.md` §6 |
| Job + lesson endpoints | Satwik → Varun | H+8 | `api-contracts.md` |
| Real hi + kn outputs for font/caption checks | Satwik → Varun | H+10 | `lesson-schema.md` §6–7 |
| `data/test_topics.json` results | Varun → Satwik | H+18 | `test-cases.md` |

---

## 5. Working rules
- **Git:** commit only in your own folders (AGENTS.md → owners). Pull before every push; commit every 30–60 min. Never commit `.env`, `cache/`, `models/`.
- **Contracts:** `lesson-schema.md` and `api-contracts.md` change only when both agree, in the same commit as the code.
- **Prompt changes:** only Satwik edits the prompt; Varun re-runs the topic set after each change; both get logged in `test-log.md`.
- **Packages:** tell each other before adding one; never upgrade transformers; keep every `@remotion/*` package on one version.
- **Checkpoints:** 5-minute sync at H+2, H+5, H+8, H+12, H+16. Missed by more than an hour → cut scope (§6), don't push on.
- **Coding agents:** one task per prompt, pointing at the doc section ("implement `pipeline.md` §6 in `backend/app/timeline/build.py`"). Agents read `AGENTS.md` first. Read every diff before committing; run it before moving on.

---

## 6. If you fall behind
**Skip first** (bonus): quiz, edit-one-scene, library, extra languages, phone polish.

**Then cut, in this order:**
1. Parler → Kokoro for Kannada
2. `formula` and `recap` scene types (keep the 3 required: title card, diagram, code walkthrough)
3. Remotion export → Plan B exporter (Playwright capture + FFmpeg)

**Never cut:** topic → MP4 end to end, the fallback lesson, English + 2 Indian languages, the 3 required scene types, play/pause/next/replay.

---

## 7. Sleep
About 2 hours each, in shifts between H+12 and H+18, **never both asleep**. Example: Varun H+13–15 (Satwik keeps going on revoice and the CPU-only run), Satwik H+15–17 (Varun on the phone check and test topics). The table's H+12–18 rows stretch to fit the shifts. More sleep in H+22–24 if everything's done. Convert to clock times once H+0 is known.
