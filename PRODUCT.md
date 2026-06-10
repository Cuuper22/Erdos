# Product

## Register

brand

## Users

Two audiences, one behavior: skeptical scanning.

1. **Recruiters and hiring managers** evaluating a solo developer. They arrive from a resume link or the GitHub repo, give the page 30 to 90 seconds, and are pattern-matching for evidence of real engineering judgment versus AI-assembled portfolio filler. They have seen a hundred purple-gradient project pages this month.
2. **AI-safety-literate engineers** scanning for signal. They know what specification gaming is, they know what a Prover/Critic loop is, and they will close the tab the moment a claim smells inflated. They want the failure mode, the boundary that fixed it, and the tests that keep it fixed. Several will actually open `src/validator.py`.

The job to be done for both: decide, quickly, whether the person behind this repo is worth a conversation. The page exists to make that decision easy by showing receipts, not adjectives.

## Product Purpose

A single static page (GitHub Pages, `docs/` on `main`) that presents the Erdos project: a multi-agent LLM theorem prover for Lean 4 whose agents learned to cheat by rewriting theorem statements, and the SHA-256 theorem-locking boundary that stops them. The page is a portfolio case study, not a product landing page. Nothing is for sale; the conversion event is "opened the source code" or "replied to the candidate."

Success looks like: a reader can retell the cheat ("valid proof, wrong theorem") after one read, can name the fix (hash the statement before the loop, reject any candidate that changes it), and knows exactly which file to open to verify the claim. Every fact on the page is traceable to `README.md` or `ASSESSMENT.md`.

## Brand Personality

Dry, technical, confident. The page must read like the README's author built it: short declarative sentences, concrete nouns, zero hype, comfortable stating what does not work yet. The README and ASSESSMENT.md disclose what is unproven (toy example theorems, unbenchmarked real-model solve rates, no public release artifacts yet); the page does the same, on purpose, because disclosure IS the brand.

Three-word personality: **exact, adversarial, unimpressed.**

Emotional goal: the quiet credibility of an examiner's report. The reader should feel they are being shown evidence by someone who assumes they will check it.

## Anti-references

The page must be the opposite of the generic AI project page. Specifically banned:

- **The AI-slop landing kit**: purple-to-blue gradients, centered hero over a dark mesh, glassmorphism, glowing particles, three equal feature cards, Inter + slate-900, gradient text.
- **Terminal cosplay**: the "dark hacker dashboard" reflex for anything developer-shaped. Real code appears on this page because the code is the evidence, not because mono-on-black looks technical.
- **Editorial-typographic costume**: oversized italic serif headline + tracked mono eyebrows above every section + hairline-ruled three-column restraint. Saturated lane; not this voice.
- **Marketing register**: testimonials, logo walls, "trusted by", invented metrics, "blazing fast", "next-generation", any verb like elevate/unleash/supercharge. The project has 342 test functions and 4 documented bug fixes; those numbers are the only flex allowed.
- **Fabrication of any kind**: no stock imagery, no fake screenshots assembled from divs, no invented benchmark claims, no providers the repo does not implement.

## Design Principles

1. **The artifact is the hero.** The most persuasive thing this project owns is the cheat itself: a real theorem, the rewritten candidate, two different hashes, a rejection. Lead with that, rendered as real code, with hashes a reader can recompute from `src/validator.py`.
2. **Receipts over adjectives.** Every claim ships with its evidence: test counts with their failure count, bugs with their before/after, commands the reader can run. If a claim has no receipt, cut the claim.
3. **Disclose the unflattering part.** Toy example theorems, unbenchmarked real-model solve rates, no public release artifacts yet, mock mode proves orchestration not math ability. Stating these plainly is the strongest trust move available to a solo project.
4. **Read like the README's author.** One voice across repo and page. If a sentence would look out of place in the README, rewrite it.
5. **Nothing decorative.** Every visual element either carries information (a verdict, a diff, a pipeline order) or earns deletion. The restraint is the aesthetic.

## Accessibility & Inclusion

Baseline: WCAG 2.1 AA.

- Semantic HTML first: real landmarks, one `h1`, no skipped heading levels, lists are lists, code is `<pre><code>`.
- Color contrast 4.5:1 minimum for body text in both color schemes, verified, not eyeballed. Verdicts never communicated by color alone (always paired with a text label).
- Every interactive element keyboard-reachable with a visible `:focus-visible` state.
- `prefers-color-scheme` respected (light and dark both designed); `prefers-reduced-motion` collapses all animation to static.
- Page is fully readable with JavaScript disabled. There is no JavaScript to disable.
