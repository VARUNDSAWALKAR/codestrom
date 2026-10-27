# Scene components — Blu VisualTeacher

Build file · What each scene looks like and how it moves. Code: `web/src/lesson/`.
Contract: `lesson-schema.md` §3 (fields), §6 (timeline), §7 (render props). Rules: `../AGENTS.md` → "Rules for scene code".

**Design rule:** animation explains, it doesn't decorate. Only the step being narrated moves or highlights. Everything else holds still.

---

## 1. Frame grid (1280×720)
| Band | x | y | Content |
|---|---|---|---|
| Header | 64–1216 | 0–96 | `StepHeading` (left), scene counter `2 / 4` (right). Hidden on the title card |
| Content | 64–1216 | 120–580 | the scene |
| Caption bar | 64–1216 | 604–692 | `CaptionBar` |
| Progress | 0–1280 | 714–720 | `ProgressBar` |
Side margins 64 px. Nothing is drawn outside these bands.

## 2. Theme (`theme.ts`)
| Token | Value | Use |
|---|---|---|
| `bg` | `#F7F9FC` | frame background (light: reads well on projectors) |
| `surface` | `#FFFFFF` | boxes, cards |
| `ink` | `#0F172A` | main text |
| `ink2` | `#475569` | notes, counter |
| `line` | `#CBD5E1` | box borders, arrows not yet active |
| `accent` | `#2563EB` | active box border, arrows, progress fill |
| `accentSoft` | `#DBEAFE` | active box fill |
| `ok` | `#16A34A` | recap ticks |
| `codeBg` / `codeInk` | `#0F172A` / `#E2E8F0` | code panel |
| `codeHl` | `rgba(59,130,246,0.28)` + 4 px strip `#60A5FA` | code highlight bar |
| `capBg` | `rgba(15,23,42,0.88)` | caption bar |
| `parts` | `#2563EB`, `#0D9488`, `#D97706`, `#7C3AED`, `#E11D48` | formula parts, in step order |
Corners 16 px on boxes, 12 px on the caption bar. No shadows, gradients or blur (they cost frames on phones).

## 3. Type
| Element | Size (Latin) | Size (Indic) | Weight | Line height |
|---|---|---|---|---|
| Title-card heading | 56 | 50 | 600 | 1.25 |
| Step heading | 34 | 32 | 600 | 1.3 |
| Box label | 28 | 26 | 600 | 1.35 |
| Note | 20 | 19 | 400 | 1.4 |
| Code | 24 mono | – | 400 | 34 px |
| Formula expression | 76 | – | 600 | 1.1 |
| Recap bullet | 32 | 30 | 400 | 1.45 |
| Caption | 30 | 28 | 500 | 1.4 Latin · 1.6 Indic |
| Counter | 20 | 20 | 400 | – |
Indic scripts need the taller line height for vowel signs above and below. Font stacks come from `fonts.ts` (`narration-languages.md` §7); Latin letters inside Indic text (keep_terms, digits) fall back to Noto Sans.

**Fitting text:** each element has a `maxChars` bucket. Longer text scales the font by `max(0.7, maxChars / length)` and clamps to 2 lines. Nothing may overflow its box. Buckets: heading 44, box label 18, note 24, recap 40, caption: see the chunk limits in `pipeline.md` §6.

## 4. Motion (30 fps)
| Motion | Frames | How |
|---|---|---|
| **Enter** | 12 | opacity 0→1 and translateY 12→0, `spring({damping: 200})` |
| **Arrow draw** | 15 | SVG `strokeDashoffset` from path length to 0, starting 3 frames before its target box enters |
| **Activate** | 8 | border `line`→`accent`, fill `surface`→`accentSoft` |
| **Deactivate** | 8 | back to normal when the next beat starts (stays visible) |
| **Code highlight move** | 8 | the bar's y and height interpolate to the new lines |
| **Caption swap** | 6 | cross-fade |
Timing comes only from the timeline: `rel = beat.start_frame − scene.start_frame`. A step's motion starts at its beat. The scene's skeleton enters on frames 0–12 of the scene.

## 5. Scenes

### `TitleCard`
- Heading centred at y ≈ 300, max 2 lines; subtitle 28 px in `ink2` below; an `accent` bar (4 px) under the heading grows 0→160 px.
- Small "Blu VisualTeacher" wordmark top-left, 20 px `ink2`.
- Enter: heading 0–12, subtitle 6–18, bar 10–25. No other motion.

### `CodeWalkthrough`
- **Code panel** x 64–760, y 128–568: line numbers in `#64748B`, 24 px mono, simple syntax colours (keywords `#93C5FD`, strings `#86EFAC`, numbers `#FCD34D`, comments `#94A3B8`; `prism-react-renderer` or a 30-line tokenizer). Preserve indentation (`white-space: pre`).
- **Highlight bar** over `step.lines` (one bar per run of consecutive lines). Moves when each step starts.
- **State card** x 792–1216, y 128–300: the current step's `text` in 30 px, swapping per step.
- **Output panel** x 792–1216, y 320–568: dark console labelled "Output". When a step with `output` starts, its lines appear one by one, spread evenly across that beat (so "0, 1, 2" appear as the narration says "runs once for every value"). Earlier output stays.
- Intro beat: code panel enters, no highlight yet.

