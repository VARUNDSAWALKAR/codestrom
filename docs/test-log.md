# Test log — Blu VisualTeacher

Associated file · Measured results only. Tests are defined in `test-cases.md`. Fill in as you go; the README's speed numbers and the demo's N values come from here.

---

## 1. Tonight's checks
| # | Date | Result | Notes |
|---|---|---|---|
| T1 Kokoro offline | 27 Oct | ✅ | `hf_alpha`, `en-us`: "A loop repeats an instruction." → 2.1 s of audio (`tts_test.wav`). Listen: ☐ |
| T2 IndicTrans2 offline | 27 Oct | ✅ | → "एक लूप एक निर्देश को दोहराता है।" Correct; "loop" came out as लूप without masking. Model folder = `models\indictrans2` itself |
| T3 Planner JSON, `qwen3:8b` GPU | | | s: ___ · tokens: ___ · tok/s: ___ · valid: ☐ |
| T3 Planner JSON, `qwen3:4b` CPU | | | s: ___ · tokens: ___ · tok/s: ___ · valid: ☐ |
| T4 Kannada voice | | | see §2 |
| T5 English accent | | | `en-us` ___/5 · `en-gb` ___/5 → pick: ___ |
| T6 Latin terms | | | Hindi Kokoro: "Python", "loop", "range 3" said right? ☐ · Kannada Parler: ☐ |
| T7 Masking | | | `<ID…>`: hi __/10, kn __/10 · `[T…]`: hi __/10, kn __/10 → pick: ___ · unmasked "range" became: ___ |
| T8 npm prefetch | | | Remotion version: ___ · browser path: ___ |
| T9 Offline | | | ☐ all passed |
| T10 Varun's laptop | | | CPU: ___ · RAM: ___ · GPU: ___ |

## 2. Voice listening results (T4–T6)
| File | Rated by | Natural (1–5) | Words right (1–5) | Audio s | Synth s | RTF | Device |
|---|---|---|---|---|---|---|---|
| T4_kn_kokoro_female | Varun | | | | | | CPU |
| T4_kn_kokoro_male | Varun | | | | | | CPU |
| T4_kn_parler_anu | Varun | | | | | | GPU |
| T4_kn_parler_suresh | Varun | | | | | | GPU |
| T5_en_us | Satwik | | | | | | CPU |
| T5_en_gb | Satwik | | | | | | CPU |
| T6_hi_kokoro | Satwik | | | | | | CPU |
| T6_hi_latin_terms | Satwik | | | | | | CPU |
| T6_kn_parler_latin_terms | Varun | | | | | | GPU |
**Decision:** Kannada on the GPU profile = ___ · English phonemes = ___

## 3. Prompt check (`prompts.md` §6)
| Prompt | Model | # | Valid first try | After repair | Fallback | Plan s | Words / budget | Factual errors | Scene types fit? |
|---|---|---|---|---|---|---|---|---|---|
| p1 | qwen3:8b | 1–5 | | | | | | | |
| p1 | qwen3:4b | 1–5 | | | | | | | |

## 4. Speech-rate calibration
| Language | Engine | English words | Audio s | Words/s (English words ÷ audio s) |
|---|---|---|---|---|
| en | Kokoro | | | |
| hi | Kokoro | | | |
| kn | ___ | | | |
Set the planner budget factor (`pipeline.md` §2, default 2.2) so the longest core language still fits 90 s.

## 5. Stage times (fill from the UI's stage panel)
| Run | Device | Language | plan | validate | translate | voice | timeline | → playable | export | Peak RAM |
|---|---|---|---|---|---|---|---|---|---|---|
| fallback lesson | GPU | en | – | – | – | | | | | |
| t01 | GPU | en | | | – | | | | | |
| t08 | GPU | hi | | | | | | | | |
| t13 | GPU | kn | | | | | | | | |
| t01 | CPU | en | | | – | | | | | |
| t08 | CPU | hi | | | | | | | | |
| t13 | CPU | kn | | | | | | | | |
| t01 | Varun's laptop (CPU) | en | | | – | | | | | |

