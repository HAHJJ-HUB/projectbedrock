# Claude Code — Starter Prompt Sequence

A series of prompts to give Claude Code, **in this order**, to build The Casefilers correctly from a fresh repository.

Do not combine prompts. Do not skip ahead. After each session, read what Claude Code produced before moving to the next.

---

## Setup prompt — run once, at the very start of a fresh repo

```
Please read CLAUDE.md in the project root, then read every file in /docs.
Confirm you have understood:

1. The product's name, tagline, and the four filers' names and roles
2. The voice register rules (institutional vs. Oracle's vs. filer working voice)
3. The dossier palette hex values for all four filers
4. The two-materials rule (wood-and-brass / cream paper / operations green)
5. The build order specified in CLAUDE.md

After confirming, do NOT begin coding yet. Reply with a one-paragraph summary
of what you understand the product to be, in your own words, so I can verify
nothing has drifted.
```

This is the most important prompt. If Claude Code's summary is off — if it calls the filers "AI agents," if it describes the product as a "search tool," if it misses the metaphor — stop and correct it before any code is written.

---

## Session 1 — Repo scaffolding

```
Set up a Next.js project with the App Router using TypeScript and Tailwind CSS.

Configure the Tailwind theme to include the full color and typography token set
from docs/05_engineering_handoff.md. The dossier palette (crimson, slate,
forest, gold) should be available as filer-* utility classes. The chrome
palette (wood-deepest, wood-mid, wood-room, brass, brass-muted, bone, etc.)
should be available as utility classes. The document palette (paper, paper-aged,
paper-band, ink) should be available as utility classes.

Set up the three font families (serif, sans, mono) as Tailwind font-family
tokens. Use Inter as the sans substitute, Source Serif Pro as the serif
substitute, and JetBrains Mono as the mono. We'll swap in licensed fonts later.

Do not build any UI yet. Just the scaffolding. When done, show me the
tailwind.config.ts and globals.css so I can verify the tokens are correct.
```

---

## Session 2 — The case file (the deliverable)

```
Build the case file cover surface — the first surface a user sees after the
unit finishes work.

The full specification is in docs/05_engineering_handoff.md, sections 3 and
9 (the case file cover). Use the example content from the brand bible:

- Case number: № 049
- Subject: "Calderon Holdings — pre-2018 ownership structure and known
  subsidiaries in maritime logistics."
- Confidence: High
- Contradictions: 11 on record
- Narrative drift: Substantial
- Written by Oracle, bound at 14:42:31

Build the four-voice attribution panels using all four filer colors. Use
the exact specimen passages from docs/02_oracle_voice_guide.md.

Implementation rules:
- The case file lives on cream paper (var(--paper) = #F0EBDE)
- The top masthead band is warm dark wood with brass accents
- The document title is serif, sentence case
- Oracle's finding is rendered in serif body type
- Margin notes are italic serif inside filled colored panels
- "Signed by Oracle · timestamp" appears in the footer

Build this as a static page at /case-files/049 with hardcoded content.
We will add dynamic data later. Get the typography, color, and spacing
right first.

Show me the result. We will iterate.
```

---

## Session 3 — The briefing room (the entry point)

```
Build the briefing room surface at the route /.

Specification is in docs/05_engineering_handoff.md, section 9 (briefing room).

This is the user's home screen. It should contain:

1. A warm dark masthead with the unit brass mark and user name
2. A left sidebar listing the four filers with personal-colored badges
3. A main panel with the headline "Good afternoon, [name]." in serif
4. The case input field, with the institutional-voice prompt copy
5. A "Cases on the table" registry list of recent cases

Use mock data for the cases list — at least 4 cases, including one
currently in progress (status: "in the room") and three filed cases.

Voice rules:
- The case input field's helper text is institutional voice (italic serif).
  Pull the exact line from the brand bible.
- The "Activate the unit ↗" button must use exactly that text.
- Status labels for cases use the canonical phrases:
  "▸ in the room", "▪ filed"

Do not invent any copy. If something is not specified in the docs,
ask me for the canonical version.
```

---

## Session 4 — The activation transition

```
Build the activation transition at /case-files/new/activating, triggered
when the user clicks "Activate the unit ↗" from the briefing room.

Full beat-by-beat specification is in docs/05_engineering_handoff.md,
section 5 (Activation transition).

The transition is about 5 seconds total. Filers arrive in pipeline order:
Infiltrator (01) → Ghost (02) → Nexus (03) → Oracle (04).

Implementation:
- Use Framer Motion for the animation choreography
- The italic serif "The unit has been convened." line fades in first
- Each filer's card fades in from below with Y-translation, ~700ms apart
- Oracle has a slightly longer "↻ ARRIVING" pause before her ▪ IN ROOM
  status appears
- A 2-second countdown ("Room sealing in 2…") gives the user time to
  watch before the room seals
- After the countdown, route to /case-files/049/operations

The four filer cards each show:
- Their badge in their personal color
- Their name
- Their canonical role line ("finds what search misses", etc.)
- Status: ▪ IN ROOM (or ↻ ARRIVING for Oracle, briefly)

Voice: the institutional voice carries this entire surface. No filer
speaks in first person.
```

