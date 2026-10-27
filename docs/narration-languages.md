# Narration and languages — Blu VisualTeacher

Build file · Translation, term masking, voices, speech text, captions and fonts per language. Code: `backend/app/localize/`, `backend/app/speech/`, `web/src/lesson/fonts.ts`.
Stage order and caching: `pipeline.md` §4–6.

Task 7 current status: translation supports six Indic tags. English/Hindi keep
Kokoro; Kannada has a lazy local Indic Parler-TTS adapter for CPU/configured CUDA.
Code approval defaults to en; this deployment has en,hi after owner approval on
27 October 2026. Kannada remains separately unapproved. Bonus voice rows are plans.

---

## 1. Language table
| Code | Language | IndicTrans2 tag | Script | Font | Kokoro `lang` | Parler voices (F / M) | Caption max chars | Tier |
|---|---|---|---|---|---|---|---|---|
| `en` | English | – | Latin | Noto Sans | `en-us` or `en-gb` (T5 decides) | not used | 90 | core |
| `hi` | Hindi | `hin_Deva` | Devanagari | Noto Sans Devanagari | `hi` | `Divya` / `Rohit` | 90 | core |
| `kn` | Kannada | `kan_Knda` | Kannada | Noto Sans Kannada | `kn` | `Anu` / `Suresh` | 80 | core |
| `ta` | Tamil | `tam_Taml` | Tamil | Noto Sans Tamil | `ta` | `Jaya` / – | 75 | bonus |
| `te` | Telugu | `tel_Telu` | Telugu | Noto Sans Telugu | `te` | `Lalitha` / `Prakash` | 80 | bonus |
| `bn` | Bengali | `ben_Beng` | Bengali | Noto Sans Bengali | `bn` | `Aditi` / `Arjun` | 85 | bonus |
| `mr` | Marathi | `mar_Deva` | Devanagari | Noto Sans Devanagari | `mr` | `Sunita` / `Sanjay` | 90 | bonus |
Parler voices are the model card's recommended speakers. Tamil has no recommended male voice: male Tamil uses Kokoro `hm_omega`.
A language shows in the UI only if its engine for the current profile passed its listening test (`test-log.md`).

## 2. Translation (IndicTrans2 en→Indic dist-200M)
Public interface: `localize_lesson(lesson, lang, settings, translator=None)`;
optional keyword `voice`/`speed` select variant paths. Returns a validated
`LocalizeResult` with lesson, quality, English fallback fraction, diagnostics,
warnings, statistics and provenance. The fake translator protocol exposes
`identity` and `translate(texts, target_tag, num_beams=...)` for tests.

Model folder: configured `INDICTRANS_MODEL`, default `MODELS_DIR/indictrans2`.
Lazy singleton per local path/device profile; existing local Python implementation
is trusted, `local_files_only=True`, offline flags forced before imports. CPU
float32, GPU float16, device from config; Transformers remains **4.46.1**.
Toolkit `IndicProcessor` handles eng_Latn → the target tag. Source overflow beyond
256 tokens fails explicitly; protected content is never silently truncated.

- Deduplicate source strings and infer in chunks of 16, CPU beams 2; script retry beams 5.
- Translate only lesson title; scene heading/narration/subtitle/center; step
  text/note/narration. Code/language/layout/expression/lines/output/keep_terms,
  IDs and structure are preserved. Unknown future string fields warn.
- Translate prose around expressions; skip only fields with no prose outside
  protected spans. Localized display-length overages warn without truncation.
- String cache `cache/translations/<lang>.json` uses SHA-256 of masked source,
  target tag, model asset identity, localization version and masking fingerprint.
  Entries include a checksum and are rechecked for script/protection on reuse.
- Variant `lesson.json` plus checked `localization.json` commit record include
  source-plan hash, language/tag, model, versions, variant, quality and diagnostics.
  Both are atomic replacements; missing/stale/mismatched records are rejected.
  No localization metadata is inserted into Lesson v1.