## 6. Topic-set run (`data/test_topics.json`)
Valid first try __/20 · after repair __/20 · fallback __/20 · must_include met __/20 · median s to playable ___ · topics with factual errors: ___

## 7. Phone and render
| Check | Result |
|---|---|
| Phone browser plays a full lesson smoothly | ☐ |
| DevTools CPU 4× throttle, no stutter | ☐ |
| Page weight (JS + fonts + audio) | ___ KB |
| MP4 size for a 60 s lesson | ___ MB |
| Render speed (frames/s), GPU laptop | ___ |
| Render speed (frames/s), CPU profile | ___ |

## 8. Task 5C — production acceptance (real uvicorn + Ollama cache + Kokoro + Remotion + FFmpeg), 2026-10-27
Env: `DEVICE=cpu`, `MOCK_PIPELINE=0`, `PYTHONUTF8=1`, `LOW_RAM` unset; one uvicorn on 127.0.0.1:8000; model `qwen3:4b-instruct-2507-q4_K_M`. Bundle `C:\Users\ROG\VisualTeacher-varun\web\build\index.html`, modified `2026-10-27T15:48:01+05:30`, **unchanged between Run 1 and Run 2**. Planner stage was a cache hit in both runs (plans from the Task 4b CLI runs); fresh Ollama planning was verified in Task 5B (31 s).

| | Run 1: Water Cycle | Run 2: Binary Search |
|---|---|---|
| job / lesson / variant | `j_5804e58d3ff6` / `c1f63f0ed69b` / `en-female-1` | `j_5c36adf4b88d` / `d09d4030959b` / `en-female-1` |
| stages (ms) | plan 2 (cached), validate 0, translate skipped, voice 10,893, timeline 1,429, export 114,474 | plan 3 (cached), validate 1, translate skipped, voice 13,241, timeline 1,608, export 132,661 |
| wall clock | 127.2 s | 147.9 s |
| first preview_ready | t=12.7 s, export `running`, `mp4: null`, all preview URLs 200 | t=15.2 s, export `running`, `mp4: null`, preview URLs 200 |
| backend `rss_mb` (job-stage snapshots) | voice 616.5, timeline 621.2, export 617.1 | voice 677.9, timeline 682.3, export 677.4 |
| **sampled** peak RSS during export (psutil, 0.5 s) | backend 617.1 MB; renderer node+chrome 814.7 MB; backend+renderer 1431.7 MB; backend+all descendants 1894.8 MB (220 samples, 114.6 s) | backend 677.4; renderer 803.9; backend+renderer 1481.2; all 1958.6 (252 samples, 132.8 s) |
| MP4 | `cache\lessons\c1f63f0ed69b\en-female-1\lesson.mp4`, 1,398,933 B | `cache\lessons\d09d4030959b\en-female-1\lesson.mp4`, 1,673,394 B |
| ffprobe | h264 High, 1280x720, yuv420p, 30.0 fps, 1507 frames; aac 48 kHz stereo | h264 High, 1280x720, yuv420p, 30.0 fps, 1755 frames; aac 48 kHz stereo |
| durations (video / audio / container vs timeline) | 50.233 / 50.240 / 50.240 vs 50.2333 s (diffs 0.000 / 0.007 / 0.007) | 58.500 / 58.517 / 58.517 vs 58.500 s (diffs 0.000 / 0.017 / 0.017) |
| faststart | atoms `ftyp, moov, free, mdat` | moov before mdat |
| final-MP4 audio (volumedetect) | mean -23.4 dB, max -7.0 dB | mean -23.4 dB, max -7.7 dB |
| SRT vs timeline | 14 cues = 14 captions, ordered, intervals equal frames; last cue ends 0.6 s before end (scene tail) | 20 = 20, same checks; last cue 0.6 s before end |
| `props.sha1` | matches current props | matches |

Renderer process names in the sample: `node.exe`, `chrome.exe`. Sampled peaks are not exact peaks. Duration and volume checks do not establish perceptual A/V sync (not tested by ear).

