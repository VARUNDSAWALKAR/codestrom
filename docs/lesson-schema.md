# Lesson schema — Blu VisualTeacher

Build file · The JSON contracts between planner, backend, renderer and exporter.
Python: `backend/app/planner/schema.py` (Pydantic v2). TypeScript: `web/src/lesson/types.ts`. Keep both identical to this file.

---

## 1. Three shapes
| Shape | Made by | Used by | File |
|---|---|---|---|
| **Lesson** (English plan) | LLM fills §2–3; backend adds meta | translator, voice, fallback, cache | `cache/lessons/<id>/plan.json` |
| **Localized lesson** | translator | renderer (on-screen text) | `cache/lessons/<id>/<variant>/lesson.json` |
| **Timeline** | timeline stage, from real audio lengths | renderer, SRT, exporter | `cache/lessons/<id>/<variant>/timeline.json` |

A localized lesson has exactly the same shape as the English lesson. Only translatable strings change (§8) and `language` is set. `<variant>` = `<lang>-<voice>-<speed>`, e.g. `hi-female-1`.

**Beat** = one narration unit: a scene's intro (`scene.narration`, if not empty) or one step (`step.narration`). Each beat becomes one audio clip with its own start and end. This is what keeps audio, captions and animation in sync.

---

## 2. Lesson v1: top level
| Field | Type | Set by | Rule |
|---|---|---|---|
| `schema_version` | `"1.0"` | backend | |
| `lesson_id` | string | backend | 12-hex cache key (`pipeline.md` §8); edited copies get `-v2`, `-v3`… |
| `topic` | string | backend | what the learner typed (3–120 chars) |
| `level` | `beginner` \| `intermediate` | backend | from input |
| `target_seconds` | int 30–90 | backend | from input |
| `language` | `en` \| `hi` \| `kn` \| `ta` \| `te` \| `bn` \| `mr` | backend | `en` for the plan |
| `source` | `llm` \| `fallback` \| `sample` \| `edited` | backend | |
| `model`, `prompt_version` | string | backend | for the cache key and the README |
| `warnings` | string[] | backend | lint notes from validation (§5c) |
| **`title`** | string ≤ 70 | **LLM** | the lesson question or title |
| **`subject`** | `programming` \| `physics` \| `chemistry` \| `biology` \| `math` \| `other` | **LLM** | drives validation rules |
| **`keep_terms`** | string[] ≤ 8, each ≤ 24 chars | **LLM** | technical words students say in English (`loop`, `range`, `print`). Never translated. |
| **`scenes`** | Scene[] 3–6 | **LLM** | §3 |

Lesson rules:
- Scene 1 is a `title_card`; there is only one.
- The last scene is a `recap` (lint warning if not). With the quiz bonus on, a `quiz` may follow the recap.
- `subject = programming` → at least one `code_walkthrough` (hard error otherwise).
- At least one "explaining" scene: `code_walkthrough`, `diagram` or `formula`.
- Word budget: total narration words ≈ `target_seconds × 2.2` (calibrate after measuring, `pipeline.md` §2).

---

## 3. Scenes and steps
Every scene has `id` (backend sets `s1`…`sN`), `type`, `heading`, `narration`, `steps`. Other fields belong to one type; the validator clears fields a type doesn't use.

### Scene fields
| Field | Type | Used by | Limit |
|---|---|---|---|
| `type` | enum | all | `title_card`, `code_walkthrough`, `diagram`, `formula`, `recap` (`quiz` = bonus, schema v1.1) |
| `heading` | string | all | ≤ 60 chars. Title card: the lesson question. Others: a step heading like "Step 1: Read the code" |
| `narration` | string | all | the intro beat. **Required for `title_card`**; may be `""` elsewhere. ≤ 2 sentences, ≤ 35 words |
| `subtitle` | string | title_card | ≤ 80 chars, optional |
| `code` | string | code_walkthrough | 1–12 lines, ≤ 48 chars per line, spaces not tabs, `\n` between lines |
| `code_language` | enum | code_walkthrough | `python`, `javascript`, `java`, `c`, `cpp`, `other` |
| `layout` | enum | diagram | `flow` (left → right), `cycle` (ring, last → first), `labelled` (centre + callouts) |
| `center` | string | diagram | ≤ 28 chars. Required for `labelled`, optional for `cycle`, unused for `flow` |
| `expression` | string | formula | one line, ≤ 40 chars, Unicode allowed: `F = m × a`, `2H₂ + O₂ → 2H₂O` |
| `steps` | Step[] | all | count per type below |