---

## Session 5 — The operations room

```
Build the operations room at /case-files/049/operations.

Use the "situation room" specification from docs/05_engineering_handoff.md,
section 4 (State 2). Background is wood-deepest. The interior workspace
contains six green displays:

- 4 filer displays (top row, one per filer)
- 1 log display (large, bottom-left)
- 1 file-so-far metrics display (bottom-right)

Critical rule:
- Each filer's badge HOLDS THEIR PERSONAL COLOR even though everything
  else is operations green. This is non-negotiable. See section 1, rule 3
  in the engineering handoff.

- Active filers (01 Infiltrator, 02 Ghost): top-border bright ops green,
  status "▸ ON THE FLOOR", ASCII progress bar in bright green
- Standby filers (03 Nexus, 04 Oracle): top-border ops-green-deep,
  status "○ AT THE BOARD" / "○ AT HER DESK", opacity 0.7

The log streams in monospace with bracketed timestamps. Use the
specimen entries from the brand bible.

The metrics display shows zero-padded numbers in monospace (0412 not 412)
because they are display readouts, not document figures.

The masthead and footer stay warm dark wood with brass accents.
The italic serif subject quote sits in a band below the masthead.

Do not animate everything — slow breath only. Progress bars inch.
Log streams every 3-5 seconds with a new entry. Cards do not pulse.
```

---

## Session 6 — Marketing landing page

```
Build the marketing landing page at /about (or as a separate marketing site
if we're keeping the product and marketing on different domains — your call,
ask me).

Full copy specification is in docs/04_marketing_onepager.md. Build the page
exactly as specified there. Do not improvise copy. Every line should map
to a line in that document.

Structure:
1. Top nav: THE UNIT / HOW IT WORKS / SAMPLE FILE / METHODS / REQUEST ACCESS
2. Hero: image-first, with the cast image as full-bleed background
   (asset placeholder for now — we'll add the real image later)
3. Tagline overlay on hero: "Reconstruct the record. Build the case."
4. Trust signals band: "By invitation. No public log. Built for the record."
5. CTAs: REQUEST ACCESS ↗ / READ A SAMPLE FILE
6. THE UNIT section: 4-up grid of filer cards with portraits on cream panels
7. HOW IT WORKS: 4 numbered roman-numeral steps (I, II, III, IV)
8. THE UNIT'S PRINCIPLES: DISCREET / VERIFIED / STRATEGIC / RESOLUTE
9. Final CTA: "Open a case. Build the file. Read the finding."
10. Footer with by-invitation note

Image rules:
- The cast image (when available) is full-bleed in the hero
- The four filer portraits live on cream panels inside the warm dark cards
- Black silhouettes on cream — never on warm dark

Do not add any animations on the marketing site beyond a subtle fade-in
on scroll. The brand is restraint.
```

---

## Session 7 onward — open questions

By this point you have a working brand-correct skeleton. Subsequent sessions
should address:

- The exit transition (Operations → Case file handoff)
- Filer profile pages (one template, four instances at /filers/[name])
- The case file sections (Section II: Timeline, Section III: Contradictions,
  Section IV: Narrative Drift, Section V: Source Inventory, Section VI: Exhibits)
- The error and edge states from `docs/05_engineering_handoff.md` section 11
- Mobile layouts (do this after desktop is done — mobile is a port, not a redesign)
- The access-request flow (depends on a pricing/access decision)
- The actual backend that runs the unit's work (out of scope for brand surfaces)

Settings, billing, and account pages come LAST. They must be in the warm-dark
palette and institutional voice. Do not let them fall back to default SaaS
aesthetics.

---

## How to give feedback when something is wrong

If Claude Code produces something that drifts from the brand, the most
effective correction is to point to the specific document and section that
specifies the correct behavior:

✗ "That doesn't feel right."

✓ "The masthead text reads 'AI-powered investigation' — see
   docs/01_brand_bible.md section 10, the word 'AI' is on the never-use list.
   Replace with 'Underground intelligence unit.'"

✓ "The case input prompt says 'What do you want to search for?' — that's
   search-tool voice. See docs/02_oracle_voice_guide.md, the institutional
   voice section. The canonical line is 'Name the subject. The unit takes
   it from there. Be precise or be broad — we'll reconstruct the record
   either way.'"

Reference > improvise. Always.

---

## Files to upload to the repo before starting

Before running the setup prompt, the following must be in the repo:

- `CLAUDE.md` at root (the standing brief)
- `README.md` at root
- All six files in `/docs`:
  - `00_README.md`
  - `01_brand_bible.md`
  - `02_oracle_voice_guide.md`
  - `03_illustrator_brief.md`
  - `04_marketing_onepager.md`
  - `05_engineering_handoff.md`
- The four filer portrait PNGs in `/assets/portraits/`:
  - `infiltrator.png`
  - `ghost.png`
  - `nexus.png`
  - `oracle.png`
- The cast image in `/assets/cast/`:
  - `unit_at_the_table.png`

Without these in place, Claude Code will improvise — and improvisation is
where the brand drifts.

---

*End of starter prompts.*