**Visual review** (`scratch\accept\...`, kept for review): `water_cycle\contact_sheet.png` (+ `frame_01..08.png`): title card, left-to-right flow diagrams with arrows, active step highlighted, captions fit within 2 lines, nothing clipped; content defect: scene s2 headed "Title Card", s2 and s3 share the same four steps. `binary_search\contact_sheet.png` (+ `frame_01..05.png`, code scene only): code legible with line numbers, highlight bar moves per step, State panel shows the step, Output panel empty; **highlight is one line too early for every step** (lesson data: step 1 text is code line 2 but `lines=[1]`); the renderer is faithful to the lesson. Only the 11 lines of code are shown; steps cover lines 1-4 only.

**Repeat request** (Run 1): 202, `cached: true`, 47 ms, six stages `cached`, `cache/runs.jsonl`, MP4 and `props.sha1` mtimes unchanged, no child processes.

**Damaged output** (temporary copies only; real files hash-identical before/after): real folder -> True; truncated MP4 -> **True before the fix** (defect), False after; corrupted `props.sha1` -> False; untouched copy -> True.

**API checks (live server):** hi/kn/ta -> 422 `language_unavailable`; invalid fields -> 422 `validation_error`; unknown job -> 404 `job_not_found`; unknown/malformed lesson -> 404 `lesson_not_found`; CORS allowed for the three documented origins, rejected for `https://evil.example` and `http://localhost:8080`; Range request 206; `?download=1` has no `Content-Disposition` (not implemented).

**Regression:** `pytest backend/tests -q -rs`: **143 passed, 1 skipped** (baseline 141 + 1; +2 Mp4 structure regression tests; the skip is the renderer-conditional test at `test_task3.py:118`).

## 9. Task 6 — offline localization and Hindi preview, 2026-10-27

M0/M0b baseline was 160 passed, 1 skipped; it was reused rather than rerun.
CPU, PYTHONUTF8=1, HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1. Existing IndicTrans2
en-indic-dist-200M / IndicTransToolkit / Transformers 4.46.1; no package changes.
Mock M1+identity tests passed (35 tests) before real translation; focused M3
tests passed (68 tests, 13 subtests) before real Hindi speech. Final totals below.

T7: ten documented strings per language, num_beams=4, model reused across batches:

| Strategy | Hindi preserved | Kannada preserved |
|---|---:|---:|
| `<ID101>` | 10/10 | 9/10 |
| `[T1]` | 9/10 | 4/10 |
| Unmasked (exact original terms) | 0/10 | 0/10 |

ID is the safest tested format but not unconditional. Kannada lost one ID through
transliteration (`<ಐಡಿ101>`); strict restoration/retry guards remain required.
Unmasked range: `सीमा` / `ವ್ಯಾಪ್ತಿ`. Full T7 text/output/times: `scratch/task6/t7.json`.

Three existing cached English plans, two languages each; no new Ollama plans:

| Lesson/language | Seconds | Unique strings | Restore retries | Script retries/failures | English narration fraction | Quality |
|---|---:|---:|---:|---:|---:|---|
| Water Cycle hi | 7.169 | 21 | 0 | 0/0 | 0/11 | complete |
| Water Cycle kn | 3.348 | 21 | 0 | 0/0 | 0/11 | complete |
| Binary Search hi | 7.030 | 24 | 0 | 0/0 | 0/11 | complete |
| Binary Search kn | 7.140 | 24 | 0 | 2/2 | 0/11 | partial (2 labels) |
| Python for loop hi | 6.260 | 21 | 0 | 0/0 | 0/9 | complete |
| Python for loop kn | 6.178 | 21 | 1 | 0/0 | 1/9 = 0.1111 | partial |