### Step fields
| Field | Type | Meaning | Limit |
|---|---|---|---|
| `text` | string | main on-screen text for this step | diagram ≤ 32, recap ≤ 60, others ≤ 40 |
| `note` | string | small secondary text | ≤ 32 |
| `lines` | int[] | code_walkthrough only: 1-based lines to highlight | each within 1..number of lines |
| `output` | string | code_walkthrough only: what this step prints (shown in an output panel) | ≤ 40, `\n` allowed, `""` if none |
| `narration` | string | spoken for this step (one beat) | **required**, ≤ 2 sentences, ≤ 30 words |

### Per type
| Type | Steps | `text` | `note` | On screen (details in `scene-components.md`) |
|---|---|---|---|---|
| `title_card` | 0 | – | – | Big heading + subtitle |
| `code_walkthrough` | 1–5 | optional annotation / state, e.g. `i = 0` | – | Code panel; highlight bar moves to `lines`; annotation beside it; `output` appears in an output panel |
| `diagram` | 2–6 | **required**: box label | optional caption under the box | Boxes appear one per step, arrows draw between them |
| `formula` | 1–5 | **required**: exact substring of `expression` | **required**: what it means | Expression large; each step highlights its part and shows the meaning |
| `recap` | 2–4 | **required**: one takeaway | – | Bullets tick in one per step |
| `quiz` *(bonus, v1.1)* | 0 | – | – | Uses `question`, `options` (3–4), `answer_index`, `explanation` |

Writing rules the prompt enforces (and the validator checks where it can):
- Narration is spoken English: no code symbols, no markdown. Say "print i", not `print(i)`; "range of three", not `range(3)`.
- Numbers in narration as words ("three values: zero, one and two"). Digits belong in on-screen text.
- Never say a lone single-letter variable that is also an English word (`a`, `I`). Say what it stands for.
- If `text` contains symbols (`=`, `÷`, `→`, brackets), keep it short and symbolic and put the words in `note`. Symbolic text is never translated.

---

## 4. JSON Schema passed to Ollama (`format`)
Uses only keywords that Ollama's grammar support handles reliably (`type`, `properties`, `required`, `items`, `enum`, `minItems`, `maxItems`). Length limits are checked afterwards in Pydantic.

```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "subject": {"type": "string", "enum": ["programming", "physics", "chemistry", "biology", "math", "other"]},
    "keep_terms": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    "scenes": {
      "type": "array",
      "minItems": 3,
      "maxItems": 6,
      "items": {
        "type": "object",
        "properties": {
          "type": {"type": "string", "enum": ["title_card", "code_walkthrough", "diagram", "formula", "recap"]},
          "heading": {"type": "string"},
          "narration": {"type": "string"},
          "subtitle": {"type": "string"},
          "code": {"type": "string"},
          "code_language": {"type": "string", "enum": ["python", "javascript", "java", "c", "cpp", "other"]},
          "layout": {"type": "string", "enum": ["flow", "cycle", "labelled"]},
          "center": {"type": "string"},
          "expression": {"type": "string"},
          "steps": {
            "type": "array",
            "maxItems": 6,
            "items": {
              "type": "object",
              "properties": {
                "text": {"type": "string"},
                "note": {"type": "string"},
                "lines": {"type": "array", "items": {"type": "integer"}},
                "output": {"type": "string"},
                "narration": {"type": "string"}
              },
              "required": ["text", "narration"]
            }
          }
        },
        "required": ["type", "heading", "narration", "steps"]
      }
    }
  },
  "required": ["title", "subject", "keep_terms", "scenes"]
}
```
The same JSON is in `data/lesson.schema.json`: copy it to `backend/app/planner/lesson.schema.json` and load it at startup. The Pydantic models are stricter than this schema; this schema only keeps the model's JSON in shape.

