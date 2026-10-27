# UI flow — Blu VisualTeacher

Build file · Screens and controls. Code: `web/src/app/` (Varun). API: `api-contracts.md`.
One page, three main views switched by state (hash routes `#/`, `#/job/<id>`, `#/lesson/<id>?variant=…` so refresh works). Tailwind is fine here (the app shell, not the video).

---

## S1 — Create
| Element | Behaviour |
|---|---|
| Health badges | Planner · Translator · Voice · Renderer · `GPU`/`CPU` · `Offline ✓`. From `/api/health`; grey "loading" until ready |
| Topic box | One line, 120 chars max. Placeholder: "How does a Python loop work?". Enter submits |
| Example chips | 3 clickable topics: Python loop · Ohm's law · Photosynthesis |
| Level | Toggle: Beginner / Intermediate |
| Language | Dropdown with native names (हिन्दी, ಕನ್ನಡ…). Core languages first; bonus ones marked "beta"; unavailable ones disabled with a tooltip |
| Length | Slider 30–90 s, step 15, shows "60 s" |
| Voice | Female / Male |
| Speed | 0.85× / 1× / 1.15× |
| Generate | Disabled until health `ok`. Topic under 3 chars → inline error "Type a topic first" next to the box, nothing sent |
Submit → `POST /api/lessons` → go to S2 (or straight to S3 if `cached`).

## S2 — Making the lesson
- Stage list, one row per stage: icon (pending ○, running spinner, done ✓, cached ⟳, skipped –, error ✕) · name in plain words (Planning · Checking · Translating · Voicing · Syncing · Making MP4) · time in seconds.
- Total elapsed timer at the top, plus the device profile.
- **Fallback banner** (amber) when `fallback: true`: the reason line + "Playing our sample lesson instead."
- When `playable` turns true → open S3 automatically. Export keeps running there.
- `status: "error"` → red message + button "Play the sample lesson".

## S3 — Player
```
┌──────────────────────────────── 16:9 Remotion Player ───────────────────────────────┐
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
 ⏮ Prev   ▶/⏸   Next ⏭   ↻ Replay     [1 Title][2 Code][3 Diagram][4 Recap]     CC
 Language [हिन्दी ▾]  Voice [F ▾]  Speed [1× ▾]        ⬇ MP4 (rendering 42%)   ⬇ SRT
 ▸ Stage times   ▸ Plan JSON   ▸ Warnings
```
| Control | Does |
|---|---|
| ▶/⏸ | `playerRef.toggle()` |
| ⏮ / ⏭ | seek to the previous / next scene's `start_frame` (from the timeline) |
| ↻ Replay | `seekTo(0)` then `play()` |
| Scene chips | jump to that scene; the current one is highlighted (`frameupdate` event) |
| CC | toggles `showCaptions` |
| Language / Voice / Speed | if that variant exists → load it; else `POST …/voice` → small progress strip → swap in when playable (bonus) |
| ⬇ MP4 | disabled with "rendering n%" until `media.mp4` exists, then `?download=1` |
| ⬇ SRT | `?download=1` |
| Stage times | table: stage · seconds · peak RAM · device (for the speed criterion) |
| Plan JSON | the English plan + validation report (debug endpoint) — good for the engineering questions |
| Warnings | lint warnings, if any |
Keyboard: Space play/pause · ← / → previous / next scene · R replay.
Player props: `lesson`, `timeline`, `mediaBase: ""`, `audioVariant: "web"`, `showCaptions`. `controls` off (our own bar), `clickToPlay` on.

## S4 — Edit a scene (bonus)
From S3: "Edit" on the current scene → a side panel with its English fields (heading, intro narration, each step's text/narration). "Regenerate this scene" → `PATCH …/scenes/{id}` → progress strip → the new version opens in S3. Validation errors show inline under the field.

## S5 — Library (bonus)
Cards from `GET /api/lessons`: title · level · length · language chips (variants). Click → S3.

## Phone layout (≤ 640 px wide)
Single column; player full width; controls wrap into two rows; buttons at least 44 px tall; panels collapsed. The MP4 link is the light option for slow phones.

## Hidden route: `#/capture`
Only for the Plan B exporter (`export.md` §6): the composition alone at 1280×720, no controls, muted autoplay; sets `window.__startMs` on play and `window.__done` on `ended`.

## Build order
1. S1 with fake health → 2. S2 polling the real job → 3. S3: player + play/pause/prev/next/replay → 4. downloads + CC → 5. stage times panel + fallback banner → 6. language switch → 7. S5 → 8. S4.
