# Blu VisualTeacher — a typed concept becomes a narrated, animated lesson, offline

**Unlox24 (Codestorm), new problem statement: Blu VisualTeacher** (PS dated 28 Oct 2026) · 24 hours
**Team:** Satwik Ray, Varun D S

> **Pitch line:** Type a concept, pick a language, and get a 30–90 second animated lesson with voice-over and captions in English, Hindi or Kannada, made on a laptop with the internet switched off.

---

## What it does
A learner types a topic ("How does a Python loop work?") and picks a level, a language and a length. A small local LLM writes the lesson plan as JSON. Our code checks it, translates it, voices it and plays it as animated scenes (title card, code walkthrough, diagram, formula, recap) with step headings, captions and a progress bar. The same lesson exports as a 1280×720 MP4 with burned-in captions plus an `.srt`.

## The 5 required stages → how we build each
| # | Stage | Our approach | Done when (PS) |
|---|---|---|---|
| 1 | Concept input | React page: topic, level, language, length (+ voice, speed) | Inputs reach the backend |
| 2 | Lesson planner | Ollama (`qwen3:8b` on GPU, `qwen3:4b-instruct-2507-q4_K_M` on CPU) with a JSON-schema `format` → Pydantic check + auto-fix + 1 repair call → built-in fallback lesson | Passes the schema check; bad output → fallback plays |
| 3 | Visual engine | Remotion (React) scenes driven by frame number; Remotion Player in the browser | Play, pause, next scene, replay |
| 4 | Narration | Plan in English → IndicTrans2 → Kokoro (en, hi) / Kokoro or Indic Parler-TTS (kn, picked tonight) / Parler (bonus languages, GPU). **One audio clip per beat; the audio sets every length** | Same lesson in en, hi, kn with audio, captions and scenes in sync |
| 5 | MP4 export | Remotion renderer → 1280×720 H.264/AAC, captions burned in + `.srt` | A playable 720p MP4 |

## Core vs bonus
| | What | Rule |
|---|---|---|
| **Core** | All 5 stages in en + hi + kn · scene types title card, code walkthrough, diagram, formula, recap · fallback lesson · offline · works CPU-only | Build first; never cut |
| **Bonus** | ta, te, bn, mr · revoice switch · male/female + speed · quiz scene · edit one scene · cache by topic/language/version · stage times on the weakest laptop | After the H+16 checkpoint |
Some bonus items come almost free from the design (cache, revoice, stage timings). Build the plumbing in core; add the UI later.

