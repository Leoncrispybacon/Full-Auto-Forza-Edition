# FAFE — Design System

Canonical design system for **Full Auto Forza Edition (FAFE)**, a Windows
desktop automation tool for Forza Horizon 6, plus its marketing website.
This file is the source of truth for Claude Design. If automatic inference
disagrees with anything here, this file wins.

Product is **dark-mode only**. There is no light theme. Never generate
light-background variants.

---

## Brand essence

FAFE is a focused, slightly technical utility with a racing-game subject.
The visual language is **dark, calm, and precise** with a single confident
blue accent and a green "ready/active" status signal. It should feel like a
clean developer tool, not a flashy gamer skin. Restraint over decoration.

Tone words: precise, dark, technical, trustworthy, quietly sporty.
Avoid: neon overload, gradients-as-decoration, busy textures, light themes,
skeuomorphism.

---

## Color tokens

All values are the canonical brand palette. Use token names, not raw hex,
when describing components.

### Core

| Token          | Hex         | RGB             | Role |
|----------------|-------------|-----------------|------|
| `bg`           | `#0B0F17`   | 11, 15, 23      | App / page background (darkest) |
| `bg_mid`       | `#121A28`   | 18, 26, 40      | Gradient partner, raised areas |
| `surface`      | `#161E28`   | 22, 30, 40      | Cards, panels |
| `surface_alt`  | `#0A0E14`   | 10, 14, 20      | Inset areas (log body, code) |
| `sidebar_bg`   | `#141B26`   | 20, 27, 38      | Left navigation panel |
| `border`       | `#243044`   | 36, 48, 68      | Card / panel borders (subtle) |

### Accent

| Token          | Hex         | RGB             | Role |
|----------------|-------------|-----------------|------|
| `accent`       | `#2563EB`   | 37, 99, 235     | Primary action, active nav, title bars |
| `accent_hover` | `#1D4FD7`   | 29, 79, 215     | Hover state for primary |
| `accent_light` | `#7DB2FF`   | 125, 178, 255   | Highlights, secondary title text, glints |
| `accent_text`  | `#0A1320`   | 10, 19, 32      | Text/icons placed ON an accent fill |

### Status & semantic

| Token          | Hex         | RGB             | Role |
|----------------|-------------|-----------------|------|
| `status_dot`   | `#22C55E`   | 34, 197, 94     | Green "ready / detected / active" dot |
| `stop`         | `#DC2626`   | 220, 38, 38     | Stop button fill |
| `stop_hover`   | `#B91C1C`   | 185, 28, 28     | Stop button hover |
| `warn`         | `#FF4444`   | 255, 68, 68     | Warning log text, capture instructions |

### Text

| Token          | Hex         | RGB             | Role |
|----------------|-------------|-----------------|------|
| `text`         | `#F4F8FD`   | 244, 248, 253   | Primary text |
| `text_muted`   | `#82A0B2`   | 130, 150, 178   | Secondary text, captions, subtitles |
| `log_text`     | `#A6B0BC`   | 166, 176, 188   | Normal automation-log lines |
| `log_accent`   | `#7DB2FF`   | 125, 178, 255   | Log section/loop headers |

> Color-role guardrails (do not cross-wire):
> - `warn` (`#FF4444`) is for warnings ONLY. It is not a generic accent and
>   not the same as `stop`.
> - `status_dot` green is a status signal ONLY. Do not use it for buttons,
>   links, or decoration.
> - The one and only brand accent is the blue family
>   (`accent` / `accent_light`). Do not introduce purple, teal, amber, etc.

---

## Typography

The desktop app and the website use different font stacks (Windows-native
vs. web), but the same hierarchy and intent.

### App (CustomTkinter, Windows)

| Token         | Family (primary)        | Notes |
|---------------|-------------------------|-------|
| `font_title`  | Segoe UI (Bold)         | Headers, page titles |
| `font_body`   | Segoe UI                | Labels, body, controls |
| `font_button` | Segoe UI (Bold)         | Button labels |
| `font_mono`   | Consolas                | Log output, numeric readouts |

