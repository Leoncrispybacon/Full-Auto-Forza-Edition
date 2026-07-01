# FAFE — Design System

Canonical design system for **Full Auto Forza Edition (FAFE)**, a Windows
desktop automation tool for Forza Horizon 6, plus its marketing/guide website.
This file is the source of truth for Claude Design. If automatic inference
disagrees with anything here, this file wins.

Product is **dark-mode only**. There is no light theme. Never generate
light-background variants.

There are **two surfaces** with their own concrete tokens: the **desktop app WebUI**
(`webui/`) and the **website** (static HTML/CSS under `en/`, `zh-tw/`,
`assets/site/`). They share the same intent — dark, blue accent — but
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

## Color - App WebUI

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

## Color — Website (mirrors the app palette as of the v2.0.0 site refresh)

The website now follows the **app's dark tokens**, not the older, brighter Tailwind
slate/blue scale — the site is being brought visually in line with the desktop app
(a calm, precise "developer tool" look). Use these for web mockups. The prior Tailwind
values (`#070A0F`, `#111827`, `#3B82F6`, `#94A3B8`, …) are **superseded** and survive
only on guide pages not yet restyled.

### Surfaces & borders
| Role | Hex | Notes |
|------|-----|-------|
| page bg (darkest) | `#0B0F17` | homepage / body; `#0A0E14` for inset/code areas |
| card / section | `#121A28` | sections, feature cards |
| raised panel | `#161E28` | inner panels, controls, code bg |
| notice / blue-tinted panel | `#0C1A2E` | callouts, TOC, **the Full Auto panel** |
| border (neutral) | `#243044` | cards, dividers (1px, low-contrast) |
| border (soft) | `#1a2433` | hairlines |

### Accent / text
| Role | Hex | Notes |
|------|-----|-------|
| accent (primary) | `#2563EB` | links, primary buttons, active |
| accent hover | `#1D4FD7` | hover for primary |
| accent light | `#7DB2FF` | highlights, eyebrow, secondary title text |
| code text | `#BFDBFE` | on raised panel bg |
| heading text | `#F4F8FD` | h1 / h2 |
| body text | `#cdd9e5` | paragraphs |
| muted | `#82A0B2` | lede, captions |
| dim (meta) | `#5f7488` | breadcrumbs, dates, footer |

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

Both surfaces share the app's typeface set — a **display** face for headings, a
humanist **sans** for body, and a **mono** for numbers/labels — with system + CJK
fallbacks. (This supersedes the older "system stack only" guidance: the site now loads
the same families as the app so the two match.)

### App (WebUI, Windows)
| Token | Family | Notes |
|-------|--------|-------|
| `font_title` / `font_button` | Segoe UI (Bold) | headers, buttons |
| `font_body` | Segoe UI | labels, body |
| `font_mono` | Consolas | log output, numbers |

Per-language pinning: **繁中/简中 → Microsoft JhengHei UI**, **English → Segoe UI**.

### Website (app-aligned)
- **Display (headings):** `'Bricolage Grotesque'` (the app's display face; the wordmark
  may use `'Big Shoulders Display'`), falling back to `'Work Sans'` + system + CJK.
- **Body:** `'Work Sans', system-ui, 'Segoe UI', <cjk>, sans-serif`.
- **Mono (stat/label chips, code):** `'Geist Mono', ui-monospace, Consolas, <cjk>`.
- **CJK fallback:** `'Microsoft JhengHei','Microsoft YaHei','PingFang TC','Noto Sans CJK TC'`
  — keep it so 繁中 stays crisp; layouts must tolerate longer CJK strings.
- Fonts are **loaded** (Google Fonts, with bundled TTFs under `assets/site/fonts/` for
  offline parity) — matching the app, which loads the same families.
- Body line-height ~1.6–1.75. `h1`: `clamp(2rem, 5vw, 3.1rem)`, lh 1.15, `#F4F8FD`.
  `.lede`: ~1.13rem, `#82A0B2`. `h2`: ~1.45rem, `#F4F8FD`.
- `.eyebrow` (kicker): 0.78rem, weight 700, `letter-spacing .12em`, UPPERCASE,
  `#7DB2FF` — the small blue label above each h1.
- `code`: mono, `#BFDBFE` on `#161E28`.

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
- **Homepage section order:** dark hero (radial blue glow, app-style) + an **installer**
  download button → in-page nav → **What is FAFE** (`#about`) → **Full Auto**
  (`#full-auto`, the paid section — see the Full Auto subsection below) → **Features &
  Guides** (`#guides`, clickable cards, restrained text category labels, **no decorative
  emoji**) → **Three Steps to Start** (`#howto`) → **Advanced Settings** (`#settings`) →
  **Disclaimer** → footer Support/PayPal link. The Horizon/festival element may use the
  amber set, sparingly.
- **Download** points at the latest **installer**:
  `…/releases/latest/download/FAFE_Setup.exe` (version-less name, auto-tracks latest; not
  a zip — the installer avoids Windows' Mark-of-the-Web DLL block).
- **Responsive:** ≤640px collapses the 2-column grids (guide grid, TOC,
  pagination) to a single column.
- **Screenshots:** WebP, resized to ~≤1600px wide; every image needs
  `width`/`height`, lazy loading, async decoding, descriptive alt, and a caption.

### Full Auto — the paid homepage section (`#full-auto`)
Placed **between `#about` and `#guides`**, and linked in the in-page nav between "About"
and "Features & Guides". The optional paid mode; everything else in FAFE stays free.
- **Attention, restrained.** A distinct, self-contained panel on the blue-tinted surface
  (`#0C1A2E`) with a subtle `#2563EB` accent border and a small uppercase eyebrow
  ("PREMIUM" / 「進階模式」). Reads a notch above the feature cards, well below the hero —
  no amber, no neon, no animation beyond the site's restrained glow.
- **What it is:** Full Auto chains FAFE's individual tools into one hands-off loop — it
  races, buys cars, unlocks mastery, sells, and repeats unattended. Mirror the app's own
  locked/teaser preview so the site and app agree.
- **Bullets:** two grind modes — **Wheelspin Grind** and **Money Grind**; automatic
  mastery-point detection + car-count calculation; real-time stage progress; optional
  Auto Wheelspin branch after selling.
- **Pricing (one-time unlock):** `$5.99 one-time unlock` (`/en/`), `NT$190 一次買斷`
  (`/zh-tw/`), with a small regional-equivalent-price note.
- **CTA:** a single accent-blue button → `https://ko-fi.com/s/edbeb0552c`
  (EN "Unlock Full Auto" · 繁中 「解鎖全自動模式」).
- **Naming:** in 繁中 the mode is always **「全自動模式」** — never mix in English
  "farming"/"掛機".
- **Scope guard:** marketing copy, pricing, and the purchase link are public and belong
  here; the chain's implementation details do **not** — keep them out of this file.

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