### `Diagram`
Boxes: `surface` fill, 2 px `line` border, label centred, `note` 20 px in `ink2` under the box. Step *k* adds box *k* (and its incoming arrow); the active box is highlighted.
- **`flow`**, 2–4 steps: one row centred at y = 330. Box width `min(240, (1152 − (n−1)·72) / n)`, height 112, 72 px gaps for arrows.
  5–6 steps: two rows (3 + 2 or 3 + 3) at y = 230 and y = 450; an elbow arrow runs from the end of row 1 down to the start of row 2.
- **`cycle`**: boxes 200×84 on an ellipse centred at (640, 350), rx 380, ry 170, starting at the top and going clockwise. Curved arrows follow the ellipse between neighbours, and the last box points back to the first (that arrow draws with the last step). Optional `center` sits in a circle (r 70) in the middle.
- **`labelled`**: `center` in a 260×96 box at (640, 350). Callouts are 280×80 boxes; a straight line with a dot at the end joins each to the centre box. Slots by count:
  | n | Slots (L = x 240, R = x 1040, T = y 210, M = y 350, B = y 490) |
  |---|---|
  | 2 | LM, RM |
  | 3 | LM, RT, RB |
  | 4 | LT, RT, LB, RB |
  | 5 | LT, RT, LB, RB, bottom-centre (640, 540) |
  | 6 | LT, RT, LB, RB, LM, RM |
- Intro beat: show the empty frame (the centre for `cycle`/`labelled`, nothing for `flow`).

### `Formula`
- `expression` centred at y = 250, 76 px. Split it into segments at the first occurrence of each step's `text`.
- When step *k* starts, its segment turns `parts[k]` and gets a 6 px underline that grows left→right (10 frames); the active segment is also scaled 1.06. Revealed segments keep their colour.
- **Meaning list** from y = 340, one 44 px row per step (5 rows end at y ≈ 560), left edge at x = 280: coloured dot · the part in bold · "—" · `note` (26 px). Rows enter with their step.
- `in_expression: false` steps show only their row (no underline).

### `Recap`
- Bullets from y = 170, 96 px apart, left at x = 160. Each bullet: a 40 px circle whose tick draws in (12 frames), then the text enters.
- All bullets stay; the newest is in `ink`, earlier ones in `ink2`.

### `Quiz` (bonus)
- Question 36 px at the top; 3–4 option cards in a 2×2 grid. During the 2.5 s think gap, a ring counts down. At the reveal beat the correct card turns `ok` with a tick, the others fade to 50%.

## 6. Chrome
- **`StepHeading`:** scene `heading` at x 64, top 36; enters with the scene. Counter `n / N` at the right (title card excluded from N).
- **`CaptionBar`:** finds the caption whose `[start_frame, end_frame)` contains the current absolute frame. White text, centred, max 2 lines; bar fades out when no caption is active. Hidden when `showCaptions` is false. Set `lang` + font for the lesson's script.
- **`ProgressBar`:** 6 px track (`#E2E8F0`) across the bottom; fill (`accent`) = `frame / duration_frames`; a 2 px gap marks each scene boundary.

## 7. `Lesson.tsx` (the composition)
```
<AbsoluteFill bg>
  {audio && <Audio src={mediaBase + timeline.audio[audioVariant]} />}
  {timeline.scenes.map(s => (
    <Sequence from={s.start_frame} durationInFrames={s.duration_frames}>
      <StepHeading/> <SceneByType scene={lesson scene with id s.scene_id} beats={s.beats}/>
    </Sequence>
  ))}
  <CaptionBar/> <ProgressBar/>
</AbsoluteFill>
```
Helpers in `timing.ts`: `beatState(beats, k, frame)` → `hidden | active | revealed`; `relFrame(beat, scene)`; `activeCaption(timeline, frame)`.

## 8. Phone and performance
- Player: `compositionWidth 1280`, `compositionHeight 720`, CSS width 100%, aspect ratio 16:9.
- Precompute layouts with `useMemo` (box positions, segments, wrapped lines); per frame, only compute opacity/transform.
- Load fonts for the lesson's language only (+ Latin + mono).
- No filters, shadows or blur; SVG paths stay simple.
- Check: Chrome DevTools → Performance, CPU 4× slowdown, play the fallback lesson: no visible stutter. Then a real phone over Wi-Fi. Phones can also just play the MP4 (720p, faststart).

## 9. Build order (Varun)
1. `types.ts`, `theme.ts`, `fonts.ts`, `timing.ts`, `Lesson.tsx`, chrome → plays `python_loop.props.json` in Studio
2. `TitleCard` → `CodeWalkthrough` → `Diagram` (flow → cycle → labelled) → `Formula` → `Recap`
3. Check each with all 3 sample props files, then with real hi/kn outputs (long labels, Indic line height)
4. `Quiz` (bonus)