- `LOCALIZE_MAX_ENGLISH_FRACTION=0.2`: production rejects excessive English
  fallback at `translate`, before TTS. Denominator is eligible narration beats;
  code-only beats and protected Latin technical terms are excluded. Quality is
  `partial` if any field falls back, even when narration fraction is acceptable.
- LOW_RAM release is synchronized and follows persisted caches/artifacts. Health
  reports readiness only while successful initialization is resident.

CLI (translation only, no TTS/MP4):
`python -m backend.localize_lesson --lesson c1f63f0ed69b --lang hi --show 6`.
An English plan path may replace the ID; `--lang kn` produces Kannada fixtures.
CLI returns 2 for an English fallback fraction exceeding the configured ceiling.

**Script check** after each string: at least 70% of its letters (outside protected spans) must be in the target script's Unicode block (Devanagari `0900–097F`, Bengali `0980–09FF`, Tamil `0B80–0BFF`, Telugu `0C00–0C7F`, Kannada `0C80–0CFF`). Fail → retranslate with `num_beams=5`; fail again → keep English for that string and add a warning.

## 3. Keeping terms and code in English (masking)
The PS tip: keep code, numbers and technical terms in English where students would say them that way.
1. **Find protected spans** in the English string, longest first:
   - code calls: `[A-Za-z_][\w.]*\([^()]*\)` → `range(3)`, `print(i)`
   - expressions: anything around `= < > + − * / ÷ × →`, e.g. `i = 0`, `a = 10 ÷ 2 = 5 m/s²`
   - tokens with sub/superscripts or units: `H₂O`, `m/s²`
   - `keep_terms`, whole word, case-insensitive
2. **Replace** each span with a numbered placeholder.
3. **Translate.**
4. **Restore** the original English text into each placeholder.
5. **Check:** every placeholder appears exactly once; none is lost, duplicated or
   left over. Restoration failure gets one unmasked retry; accept it only with
   protected spans verbatim and a passing target-script check. Otherwise retain
   the English field and record a structured reason. Script failure gets one
   beam-5 retry; continued failure also retains English with diagnostics.

**T7 measured, 27 Oct 2026:** `<ID101>` survived hi 10/10, kn 9/10;
`[T1]` hi 9/10, kn 4/10; unmasked exact technical-term survival 0/10 each.
No format passed 10/10 in both languages. Use ID placeholders with mandatory
checks/fallback; never assume unconditional survival. Kannada's failed ID was
transliterated as `<ಐಡಿ101>`. Full inputs/outputs: `scratch/task6/t7.json`.
Units (including plain SI units), identifiers, numbers and sub/superscript tokens
are protected; code-derived identifiers and formula fragments join keep_terms.

Unmasked `range` became `सीमा` in Hindi and `ವ್ಯಾಪ್ತಿ` in Kannada. Technical
terms must stay exact, even when transliteration would sound similar.

