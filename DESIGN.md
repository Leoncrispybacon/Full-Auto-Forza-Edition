# FAFE — Design System

Canonical design system for **Full Auto Forza Edition (FAFE)**, a Windows
desktop automation tool for Forza Horizon 6, plus its marketing/guide website.
This file is the source of truth for Claude Design. If automatic inference
disagrees with anything here, this file wins.

Product is **dark-mode only**. There is no light theme. Never generate
light-background variants.

There are **two surfaces** with their own concrete tokens: the **desktop app**
(CustomTkinter / `theme.py`) and the **website** (static HTML/CSS under `en/`,
`zh-tw/`, `assets/site/`). They share the same intent — dark, blue accent — but
use different exact values. Web mockups should follow the **website** palette and
fonts below; app mockups the **app** ones.

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

## Color — App (CustomTkinter / theme.py)

Use token names, not raw hex, when describing app components.

### Core
| Token          | Hex         | Role |
|----------------|-------------|------|
| `bg`           | `#0B0F17`   | App background (darkest) |
| `bg_mid`       | `#121A28`   | Gradient partner, raised areas |
| `surface`      | `#161E28`   | Cards, panels |
| `surface_alt`  | `#0A0E14`   | Inset areas (log body, code) |
| `sidebar_bg`   | `#141B26`   | Left navigation panel |
| `border`       | `#243044`   | Card / panel borders |

### Accent / status / text
| Token          | Hex         | Role |
|----------------|-------------|------|
| `accent`       | `#2563EB`   | Primary action, active nav, title bars |
| `accent_hover` | `#1D4FD7`   | Hover state for primary |
| `accent_light` | `#7DB2FF`   | Highlights, secondary title text |
| `status_dot`   | `#22C55E`   | Green "ready / detected / active" dot |
| `stop`         | `#DC2626`   | Stop button fill (`#B91C1C` hover) |
| `warn`         | `#FF4444`   | Warning log text, capture instructions |
| `text`         | `#F4F8FD`   | Primary text |
| `text_muted`   | `#82A0B2`   | Secondary text, captions |
| `log_text`     | `#A6B0BC`   | Normal automation-log lines |
| `log_accent`   | `#7DB2FF`   | Log section/loop headers |

---

## Color — Website (actual CSS: a Tailwind slate + blue scale)

The site is built on Tailwind's slate/blue values — same dark+blue spirit as the
app, slightly brighter accents. These are the values to use for web mockups.

### Surfaces & borders
| Role | Hex | Notes |
|------|-----|-------|
| page bg (darkest) | `#070A0F` / `#0F0F0F` | homepage / guide body |
| header & caption strip | `#0B1220` | site header, screenshot captions |
| card / section | `#111827` | guide sections, feature cards |
| notice / TOC (blue-tinted) | `#0C1A2E` | callouts, table-of-contents |
| code background | `#1E293B` | inline `code` |
| border (neutral) | `#334155` | cards, dividers |
| border (subtle / blue-tinted) | `#1E293B` / `#1E3A5F` | hairlines / notice & step accents |

### Accent / text
| Role | Hex | Notes |
|------|-----|-------|
| accent (primary) | `#3B82F6` | blue-500 — hover borders, primary |
| accent (strong) | `#2563EB` | blue-600 |
| accent light | `#60A5FA` | blue-400 — links, eyebrow, step numbers |
| code text | `#BFDBFE` | blue-200 on code bg |
| heading text | `#F8FAFC` / `#F1F5F9` | h1 / h2 |
| body text | `#E2E8F0` | paragraphs |
| muted | `#94A3B8` | lede, captions |
| dim (meta) | `#64748B` | breadcrumbs, dates, footer |

### Forza-festival amber (website only, sparing)
| Hex | Use |
|-----|-----|
| `#F97316` `#FB923C` `#FBBF24` `#FED7AA` `#C2410C` | the **Horizon / festival-playlist** element only |

> Color-role guardrails:
> - **Blue is the one brand accent.** The amber set is a *Forza-festival* nod used
>   **sparingly on the website only**, for Horizon/festival-themed elements —
>   never in the app, never as a generic accent, never introduce purple/teal/etc.
> - `status_dot` green is a status signal ONLY (app). `warn`/`stop` red are
>   warning/stop ONLY.

---

## Typography

No web fonts are loaded — both surfaces use a **system font stack** (fast, and it
matches the native app look).

### App (CustomTkinter, Windows)
| Token | Family | Notes |
|-------|--------|-------|
| `font_title` / `font_button` | Segoe UI (Bold) | headers, buttons |
| `font_body` | Segoe UI | labels, body |
| `font_mono` | Consolas | log output, numbers |

Per-language pinning: **繁中/简中 → Microsoft JhengHei UI**, **English → Segoe UI**.

### Website
- Stack: **`"Segoe UI", "Microsoft JhengHei UI", sans-serif`** (guides);
  homepage leads CJK-first: `'Microsoft JhengHei', 'PingFang TC', 'Helvetica Neue', sans-serif`.
- Body line-height **1.75** (roomy, reading-oriented).
- `h1`: `clamp(2rem, 5vw, 3.1rem)`, line-height 1.15, `#F8FAFC`.
- `.lede`: 1.13rem, `#94A3B8`. `h2`: 1.45rem, `#F1F5F9`.
- `.eyebrow` (kicker): 0.78rem, weight 700, `letter-spacing .12em`, UPPERCASE,
  `#60A5FA` — the small blue label above each h1.
- `code`: monospace, `#BFDBFE` on `#1E293B`.

---

## Shape & spacing

- **Website radii:** `12px` sections/cards/notice/TOC · `10px` screenshots,
  guide cards, pagination · `9px` brand icon · `7px` language pill · `5px` inline
  code · `999px` step-number pill.