Times include translation/cache publication and exclude process imports. First
Water Cycle Hindi includes cold model/asset-identity work. All accepted fields
pass the 70% script check outside protected spans. Protected content and structure
remain exact; fallback English is explicitly diagnosed. Each second call was a
validated cache hit without rewriting its commit record. Source plans unchanged.
Fixtures: `data/samples/localized/{water_cycle,binary_search,python_for_loop}.{hi,kn}.json`
and `.localization.json` diagnostics. Full statistics/warnings: `scratch/task6/m2.json`.
Example: Water Cycle → `जल चक्र` / `ನೀರಿನ ಚಕ್ರ`; the opening narration retains
literal `evaporation` and `collection` within translated prose. Narration expansion:
hi 1.20x chars / 1.30–1.50x words; kn 1.25–1.38x chars / 0.87–0.93x words.

Real Hindi TestClient smoke: `j_b7dc8b4c95d7`, `c1f63f0ed69b/hi-female-1`;
beginner, science, 60 s request. Approval only in test settings, production remains
en. Real translator initialized (2.529 s) and its M2 translation cache reused.
Guarded planner: zero Ollama calls, same canonical plan bytes. Real Kokoro and
timeline; exporter replaced with explicit skip. Stages: plan cached 4 ms,
validate 1 ms, translate cached 596 ms, voice 14,357 ms (11 beats, 1 cached),
timeline 1,591 ms, export skipped 0 ms. Job 16.552 s; wall 19.216 s.

Hindi WAV 24 kHz, 73.1 s, RMS 0.09674, peak 0.76935. Timeline 2193 frames at
30 fps, tempo 1.0; 14 captions, SRT matches exactly. HTTP media 200/nonempty:
WAV 3,508,844 B; M4A 640,045 B; SRT 2,532 B; timeline 4,460 B; props 9,545 B.
Preview ready before skip-export. MP4 null, no real MP4 rendered. Complete
localization, 0 eligible English fallback beats; five distinct note-length warnings,
no 90-second/tempo warning. Health translator/Kokoro ready; planner false because
injected acceptance operations deliberately install no live Ollama health probe.
`hi_technical_ready=true`, **human_approved=false**.

Review pack: `scratch/review/hi/` contains 20 pairs, technical examples,
warnings/stats, real narration WAV, matching SRT and an unchecked human-review
checklist. No browser visual review, pronunciation approval or new Hindi MP4
acceptance is claimed. Detailed smoke: `scratch/task6/hi_smoke.json`.

Final focused tests: **78 passed, 13 subtests passed in 2.12 s**.
Full backend regression: **197 passed, 1 skipped, 42 subtests passed in 41.99 s**;
specified Python, CPU/offline flags, bytecode disabled,
`python -m pytest backend/tests -q -rs -p no:cacheprovider`. Only skip remains
`test_task3.py:118`; no pytest warnings. `git diff --check` passed. Additional
tests cover unit/formula protection, overlapping unit spans, late placeholder
loss, current-source provenance and all six saved real fixtures.
Final CLI hi/kn checks were guarded against fresh inference and returned
`cached=true`; translator remained unloaded. Production approval verified en only.

## 10. Task 7 — real CPU Kannada TTS/preview/MP4, 2026-10-27

Preflight baseline: **197 passed, 1 skipped, 42 subtests in 44.39 s**. Hindi owner
approval and `.env` en,hi preserved. Kannada translation fixtures/canonical IDs
validated. Task split H+10-12 corresponds to this voice milestone (no numbered 7).

Local AI4Bharat/Hugging Face Indic Parler-TTS, Apache-2.0; prior verified revision
660bc53c64ae83150613264111708a0465211237. Existing 3,751,321,772-byte safetensors
plus local prompt and separate FLAN-T5 description tokenizer; no downloads.
torch 2.11.0+cu128 / transformers 4.46.1 / parler-tts 0.2.2 unchanged.

Fresh CPU float32/4-thread feasibility load **6.258 s**. Anu native sentence:
**27.719 s inference / 6.293 s audio, RTF 4.405**; Suresh technical/number sample:
**18.503 / 4.807 s, RTF 3.849**. Both 44.1 kHz, finite and non-silent, below cap.
Sampled peak RSS **6826.62 MiB**. Warnings: optional Flash Attention 2 absent,
component-config replacement notices, internal decoder attention-mask warning
despite explicit masks. No traceback/network connection attempt. Files:
`scratch/task7/feasibility/`. Non-silence is not a native pronunciation rating.