## 4. Speech text (`speech/textnorm.py`)
Input: the localized narration for one beat.
- Collapse whitespace; remove `( ) [ ] { } < > _ * # \` | "`.
- End with sentence punctuation: `।` for hi/mr (keep IndicTrans2's), `.` otherwise.
- Keep `keep_terms` in Latin letters. Kokoro reads them in English (espeak switches language on Latin words); for Parler, T6 checks.
- Numbers are already words in English narration. If digits survive translation, Kokoro reads them in the target language; Parler is checked in T6.

## 5. Voices
### Kokoro (`kokoro-onnx` 0.6.1, CPU) — **verified offline 27 Oct** (`test-log.md` T1)
```python
k = Kokoro(models / "kokoro/kokoro-v1.0.onnx", models / "kokoro/voices-v1.0.bin")
audio, sr = k.create(text, voice="hf_alpha", speed=1.0, lang="hi")   # sr = 24000
```
| Voice | Gender | Used for |
|---|---|---|
| `hf_alpha` | female | en (Indian-accented), approved hi |
| `hm_omega` | male | same |
`speed` = the learner's speed (0.85 / 1.0 / 1.15). Load lazily once; one call per beat.

### Indic Parler-TTS — implemented Kannada adapter (Task 7)

AI4Bharat/Hugging Face Indic Parler-TTS, Apache-2.0. Prior verified experiment
identifies revision `660bc53c64ae83150613264111708a0465211237`; actual cache identity
hashes local assets/package versions. PARLER_MODEL defaults to
MODELS_DIR/indic-parler-tts. PARLER_DESCRIPTION_TOKENIZER defaults to the separate
MODELS_DIR/parler-description-tokenizer; never fetch the remote config name.

- Local-only lazy model/tokenizers; no heavy load at import/en/hi requests.
  CPU float32 / PARLER_CPU_THREADS=4; configured CUDA uses bfloat16.
  Transformers remains 4.46.1; no model/package changes.
- Female→Anu, male→Suresh are distinct named controls recommended in the local
  model card. Unknown speakers fail; naturalness/pronunciation still need review.
- One clip per beat; sample=True, temperature 1, top_k 50, top_p 1, one beam,
  cache=True, isolated per-beat PARLER_SEED=7. PARLER_MAX_NEW_TOKENS=2400;
  near-cap output is an error, never silently truncated speech.
- Fixed moderate-pace description; requested speed uses deterministic FFmpeg
  atempo. kn-speech-v1 only applies established speech markup cleanup. Original
  text/captions/code and Latin technical terms remain intact; no guessed phonetics.
- Raw 44,100 Hz is normalized/resampled to validated 24,000 Hz mono PCM16.
  Silent/nonfinite/corrupt/wrong-format audio is rejected.
- Existing audio_key convention is extended for Kannada with canonical lesson
  ID, original/normalized narration, kn/Parler, named speaker, speed, asset/package/
  generation/normalization versions. .kn.json records validate SHA-256, spec,
  sample rate and measured samples before reporting cached success.
- Shared reentrant lock covers initialization, inference/RNG, sessions and release.
  LOW_RAM releases after clip publication and waits for other active users.
- CPU feasibility: load 6.258 s; Anu native 27.719 s synthesis / 6.293 s audio
  (RTF 4.405), Suresh technical 18.503 / 4.807 s (RTF 3.849). Peak sampled RSS
  6826.62 MiB. Budget about 7 GiB plus OS/render memory; this is not an 8-GB-laptop
  performance acceptance. Measurements and warnings: task7-status.md.

### Engine choice (`speech/engines.py`)
`run_voice` dispatches en/hi through unchanged Kokoro and kn through its separate
adapter. No alternate-engine fallback. ENABLE_PARLER=0 removes kn capability
even if approved. All languages retain the canonical English plan identity.

## 6. Captions
- Text = the beat's localized narration (not the speech text), so captions keep `keep_terms` and punctuation as written.
- Chunking and timing: `pipeline.md` §6 (limits in §1 above).
- Captions are in the lesson's script by construction; the script check (§2) guards against English leaking in.
- SRT: the same chunks, UTF-8.

## 7. Fonts (`fonts.ts`)
Files in `web/public/fonts/`, loaded with `@remotion/fonts` → `loadFont({family, url: staticFile(...)})`.
| Language | Family stack |
|---|---|
| en | `"Noto Sans", sans-serif` |
| hi, mr | `"Noto Sans Devanagari", "Noto Sans", sans-serif` |
| kn | `"Noto Sans Kannada", "Noto Sans", sans-serif` |
| ta | `"Noto Sans Tamil", "Noto Sans", sans-serif` |
| te | `"Noto Sans Telugu", "Noto Sans", sans-serif` |
| bn | `"Noto Sans Bengali", "Noto Sans", sans-serif` |
| code | `"Noto Sans Mono", monospace` |
Load Latin + mono + the lesson's script. Every text element gets `lang="<code>"`.

## 8. Adding a language (bonus)
1. Row in §1 + `config.py` language list
2. Font file + `fonts.ts` stack
3. Listening test (Kokoro and/or Parler) → `test-log.md`
4. Run the fallback lesson in it, check captions and the MP4
About 20 minutes per language once the core works.
