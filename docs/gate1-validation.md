# Gate 1 consolidation and verification

Date: 2026-10-27. Repository: `VARUNDSAWALKAR/codestrom`.
Target checkout: `C:/Users/ROG/VisualTeacher-varun`.
Original integrated application: `C:/Users/ROG/VisualTeacher` (preserved).

## Repository baseline and transfer

The target was clean on `main`, at `d07593810f76d540d8dc194e2fb4c30a5293843e`
(`Build Blu VisualTeacher frontend, lesson animations, and MP4 exporter`).
Its parent is `cc635e7` (`Initial commit`). `origin` is
`https://github.com/VARUNDSAWALKAR/codestrom.git`; the locally recorded
`origin/main` matched HEAD. No remote fetch was made under the project's offline
rule, so newer server-side commits have not been checked. No repository was
initialized, branch reset, commit created, tag created or push performed.

Both source trees were compared before writing. Existing frontend source was
identical; only some font licence line endings differed. Every original `web/`
file is preserved byte for byte, including the lockfile, fonts and renderer.
The npm font postinstall script normalized licence line endings; these were
restored to the exact pre-install hashes. No frontend integration fix was needed.

The only substantive overlapping differences were `.gitignore` and
`docs/licenses.md`. The target licence document is a superset with Varun's
frontend entries and was preserved unchanged. Ignore rules were extended
additively. No conflicting implementation files were overwritten.

Added:
- All 33 backend Python/configuration files from the integrated application:
  foundation, cache, jobs, schema, speech, timeline, export, both CLI commands,
  pinned requirements/constraints and the existing test suite/fake renderer.
  They match the original source byte for byte.
- `data/samples/photosynthesis.en.json`, an assistant-authored English sample
  lesson. It is source content only; no audio or video was copied.
- `docs/qa-task1.md`, retaining the original QA plan with a current status note.
- `.env.example`, a non-secret local configuration template.
- This verification record.

Updated:
- `.gitignore`: models, Python caches, virtual environments, scratch files,
  generated videos, model-weight extensions, logs and temporary output.
- `README.md`: integrated backend status, prerequisites and the real CLI workflow.
- `HANDOFF.md`: a note identifying the existing frontend-only handoff as historical.

No `.env`, credentials, model weights, environments, dependencies, cache files,
scratch scripts or generated videos were transferred into version control.
Dependencies were installed with `npm ci --offline --no-audit --no-fund` from
the local npm cache. Narration, bundles, stills and MP4s are generated anew in
ignored target directories, never copied from the original application's cache.

## Checks run from the target checkout

Python: `C:/Users/ROG/Kavach/kavach-env/Scripts/python.exe` (3.11 environment).
Node: 24.21.0. Local browser: `C:/Program Files/Google/Chrome/Application/chrome.exe`.
No Python packages, model weights or browser were downloaded or upgraded.

| Check | Result |
| --- | --- |
| `python -m backend.generate_narration` | Passed; 13 fresh Kokoro beats, 46.089 s speech, 1558 frames at 30 fps, no warnings |
| `python -m pytest backend/tests -q -ra` | 76 passed, 0 failed, 2 skipped (38.11 s) |
| `npm test` | 35 passed, 0 failed |
| `npm run build:demo` | TypeScript, Vite production build and Remotion bundle passed |
| Local `remotion versions` | All Remotion packages match 4.0.539 |
| `npm run test:render` with local `CHROMIUM_PATH` | All 12 scenes across 3 samples rendered; metadata and repeated-frame determinism passed |

Backend skips are intentional: `/api/jobs/{job_id}` is not implemented in Task 1;
the missing-renderer test skips because the real renderer now exists. The
artifact-consistency test ran against newly generated target narration.
Vite reported nonblocking bundle-size and dependency `use client` warnings.

The server was switched from the original application's process to this
checkout on `127.0.0.1:8000`, without modifying the original folder. This ensures
Remotion fetches the target checkout's WAV rather than an old media artifact.

## Scope and remaining work

Gate 1 verifies the CLI path from a validated fixed English lesson through
Kokoro narration, timeline/captions and a real Remotion MP4. It does not establish
live topic generation, Ollama planning, translation, Kannada synthesis or the
unimplemented create/job endpoints. Health deliberately reports models as not
ready until their future startup warm-up is implemented. Varun's original
frontend-only `web/VALIDATION.md` remains intact as historical evidence.

