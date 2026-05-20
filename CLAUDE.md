# The Casefilers — Project Instructions for Claude Code

You are building **The Casefilers**, a four-filer underground public-source intelligence unit. This is a software product, but it is **never framed as software** — it is framed as a working intelligence unit.

This file is your standing brief. Read it every session before starting work.

---

## Canonical reference documents

Before making any decisions about copy, color, layout, or naming, consult the appropriate document in `/docs`:

| Document | When to read it |
|---|---|
| `docs/01_brand_bible.md` | Always — at the start of any session |
| `docs/02_oracle_voice_guide.md` | Before writing any user-facing copy |
| `docs/03_illustrator_brief.md` | Before placing or modifying filer portraits |
| `docs/04_marketing_onepager.md` | Before working on marketing or landing pages |
| `docs/05_engineering_handoff.md` | Always — for tokens, layout, state specs |

**When these documents disagree, the brand bible wins.** When in doubt, ask the user before improvising.

---

## Non-negotiable rules

These rules are absolute. Violating any of them is a bug, regardless of whether tests pass.

### 1. The unit is never called AI

No mention of "AI," "agent," "model," "LLM," "machine learning," "generated," "powered by," "prompt," or any other implementation language anywhere in user-facing copy, code comments visible in production, or HTML metadata.

The four filers are **filers**, not agents.

### 2. Voice register is locked

There are three voices used in deliberately different contexts:

- **Institutional voice** (italic serif): the unit speaking — transitions, prompts, errors
- **Oracle's voice** (serif body): findings, margin notes, section introductions in case files
- **Filer working voice** (sans-serif or monospace, third person past tense): logs, status, operational text

See `docs/02_oracle_voice_guide.md` for full specification. Do not invent new voices or registers.

### 3. The color system is locked

The dossier palette (filer colors) is canonical:

```
--filer-infiltrator:  #9C3B3A   (crimson)
--filer-ghost:        #5B7A8C   (slate)
--filer-nexus:        #4A5D3C   (forest)
--filer-oracle:       #B8902A   (gold)
```

The full token set is in `docs/05_engineering_handoff.md`. Do not invent new colors or substitute "close enough" values.

### 4. Vocabulary is locked

| Use | Don't use |
|---|---|
| Open a case | Start a search |
| Activate the unit / Convene the unit | Run a query |
| The room is sealed | Loading |
| Items filed | Sources |
| Contradictions on record | Flagged / detected |
| The finding | The report / summary |
| Bind the file | Compile / generate |
| Leave the room | Back / close |
| The unit | Agents / AI / system |

If you find yourself wanting to write "Welcome!" or "Sorry, something went wrong" or "Powered by AI," stop. That is the wrong voice.

### 5. The four filers are never given first names

They are Infiltrator, Ghost, Nexus, Oracle. They have no biographies, no ages, no personalities in the consumer sense. They have roles and voices.

### 6. Filers do not speak in first person

Never write `"I'll find what search misses," — Infiltrator`. The filers are referred to in third person, by name and what they did.

### 7. The badge always holds the filer color

Even during operations mode when everything else flips to operations green, the filer badge (the small filled square with the two-digit number) holds the filer's personal color. This rule is non-negotiable.

### 8. Two materials, never blended

The product lives in distinct visual materials:

- **Warm dark wood and brass** = the room (briefing room, operations room, chrome)
- **Cream paper** = the document (case files, exhibits, findings)
- **Operations green** = the displays (only during sealed-room state)

A piece of UI is one of these materials. It is never a blend. Cream paper never appears in the operations room. Operations green never appears in the case file.

### 9. The unit is selective

The product is "by invitation." It does not optimize for breadth. If a design choice serves general consumers but works against investigative journalists, intelligence analysts, or serious researchers, the serious users win.

### 10. Restraint is the brand

The competition is loud. The Casefilers wins by being *quieter and more confident* than every product in its category. No gradients, no glow effects, no animated illustrations on the marketing site, no chatbot popups, no "trusted by [logos]" walls, no cookie banners larger than the hero. If you're about to add something decorative, ask whether it earns its place.

---

## Tech stack (recommended, not required)

Unless the user specifies otherwise:

- **Framework:** Next.js (App Router) or SvelteKit
- **Styling:** Tailwind CSS with the design tokens from `docs/05_engineering_handoff.md` configured as theme extensions
- **Typography:** `Tiempos Text` (serif), `Inter` (sans), `JetBrains Mono` (mono) — or substitutes specified in the engineering handoff
- **Database:** PostgreSQL with row-level security
- **Hosting:** Vercel or Cloudflare Pages
- **Forms:** Server actions or API routes; no third-party form services that would add their own branding

Do not introduce a UI library (Chakra, MUI, Radix primitives) without checking with the user first. The chrome must be custom; the unit has its own visual language and prebuilt component libraries fight it.

---

## Build order

Build in this order. Do not skip ahead.

1. **The case file** (the deliverable — get this right first, everything else exists to produce it)
2. **The briefing room** (the entry point)
3. **The activation transition** (the moment the metaphor lands hardest)
4. **The operations room** (the long middle)
5. **The exit transition**
6. **Filer profile pages** (one template, four instances)
7. **Marketing landing page**
8. **Settings, account, billing** (must be in the warm-dark palette and institutional voice — do not let these fall back to default SaaS aesthetics)

---

## Working principles

**Ask before improvising.** If a copy line isn't in the voice guide, ask the user for the canonical version. Don't write "Loading…" because the voice guide doesn't have a loading state.

**Reference documents in commit messages.** When implementing a surface, reference the section of the engineering handoff or brand bible that specifies it. This creates an audit trail and surfaces drift.

**Build the smallest viable surface first.** A static case file with hardcoded content is more useful than a dynamic case file with placeholder copy. Get the typography and color right on a real example, then add interactivity.

**The transitions are theatrical on purpose.** When implementing the activation or exit transitions, follow the beat timings in the engineering handoff. They are not loading spinners. They are the moment the metaphor lands.

**Mobile is a port, not a redesign.** Mobile layouts collapse to 2 columns max but keep the same typography and chrome. Do not introduce mobile-specific design language.

---

## Things to flag to the user

Flag these as questions, not as decisions to make alone:

- Pricing model and billing flow (no decision yet)
- "By invitation" access flow specifics (no decision yet)
- Real backend for the unit's work (out of scope for early surfaces — mock data is fine until the brand surfaces are locked)
- Third-party integrations (none assumed; ask before adding any)
- Analytics and tracking (must be GDPR-compliant and never branded as "user engagement tracking" — the unit does not surveil)

---

## A final note

This is a brand-led product. The visual world, the voice, and the cultural register are not decoration on top of the engineering — they are the product. If the engineering is correct but the brand drifts, the product fails. If the brand holds but the engineering has rough edges, the product still works.

When in doubt: read the brand bible. When still in doubt: ask the user.

Get to work.
