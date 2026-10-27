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