The photosynthesis JSON is preserved as an extra source sample. The existing
narration CLI still intentionally targets the built-in Python-loop lesson;
its sample-prefixed ID needs a content-based cache ID when used by a custom
caller, as in the previous one-off generation. No temporary helper was imported.

## Real export verification from this checkout

`python -m backend.export_lesson` completed a fresh real render in **118.453 s**.
Output (ignored, not a commit candidate):
`cache/lessons/fallback-python-loop/en-female-1/lesson.mp4` (1,410,928 bytes),
with `lesson.srt` alongside it.

- H.264, 1280 x 720, 30 fps, yuv420p, BT.709; 1558 video frames.
- AAC stereo at 48 kHz, approximately 125 kbps (128k encoder setting).
- Container duration 51.947 s; timeline/video 51.933333 s (difference 0.013667 s).
- Full FFmpeg decode succeeded. MP4 `moov` precedes `mdat` (faststart).
- Decoded narration correlates with the source WAV at 0.999930, aligned from
  time zero. Audio-manifest hashes remain valid after export.
- All 14 UTF-8 SRT cues exactly match timeline-derived captions. Captioned
  frames from the title, code, diagram and recap scenes were visually inspected.
- HTTP responses for the WAV, MP4 and SRT match target files byte for byte.
  The built website and offline health endpoint respond; bundle readiness is true.

Detailed probe results and scene PNGs are retained in the ignored lesson cache
(`verification.json`, `verify-s1.png` through `verify-s4.png`). The temporary
verification helper was read from the original working directory, not copied
into this repository.

## Pre-commit review state

37 new source/documentation files and 3 modified documentation/ignore files;
no staged changes. HEAD, branch and remote are unchanged. No implementation
conflicts, frontend changes or export blockers were found. Original source
file hashes (144 files excluding generated/dependency directories) and all
79 original frontend file hashes match the pre-transfer snapshot.
Git ignore checks cover models, environments, credentials, generated videos,
cache, dependencies, build outputs and scratch files. `git diff --check` passes.

The localhost backend is running from `VisualTeacher-varun`. The original
`VisualTeacher` directory, its generated lessons and its dependencies remain
in place. Commit, tag and push require separate user authorization.

### Exact pending file inventory

Modified:
- `.gitignore`
- `HANDOFF.md`
- `README.md`

Added:
- `.env.example`
- `backend/__init__.py`
- `backend/app/__init__.py`
- `backend/app/cache.py`
- `backend/app/config.py`
- `backend/app/contracts.py`
- `backend/app/export/__init__.py`
- `backend/app/export/ffmpeg.py`
- `backend/app/export/render.py`
- `backend/app/jobs.py`
- `backend/app/localize/__init__.py`
- `backend/app/main.py`
- `backend/app/planner/__init__.py`
- `backend/app/planner/schema.py`
- `backend/app/speech/__init__.py`
- `backend/app/speech/audio.py`
- `backend/app/speech/engines.py`
- `backend/app/speech/kokoro_engine.py`
- `backend/app/speech/textnorm.py`
- `backend/app/timeline/__init__.py`
- `backend/app/timeline/build.py`
- `backend/app/timeline/captions.py`
- `backend/app/timeline/schema.py`
- `backend/app/timeline/srt.py`
- `backend/constraints.txt`
- `backend/export_lesson.py`
- `backend/generate_narration.py`
- `backend/requirements.txt`
- `backend/tests/__init__.py`
- `backend/tests/fake_render.py`
- `backend/tests/test_foundation.py`
- `backend/tests/test_task1_qa.py`
- `backend/tests/test_task2.py`
- `backend/tests/test_task3.py`
- `data/samples/photosynthesis.en.json`
- `docs/gate1-validation.md`
- `docs/qa-task1.md`

## Publication authorization and remote check

After consolidation review, the user explicitly authorized the Gate 1 commit
and a normal push to `origin/main` in the existing team repository. The authorized
`git fetch origin` completed successfully; local `main` and freshly fetched
`origin/main` both pointed to `d07593810f76d540d8dc194e2fb4c30a5293843e`.
No remote changes required reconciliation. The 40-file commit scope was reviewed
again: source, tests, documentation and `.env.example` only, with no generated
artifacts, model weights, virtual environments or secrets included.