Per-language pinning (app):
- Traditional / Simplified Chinese → **Microsoft JhengHei UI** (繁中) /
  appropriate CJK UI font, so glyphs render cleanly.
- English → **Segoe UI**.

### Website (and Claude Design web mockups)

| Role          | Family                  | Notes |
|---------------|-------------------------|-------|
| Display title | Bricolage Grotesque (Bold) | Big two-line hero titles |
| Alt display   | Big Shoulders (Bold)    | Condensed "FAFE" wordmark, badges |
| Body / UI     | Work Sans / Instrument Sans | Subtitles, paragraphs, controls |
| Mono / kicker | Geist Mono              | Small caps kickers, version tags, code |

Hierarchy intent (both surfaces):
- Title: large, bold, tight. Often two lines with the second line in
  `accent_light`.
- Subtitle: `text_muted`, medium weight, comfortable.
- Kicker: small mono, uppercase, letter-spaced, `accent_light`.

---

## Shape & spacing

- **Corner radius:** default `8px` for cards/buttons, `4px` for small
  controls (chips, sliders' value labels). The app icon uses a larger
  `~20%` radius rounded square.
- **Borders:** 1px, color `border`, used sparingly to separate cards from
  background. Prefer fill contrast over heavy outlines.
- **Spacing scale:** 4 / 8 / 12 / 16 / 24 / 32. Cards use 16–20 internal
  padding. Don't collapse this to a coarse 8/16/32-only scale.
- **Density:** comfortable, not cramped. This is a tool used while glancing
  between windows, so legibility beats density.

---

## Layout patterns

### App — Fluent sidebar layout (current)

- **Left sidebar** (fixed ~210px): FAFE wordmark at top; vertical nav items
  (one per automation mode); Settings and a Support Me button at the bottom.
  Active nav item = `accent` indicator bar on the left edge + raised
  `surface` fill; inactive = transparent + `text_muted`.
- **Main column:** header row (page title + monitor dropdown, right-aligned),
  then the mode's content: a collapsible "Setup & Templates" panel (with a
  green `status_dot` when ready), a control row (Start = `accent`,
  Stop = `stop`, plus an "F9 to start / stop" hint), and an activity **log**
  panel filling the rest.
- Settings opens **inline in the main column** (sidebar stays visible),
  with a ← Back affordance.

### Website — landing page

- Dark hero with the FAFE window-chrome icon, a two-line title
  ("Full Auto" in `text`, "Forza Edition" in `accent_light`), a
  `text_muted` subtitle, and a primary download button in `accent`.
- Feature cards on `surface` with subtle `border`, bilingual-friendly
  (English + Traditional Chinese coexist).
- Subtle diagonal accent bands and faint horizontal "speed-line" streaks
  are the ONLY decorative motif. Use them sparingly, right-weighted.
- A fixed bottom-right "☕ Support Me" button (PayPal).

---

## Iconography & motifs

- **App mark:** a stylized window/app frame — dark rounded square, an
  `accent` title bar with three "traffic light" dots, a bold `accent_light`
  "F" centered, and a small green `status_dot` in the lower-right corner.
- **Decorative motif (marketing only):** thin speed-line streaks and one or
  two diagonal accent bands. Never use these inside the app UI itself.
- Icons in the app are simple line/emoji-style glyphs aligned to nav labels;
  keep them monochrome-ish and unobtrusive.

---

## Voice & content

- Bilingual: English and Traditional Chinese are first-class. Many strings
  appear in both. Keep layouts tolerant of longer CJK strings.
- Microcopy is plain and direct ("Before starting, enter the race you want
  to grind and stop at the Start Race screen.").
- The product is unofficial / fan-made: never imply official affiliation
  with Forza, Playground Games, or Xbox Game Studios.

---

## Hard don'ts

- No light mode, ever.
- No second accent color. Blue is the brand; green is status-only;
  red is stop/warn-only.
- No gradient-heavy or glow-heavy UI *inside the app* (the framework can't
  render it well anyway). Marketing pages may use restrained glow/gradient.
- Don't crowd the layout; whitespace and calm are part of the brand.
- Don't reproduce official Forza logos, car imagery, or game art as if
  first-party.
