# Licences — Blu VisualTeacher

Associated file · Every model, voice, library, tool and font we use, with its licence. The PS: *"Every model, voice and asset you use must allow this use. List them in your README."* §6 is ready to paste into the repo README.
Rule: anything new gets a row here in the same commit (`../AGENTS.md`).

---

## 1. Models and voices
| Component | Used for | Licence | Notes |
|---|---|---|---|
| Qwen3-8B (`qwen3:8b`) | Planner, GPU profile | Apache 2.0 | |
| Qwen3-4B-Instruct-2507 (`qwen3:4b-instruct-2507-q4_K_M`) | Planner, CPU profile | Apache 2.0 | |
| Llama 3.2 3B (`llama3.2:3b`) | Backup planner only | Llama 3.2 Community License | If it's ever used, the README must say "Built with Llama"; Meta's acceptable use policy applies |
| IndicTrans2 en→Indic dist-200M (AI4Bharat) | Translation | MIT | |
| Kokoro-82M + `voices-v1.0.bin` (`hf_alpha`, `hm_omega`) | Voice: en, hi (+ others on CPU) | Apache 2.0 | |
| Indic Parler-TTS (AI4Bharat + Hugging Face) | Voice: kn and bonus languages on GPU | Apache 2.0 | Gated on Hugging Face (contact details shared to download); training data under CC BY 4.0 and similar |
| FLAN-T5 tokenizer (Google) | Parler's description encoder | Apache 2.0 | Loaded from the HF cache |
| DAC audio codec (Descript) | Inside Parler (audio decoding) | MIT | |

## 2. Python libraries
| Library | Licence | Library | Licence |
|---|---|---|---|
| FastAPI | MIT | transformers (4.46.1) | Apache 2.0 |
| Starlette | BSD-3-Clause | parler-tts | Apache 2.0 |
| Uvicorn | BSD-3-Clause | IndicTransToolkit | MIT |
| Pydantic | MIT | indic-nlp-library | MIT |
| httpx | BSD-3-Clause | sacremoses | MIT |
| psutil | BSD-3-Clause | sacrebleu | Apache 2.0 |
| NumPy | BSD-3-Clause | kokoro-onnx | MIT |
| soundfile | BSD-3-Clause | ONNX Runtime | MIT |
| PyTorch | BSD-3-Clause (BSD-style) | phonemizer | **GPL-3.0** |
| | | espeak-ng (via espeakng-loader) | **GPL-3.0** |
kokoro-onnx turns text into phonemes with espeak-ng through phonemizer. We use them as installed libraries and don't ship their code in our repo; if this were ever distributed as a product, the GPL terms would need a proper review.

## 3. Web and rendering
| Component | Licence | Notes |
|---|---|---|
| React, React DOM | MIT | |
| Vite, @vitejs/plugin-react | MIT | |
| TypeScript | Apache 2.0 | |
| @types/node, @types/react, @types/react-dom | MIT | Development type declarations |
| tsx | MIT | Runs the lesson engine's timing tests |
| @fontsource/noto-sans, @fontsource/noto-sans-mono, @fontsource/noto-sans-devanagari, @fontsource/noto-sans-kannada, @fontsource/noto-sans-tamil, @fontsource/noto-sans-telugu, @fontsource/noto-sans-bengali | SIL OFL 1.1 | Local font assets; OFL notices bundled with the files |
| Tailwind CSS | MIT | App shell only |
| prism-react-renderer | MIT | Code highlighting |
| **Remotion** (`remotion`, `@remotion/*`, v4) | **Remotion License** | Free for individuals, for-profit companies of up to 3 people, and non-profits; commercial use allowed for them. **Source-available, not OSI open source.** Larger companies need a paid company licence. We pin v4 (v5 changes the licence slightly) |
| Chrome Headless Shell (downloaded by Remotion) | BSD-3-Clause (Chromium) + third-party notices | Renders frames |
| Playwright + Chromium | Apache 2.0 / BSD-3-Clause | Plan B exporter only |
| playwright-core | Apache 2.0 | Phase 2 browser smoke checks using installed Chromium |

## 4. Tools and fonts
| Component | Licence | Notes |
|---|---|---|
| Ollama (includes llama.cpp) | MIT | |
| FFmpeg / ffprobe | LGPL-2.1+; GPL when built with GPL parts (most full Windows builds, incl. libx264) | Used as a separate program, not linked |
| Node.js | MIT | |
| Noto Sans, Noto Sans Devanagari / Kannada / Tamil / Telugu / Bengali, Noto Sans Mono | SIL Open Font License 1.1 | Bundled in `web/public/fonts/` |

## 5. Considered and not used
| Component | Why not |
|---|---|
| Qwen2.5-3B | Qwen *research* licence: non-commercial |
| Meta MMS-TTS | CC BY-NC 4.0: non-commercial |
| Indic-Speak (Bodhan AI) | Custom licence with hosting conditions; 3.8B parameters, GPU-only; needs transformers 5 (Parler needs 4.46) |
| NII AntiDeepfake | Non-commercial; not relevant here |
| Any cloud API (OpenAI, Gemini, Claude, ElevenLabs, Google/Microsoft voices, Google Translate) | Forbidden by the PS |

## 6. README section (paste into the repo README)
```markdown
## Models, voices and licences
Everything runs locally; no external AI APIs.

| What | Component | Licence |
|---|---|---|
| Lesson planner | Qwen3-8B (GPU) / Qwen3-4B-Instruct-2507 (CPU) via Ollama | Apache 2.0 |
| Translation | AI4Bharat IndicTrans2 en→Indic dist-200M | MIT |
| Voice (English, Hindi) | Kokoro-82M (voices hf_alpha, hm_omega) via kokoro-onnx | Apache 2.0 (model), MIT (library) |
| Voice (Kannada and other Indian languages, GPU) | AI4Bharat Indic Parler-TTS | Apache 2.0 |
| Phonemes for Kokoro | espeak-ng via phonemizer | GPL-3.0 (used as installed libraries) |
| Video engine + MP4 export | Remotion 4 | Remotion License (free for individuals and teams of up to 3; source-available) |
| Fonts | Noto Sans family | SIL OFL 1.1 |
| Other libraries | FastAPI, Pydantic, transformers, PyTorch, React, Vite, FFmpeg | MIT / BSD / Apache 2.0 / LGPL-GPL (FFmpeg) |
```