---

## 5. Validation (`backend/app/planner/validate.py`)
Order: parse → Pydantic → auto-fix → hard errors → lint. Hard errors trigger **one** repair call (`prompts.md`); if errors remain, the fallback lesson plays.

### 5a. Auto-fixes (silent, logged in `warnings`)
1. Cut anything before the first `{` and after the last `}`. Remove code fences.
2. Trim every string and collapse inner whitespace (except `code`: keep newlines, tabs → 4 spaces, strip trailing spaces and blank edge lines).
3. Set scene ids `s1`…`sN`.
4. First scene not a `title_card` → insert one with `heading = title`, `narration = title`. Drop any later title cards.
5. Clear fields the scene type doesn't use. Title card: `steps = []`. Drop steps beyond the type's maximum.
6. `lines`: drop out-of-range numbers, dedupe, sort. Empty → previous step's lines, else `[1]`.
7. Diagram without `layout` → `flow`. `labelled` without `center` → `center = heading`.
8. Formula step whose `text` isn't in `expression` → retry with case and spaces ignored; still missing → set `in_expression: false` (the component shows it as a chip under the expression).
9. Narration cleanup: remove markdown and backticks, replace `_` with a space, remove brackets but keep their contents (`print(i)` → `print i`), collapse spaces, end with `.`, `?` or `!`.
10. `keep_terms`: dedupe, drop items over 24 chars, keep 8. Add code keywords/builtins that also appear in narration (`range`, `print`).
11. `code_language` missing → `python` if `ast.parse` succeeds, else `other`.
12. `heading` over 60 chars → cut at a word boundary.

### 5b. Hard errors (→ one repair call → fallback)
- Not valid JSON, or a type error Pydantic can't coerce
- Fewer than 3 scenes after the fixes
- An empty beat: title card without narration, or any step without narration
- `code_walkthrough` with empty code, more than 12 lines, or a line over 60 chars
- `code_language = python` and `ast.parse` fails (parsed only, **never run**)
- `diagram` with fewer than 2 steps; `formula` without `expression` or steps; `recap` with fewer than 2 steps
- `subject = programming` and no `code_walkthrough`
- Any beat over 45 words
- Total narration words below 0.5× or above 1.6× the budget

### 5c. Lint warnings (logged, no retry)
- A beat of 31–45 words
- Total words outside 0.8–1.25× the budget
- Last scene isn't a `recap`
- A label longer than its limit (the component shrinks the font)

### 5d. Fallback
Any hard error left after the repair, an Ollama error or a timeout → load `data/fallback/python_loop.en.json`, set `source = "fallback"`, keep the learner's `topic`, and show the banner: *"Couldn't plan this topic — playing our sample lesson instead."*

---

## 6. Timeline v1 (`timeline.json`)
Built from the real audio lengths (`pipeline.md` §6). All frame numbers are **absolute** (from the lesson start).

