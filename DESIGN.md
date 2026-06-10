---
name: Erdos portfolio page
description: Examiner's markup system. Plain paper surfaces, near-black ink, one committed verdict-red accent carried over from the repo's own architecture diagram, monospace reserved for evidence (code, hashes, counts). Sharp corners, hairline rules, no decoration.

# Source of truth for docs/style.css custom properties. If a token changes
# there, update both. All values OKLCH.
colors:
  # Light scheme (default)
  paper: "oklch(1 0 0)"                      # page ground, literal white
  pane: "oklch(0.967 0.003 262)"             # code panes, evidence surfaces
  ink: "oklch(0.25 0.015 262)"               # body text
  ink-strong: "oklch(0.16 0.015 262)"        # headlines, strong
  muted: "oklch(0.45 0.012 262)"             # captions, meta (>= 7:1 on paper)
  rule: "oklch(0.87 0.005 262)"              # hairline borders
  verdict-red: "oklch(0.50 0.185 27)"        # brand accent + REJECTED state, text-grade
  verdict-red-deep: "oklch(0.42 0.165 27)"   # hover / active on red
  red-tint: "oklch(0.96 0.02 27)"            # diff highlight fill behind changed tokens
  verified-green: "oklch(0.50 0.13 152)"     # VERIFIED state only, text-grade
  green-tint: "oklch(0.96 0.025 152)"        # verified fill

  # Dark scheme (prefers-color-scheme: dark)
  dark-paper: "oklch(0.165 0.012 262)"       # near-black, never pure black
  dark-pane: "oklch(0.215 0.012 262)"
  dark-ink: "oklch(0.88 0.006 262)"
  dark-ink-strong: "oklch(0.965 0.004 262)"
  dark-muted: "oklch(0.70 0.01 262)"
  dark-rule: "oklch(0.33 0.012 262)"
  dark-verdict-red: "oklch(0.70 0.175 25)"
  dark-red-tint: "oklch(0.28 0.06 27)"
  dark-verified-green: "oklch(0.74 0.13 152)"
  dark-green-tint: "oklch(0.27 0.05 152)"

typography:
  display:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(2.5rem, 1.4rem + 4.2vw, 4.25rem)"
    fontWeight: 750
    letterSpacing: "-0.025em"
    lineHeight: 1.02
  headline:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(1.7rem, 1.2rem + 1.9vw, 2.5rem)"
    fontWeight: 700
    letterSpacing: "-0.02em"
    lineHeight: 1.1
  title:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 650
    lineHeight: 1.3
  body:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.65
  code:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.04em"

rounded:
  all: "0"   # one shape system: sharp. No exceptions, no pills.

spacing:
  xs: "8px"
  sm: "16px"
  md: "24px"
  lg: "40px"
  xl: "64px"
  "2xl": "96px"
  "3xl": "128px"

components:
  button-primary:
    backgroundColor: "{colors.verdict-red}"
    textColor: "{colors.paper}"
    typography: "{typography.title}"
    rounded: "{rounded.all}"
    padding: "0 28px"
    minHeight: "48px"
  button-primary-hover:
    backgroundColor: "{colors.verdict-red-deep}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink-strong}"
    borderColor: "{colors.ink-strong}"
    rounded: "{rounded.all}"
    padding: "0 28px"
    minHeight: "48px"
  verdict-chip:
    typography: "{typography.label}"
    rounded: "{rounded.all}"
    padding: "4px 10px"
    note: "Always text + color, never color alone. REJECTED = verdict-red on red-tint; LOCKED = ink on pane; VERIFIED = verified-green on green-tint."
  evidence-pane:
    backgroundColor: "{colors.pane}"
    textColor: "{colors.ink}"
    borderColor: "{colors.rule}"
    rounded: "{rounded.all}"
    padding: "20px 24px"
  nav-link:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
  nav-link-hover:
    textColor: "{colors.verdict-red}"
---

# Design System: Examiner's Markup

## 1. Design read and dials

Per the taste-skill brief-inference step, stated before any code was written:

> **Reading this as:** a solo-developer portfolio *project* page for hiring managers and AI-safety-literate engineers, with a dry, evidence-first "examiner's markup" language, leaning toward native CSS, Archivo + JetBrains Mono, and a single committed verdict-red accent on plain paper (auto dark scheme). Deliberately not: AI-purple gradients, centered-hero-over-dark-mesh, three equal feature cards, Inter + slate-900, glassmorphism, or terminal-cosplay dark mode.

Scene sentence (theme decision): a skeptical reviewer reads this at a desk in the afternoon, the way they would read a referee report. That forces a reading surface: light by default, with a designed dark scheme honored via `prefers-color-scheme`.

Dials (taste-skill Section 1, developer-portfolio preset 6/5/4, adjusted and reasoned):

- `DESIGN_VARIANCE: 6`. Offset asymmetry: split hero (text 7 / artifact 5), ledger grids, one centered essay moment. Collapses to single column below 880px.
- `MOTION_INTENSITY: 3`. This is an evidence page, not a show reel, and it must work with JavaScript disabled. Motion is limited to hover/focus transitions, one short CSS-only hero entrance, and a one-time diff-highlight sweep, all gated behind `prefers-reduced-motion: no-preference`.
- `VISUAL_DENSITY: 5`. Technical audience; numbers and code carry the page. Mono for all evidence figures.

