# UX Contract

## Product context

- Audience: students creating and watching local animated lessons.
- Primary jobs: create a lesson in a backend-approved language, follow generation, watch as soon as preview files are verified, download MP4/SRT when available.
- Active locales: English application UI; creation availability comes from `/api/config.languages[].available`. The prepared deployment approves English/Hindi; Kannada requires separate backend approval and voice support.
- Accessibility target: WCAG 2.2 AA.

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| Lesson creation, job lifecycle, preview/export readiness | `docs/frontend-integration.md` | API integration contract | 2026-10-27 |
| API payloads and errors | `docs/api-contracts.md` | API contract | 2026-10-27 |
| Player and route behavior | `docs/ui-flow.md`, overridden by current task | UI specification | 2026-10-27 |
| Timeline and render props | `docs/lesson-schema.md` | Data contract | 2026-10-27 |

## Visual contract

- Project `DESIGN.md`: `DESIGN.md`
- Token ownership: existing runtime CSS is canonical; DESIGN.md mirrors accepted values.
- Runtime source: `web/src/app/styles.css`; Remotion source: `web/src/lesson/theme.ts`.
- Supported theme: light.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native select in CreateForm | DESIGN.md | native | browser keyboard/popup |
| Form | CreateForm | this contract | create | app browser test |
| Scrollbar | global app stylesheet | DESIGN.md | geometry exceptions | premium audit/browser |

## Component behavior

| Component | Default | Hover | Focus | Active | Disabled | Busy | Error |
|---|---|---|---|---|---|---|---|
| Button | labelled action | lift/border | 3px ring | pressed | muted + reason | stable label/size | adjacent recovery |
| Icon button | tooltip/title | tonal surface | 3px ring | pressed | non-interactive | n/a | n/a |
| Textarea | labelled, help + count | border | 3px ring | n/a | n/a | preserved value | inline associated error |
| Segmented choice | visible options | tonal surface | ring on input label | selected card | grey + Coming soon | n/a | inline form error |

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| Create lesson | Generate Visual Lesson | locked stable CTA | `#/job/<id>` | progress route | field errors, busy retry, or inline error | first invalid field / progress heading | frontend-integration §Flow |
| Preview | `preview_ready=true` | progress stays live | player route with job query | playable lesson | job error or invalid-id state | player heading | frontend-integration §Preview readiness |
| Export | background export | disabled percent button | same player | active MP4 link after refetch | Video export failed + retry | retry action | frontend-integration §Failure |
| Cancel/back | Create another lesson | n/a | `#/` | form values retained in session | n/a | topic field | current task |

## Navigation and responsive behavior

- Routes: `#/`, `#/job/<id>`, `#/lesson/<id>?variant=…`, `#/sample/<id>`, `#/about`.
- Unknown job/lesson IDs show an app-owned inline error and leave navigation available.
- Player sidebar stacks below the player at narrow widths; controls remain at least 44px.
- Route transitions never wait for MP4 after preview readiness.

## Async and resilience

- Mutations are pessimistic; duplicate create submissions are blocked.
- Job polling is one abortable 500ms loop.
- HTTP 429 honors `Retry-After` or `error.retry_after`, then retries automatically.
- Preview fetch occurs once when ready; lesson data refetches once export completes.
- Job polling stops on completed/failed export or terminal non-preview error.
- Mock mode is announced persistently and never presented as production output.

## Validation

- Client validation runs on submit/blur; server 422 `error.fields` maps to fields.
- Forms use `noValidate`; the first invalid field receives focus.
- User values persist after server errors and when returning from a failed job.

## Verification

- Static: premium strict audit, TypeScript, unit tests, Vite build, Remotion bundle.
- Browser: unavailable/ready/mock health, validation, 429 retry, job error, export failure, preview-before-export, MP4 refetch, keyboard, 320px and 390px.
- Canonical sibling flow: supplied sample player uses the same player controls without backend success claims.
