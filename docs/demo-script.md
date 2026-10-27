# Demo script — Blu VisualTeacher

Associated file · The 5-minute live demo (Wi-Fi off) and the 3 minutes of questions.
Rehearse twice at H+18–20 (`test-cases.md` §8). Satwik drives the laptop; Varun talks and holds the phone.

---

## Before the judges arrive
- Wi-Fi **off** (taskbar visible), charger in, sleep off, browser at 100% zoom on the projector.
- Backend freshly started; all health badges green; `GPU` badge showing.
- Tabs ready: (1) the app, S1 · (2) a cached lesson in Kannada, S3 · (3) the stage-times table for the CPU-only run (`test-log.md`).
- Phone with the submission MP4 downloaded. Backup video on the desktop.

## The 5 minutes
| Time | Who | Do | Say (short) |
|---|---|---|---|
| 0:00–0:30 | Varun | Point at the Wi-Fi icon and the badges | "A teacher spends hours on one explainer video. Blu VisualTeacher makes one in about a minute, on this laptop, offline. Wi-Fi is off; every model runs here." |
| 0:30–0:45 | Satwik | Ask the judges for a topic and a language; type it; Generate | "Pick any topic and Hindi or Kannada." |
| 0:45–1:45 | Varun | Narrate the stage panel as it moves | "A local Qwen model writes the lesson as JSON. We validate it against our schema; if it's bad, we repair it or play a safe fallback. We plan in English, translate with IndicTrans2, then voice every sentence separately, so the audio decides how long each step stays on screen." |
| 1:45–2:45 | Satwik | Lesson opens: play; pause on a diagram step; Next; Replay | "Each box appears exactly when the voice reaches it. Captions are in the lesson's own script; code and terms like 'loop' stay in English, the way students say them." |
| 2:45–3:15 | Satwik | Switch language (revoice) on the cached tab; show ⬇ MP4 and ⬇ SRT | "Same plan, new voice, no re-planning. Every lesson exports as a 720p MP4 with captions and an SRT." |
| 3:15–3:50 | Satwik | Generate with `debug_fail` → fallback banner + lesson plays | "If the model fails, the learner still gets a lesson. The demo can't break." |
| 3:50–4:30 | Varun | Stage-times panel; the CPU-only table; the phone playing the MP4 | "No GPU needed: on CPU only, the same lesson takes N min with a peak of N GB. The player is light enough for a modest phone." |
| 4:30–5:00 | Varun | Close | "Typed concept in, narrated lesson out, in English and Indian languages, offline, with licensed open models. Thank you." |
Fill the N values from `test-log.md` before rehearsing.

**If generation is slow:** keep talking over the stage panel; go to the cached tab if it passes 2 minutes. **If anything crashes:** play the backup video, restart the backend during questions.

## Likely questions (answer in 1–2 sentences)
| Question | Answer |
|---|---|
| Is anything going to the internet? | No. Wi-Fi is off; the app only talks to localhost (Ollama and our backend). |
| How do audio and visuals stay in sync? | We synthesize each sentence separately, measure its length, and build the timeline from those lengths. Nothing has a hard-coded duration. |
| What if the LLM returns garbage? | Its output is constrained to our JSON schema, then checked by Pydantic, auto-fixed, repaired once, and otherwise replaced by a built-in lesson. Model output is never executed. |
| How do you know the content is correct? | Low temperature, a "standard textbook definitions" rule, Python code parse-checked; and a teacher can edit any scene and regenerate just that scene. We don't claim full fact-checking. |
| Why plan in English? | Small models write much weaker Hindi and Kannada; IndicTrans2 translates far better. It also lets us switch language without re-planning. |
| How do technical terms stay in English? | The planner lists them; we mask them during translation and restore them. |
| Why Remotion? | The same React components drive the browser player and the MP4 render, so they can't drift. It's free for individuals and teams of up to 3; it's source-available, not OSI open source, and we list that. |
| Why not a video-generation model? | Correct, clear teaching matters more than cinematic visuals; a deterministic engine is accurate, cheap and runs on a laptop. |
| How fast on a weak laptop? | Quote the CPU-only table: per-stage seconds and peak RAM. |
| How do you add a language? | A config row, a font and a voice check: about 20 minutes. |
| What's next? | More scene types (charts, timelines), better Indian-language voices, teacher review before publishing, and quizzes with results. |
