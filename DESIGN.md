---
version: alpha
name: "Blu VisualTeacher"
description: "A calm visual learning studio that turns local AI output into inspectable animated lessons."
colors:
  primary: "#2464E8"
  primary-strong: "#165CD9"
  cyan: "#168ED7"
  violet: "#6558DD"
  background: "#F6F8FC"
  surface: "#FFFFFF"
  text: "#15223B"
  text-muted: "#637188"
  border: "#DFE6F0"
  success: "#2E9E77"
  warning: "#D97706"
  danger: "#B9433E"
  code-surface: "#0F1D36"
  focus: "#719DF6"
typography:
  body:
    fontFamily: "App Noto, App Indic, App Kannada, sans-serif"
    fontSize: "14px"
    lineHeight: "1.6"
  display:
    fontFamily: "App Noto, App Indic, App Kannada, sans-serif"
    fontSize: "62px"
    lineHeight: "1.08"
  mono:
    fontFamily: "App Noto Mono, ui-monospace, monospace"
rounded:
  DEFAULT: "0.625rem"
  sm: "0.375rem"
  md: "0.75rem"
  lg: "1rem"
  card: "1.25rem"
spacing:
  control-height: "2.75rem"
  card-padding: "2.125rem"
  page-gutter: "6%"
  page-max: "90rem"
components:
  button: {}
  card: {}
  form: {}
  status-banner: {}
  lesson-player: {}
---

# Blu VisualTeacher Design System

## Overview

### Creative North Star

Blu should feel like an **animated lesson storyboard on a precise studio desk**: pale working surfaces, dark navy technical panels, blue timeline marks, and small instructional annotations. The signature is the live lesson specimen beside the creation form—it proves the product visually before asking for trust.

### Product context and register

- **Audience and primary job:** students who need a difficult concept turned into a short, inspectable visual explanation.
- **Target markets and evidence:** multilingual Indian learning is the long-term product context; the current production creation flow is English-only per `docs/frontend-integration.md`.
- **Locales and language policy:** application chrome is English. English lesson generation is enabled. हिन्दी and ಕನ್ನಡ appear only as disabled “Coming soon” choices until translation and voice integration is approved.
- **Usage scene:** laptop-first lesson creation and playback, with touch-friendly phone playback and controls.
- **Register:** hybrid. The home hero carries brand expression; create, progress, error, and player surfaces prioritize product clarity.
- **Memorable signature:** the dark “lesson specimen” showing code, state, output, and captions as one teaching surface.
- **Restraint:** forms, pipeline state, diagnostics, errors, and downloads remain familiar and quiet.
- **Anti-references:** no chat bubbles, generic AI gradients across every surface, childish gamification, glass-heavy dashboards, or fake-success states.
- **Token ownership/runtime mapping:** `web/src/app/styles.css` is the existing runtime source of truth. This file mirrors its accepted semantic values. Remotion scenes retain their separate documented tokens in `web/src/lesson/theme.ts`.

## Colors

Deep educational blue owns primary actions and current state. Cyan and violet are expressive accents limited to the hero, generation illustration, and signature preview. White surfaces sit on blue-gray `background`; `border` and restrained shadows carry hierarchy. Green, amber, and red retain status meaning and always pair with text or symbols. Focus uses `focus` with a visible three-pixel outline.

## Typography

Local Noto assets support Latin, Devanagari, and Kannada without network access. Display type uses tight spacing and a 600 weight; product copy stays readable and modest. Code and technical values use the local mono face. Uppercase eyebrows are short structural labels, not decorative paragraphs. Native-script labels use script-appropriate local fonts and never italic styling.

## Layout

The app is capped at `page-max` with fluid `page-gutter`. The create route uses a two-column studio layout and collapses below 780px. Player and chapter navigation use a main-plus-sidebar grid, then stack on smaller screens. Controls keep a 44px minimum touch target. Async content reserves card geometry; loading and error text do not move the primary action.

## Elevation & Depth

Static cards use a thin border and a low-opacity blue shadow. The lesson specimen and active player may use deeper elevation because they are the visual focus. Navigation, diagnostics, and status banners stay flatter. Blur is decorative only and never reduces text contrast.

## Shapes

Controls use 9–12px radii, cards 16–20px, and status pills a full capsule. Dark code surfaces use the same card grammar. Lines and arrows represent real timelines, data flow, or progression.

## Components

### Foundational visual states

Hover adds a small lift only to enabled navigation cards and actions. Focus is always visible. Selected state combines color, border, and text. Disabled actions keep their footprint and expose a reason. Busy controls preserve size and announce state. Success, warning, and error surfaces use icon/text plus semantic color.

### Buttons and actions

Primary solid blue is reserved for generation, playback, retry, and ready downloads. Outline buttons support adjacent safe actions; ghost links navigate. Busy labels keep stable geometry. Unavailable MP4 and generation actions remain disabled with explanatory text.

### Navigation and data display

Hash routes keep refreshable create, job, lesson, sample, and About views. Pipeline stages are ordered rows. Telemetry is a semantic table. Mock mode is a persistent global banner above navigation.

### Forms and overlays

The creation form owns validation through `noValidate`, inline field errors, and first-error focus. Segmented controls own short finite choices. Native selects are accepted for optional subject and speech speed because OS popup behavior is suitable for these secondary controls.

### Iconography

Use simple one-color SVG or typographic symbols at 16–20px. Icon-only controls require accessible names and titles. Icons support labels rather than replacing unfamiliar actions.

### Motion

Feedback transitions use 180ms ease; generation orbit may run slowly to communicate work. Motion stops under `prefers-reduced-motion`. Remotion lesson motion remains deterministic and timeline-driven.

### Content and data visualization

Copy uses plain active language: Create, Try again, Download, Video export failed. Errors name the failed stage and recovery. Progress reports only backend data. Diagnostics retain milliseconds, peak RSS, and device profile.

## Do's and Don'ts

- **Do:** prove visual learning with real sample content and honest state.
- **Do:** keep the same stage names, status language, and recovery actions across progress and player.
- **Don't:** imply translation, narration, or MP4 readiness before the backend reports it.
- **Don't:** let expressive gradients or motion compete with lesson content and controls.