```json
{
  "timeline_version": 1,
  "lesson_id": "3f9a1c2b7d10",
  "language": "hi",
  "variant": "hi-female-1",
  "fps": 30,
  "width": 1280,
  "height": 720,
  "duration_frames": 1890,
  "audio": {
    "web": "/media/3f9a1c2b7d10/hi-female-1/narration.m4a",
    "wav": "/media/3f9a1c2b7d10/hi-female-1/narration.wav"
  },
  "voice": {"engine": "kokoro", "voice_id": "hf_alpha", "speed": 1.0},
  "tempo": 1.0,
  "scenes": [
    {
      "scene_id": "s1",
      "type": "title_card",
      "start_frame": 0,
      "duration_frames": 165,
      "beats": [
        {
          "beat_id": "s1.intro",
          "step_index": null,
          "start_frame": 9,
          "end_frame": 140,
          "captions": [{"text": "…", "start_frame": 9, "end_frame": 140}]
        }
      ]
    }
  ]
}
```
Rules:
- Scenes are back to back: `scenes[i+1].start_frame = scenes[i].start_frame + scenes[i].duration_frames`. Their sum is `duration_frames`.
- `beat_id` = `<scene_id>.intro` or `<scene_id>.step<k>` (k from 0). `step_index` is `null` for the intro beat, else `k`.
- A scene with `narration = ""` has no intro beat.
- Beats lie inside their scene; captions lie inside their beat.
- `audio` is `null` in mock timelines (`data/samples/*.timeline.mock.json`): render silently.
- `tempo` > 1.0 means the narration was sped up to fit 90 s (`pipeline.md` §6).

Renderer rules:
- Step *k* is **revealed** from its beat's `start_frame` onward and **active** until the next beat starts.
- Before the first step beat, show the scene's skeleton (heading, code panel or empty diagram frame).
- Inside a scene's `<Sequence>`: `rel = beat.start_frame - scene.start_frame`.

---

## 7. Render props
One object drives both the browser player and the MP4 render.
```json
{
  "lesson": "<localized lesson, §1>",
  "timeline": "<timeline, §6>",
  "mediaBase": "",
  "audioVariant": "web",
  "showCaptions": true
}
```
| | Browser player | MP4 render |
|---|---|---|
| `mediaBase` | `""` (same origin) | `"http://127.0.0.1:8000"` |
| `audioVariant` | `"web"` (m4a, small) | `"wav"` |

Composition `Lesson`: 1280×720; `fps` and `durationInFrames` come from `timeline` via `calculateMetadata`.

**Frame layout v0** (full spec in `scene-components.md`):
| Band | y (px) | Content |
|---|---|---|
| Header | 0–96 | step heading (left), scene `n / N` (right) |
| Content | 96–600 | the scene |
| Caption bar | 600–700 | current caption, max 2 lines, script font |
| Progress bar | 712–720 | lesson progress with scene ticks |

---

## 8. What gets translated
| Translate | Never translate |
|---|---|
| `title`; scene `heading`, `narration`, `subtitle`, `center`; step `text`, `note`, `narration` | `code`, `code_language`, `layout`, `expression`, `lines`, `output`, `keep_terms`, `type`, ids |

- `keep_terms`, code-like spans (`range(3)`, `i = 0`, `m/s²`) and numbers are masked before translation and restored after. A string that is only symbols plus a few words stays as is. Exact masking rules: `narration-languages.md`.
- Captions come from the translated narration, so they're always in the lesson's script.

---

## 9. Files in `data/`
| File | What it is |
|---|---|
| `data/fallback/python_loop.en.json` | **The built-in fallback lesson** (title card, code walkthrough, flow diagram, recap) |
| `data/samples/newtons_second_law.en.json` | Sample: formula + flow diagram |
| `data/samples/water_cycle.en.json` | Sample: cycle diagram + labelled diagram |
| `data/samples/*.timeline.mock.json` | Timelines estimated at 2.4 words/s, `audio: null`. For building the renderer before real audio exists |
| `data/samples/*.props.json` | Ready-to-use render props (mock timeline, captions on) for Remotion Studio and `render.mjs` |
| `data/lesson.schema.json` | The §4 JSON Schema as a file (for Ollama `format` and test T3) |
| `data/test_topics.json` | 20 test topics across subjects, levels and languages (`test-cases.md` §5) |

All three lessons pass the §4 schema and the §5 checks.

## 10. Versions
`SCHEMA_VERSION = "1.0"` · `TIMELINE_VERSION = 1` · `PROMPT_VERSION` lives in `prompts.md`. All three are part of the cache key, so bumping one regenerates instead of reusing stale lessons.