Mock checks ran before full generation: **90 passed, 13 subtests in 5.16 s**
(Task 7 plus Task 6/5B/2 regression set). Fixture timing/CRLF issues were corrected;
no production timing was hard-coded. Final Task 7 file: **23 passed in 3.75 s**,
including generation/normalization-version cache identity, actual synthetic audio
speed adjustment and LOW_RAM failure cleanup.

### M6 primary preview — passed, no retry

Job j_47e52c6ae18e; canonical c1f63f0ed69b; kn-female-1; beginner/science/60 s.
Both plan and Kannada translation cached under fresh-inference guards:
**zero Ollama calls, zero translator inference**, source plan unchanged.

| Stage | Status | ms |
|---|---|---:|
| plan | cached | 3 |
| validate | done | 1 |
| translate | cached | 562 |
| voice | done | 268159 |
| timeline | done | 1393 |
| export | deliberately skipped | 1 |

Cold TTS load inside voice **7.150 s**; **11 beats**, one cached, **68.011 s speech**.
Preview wall **271.060 s**, sampled RSS **6785.49 MiB** (job-stage snapshots also
recorded in report). WAV **24 kHz mono PCM16, 72.7 s**, RMS **0.09257**, peak
**0.89127**. Timeline **2181 frames / 30 fps**, tempo **1.0**, **17 captions**.
SRT cue/text/beat alignment validated; no duration-cap/90-second warning.
Seven existing note-length warnings. Preview ready before explicit export skip;
MP4 null/absent. HTTP 200 sizes: WAV 3,489,644 B; M4A 616,886 B; SRT 2,854 B;
timeline 4,819 B; props 10,335 B. Parler ready after real initialization, explicitly
released afterward. `.env` unchanged; Kannada approval only in test Settings.
Full metrics/clips: `scratch/task7/preview.json`.

### M7 primary export — passed, no retry

Existing exporter/renderer reused all M6 audio/timeline, unchanged. MP4
`cache/lessons/c1f63f0ed69b/kn-female-1/lesson.mp4`: **1,942,066 B**.
Export **163.650 s**, full acceptance wall **173.903 s**. FFprobe:
H.264 High, 1280x720, yuv420p, 30/1 fps, 2181 frames, video **72.700 s**;
AAC LC, 48 kHz stereo, audio/container **72.704 s**. Starts 0, A/V difference
**0.004 s**. Props/MP4 structure/provenance/full decode passed; HTTP Range **206**.
The acceptance script stopped only its own temporary backend; no existing process
was terminated. Production config still en/hi; no approval mutation.

Five PNGs inspected under `scratch/accept/kannada/`: Kannada glyphs visible,
no tofu boxes/obvious clipping; headings/captions/notes fit at sampled frames.
Expected captions and active step match sampled timeline beats. Technical diagram
labels remain English intentionally. Source-content defects (s2 headed Title Card,
repeated diagram steps) are unchanged from Task 5C, outside voice/render scope.
No frontend patch was needed. Native pronunciation/perceptual sync/full-video
readability still require a Kannada speaker. Full report: acceptance.json there.

### M8/M9 review and regression

`scratch/review/kn/`: 20 pairs, lesson, technical examples/warnings/fractions,
real WAV/SRT/MP4, five frames, performance report, Anu/Suresh short samples and
unchecked human checklist. Explicitly includes Task 6's two Binary Search labels
and one Python-loop narration English fallback. Human approval **not claimed**.

Final full backend suite: **220 passed, 1 skipped, 42 subtests in 47.66 s**;
only skip test_task3.py:118 (renderer exists), no pytest warnings. No tests removed
or newly skipped. `kn_technical_ready=true`; Kannada still disabled until separate
owner approval. Hindi approval retained. No Task 8/9/VQ1, commit/push/tag or new
package/model installation. CUDA and real-phone performance not tested.