## Decisions (27 Oct)
1. **Planner by device profile.** GPU (demo): `qwen3:8b` with `think: false`, for better lessons. CPU (the "no GPU" rule): `qwen3:4b-instruct-2507-q4_K_M` (~2.5 GB, fits 8–16 GB laptops, as the PS suggests). Both Apache 2.0. Backup: `llama3.2:3b` (already pulled).
2. **Plan in English, translate after** (the PS's tip). The English plan is cached, so switching language never re-plans.
3. **One beat = one audio clip.** A scene's intro and each step are voiced separately, so captions and step-by-step animation line up exactly with the audio. Scene length = its clips + fixed pauses. No hard-coded durations anywhere.
4. **Remotion for both playback and export.** The same React components run in the browser player and render the MP4, so they can't drift apart. Licence: free for individuals and teams up to 3; source-available, not OSI open source (goes in `licenses.md`). Plan B exporter: Playwright capture + FFmpeg.
5. **Core languages: English + Hindi + Kannada.** English and Hindi use Kokoro, already approved by ear in Kavach. Kannada: Kokoro `hf_alpha` passed for short Kavach clips; for full lessons, **tonight's listening test** picks Kokoro or Indic Parler-TTS (`Anu`/`Suresh`). Tamil, Telugu, Bengali and Marathi are bonus via Parler: the PS lists them and judges may call one out.
6. **Two device profiles.** `gpu` (demo laptop) may use Parler. `cpu` (the "must work without a GPU" rule) uses Kokoro only, since Parler runs ~7× slower than real time on a CPU.
7. **No API keys.** `.env` holds model paths and settings only.

## Stack
| Part | Tool | Runs | Licence |
|---|---|---|---|
| Planner | Ollama + `qwen3:8b` (GPU) / `qwen3:4b-instruct-2507-q4_K_M` (CPU), backup `llama3.2:3b` | Local GPU / CPU | Apache 2.0 / Llama 3.2 Community |
| Schema check | Pydantic v2 + JSON Schema (also sent as Ollama `format`) | Local | MIT |
| Translation | IndicTrans2 en→Indic `dist-200M` + IndicTransToolkit | Local | MIT |
| Voice: en, hi (and kn on CPU) | Kokoro-82M via `kokoro-onnx`, voices `hf_alpha` (F) / `hm_omega` (M) | Local CPU | Apache 2.0 model, MIT library |
| Voice: kn + bonus languages (GPU) | Indic Parler-TTS | Local GPU | Apache 2.0 |
| Backend | Python 3.11, FastAPI | Local | MIT |
| Visual engine + player | React + TypeScript (Vite), Remotion 4 + `@remotion/player` | Browser | Remotion free licence |
| MP4 export | `@remotion/renderer` (Chrome Headless Shell + FFmpeg) | Local | Remotion free licence |
| Post-processing | FFmpeg (faststart, AAC), ffprobe (checks) | Local | LGPL/GPL |
| Fonts | Noto Sans + Devanagari, Kannada, Tamil, Telugu, Bengali, Mono | Bundled | OFL 1.1 |

## Demo setup
- **Satwik's laptop runs everything with Wi-Fi off:** Ollama, the backend (which also serves the built app), the browser.
- **Live:** judges call out a topic and a language → type it → stage progress with times → the lesson plays in the browser → the MP4 appears when export finishes.
- **If a model call fails:** the fallback lesson (Python loop, pre-rendered in every language) plays with a banner.
- **CPU-only proof:** the same run with `DEVICE=cpu` and the GPU hidden; times and peak RAM in `test-log.md`.

## Machine & environment
- Windows 11 · RTX 5070 Laptop GPU (8 GB VRAM)
- **Reuse the Kavach Python venv** `C:\Users\ROG\Kavach\kavach-env` (Python 3.11.9, torch CUDA 12.8 build, kokoro-onnx 0.6.1, IndicTransToolkit 1.1.1, parler_tts, **transformers 4.46.1 pinned by Parler-TTS: never upgrade**)
- In PowerShell, plain `activate` doesn't work: use `& C:\Users\ROG\Kavach\kavach-env\Scripts\Activate.ps1`, or call the venv's Python directly (`$py`, `test-cases.md`)
- Node v24 LTS · npm 11 · FFmpeg · Ollama (`qwen3:8b`, `llama3.2:3b` pulled; `qwen3:4b-instruct-2507-q4_K_M` pulling)
- Models already on disk in `C:\Users\ROG\Kavach\models\`: `kokoro\`, `indictrans2\` (files directly in it), `indic-parler-tts\`. Point `.env` at them, don't copy them.
- **Verified offline on 27 Oct:** Kokoro speaks, IndicTrans2 translates (`test-log.md` T1–T2).

## Folder layout
```
VisualTeacher/
├── AGENTS.md      rules + contracts for coding agents (Codex reads this)
├── CLAUDE.md      imports AGENTS.md (Claude Code reads this)
├── README.md      submission README: setup, models + licences, laptop specs (written at the event)
├── docs/          these plan files
├── data/
│   ├── fallback/  python_loop.en.json (the built-in fallback lesson)
│   └── samples/   2 more lessons, mock timelines, render props
├── backend/       FastAPI app (Satwik)
├── web/           Vite + React + Remotion (Varun)
├── cache/         generated lessons, audio, MP4s (never commit)
└── .env           paths and settings (never commit)
```
`backend/` and `web/` are created at the event: all code is written during the 24 hours.

## Before H+0 (tonight)
The checklist with status is `risks-fallbacks.md` §1. Most important:
1. Finish `ollama pull qwen3:4b-instruct-2507-q4_K_M` (~2.5 GB)
2. `& $py -m pip install fastapi "uvicorn[standard]" httpx psutil`
3. npm prefetch + Remotion's headless browser (`architecture.md` §9)
4. Voice test T4–T6 and masking test T7 (`test-cases.md`)

## Start of every session
```
cd C:\Users\ROG\VisualTeacher
& C:\Users\ROG\Kavach\kavach-env\Scripts\Activate.ps1
ollama ps
```
The prompt must start with `(kavach-env)`. If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, once.

## Event rules (from the PS)
- No external AI APIs; every model runs on our machine
- Must work CPU-only with 8–16 GB RAM; a GPU is optional
- Must run fully offline once models and packages are downloaded
- The LLM returns JSON only; the app never runs model-written code; visuals come only from our components
- The finished lesson plays smoothly in a browser on a modest phone
- Every model, voice and asset licence checked and listed in the README
- All code written during the 24 hours; pretrained models and open-source libraries allowed
- Submit: repo + README (setup, models/voices + licences, laptop specs), 2 MP4s (judges' topic + ours, each in English and one Indian language), 5-min live demo with Wi-Fi off + 3 min of questions

## Judging → what we show
| Criterion | Weight | What we show |
|---|---|---|
| Works end to end | 25% | Topic → MP4 live with Wi-Fi off, no manual steps |
| Teaching quality | 20% | One idea per scene, step-by-step reveals tied to the narration, a recap; Python code parse-checked |
| Visual clarity | 15% | Fixed 1280×720 grid; only the step being explained animates |
| Languages, narration, sync | 15% | Per-beat audio → exact sync; right script; technical terms kept in English |
| Engineering & robustness | 15% | Schema + auto-fix + repair + fallback; planner / renderer / exporter kept separate |
| Speed & footprint | 10% | Stage times + peak RAM on CPU-only; a light web player; cached lessons |

## Plan files
| File | What's in it | Status |
|---|---|---|
| `README.md` | This overview | ✅ |
| `../AGENTS.md` (+ `CLAUDE.md`) | Rules and contracts for Claude Code / Codex | ✅ |
| `architecture.md` | Parts, folders, processes, device profiles, `.env`, setup | ✅ |
| `pipeline.md` | Each stage: inputs, outputs, cache, sync rule, failures | ✅ |
| `lesson-schema.md` | Lesson JSON v1, Ollama schema, validation, timeline, render props | ✅ |
| `prompts.md` | Planner prompt p1, example, repair prompt, prompt check | ✅ Run its check (§6) before building on it |
| `scene-components.md` | Frame grid, each scene type, motion, captions, progress bar | ✅ |
| `narration-languages.md` | Translation, masking, voices, speech text, captions, fonts | ✅ Masking style pending T7 |
| `export.md` | Render settings, faststart + checks, SRT, Plan B exporter | ✅ |
| `api-contracts.md` | Endpoints and JSON shapes | ✅ |
| `ui-flow.md` | Screens and controls | ✅ |
| `task-split.md` | Who builds what, hour by hour | ✅ |
| `test-cases.md` | Tonight's checks (T1–T10) + event acceptance tests | ✅ T1–T2 passed |
| `risks-fallbacks.md` | Tonight checklist, risks, offline gotchas | ✅ |
| `licenses.md` | Every licence + a README section to paste | ✅ |
| `demo-script.md` | 5-min demo + Q&A | ✅ |
| `test-log.md` | Measured results | ✅ Fill as you test |
| `../data/` | Fallback lesson, 2 samples, mock timelines, render props, `lesson.schema.json`, `test_topics.json` | ✅ |