- **App radii:** `8px` cards/buttons, `4px` small controls; app icon ~20% rounded square.
- **Borders:** 1px, low-contrast (`border` / `#334155`); prefer fill contrast over heavy outlines.
- **Website content column:** centered, `min(920px, 100% - 40px)`.
- **Spacing:** generous vertical rhythm (section `margin-top: 32px`, padding ~26px);
  app uses a 4/8/12/16/24/32 scale, cards 16–20 padding.
- **Density:** comfortable, not cramped — legibility first.

---

## Layout patterns

### Website (static, GitHub Pages — no build step)
- **`index.html` is a language router** → `/en/` and `/zh-tw/` (saved/browser
  language). Preserve these routes + their canonical/hreflang metadata; no URL
  hashes/params, no extra routing systems.
- Each language has a **localized homepage** plus an **overview guide and 11
  detailed guides** under `<lang>/guides/`. Shared presentation/behavior live in
  `assets/site/guide.css` and `assets/site/guide.js` (image zoom, prev/next).
- **Site chrome:** `.site-header` (brand wordmark + 38px icon, a language-switch
  link) → centered 920px `main` → footer. EN and 繁中 pages are kept
  structurally equivalent.
- **Guide page anatomy:** breadcrumbs → `.eyebrow` (uppercase blue) → `h1` →
  `.lede` → `.notice`/`section` cards → numbered `.steps` (round `.step-num`
  pills, `#1E3A5F` bg / `#60A5FA` number) → `.screenshot` (zoomable, with a
  caption strip) → 2-column `.toc` → `.guide-grid` of cards → prev/next
  `.guide-pagination`.
- **Homepage:** dark hero → a single **Features & Guides** section of clickable
  cards (restrained text category labels, **no decorative emoji**) → download
  button pointing at the latest `FAFE.zip` GitHub release asset → a Support/PayPal
  link. The Horizon/festival element may use the amber set, sparingly.
- **Responsive:** ≤640px collapses the 2-column grids (guide grid, TOC,
  pagination) to a single column.
- **Screenshots:** WebP, resized to ~≤1600px wide; every image needs
  `width`/`height`, lazy loading, async decoding, descriptive alt, and a caption.

### App — Fluent sidebar layout
- **Left sidebar** (~210px): FAFE wordmark; vertical nav (one per automation
  mode); Settings + Support at the bottom. Active nav = `accent` left bar + raised
  `surface` fill; inactive = transparent + `text_muted`.
- **Main column:** page title + monitor dropdown header; collapsible "Setup &
  Templates" panel (green `status_dot` when ready); control row (Start = `accent`,
  Stop = `stop`, + an "F9" hint); activity **log** filling the rest.
- Settings open **inline in the main column** with a ← Back affordance.

### Component & interaction patterns (App)

These are the recurring control patterns; reuse them rather than inventing new
ones, so every tab reads the same.

- **Segmented mode toggle** — for a small set (2–3) of mutually-exclusive modes,
  use a segmented button, not a dropdown or radio stack. Selected segment =
  `accent` fill + `accent_text`; unselected = `surface_alt` + `text`. Examples:
  the per-function option toggles (e.g. wheelspin type, duplicate handling).
- **Contextual controls (show-in-context)** — a sub-option appears **only when
  its parent mode makes it relevant**, and is hidden otherwise (not greyed out).
  The control's *absence* is the signal that it doesn't apply. Keeps each tab to
  only the choices that matter right now. Re-pack it directly under its parent
  row when shown.
- **Helper note** — a short muted (`text_muted`, ~11px) caption set inline beside
  or beneath a control to scope or qualify it (e.g. "… mode only", "Only affects
  X"). Never a full sentence of body text; it's a qualifier, not a paragraph.
- **Safe-default / keep-on-uncertain** — when an automated action is destructive
  or irreversible and a check is ambiguous, the UI/behaviour defaults to the
  **non-destructive** outcome (keep, don't sell/delete) and says so in the log.
  Confidence is required to take the destructive path, never to avoid it.
- **Detection-gated actions** — steps act only once the target screen is actually
  detected on-screen (never on a blind timer); a stage that can't be confirmed
  waits or aborts rather than firing into an unknown screen. Surfaced to the user
  as plain status/log lines, not spinners.

---

## Iconography & motifs

- **App mark:** a stylized window/app frame — dark rounded square, an `accent`
  title bar with three "traffic light" dots, a bold `accent_light` "F" centered,
  and a small green `status_dot` lower-right. Used as the 38px website brand icon too.
- **Website decoration:** restrained — no decorative emoji; category labels are
  plain text. Any festival-amber glow is light and confined to Horizon elements.
- App icons: simple monochrome line/emoji glyphs aligned to nav labels.

---

## Voice & content

- **Bilingual, first-class:** English and Traditional Chinese (the website carries
  full parallel guide trees; the app strings are EN + 繁中). Keep layouts tolerant
  of longer CJK strings. English product terms standardized as **AFK Races** and
  **Wheelspins**.
- Microcopy is plain and direct.
- Unofficial / fan-made: never imply official affiliation with Forza, Playground
  Games, or Xbox Game Studios.

---

## Hard don'ts

- No light mode, ever.
- Blue is the brand accent; green is status-only; red is stop/warn-only. The amber
  set is website-only, Horizon/festival-only, and sparing. No other accents.
- No gradient-heavy / glow-heavy UI **inside the app** (the framework renders it
  poorly); the website may use restrained glow/gradient.
- No decorative emoji on the website; no crowding — whitespace is part of the brand.
- Don't reproduce official Forza logos, car imagery, or game art as first-party.
- Website: no build step, no URL hashes/params, no extra language-routing systems;
  keep `/en//zh-tw/` routes and their canonical/hreflang metadata intact.
