# Narration and languages — Blu VisualTeacher

Build file · Translation, term masking, voices, speech text, captions and fonts per language. Code: `backend/app/localize/`, `backend/app/speech/`, `web/src/lesson/fonts.ts`.
Stage order and caching: `pipeline.md` §4–6.

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
Model folder: `MODELS_DIR\indictrans2` (the files sit directly in it). **Verified offline on the demo laptop, 27 Oct** (`test-log.md` T2).
```python
tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(path, trust_remote_code=True)   # .to("cuda").half() on gpu
ip = IndicProcessor(inference=True)        # from IndicTransToolkit import IndicProcessor  (v1.1.1)
batch = ip.preprocess_batch(texts, src_lang="eng_Latn", tgt_lang=tag)
enc = tok(batch, truncation=True, padding="longest", max_length=256, return_tensors="pt")
out = model.generate(**enc, max_length=256, num_beams=4)   # num_beams=2 on cpu
result = ip.postprocess_batch(tok.batch_decode(out, skip_special_tokens=True), lang=tag)
```
- Batch size 16. All strings of one lesson go in one call.
- Skip a string that has no real words outside protected spans (§3), e.g. `i = 0`, `F = m × a`.
- Cache: `cache/translations/<lang>.json`, key `sha1(text + model)`.

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
5. **Check:** every placeholder appears exactly once and none is left over. If not, translate that string again without masking and log a warning.

**Placeholder format: decided by test T7** (`test-cases.md`) before translation is built. Candidates in order: `<ID101>`-style (IndicProcessor's own placeholder style, numbered from 101), then `[T1]`, then no masking. Pick the first that survives 10 of 10 round trips.

What the test on 27 Oct showed: unmasked, IndicTrans2 already wrote "loop" as लूप (spoken English in Devanagari), which is fine. Masking matters for words it would otherwise *translate*, e.g. "range" → सीमा ("limit"), which would be wrong in a lesson.

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
| `hf_alpha` | female | en (Indian-accented), hi, and kn/ta/te/bn/mr on the cpu profile |
| `hm_omega` | male | same |
`speed` = the learner's speed (0.85 / 1.0 / 1.15). Load once at startup; one call per beat.

### Indic Parler-TTS (GPU profile)
```python
model = ParlerTTSForConditionalGeneration.from_pretrained(path, torch_dtype=torch.bfloat16).to("cuda")
tok = AutoTokenizer.from_pretrained(path)
desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)   # flan-t5 tokenizer
```
- **Offline trap:** `desc_tok` loads the flan-t5 tokenizer by name from the Hugging Face cache. If T4 fails offline on that line, run it once online to cache it.
- Description (fill speaker and pace): *"{speaker} speaks at a {pace} pace with a clear, close-sounding voice. The recording is very clear audio with no background noise."* Pace: 0.85 → "slightly slow", 1.0 → "moderate", 1.15 → "slightly fast".
- Batch every beat of a lesson in one `generate` (same description repeated, prompts padded). Use `return_dict_in_generate=True` and trim each output to its `audios_length`.
- `torch.manual_seed(7)` before generating, so the voice stays steady.
- Output rate `model.config.sampling_rate` (44.1 kHz) → resampled to 24 kHz.
- If bf16 sounds wrong, use fp32 and unload the LLM first (`architecture.md` §5).

### Engine choice (`speech/engines.py`)
`engine_for(lang, voice, profile)` follows the table in `pipeline.md` §5. On any engine error for a beat, try the other engine once.

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
