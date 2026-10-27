# Export — Blu VisualTeacher

Build file · Turning render props into a checked 1280×720 MP4 + `.srt`. Code: `web/render/render.mjs` (Varun), `backend/app/export/` (Satwik).
Stage flow: `pipeline.md` §7. Props: `lesson-schema.md` §7.

---

## 1. Output spec (from the PS)
| | Value |
|---|---|
| Container | MP4, `+faststart` |
| Video | H.264, 1280×720, `yuv420p`, 30 fps, CRF 23 |
| Audio | AAC, 128 kbps |
| Captions | burned in (the `CaptionBar`) **and** `lesson.srt` next to the MP4 |
| Length | = `timeline.duration_frames / fps` (±0.2 s) |
| Size | about 3–8 MB per minute (simple graphics compress well) |

## 2. Remotion setup (`web/`)
- `remotion.config.ts`: `Config.setEntryPoint("./src/remotion/index.ts")`, `Config.setVideoImageFormat("jpeg")`.
- `src/remotion/Root.tsx`:
  ```tsx
  <Composition id="Lesson" component={Lesson} width={1280} height={720}
    fps={30} durationInFrames={300} defaultProps={sampleProps}
    calculateMetadata={({props}) => ({durationInFrames: props.timeline.duration_frames, fps: props.timeline.fps})} />
  ```
  `sampleProps` = `data/samples/python_loop.props.json` (copied into `web/src/remotion/`).
- **Bundle once:** `npx remotion bundle` → `web/build`. Re-bundle after every change to `web/src/lesson/` (the demo build script does it).
- All `remotion` / `@remotion/*` packages on one version (`npx remotion versions`).

## 3. `render.mjs` (CLI contract in `../AGENTS.md`)
```
node web/render/render.mjs --props <props.json> --out <raw.mp4> [--concurrency N]
```
Steps:
1. Read props. `serveUrl` = `web/build` if it exists, else `bundle({entryPoint: "web/src/remotion/index.ts"})`.
2. `selectComposition({serveUrl, id: "Lesson", inputProps: props})`.
3. `renderMedia({composition, serveUrl, inputProps: props, outputLocation, codec: "h264", audioCodec: "aac", audioBitrate: "128k", crf: 23, pixelFormat: "yuv420p", concurrency, timeoutInMilliseconds: 60000, onProgress})`.
4. `onProgress`: print `{"progress":0.42}` at most every 2%. On success print `{"done":true,"out":"…","ms":…}` and exit 0; on any error print `{"error":"…"}` and exit 1.
- `concurrency`: CLI flag, else `RENDER_CONCURRENCY`, else half the cores (2 on 8 GB machines).
- Audio comes from `mediaBase + timeline.audio.wav` (`http://127.0.0.1:8000/media/…`), so the backend must be running. It is, because the backend starts the render.
- Fonts load through `delayRender` inside `loadFont`; the 60 s timeout covers slow first loads.

## 4. Backend side (`backend/app/export/`)
1. Write `props.json`: localized lesson + timeline + `mediaBase: "http://127.0.0.1:8000"`, `audioVariant: "wav"`, `showCaptions: true`. Skip the render if `props.sha1` matches and `lesson.mp4` exists.
2. Run `render.mjs` with `subprocess.Popen`, read stdout line by line, feed `progress` into the job.
3. Faststart:
   ```
   ffmpeg -y -i raw.mp4 -c copy -movflags +faststart lesson.mp4
   ```
4. Check:
   ```
   ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,pix_fmt -show_entries format=duration -of json lesson.mp4
   ```
   Must show `h264` 1280×720 `yuv420p`, `aac`, and a duration within 0.2 s of the timeline. Otherwise → export error (§6).
5. `lesson.srt` is already there from the timeline stage. Done.

## 5. SRT format
```
1
00:00:00,300 --> 00:00:04,650
A loop repeats the same instruction for each value in a sequence.

2
00:00:04,650 --> 00:00:06,700
Let's watch one run, step by step.
```
UTF-8 without BOM, one cue per caption chunk, times from the timeline frames (`frame / fps`).

## 6. Plan B exporter (only if Remotion rendering breaks)
Real-time screen capture of the same player, then FFmpeg adds the narration.
1. `web/render/capture.mjs` (Playwright, Node): headless Chromium, viewport 1280×720, `recordVideo: {dir, size: {width: 1280, height: 720}}`, launch flag `--autoplay-policy=no-user-gesture-required`.
2. Open `http://127.0.0.1:8000/#/capture?lesson=<id>&variant=<v>`: a page showing only the composition at 1280×720 with the Remotion Player, muted, autoplay, no controls. It sets `window.__startMs` when playback starts and `window.__done = true` on `ended`.
3. Wait for `__done`, close the context → `.webm`. Offset = time from page open to `__startMs`.
4. ```
   ffmpeg -y -ss <offset> -i capture.webm -i narration.wav -map 0:v -map 1:a -r 30 -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest -movflags +faststart lesson.mp4
   ```
5. Same ffprobe check (allow ±0.5 s).
Weak points: takes real time (a 60 s lesson needs ~70 s), may drop frames on slow CPUs. Emergencies only.

## 7. Submission files
After H+20, copy each required MP4 and SRT to `submission/<topic-slug>_<lang>.mp4` / `.srt` (2 lessons × English + one Indian language = 4 MP4s). Keep the generation times shown in the UI for the README.