## 2. Color: one accent, and it means something

**Decision trail.** Impeccable's `palette.mjs` issued seed-058 (`oklch(0.764 0.120 77.1)`, honey/ochre). The skill's own rule says committed brand colors in the repo win over the seed ("identity-preservation wins"), and the repo has them: the README architecture diagram styles `REJECTED: Theorem Modified` in red (`#ff4444`) and `Verified Proof` in green (`#22c55e`). Those verdict colors are the project's identity. The seed was therefore set aside, documented here.

- **Verdict red is the brand.** The product's hero moment is a rejection: the hash check killing a cheating proof. So the one accent is the examiner's red, formalized at text-grade contrast (`oklch(0.50 0.185 27)` on white is about 6.5:1). It marks the primary CTA, links on hover, changed tokens in the diff, and REJECTED chips. Nothing else is red.
- **Verified green is a state, not an accent.** It appears only where the system says "verified", always with a text label, never decoratively.
- **The mood lives in the brand color and the type, not the surface.** Background is literal white (`oklch(1 0 0)`), per the palette script's own Default A. No cream, no beige, no warm tint.
- **Dark scheme** swaps to near-black cool paper (never `#000`), brightens red and green to keep AA contrast, and uses **zero glows**: no colored box-shadows anywhere in dark mode.

## 3. Typography: grotesque speaks, mono testifies

- **Archivo** (display through body). Chosen by the font procedure: brand-voice words "exact, adversarial, unimpressed"; the reflex picks (Inter, Geist, Space Grotesk, IBM Plex) are on the ban lists of both skills. Archivo is a signage grotesque: utilitarian, assertive at weight 700+, quiet at 400.
- **JetBrains Mono** strictly for evidence: Lean code, hashes, file paths, counts, verdict chips. Mono is not costume here; the page quotes real source. It never sets prose.
- Pairing axis: proportional grotesque vs. monospace code. Two families total.
- Scale is modular (ratio >= 1.25), fluid via `clamp()`, display ceiling under 6rem, tracking floor -0.025em (never past -0.04em).
- `text-wrap: balance` on headings, `text-wrap: pretty` on prose, body measure capped at 65ch.
- Fonts load from the Google Fonts CDN with `preconnect` + `display=swap`. This is a deliberate exception to the self-host rule: the site is a no-build static page and the constraint was set by the brief.

## 4. Layout

- Container 1120px, inline padding `clamp(20px, 5vw, 48px)`. Nav height 64px, one line at every width.
- **Each section gets its own layout family, used once:** split hero with code artifact; prose column; ordered pipeline; narrow centered essay (the one manifesto moment, which is the legitimate use of centering); stat band + 2x2 evidence grid; reading-order index. No zigzag repetition, no identical card rows.
- **Zero eyebrows.** No tracked uppercase kickers above headings, no `01 / 02 / 03` section markers. The one ordered sequence on the page is the Prover -> Lean -> hash -> Critic pipeline, numbered because it genuinely is a sequence.
- Spacing has rhythm: tight inside groups (8 to 24px), generous between sections (96 to 128px), and the hero sits high (top padding under 6rem).
- Grid for 2D, flex for 1D, single-column collapse below 880px declared explicitly per section.

## 5. Material and shape

- **Sharp everywhere.** `border-radius: 0` is the locked shape system; the page reads as print, stamp, and rule, not as app chrome.
- Depth comes from hairline borders and pane tints. No drop shadows in light mode beyond a faint paper lift on the artifact; no glows in dark mode; no glassmorphism; no gradients anywhere (surface or text).
- **No side-stripe accents.** Diff emphasis uses full-width tinted line fills and tinted token marks, the way real diffs do, never a thick colored left border.
- Cards are avoided; groups separate with rules and space. The 2x2 bug grid uses ruled cells, not floating cards, and nothing nests.

## 6. Motion

- Hover/focus transitions at 150 to 250ms, `cubic-bezier(0.22, 1, 0.36, 1)` (ease-out-quint family). No bounce, no elastic.
- One hero entrance: a short fade/rise cascade over the headline block and artifact, CSS-only, finishing under 700ms, `animation-fill-mode: both` so content is never gated on JS.
- The candidate pane's changed tokens get a one-time tint sweep on load to direct the eye to the cheat. That is the entire motion budget.
- Everything sits inside `@media (prefers-reduced-motion: no-preference)`; reduced motion gets the final frame instantly.

## 7. Do and do not

### Do

- Do show real artifacts: real Lean from `examples/`, hashes computed exactly as `src/validator.py` computes them, bug fixes quoted from `ASSESSMENT.md`.
- Do pair every verdict color with a text label (REJECTED, LOCKED, VERIFIED).
- Do keep mono for evidence and grotesque for argument.
- Do state the unflattering facts (toy example theorems, unbenchmarked solve rates, no public release artifacts yet) in the same breath as the flattering ones.

### Do not

- Do not introduce a second accent hue, a gradient, or a glow.
- Do not round a corner.
- Do not add an eyebrow, a numbered section marker, a scroll cue, a locale strip, a version footer, or a decorative status dot.
- Do not use an em-dash anywhere on the page. Hyphens, commas, colons, periods.
- Do not fabricate: no invented metrics, attempt numbers, testimonials, logos, or providers the repo does not ship.
