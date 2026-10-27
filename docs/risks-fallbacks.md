# Risks and fallbacks — Blu VisualTeacher

Associated file · What could break, what we do about it, and the checklists.
Runtime fallbacks per stage: `pipeline.md` §11. Cut order: `task-split.md` §6.

---

## 1. Tonight checklist
| # | Item | How | Status |
|---|---|---|---|
| 1 | Kokoro works offline | `test-cases.md` T1 | ✅ 27 Oct |
| 2 | IndicTrans2 works offline | T2 | ✅ 27 Oct |
| 3 | `qwen3:4b-instruct-2507-q4_K_M` pulled | `ollama pull …`, then `ollama list` shows ~2.5 GB | ☐ |
| 4 | Planner JSON check, both models | T3 | ☐ |
| 5 | Backend packages | `& $py -m pip install fastapi "uvicorn[standard]" httpx psutil` | ☐ |
| 6 | npm prefetch + Remotion browser | `architecture.md` §9 (T8) | ☐ |
| 7 | Fonts: Noto Sans Mono (+ Tamil, Telugu, Bengali for bonus) | into `C:\Users\ROG\Kavach\fonts` | ☐ |
| 8 | Voice test: Kannada engine, English accent, Latin terms | T4–T6, Varun judges Kannada | ☐ |
| 9 | Masking round trip | T7 | ☐ |
| 10 | Offline check | T9 | ☐ |
| 11 | Varun's laptop | T10 | ☐ |
| 12 | Charge both laptops; pack chargers, a phone cable, a USB drive with `models\` | – | ☐ |
Items 3, 5 and 6 matter most: without them, H+0 can't start.

## 2. At H+0 (first 30 minutes)
1. Create `C:\Users\ROG\VisualTeacher`, unzip the docs there, `git init`, `.gitignore`, push to a private repo, add Varun.
2. `.env` from `architecture.md` §6, with `MODELS_DIR=C:\Users\ROG\Kavach\models`, `INDICTRANS_MODEL=indictrans2`.
3. Copy `Kavach\fonts\*` → `web\public\fonts\` (after Varun scaffolds `web/`).
4. `ollama ps`, health check, both laptops on the same Wi-Fi or hotspot.
5. Write H+0's clock time into `task-split.md`.

## 3. Risks
| # | Risk | Likely | Impact | What we do |
|---|---|---|---|---|
| R1 | Planner returns bad JSON or a weak plan | Med | High | Schema `format` + Pydantic + auto-fix + 1 repair + fallback; prompt check before building on it |
| R2 | Planner slow on CPU (2–5 min) | High | Med | 4B model on CPU; warm-up at start; cached plans; the UI shows each stage moving |
| R3 | `qwen3:8b` + Parler run out of 8 GB VRAM | Med | High | Unload the LLM after `validate` when the voice stage uses Parler; Parler in bf16; last resort: `qwen3:4b` on the GPU too |
| R4 | Parler sounds wrong or garbled for a language | Med | Med | T4 decides; Kokoro is the fallback engine for every language |
| R5 | Kannada through Kokoro sounds foreign | Med | Med | Parler on the GPU profile if it rates better (T4) |
| R6 | Translation mangles terms or placeholders | Med | Med | T7 picks the placeholder style; restore check; unmasked retry |
| R7 | Indic text renders wrong (broken conjuncts, boxes) | Low | High | Local Noto fonts, `lang` attribute, check real hi/kn renders at H+10–12 |
| R8 | Captions or labels overflow | Med | Med | Chunk limits, 2-line clamp, font shrink (`scene-components.md` §3) |
| R9 | Audio and visuals drift | Low | High | Per-beat clips + frames from audio lengths; ffprobe duration check |
| R10 | Remotion render fails offline (browser missing, font timeout) | Med | High | Prefetched Chrome Headless Shell; 60 s timeout; Plan B exporter (`export.md` §6) |
| R11 | `@remotion/*` version mismatch | Med | Med | Install all at one version; `npx remotion versions` |
| R12 | A judge asks about Remotion's licence | Low | Low | Free for individuals and teams of up to 3; source-available, not OSI open source. Say so plainly (`licenses.md`) |
| R13 | A network call slips in (CDN font, HF download) | Med | High | Offline env vars; no CDN links; T9 and the H+18 run with Wi-Fi off; grep the repo for `http` before the freeze |
| R14 | transformers gets upgraded | Low | High | Never `pip install -U`; check `pip show transformers` = 4.46.1 before the demo |
| R15 | UTF-8 problems with Indic text on Windows | Med | Med | `encoding="utf-8"` on every file read/write; JSON with `ensure_ascii=False`; `PYTHONIOENCODING=utf-8` |
| R16 | Venv not active in PowerShell | High | Low | Use `& …\Activate.ps1` or `& $py` |
| R17 | Judges call out a language we don't support | Med | Med | Show the supported list; offer the closest; bonus languages ready by H+18 |
| R18 | A live lesson states something wrong | Med | High | Low temperature, textbook rule, code parse check; admit it, regenerate, or fix with edit-one-scene |
| R19 | Falling behind schedule | Med | High | Checkpoints at H+2, 5, 8, 12, 16; cut early (`task-split.md` §6) |
| R20 | Laptop sleeps or the projector misbehaves | Low | High | High-performance power plan, sleep off, charger in; test the projector early; backup video from H+20 |
| R21 | Phone playback stutters | Low | Med | Light player (no filters, per-language fonts); the MP4 is the phone fallback |
| R22 | The cache fills the disk | Low | Low | Lessons are ~5–10 MB each; clear `cache\lessons` before the demo if needed (keep the fallback package) |

## 4. Offline gotchas
- `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` must be set before transformers is imported (`config.py` first).
- Parler's description tokenizer (flan-t5) loads by name from the HF cache (T4).
- No Google Fonts, no CDN scripts, no `<link>` to the web anywhere in `web/`.
- Ollama must already have both planner models; `ollama list` before going offline.
- `npm i` at the event: use `--prefer-offline`; the Remotion browser must already be there.
- Windows may block the backend port on a new network: allow Python through the firewall once, while online.

## 5. If something fails during the demo
| What you see | Say / do |
|---|---|
| Planner slow | Narrate the stage panel; the times are part of our speed story |
| Fallback banner | "That's the robustness path: invalid plans never reach the screen." Then generate again |
| MP4 still rendering | Play the lesson in the browser; the MP4 lands while we talk |
| Anything crashes | Restart the backend (≈ 30 s warm-up); meanwhile show the backup video and a cached lesson |
