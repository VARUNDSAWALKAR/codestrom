# Test cases — Blu VisualTeacher

Build file · Tonight's model checks, then acceptance tests at the event. Results go in `test-log.md`.
The tonight scripts are **throwaway checks**: run them from a scratch folder, never commit them (all project code is written at the event).

PowerShell setup for every test (the venv's `activate` doesn't work in PowerShell; use its Python directly):
```powershell
$py = "C:\Users\ROG\Kavach\kavach-env\Scripts\python.exe"
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"; $env:PYTHONIOENCODING="utf-8"
```

---

## 1. Tonight (before H+0)
| # | Test | Status |
|---|---|---|
| T1 | Kokoro loads offline and speaks | ✅ 27 Oct |
| T2 | IndicTrans2 loads offline and translates | ✅ 27 Oct |
| T3 | Planner JSON with the schema: `qwen3:8b` (GPU) and `qwen3:4b-instruct` (CPU) | ☐ |
| T4 | Kannada voice: Kokoro vs Parler; Parler loads offline | ☐ |
| T5 | English accent: `en-us` vs `en-gb` with `hf_alpha` | ☐ |
| T6 | Latin terms and digits: Hindi via Kokoro, Kannada via Parler | ☐ |
| T7 | Masking placeholders survive translation | ☐ |
| T8 | npm prefetch + Remotion browser | ☐ |
| T9 | Everything above with Wi-Fi off | ☐ |
| T10 | Varun's laptop ready | ☐ |

### T3 — Planner JSON check
Needs `data\lesson.schema.json` (in the zip). GPU run:
```powershell
$schema = Get-Content C:\Users\ROG\VisualTeacher\data\lesson.schema.json -Raw | ConvertFrom-Json
$body = @{ model = "qwen3:8b"; stream = $false; think = $false; format = $schema
  options = @{ temperature = 0.3; num_ctx = 4096; num_predict = 2000 }
  messages = @(@{ role = "user"; content = "Plan a 60-second beginner video lesson as JSON: How does a Python for loop work? 3 to 5 scenes: title_card first, then a code_walkthrough, a flow diagram, and a recap last. Every step needs narration." }) } | ConvertTo-Json -Depth 30
$sw = [Diagnostics.Stopwatch]::StartNew()
$r = Invoke-RestMethod -Uri http://127.0.0.1:11434/api/chat -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/json; charset=utf-8" -TimeoutSec 600
$sw.Stop(); "{0:N1} s, {1} tokens" -f $sw.Elapsed.TotalSeconds, $r.eval_count
($r.message.content | ConvertFrom-Json).scenes | Select-Object type, heading
```
CPU run: change the model to `qwen3:4b-instruct-2507-q4_K_M`, **delete** `think = $false;`, and add `num_gpu = 0;` inside `options`.
Pass: both print a scene table (valid JSON in our shape). Note the seconds and tokens for each in `test-log.md`; tokens ÷ seconds = speed.

