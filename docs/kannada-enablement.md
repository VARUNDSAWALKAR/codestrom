# Kannada approval alignment — 28 October 2026

Application checkout: `C:/Users/ROG/AppData/Local/Temp/blu-approved-merge-20261028`.
Original checkout and its environment/media are protected. No commits or pushes.

Approved preset: `kn_parler_suresh_21`; internal voice `Suresh`, request `male`.
Original benchmark loads before `transformers.set_seed(21)`, seeds once across
S1–S3; max_new_tokens 1500, sampling temperature 1, top_k 50, top_p 1,
num_beams 1, use_cache true; CPU float32, 4 intra-op threads. Description and
separate local tokenizers are unchanged. Production now uses that sequential RNG
policy across narration beats, saving/restoring JSON RNG snapshots for partial
cache reuse. No model-generated code, pickle loading, new models or dependencies.

Anu has no separate recorded approval and is blocked by production precheck and
disabled in the Kannada UI. Switching language visibly selects the available
male voice, rather than rerouting a female API request. En/Hi keep both voices.

Difficulty and speed remain request fields. Beginner/intermediate guide the
existing planner; this is not a measured pedagogical-quality guarantee. Speed
is 0.85/1/1.15 in the UI, with existing TTS/audio tempo handling and timeline
duration limits; no new optimization or model tuning is claimed.

Recovery completed: 35 focused Kannada backend tests passed; full backend
408 passed, 1 skipped, 42 subtests passed; frontend 69 passed; TypeScript, Vite
build, Remotion bundle and strict UI audit passed. Local environment now enables
en,hi,kn with CPU Suresh/21/cap1500. Only the backend was restarted.

Real config and browser selectors passed on ports 5173 and 8000: Kannada male only,
female disabled and explicit/default-female API requests rejected with 422
voice_unavailable. English/Hindi retain both voices; their existing cached lessons
returned 202 cached:true and played with audio. Male Kannada 202/preview acceptance
was verified by the production API integration test with synthetic speech; a live
male creation was not submitted, avoiding expensive synthesis. Cold lazy model
readiness flags do not imply a completed synthesis check.

Original .env and all 64 pre-existing runtime cache files remained hash-identical.
No commits/pushes, installs, cache replacement or automatic visual planning.
Additional recovery fix: Kannada MP4 verification memoization now notices changes
or removal of voice-profile.json. Historical tests/docs reflect the new contract.

Ready for final manual testing. A fresh production Suresh/21 synthesis, native
listening review and MP4 from that exact run remain unverified. Approval is not
production synthesis verification. Full recovery mapping, live config and evidence:
`C:/Users/ROG/VisualTeacher-varun/scratch/kn-recovery-resume/REPORT.md`.

