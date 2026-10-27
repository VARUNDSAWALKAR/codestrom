# Prompts — Blu VisualTeacher

> Task 4 override: see [offline planner contract](planner-task4.md). Planner calls use 180 s, keep_alive 10m, one repair, failure-only raw logs, and English content with requested-language metadata. Failed requests return structured errors; no unrelated fallback. Task 5 orchestration is not implemented.

Build file · The planner prompt, its example, the repair prompt and the Ollama call. Code: `backend/app/planner/prompt.py`, `ollama_client.py`.
**`PROMPT_VERSION = "p1"`.** Bump it on every change (it's part of the cache key) and log the change in §8.

---

## 1. Models by device profile
| Profile | Model | Why | Extra request fields |
|---|---|---|---|
| `gpu` (demo) | `PLANNER_MODEL_GPU = qwen3:8b` | Better facts and structure; already pulled; fast on the RTX 5070 | `"think": false` |
| `cpu` (rule check) | `PLANNER_MODEL_CPU = qwen3:4b-instruct-2507-q4_K_M` | Fits 8–16 GB RAM; no thinking mode | `options.num_gpu = 0` |
| backup (either) | `PLANNER_BACKUP_MODEL = llama3.2:3b` | Only if the main model is missing or fails to load | – |

`think: false` goes only to Qwen3 models without `instruct` in the tag (they have a thinking mode). Don't send it to other models.

## 2. The Ollama call
`POST {OLLAMA_URL}/api/chat`
```json
{
  "model": "<by profile>",
  "stream": false,
  "think": false,
  "format": "<contents of backend/app/planner/lesson.schema.json>",
  "keep_alive": "30m",
  "options": {"temperature": 0.3, "top_p": 0.9, "seed": 7, "num_ctx": 4096, "num_predict": 2000},
  "messages": [
    {"role": "system", "content": "<§3 system prompt>"},
    {"role": "user", "content": "<§4 request for the example topic>"},
    {"role": "assistant", "content": "<§4 example JSON>"},
    {"role": "user", "content": "<§4 request for the learner's topic>"}
  ]
}
```
- Timeout: 60 s (`gpu`), 300 s (`cpu`).
- Read `message.content`, then validate (`lesson-schema.md` §5).
- Keep the system prompt and example byte-identical between calls: Ollama reuses the processed prefix, which saves CPU time.
- Log `eval_count`, `eval_duration` and `prompt_eval_duration` from the reply to compute tokens/s for `test-log.md`.

## 3. System prompt (p1)
`{level}` and `{word_budget}` are filled in per request; everything else is fixed.
```
You plan short animated video lessons for school and college students in India.
You write the lesson PLAN as JSON. Our app turns the plan into animated scenes and a voice-over.
Code only ever appears as on-screen content in a code_walkthrough scene. It is never run.

GOAL
A {level} learner should understand the topic after one viewing. One idea per scene.
Build up step by step: what we will learn -> the core idea -> a worked example -> recap.

OUTPUT
Return ONLY one JSON object with the keys title, subject, keep_terms, scenes. No other text.

SCENE TYPES
- title_card: heading = the lesson question. subtitle = one short line. narration = 1-2 sentences saying what the learner will see. steps = [].
- code_walkthrough: programming topics only. code = a short, correct, complete example, 2-8 lines (never more than 12), each line under 45 characters, 4-space indents. code_language = python unless the topic names another language. Each step highlights the lines it talks about (lines, counted from 1). text may show the current state, like "i = 0". output = what that step prints, or "".
- diagram: a process or structure. layout = flow (steps in order), cycle (steps that repeat; the last leads back to the first) or labelled (parts around a centre; set center). Each step adds one box: text = a 1-4 word label, note = a 1-4 word caption.
- formula: a law, equation or chemical reaction. expression = the formula on one line using Unicode symbols (×, ÷, →, ², ₂). Each step explains one part: text = that part copied exactly from expression; note = its meaning in 2-5 words.
- recap: 2-4 steps. Each text is one takeaway under 60 characters.

LESSON SHAPE
- 3 to 6 scenes. Scene 1 is a title_card. The last scene is a recap.
- Programming topic: a code_walkthrough, then usually a flow diagram that traces it step by step.
- Law, equation or reaction: a formula, then a flow diagram that works one example with small, simple numbers.
- Process or cycle: a diagram with layout flow or cycle.
- beginner: everyday words, define every new term, the simplest possible example, 3-5 scenes.
- intermediate: correct technical terms, one extra detail or edge case, 4-6 scenes.

NARRATION (read aloud by a voice, and translated into Indian languages)
- Every step has narration: 1-2 short sentences, at most 25 words, plain spoken English.
- A step's narration talks about exactly what that step shows.
- About {word_budget} words of narration in the whole lesson.
- No symbols, brackets, markdown or code in narration. Say "print i", not print(i). Say "range of three", not range(3).
- Write numbers as words: "three values: zero, one and two".
- Never say a single-letter variable that is also an English word (a, I) on its own. Say what it stands for.
- Only state facts you are sure are correct. Use standard textbook definitions. No jokes, no filler.

ON-SCREEN TEXT
- heading: under 50 characters, like "Step 1: Read the code".
- Labels and notes are short. If a text contains symbols (=, →, brackets), keep it symbolic and put the words in note.

keep_terms: up to 8 technical words a student says in English even when speaking Hindi or Kannada (loop, variable, print, range, Python). No ordinary words.
subject: one of programming, physics, chemistry, biology, math, other.

Example of one code_walkthrough scene:
{"type":"code_walkthrough","heading":"Step 1: Read the code","narration":"Here is a loop with just two lines of Python.","code":"for i in range(3):\n    print(i)","code_language":"python","steps":[{"text":"range(3) → 0, 1, 2","note":"","lines":[1],"output":"","narration":"range of three gives three values: zero, one and two."},{"text":"runs once per value","note":"","lines":[2],"output":"0\n1\n2","narration":"The indented line runs once for every value, and print shows the value of i."}]}
```

## 4. Request and example
**Request template** (user message):
```
Topic: {topic}
Level: {level}
Target length: {target_seconds} seconds, about {word_budget} words of narration in total.
Return the lesson plan JSON.
```
`word_budget = round(target_seconds × 2.2)` (recalibrate from `test-log.md`).

**Example pair:** the user message is the template filled with *What is Newton's second law?*, beginner, 60 seconds, 132 words. The assistant message is `data/samples/newtons_second_law.en.json` with the backend-only fields removed (`schema_version`, `lesson_id`, `topic`, `level`, `target_seconds`, `language`, `source`, `model`, `prompt_version`, `warnings`, scene `id`), serialized compactly. `prompt.py` builds it from that file at startup, so there is one source of truth.

The example covers `title_card`, `formula`, `diagram` (flow) and `recap`; the system prompt shows a `code_walkthrough`. Together that is every core scene type.

## 5. Repair prompt
Sent only after hard errors (`lesson-schema.md` §5b), as two more messages on the same conversation:
```json
{"role": "assistant", "content": "<the model's previous JSON>"},
{"role": "user", "content": "Your JSON has these problems:\n- <error 1>\n- <error 2>\nReturn the full corrected JSON object only. Keep everything that was already correct."}
```
Write errors so the model can act on them, e.g. `scene 2 (code_walkthrough): step 3 highlights line 5 but the code has 3 lines` or `total narration is 260 words; the target is about 132`.
One repair only. Still failing → fallback lesson.

## 6. Prompt check (run before building on a prompt version)
Five topics through each planner model, with the exact §2 request. Use the backend's test endpoint once it exists; before that, the PowerShell snippet in `test-cases.md` T3.
| # | Topic | Level | Seconds |
|---|---|---|---|
| 1 | How does a Python for loop work? | beginner | 45 |
| 2 | What is Ohm's law? | beginner | 60 |
| 3 | How does photosynthesis work? | beginner | 60 |
| 4 | How does binary search work? | intermediate | 75 |
| 5 | What happens when methane burns? | beginner | 60 |

Record per run in `test-log.md`: valid first try / after repair / fallback · plan seconds · words vs budget · any factual error · whether the scene types fit the topic.
**Pass:** ≥ 4 of 5 valid after at most one repair, no factual errors, `code_walkthrough` present for #1 and #4, `formula` present for #2 and #5.

## 7. Known traps
| Trap | Guard |
|---|---|
| The model copies the example (Newton's law) for an unrelated topic | Validator: if the topic doesn't mention Newton but the title or more than half the narration matches the example, treat it as a hard error |
| Code in narration (`print(i)`) | Prompt rule + auto-fix 9 (brackets removed) |
| Thinking text before the JSON (`qwen3:8b`) | `think: false`; the validator also cuts everything before the first `{` |
| Truncated JSON on long lessons | `num_predict 2000`; the word budget keeps output near 700–1,100 tokens |
| Wrong facts | Low temperature, "standard textbook definitions" rule, `ast.parse` for Python; the teacher can fix a scene with edit-one-scene (bonus) |
| `subject` wrong, so the code rule misfires | Auto-fix: a topic containing python, java, javascript, c++, code, coding, program, loop, algorithm, recursion, array or sorting while `subject ≠ programming` → set `subject = programming` |

## 8. Change log
| Version | Date | Change | Prompt check result |
|---|---|---|---|
| p1 | 27 Oct | First version | not run yet |