### T4–T6 — Voice test (one script)
Save as `C:\Users\ROG\scratch\voice_test.py`, run `& $py voice_test.py` from that folder, then listen to the WAVs.
```python
# voice_test.py - throwaway check, not project code
import os, time
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
import soundfile as sf, torch
from kokoro_onnx import Kokoro
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor

M = r"C:\Users\ROG\Kavach\models"
EN = ["A loop repeats the same instruction for each value in a sequence.",
      "range of three gives three values: zero, one and two.",
      "In the second pass, i is one, so it prints one."]

tok = AutoTokenizer.from_pretrained(M + r"\indictrans2", trust_remote_code=True)
mt = AutoModelForSeq2SeqLM.from_pretrained(M + r"\indictrans2", trust_remote_code=True)
ip = IndicProcessor(inference=True)
def tr(lines, tag):
    b = ip.preprocess_batch(lines, src_lang="eng_Latn", tgt_lang=tag)
    x = tok(b, return_tensors="pt", padding=True)
    y = mt.generate(**x, max_length=128, num_beams=4)
    return ip.postprocess_batch(tok.batch_decode(y, skip_special_tokens=True), lang=tag)
KN, HI = tr(EN, "kan_Knda"), tr(EN, "hin_Deva")
print("KN:", KN); print("HI:", HI)

k = Kokoro(M + r"\kokoro\kokoro-v1.0.onnx", M + r"\kokoro\voices-v1.0.bin")
def kok(name, text, lang, voice="hf_alpha"):
    t = time.time(); a, sr = k.create(text, voice=voice, lang=lang); sf.write(name, a, sr)
    print(f"{name}: {len(a)/sr:.1f} s audio in {time.time()-t:.1f} s")
kok("T5_en_us.wav", " ".join(EN), "en-us")
kok("T5_en_gb.wav", " ".join(EN), "en-gb")
kok("T6_hi_kokoro.wav", " ".join(HI), "hi")
kok("T6_hi_latin_terms.wav", "Python में loop हर value के लिए एक ही काम दोहराता है। range 3 देता है।", "hi")
kok("T4_kn_kokoro_female.wav", " ".join(KN), "kn")
kok("T4_kn_kokoro_male.wav", " ".join(KN), "kn", "hm_omega")

from parler_tts import ParlerTTSForConditionalGeneration
dev = "cuda" if torch.cuda.is_available() else "cpu"
pm = ParlerTTSForConditionalGeneration.from_pretrained(M + r"\indic-parler-tts").to(dev)
ptok = AutoTokenizer.from_pretrained(M + r"\indic-parler-tts")
dtok = AutoTokenizer.from_pretrained(pm.config.text_encoder._name_or_path)   # offline trap: see below
def par(name, text, speaker):
    d = f"{speaker} speaks at a moderate pace with a clear, close-sounding voice. The recording is very clear audio with no background noise."
    t = time.time(); torch.manual_seed(7)
    di, pi = dtok(d, return_tensors="pt").to(dev), ptok(text, return_tensors="pt").to(dev)
    g = pm.generate(input_ids=di.input_ids, attention_mask=di.attention_mask, prompt_input_ids=pi.input_ids, prompt_attention_mask=pi.attention_mask)
    a = g.cpu().numpy().squeeze(); sr = pm.config.sampling_rate; sf.write(name, a, sr)
    print(f"{name}: {len(a)/sr:.1f} s audio in {time.time()-t:.1f} s on {dev}")
par("T4_kn_parler_anu.wav", " ".join(KN), "Anu")
par("T4_kn_parler_suresh.wav", " ".join(KN), "Suresh")
par("T6_kn_parler_latin_terms.wav", "Python ನಲ್ಲಿ loop ಪ್ರತಿ value ಗೆ ಒಂದೇ ಕೆಲಸ ಮಾಡುತ್ತದೆ. range 3 ನೀಡುತ್ತದೆ.", "Anu")
```
- **Free the GPU first** if T3 just ran: `ollama stop qwen3:8b` (Parler runs in fp32 here and needs ~4 GB of VRAM).
- **If the `dtok` line fails offline:** the flan-t5 tokenizer isn't cached. Run the script once with Wi-Fi on (it caches it), then again offline.
- **Judge by ear:** Varun rates every Kannada file 1–5 for naturalness and correctness; Satwik rates Hindi and English. RTF = synth seconds ÷ audio seconds (printed).
- **Decisions this settles:** the `kn` engine on the GPU profile (best-rated voice wins, if Parler's RTF ≤ 1 on the GPU) · `en-us` vs `en-gb` · whether Latin terms are spoken correctly (if not, `narration-languages.md` §4 changes before the event).

### T7 — Masking round trip
Save as `mask_test.py` next to `voice_test.py` and run it.
```python
# mask_test.py - throwaway check, not project code
import os, re
os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit import IndicProcessor
p = r"C:\Users\ROG\Kavach\models\indictrans2"
tok = AutoTokenizer.from_pretrained(p, trust_remote_code=True)
mt = AutoModelForSeq2SeqLM.from_pretrained(p, trust_remote_code=True)
ip = IndicProcessor(inference=True)
CASES = [("{0} of three gives three values: zero, one and two.", ["range"]),
         ("The indented line runs once, and {0} shows the value of i.", ["print"]),
         ("A for {0} repeats its indented code once for each value.", ["loop"]),
         ("Here is a {0} with just two lines of {1}.", ["loop", "Python"]),
         ("The {0} i takes these values one at a time.", ["variable"]),
         ("Call the {0} with two numbers, and it returns their sum.", ["function"]),
         ("Each item in the {0} is checked one by one.", ["list"]),
         ("The while {0} runs as long as the condition is true.", ["loop"]),
         ("{0} cuts the {1} in half at every step.", ["Binary search", "list"]),
         ("The {0} statement checks a condition before running the code.", ["if"])]
STYLES = {"ID": lambda n: f"<ID{101+n}>", "T": lambda n: f"[T{n+1}]"}
def tr(lines, tag):
    b = ip.preprocess_batch(lines, src_lang="eng_Latn", tgt_lang=tag)
    x = tok(b, return_tensors="pt", padding=True)
    return ip.postprocess_batch(tok.batch_decode(mt.generate(**x, max_length=128, num_beams=4), skip_special_tokens=True), lang=tag)
for tag in ["hin_Deva", "kan_Knda"]:
    print("==", tag, "unmasked:", tr([c.format(*t) for c, t in CASES], tag)[:3])
    for sname, f in STYLES.items():
        out = tr([c.format(*[f(i) for i in range(len(t))]) for c, t in CASES], tag)
        ok = sum(all(o.count(f(i)) == 1 for i in range(len(t))) for o, (c, t) in zip(out, CASES))
        print(f"   style {sname}: {ok}/10 survived. e.g. {out[0]}")
```
Pick the first style with 10/10 in both languages; write it in `narration-languages.md` §3 and `test-log.md`. Also look at the unmasked lines: if "range" came out as सीमा / ವ್ಯಾಪ್ತಿ, masking is needed.

### T8 — npm prefetch
The block in `architecture.md` §9. Pass: `npx remotion versions` shows one version with no mismatch, `npx remotion browser ensure` finishes, and you've noted the path it printed.

### T9 — Offline
Wi-Fi off, then: T1, T2 commands from today · `ollama run qwen3:4b-instruct-2507-q4_K_M "Reply with OK"` · `voice_test.py` · `npx remotion versions` in `prefetch-web`. All must work.

### T10 — Varun's laptop
Node 24 + npm, the T8 prefetch, fonts, Git, and the repo cloned. Optional (for the weakest-laptop timing bonus): Python 3.11, Ollama + the 4B model, the models folder copied over by USB.

---

## 2. Acceptance tests at the event (the PS's "done when")
| # | Test | Pass |
|---|---|---|
| A1 | Submit the S1 form | Backend logs topic, level, language, length (stage 1) |
| A2 | 5 prompt-check topics (`prompts.md` §6) | Each validates or falls back; plans saved; pass bar met |
| A3 | Feed broken JSON / stop Ollama / `debug_fail: "plan"` | Fallback lesson plays with the banner, no crash |
| A4 | Player on the fallback lesson | Title card, diagram (labels + arrows), code walkthrough; play, pause, next scene, replay all work |
| A5 | Same lesson in en, hi, kn | Audio, captions in the right script, scenes in sync (§3) |
| A6 | MP4 export | ffprobe: 1280×720, h264, yuv420p, aac, duration ±0.2 s; plays in VLC and on a phone |
| A7 | `.srt` | Opens in VLC alongside the MP4; text and times match the burned-in captions |
| A8 | No manual steps | Topic typed → MP4 downloadable, nothing touched in between |

## 3. Sync checks (per language, on the fallback lesson and one LLM lesson)
- Caption chunks start within 1 frame of their beat and never overlap.
- Each step's reveal starts at its beat (step through frames in Remotion Studio around 3 beat boundaries).
- MP4 duration = timeline duration ±0.2 s.
- Listen at the start, middle and end: the voice matches the caption on screen.

## 4. Translation checks (hi and kn by native speakers; bonus languages by script check only)
- 10 strings per language from real lessons: meaning correct (yes/no), `keep_terms` still in English, no `<ID…>`/`[T…]` left over.
- Script check passes (`narration-languages.md` §2).
- Code, expressions and digits unchanged.

## 5. Topic-set run (`data/test_topics.json`, 20 topics)
Run all 20 through `POST /api/lessons` (a small loop script at the event). Log per topic: valid first try / after repair / fallback · `must_include` present · plan s · total s to playable · words ÷ budget · a 1–5 teaching score from a quick watch.
Targets: ≥ 17/20 without fallback · no factual errors in the topics shown to judges · median time to playable ≤ 90 s (GPU).

## 6. CPU-only run (H+14–16)
`set CUDA_VISIBLE_DEVICES=-1`, restart Ollama and the backend with `DEVICE=cpu`, `LOW_RAM=1`. Run t01 (en), t08 (hi), t13 (kn). Record each stage's seconds and peak RAM (UI stage panel), plus Task Manager's peak memory. Repeat on Varun's laptop if it's set up.

## 7. Phone check
- Real phone on the same Wi-Fi: open `http://<laptop-ip>:8000/#/lesson/<id>`; play the whole lesson; no stutter; captions readable.
- Chrome DevTools: device toolbar + CPU 4× slowdown, same lesson.
- MP4 copied to the phone plays.
- Note page weight (DevTools Network: JS + fonts + audio).

## 8. Demo rehearsal (H+18–20, twice)
Wi-Fi off · fresh backend start · health all green · a new topic in hi or kn (not cached) · plays · MP4 downloads · revoice to another language · fallback shown on purpose · stage times panel · phone playing an MP4 · under 5 minutes.
