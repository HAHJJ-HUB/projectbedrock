# The Casefilers — Engineering Handoff

*Design tokens, layout rules, state specifications. Version 1.0.*

---

## What this document is

The full implementation specification for the Casefilers product. Hex values, typography tokens, layout rules, state machines, transition timings, and edge-case handling. Hand this to any engineer building any surface of the product.

This document is descriptive of decisions made in design, not prescriptive about implementation. Use whatever framework, whatever rendering pipeline, whatever color system you like — but the *values* in this document are the truth.

---

## 1. Color tokens

### The dossier palette — filer colors

These are the four canonical filer colors. Each filer has *one* hex value that is theirs. There are no light/dark variants — the filer color is the filer color.

```
--filer-infiltrator:  #9C3B3A   (crimson)
--filer-ghost:        #5B7A8C   (slate)
--filer-nexus:        #4A5D3C   (forest)
--filer-oracle:       #B8902A   (gold)
```

**Text-on-filer-color:**

| Filer | Background hex | Text color |
|---|---|---|
| Infiltrator | `#9C3B3A` | `#F0EBDE` (cream) |
| Ghost | `#5B7A8C` | `#F0EBDE` (cream) |
| Nexus | `#4A5D3C` | `#F0EBDE` (cream) |
| Oracle | `#B8902A` | `#1A1814` (dark wood) |

Oracle's gold is light enough that cream-on-gold doesn't read. Her panels use dark text. All other filers use cream text.

**Filer tint colors** — lighter versions for non-block accents (subtitles, italic role lines, hover states):

```
--filer-infiltrator-tint:  #C97A78
--filer-ghost-tint:        #8AA8BB
--filer-nexus-tint:        #8AA17A
--filer-oracle-tint:       #D4AB50
```

### The chrome palette — the room

```
--wood-deepest:    #0E0C0A    (operations room background, page bg)
--wood-mid:        #14120F    (card background within rooms)
--wood-room:       #1A1814    (briefing room main background)
--brass:           #B8A87A    (masthead, accents, primary brand mark)
--brass-muted:     #8A8270    (secondary chrome text)
--brass-faded:     #6E6859    (tertiary chrome text)
--brass-deepest:   #4A4538    (footer text, dividers)
--bone:            #E8E2D0    (text on dark, primary)
--bone-body:       #D6D2C4    (text on dark, body)
--border-dark:     #2A2620    (hairline borders)
```

### The document palette — paper

```
--paper:           #F0EBDE    (case file background)
--paper-aged:      #FAF5E8    (exhibit backgrounds, pull-outs)
--paper-band:      #E8DFC5    (warm shadow / highlight bands)
--paper-border:    #C9BF9F    (document borders, hairlines)
--ink:             #1A1814    (body text on paper)
--ink-secondary:   #2A2620    (secondary text on paper)
--ink-faded:       #5E5849    (tertiary text, italic subtitles on paper)
```

### The mode color — operations

```
--ops-green:       #4ADE80    (active display color)
--ops-green-body:  #86EFAC    (body text in displays)
--ops-green-mid:   #16A34A    (dimmed / inactive)
--ops-green-deep:  #1D4D36    (display borders)
--ops-panel:       #061A12    (display panel background)
--ops-room:        #0A0A08    (operations room background)
```

### Semantic colors

```
--amber:           #D4A040    (attention / live status / contradiction count)
--contradiction:   #8A4A2A    (rust accent for contradiction case-file markers)
```

### Color rules

1. **The filer hex values are constant.** They appear on the badge, the top-border of cards, the margin-note panel backgrounds in the case file, and as accent borders elsewhere. The badge is the canonical use case.

2. **The badge always holds the filer color.** Even during operations mode. Even when every other treatment has flipped to green. The badge is the filer's nameplate.

3. **Operations green overrides personal color treatments only during a sealed-room state.** When `state === 'sealed'`, the four filer cards' top-borders, status text, progress bars, and body text flip to operations green. The badge background does not change.

4. **Brass, cream, and wood are constant.** They never flip during state changes. They are the unit's chrome, not its mode.

5. **Amber is cross-modal.** It appears in both operations mode (contradiction in the log) and document mode (contradiction count in the case file front matter). It is the only color that crosses both modes.

---

## 2. Typography tokens

### Type families

```
--font-serif: 'Tiempos Text', Georgia, serif;
   (or substitute: GT Sectra, Source Serif Pro)

--font-sans: 'Inter', system-ui, sans-serif;
   (or substitute: GT America, Söhne)

--font-mono: 'JetBrains Mono', 'IBM Plex Mono', monospace;
   (or substitute: Berkeley Mono, GT Pressura Mono)
```

### Type rules by surface

| Surface | Family | Weight | Size | Notes |
|---|---|---|---|---|
| Document title (case file) | Serif | 500 | 30–36px | Sentence case |
| Document subtitle | Serif italic | 400 | 14–17px | Institutional voice |
| Finding body | Serif | 400 | 17–19px | Line-height 1.65 |
| Margin note body | Serif italic | 400 | 13–15px | Inside colored block |
| Briefing room headline | Serif | 500 | 22–24px | "Good afternoon, [name]." |
| Filer name (in product) | Sans | 500 | 12–14px | |
| Filer role line | Serif italic | 400 | 10–13px | In filer's tint color |
| Status labels | Sans | 500 | 9–11px | ALL CAPS, letter-spacing 0.2em |
| Section eyebrow labels | Sans | 500 | 10–11px | ALL CAPS, letter-spacing 0.25em |
| Operations log | Mono | 400 | 11px | Line-height 2 |
| Display readout numbers (ops) | Mono | 500 | 20–22px | Zero-padded: `0412` not `412` |
| Document metric numbers | Serif | 500 | 26–28px | Natural form: `412` |
| Body text (chrome UI) | Sans | 400 | 13–14px | Line-height 1.6 |
| Eyebrow caption above heroes | Sans | 500 | 10px | ALL CAPS, letter-spacing 0.35em |

### Typography rules

- **Sentence case always.** Never Title Case. Never ALL CAPS for headlines or body text.
- **ALL CAPS** is reserved for labels and status indicators only. Always with letter-spacing of at least 0.2em.
- **Italic serif** is the institutional voice and Oracle's voice. Use sparingly. Never for UI labels.
- **Weight 500** is the heaviest used in the product. Never 600, 700, or bold. Heavier weights read as alarmist.
- **Operations room numbers are zero-padded monospace.** They are *display readouts*. Padding to four digits (0412, 0068, 0011) gives them the appearance of always-fixed-width instrumentation.
- **Document numbers are natural-form serif.** They are *figures in a document*. No padding.

---

## 3. Layout tokens

```
--radius-md: 8px;
--radius-lg: 12px;

--hairline-border: 0.5px solid;
--accent-border: 2px solid;

--gap-tight: 6px;
--gap-default: 12px;
--gap-section: 24px;
--gap-block: 36px;

--page-padding-desktop: 56px;
--page-padding-mobile: 18px;
```

### Layout rules

- **Hairlines, not thick borders.** All dividers and card borders are `0.5px solid` in the appropriate `border` token. The only exceptions are 2px accent borders on the *top* of filer cards (in the filer's color) and the 2px left-border on margin-note panels.
- **No rounded corners on single-sided borders.** If using `border-left` or `border-top` accents, `border-radius: 0`. Rounded corners only work with full borders on all sides.
- **Shadows are minimal.** A focus ring (`box-shadow: 0 0 0 2px`) is the only shadow used. No drop-shadows, no glow effects, no decorative depth.
- **Mobile column cap: 2 columns.** Never lay out more than two columns of cards on mobile (380px width). For 4-up filer grids, stack as 2×2 on mobile.

---

## 4. The three primary states

The product is a state machine with three primary states.

### State 1 — Briefing room (idle)

```
state: 'briefing'
background: --wood-room
chrome: brass masthead, brass accents
filer treatment: personal colors on badges and top-borders
voice: institutional + filer working voice
input: case input field visible, "Activate the unit" button enabled
```

User flow: review filed cases, open registry, configure unit, or activate a new case.

### State 2 — Operations room (sealed)

```
state: 'sealed'
background: --ops-room (deeper than briefing room)
chrome: brass masthead, brass accents preserved
filer treatment: badges hold personal colors; all other treatments flip to ops-green
voice: filer working voice (monospace log), institutional voice in subject quote
input: paused / locked; "Leave the room" available
```

Entered via the **Activation Transition** (see Section 5). Exited via the **Exit Transition** when filers complete work.

User flow: watch the unit work, or leave the room and return later.

### State 3 — Case file (delivered)

```
state: 'filed'
background: --paper
chrome: dark masthead band at top (the unit's letterhead), paper everywhere else
filer treatment: personal colors as full-color panel backgrounds for attributed sections
voice: Oracle's voice (finding, margin notes) + filer working voice (log entries)
input: read, navigate sections, export, cite
```

Entered when the exit transition completes. Persistent — the case file is the artifact that remains.

---

## 5. Transitions — timings and choreography

Two transitions matter. Both are theatrical on purpose and cannot be replaced with loading spinners.

### Activation transition (Briefing → Operations)

**Duration:** ~5 seconds total.

**Beats:**

| Time | What happens |
|---|---|
| 0.0s | "Activate the unit" button confirms. Briefing room dims slightly. |
| 0.0–0.5s | Single line appears: *"The unit has been convened."* (italic serif, fade in) |
| 0.5–1.2s | Case is assigned a number (`№ 049`). Subject quote is formally restated in italic serif: *"RECORDED INTO THE FILE BY [USER] · [TIMESTAMP]"* |
| 1.2–2.0s | Filer 01 (Infiltrator) card fades in from below with slight Y-translation. Badge cell lights up brass. Status: ▪ IN ROOM. |
| 2.0–2.7s | Filer 02 (Ghost) arrives. Same animation. Status: ▪ IN ROOM. Carries a folder (small narrative detail in the log). |
| 2.7–3.4s | Filer 03 (Nexus) arrives. Same animation. Status: ▪ IN ROOM. |
| 3.4–4.1s | Filer 04 (Oracle) arrives last — slightly longer pause before her card appears. Status: ↻ ARRIVING for an extra beat, then ▪ IN ROOM. |
| 4.1–5.0s | "Room sealing in 2…" countdown bottom-left. "WORK BEGINS ↗" button at right. User can click to skip the countdown. |
| 5.0s | State transitions to `sealed`. Operations room loads. |

**Filers arrive in pipeline order: Infiltrator → Ghost → Nexus → Oracle.** This is non-negotiable. Oracle arrives last because she writes the finding last.

### Exit transition (Operations → Case file)

**Duration:** 60–90 seconds (real work being done by Oracle, not just a loading screen).

**Beats:**

| Time | What happens |
|---|---|
| 0.0s | All field work complete. Operations log shows: *"unit handed everything to Oracle."* |
| 0.0–2.0s | Filers 01, 02, 03 fade to 40% opacity. Each shows a final contribution count (e.g., "347 items", "65 recovered", "68 entities · 11 contradictions"). |
| 2.0–4.0s | Oracle's card amplifies. Badge stays gold. Status: ▸ WRITING THE FINDING. |
| 4.0s–end | Oracle's working log streams at slower pace than ops log: "Reading the field log…" "Establishing chronology…" "Weighing the contradictions…" "Drafting the finding." |
| 4.0s–end | Progress bar at bottom labelled "BINDING THE CASE", crawls to completion with a bright leading edge. |
| Throughout | Italic line at bottom: *"Stay or step away — the file will be on the table when it's bound."* |
| Complete | State transitions to `filed`. Case file loads. User receives a notification if they have stepped away. |

---

## 6. The badge — the most-used component

The filer badge appears in dozens of places across the product. Specifying it precisely.

```html
<div class="badge" data-filer="oracle">04</div>
```

**Visual specification:**

- 28×28px in the briefing room sidebar
- 32×32px on filer cards
- 22×22px inside case-file attribution headers (with inverted treatment — see below)
- 24×24px in mobile sidebar

**Default treatment:**
- Background: filer's hex value (e.g., `#B8902A` for Oracle)
- Text: cream (`#F0EBDE`) for Infiltrator, Ghost, Nexus; dark wood (`#1A1814`) for Oracle
- Font: sans-serif, 500 weight, 10px, letter-spacing 0.1em
- Border: none (the fill is the identity)
- Corner radius: 0 (square, not rounded — this is a nameplate, not a button)

**Inverted treatment** (used inside case-file attribution headers where the filer's color is already the panel background):
- Background: dark wood (`#1A1814`)
- Text: filer's color (e.g., `#B8902A` for Oracle on a gold panel)
- Same font specs

**State during operations mode:**
- Badge fill stays the filer's color.
- Card top-border may flip to ops-green (for active filers) or ops-green-deep (for inactive).
- Status indicator (the small dot in the top-right corner of the badge during operations) is ops-green when working, dimmed when not.

---

## 7. The filer card — operations mode specification

The four filer cards on the operations display follow this structure:

```
┌────────────────────────────────────────┐
│ [badge: filer color]  FILER NAME (mono) │ ← top row: badge + name
│                                          │
│ ▸ on the floor                          │ ← status (ops-green-body)
│ activity description (mono, mid green) │ ← what they're doing
│                                          │
│ [██████████░░░░░] 72%                   │ ← ASCII progress bar
└────────────────────────────────────────┘
```

**Active filer card:**
- Background: `--ops-panel` (#061A12)
- Border: 0.5px solid `--ops-green-deep`
- Top border: 2px solid `--ops-green`
- Name: `--ops-green`, mono, 500 weight, 12px
- Activity: `--ops-green-body`, mono, 11px
- Progress bar: `--ops-green` filled, `--ops-green-deep` unfilled, ASCII blocks (█)

**Inactive (standby) filer card:**
- Same background and base styling
- Top border: 2px solid `--ops-green-deep` (no bright accent)
- Name color: `--ops-green-body`
- Activity: `--ops-green-mid`
- Opacity: 0.7 on the whole card
- Progress bar: minimal fill, `--ops-green-deep` empty

**Status text formats** (the canonical statuses):
- `▸ on the floor` (active — Infiltrator, Ghost during field work)
- `○ at the board` (standby — Nexus during field work)
- `○ at her desk` (standby — Oracle during field work)
- `▸ writing the finding` (active — Oracle during exit transition)

Note the typography: `▸` (active triangle, filled) and `○` (standby circle, hollow).

---

## 8. The case file — attribution panels

When a filer's voice appears in the case file as an attributed block, it uses this structure:

```html
<div class="filer-panel" data-filer="oracle">
  <header>
    <div class="badge inverted">04</div>
    <div class="label">ORACLE · MARGIN NOTE</div>
  </header>
  <p class="quote">The address discrepancy is the central anomaly…</p>
</div>
```

**Panel specification:**
- Background: filer's hex value (the full color, not a tint)
- Padding: 14px 18px
- Margin-bottom: 8px (panels stack tightly)
- No border, no border-radius (panels are document-flat)

**Inner badge:** Inverted treatment — dark background, filer-colored text.

**Label:** ALL CAPS, sans-serif 500, 10px, letter-spacing 0.25em.
- On Oracle's gold panel: text is dark wood (`#1A1814`)
- On other filers' panels: text is cream (`#F0EBDE`)

**Quote (body text):** Italic serif, 13px, line-height 1.6.
- On Oracle's gold panel: text is dark wood (`#1A1814`)
- On other filers' panels: text is cream (`#F0EBDE`)

**The four canonical attribution headers** (do not invent new ones):
- `ORACLE · MARGIN NOTE` (gold panel)
- `NEXUS · ON THE BOARD` (forest panel)
- `GHOST · ON THE RECOVERY` (slate panel)
- `INFILTRATOR · IN THE FIELD` (crimson panel)

---

## 9. Standard surfaces — component composition

A short reference for what major surfaces are composed of.

### Briefing room

- Top: warm dark masthead (brass logo, room metadata, user name)
- Left sidebar: filer roster (four badges + role lines), registry sections, admitted-user info
- Main: "Good afternoon, [name]." headline + case input field + "Cases on the table" registry list
- Bottom: brass-line metadata footer

### Operations room (situation room mode)

- Top: warm dark masthead band — case number, sealed indicator, elapsed time
- Below masthead: subject quote band (italic serif, full width)
- Main: 2×3 grid of green display panels (4 filer panels, 1 log panel, 1 metrics panel)
- Bottom: warm dark footer — room metadata, "leave the room" affordance

### Case file cover

- Top: dark masthead band (brass logo, case status, "back to room")
- Document header: case number, document title (serif), italic subtitle, opening metadata
- Left rail: confidence, contradictions, narrative drift, "the file contains" — all as document properties
- Main: the finding (3 paragraphs), Oracle's margin note, sections list (TOC), four-voice multi-author appendix
- Bottom: "signed by Oracle · timestamp", export/open actions

### Filer profile (e.g., Oracle)

- Top: dark masthead band, roster nav (← Infiltrator, Ghost, Nexus, **ORACLE**)
- Left: 4:5 portrait panel (cream background, illustration) + base facts
- Right: "Filer № 04", name, role line, two-paragraph description
- Two-column: "What she does" / "What she does not do" (the most important component on the profile)
- Mid: representative passage in italic serif (Oracle's voice, from a real case)
- Bottom: list of recent files signed by this filer

---

## 10. Mobile rules

The mobile width is ~380px. Three rules:

1. **Never 3 or 4 columns.** Filer roster collapses to 2×2 grid on mobile.
2. **Sidebars become top bands.** Two-column desktop layouts stack vertically on mobile.
3. **Operations log truncates.** Show 3 most recent log entries on mobile (vs. 7 on desktop). Tap-to-expand.

Typography scales: all 17–19px body text drops to 14–15px on mobile. Headlines drop 20–25%.

---

## 11. Edge cases — what the unit cannot do

Real products have edge cases. The unit handles them in its voice.

### Subject too narrow

```
state: 'rejected_narrow'
voice: institutional
message: "The unit cannot proceed. The subject as named has too little
          public record to convene on. Try widening — a person, an entity,
          a period — and the unit will look again."
```

### Subject too broad

```
state: 'rejected_broad'
voice: institutional
message: "The subject is wider than the unit can hold in a single case.
          Narrow to a person, an entity, a transaction, or a span of years,
          and the unit will convene."
```

### Subject is a real-time event (not yet historical)

```
state: 'rejected_live'
voice: institutional
message: "The unit reconstructs the record. This subject is still moving.
          Open the case again when the record has settled."
```

### Subject is a private person without significant public record

```
state: 'rejected_private'
voice: institutional
message: "The Casefilers operates only on public source material.
          The subject as named does not have sufficient public record
          for the unit to convene on. This is a feature, not a limitation."
```

### Subject is sensitive (legal exposure, threat against the user, etc.)

```
state: 'rejected_sensitive'
voice: institutional
message: "The unit cannot take this case. Please contact [contact] directly."
```

### Operational failures

The unit does not say "something went wrong" or "an error occurred." If the work cannot proceed:

```
state: 'unit_blocked'
voice: institutional
message: "The unit has paused on this case. [Filer name] cannot reach
          [source]. The work will resume when the path is open again,
          or you can leave the room and the unit will contact you
          when it can proceed."
```

---

## 12. Tracking and analytics — what to measure

The product should be measured by:

- **Cases opened per user per week** — usage depth
- **Case completion rate** — does the unit deliver?
- **Time-to-bind** (median) — pipeline efficiency
- **Sample file completion rate** (marketing) — does the deliverable convert?
- **"Leave the room" rate during operations** — do users hover or step away?
- **Margin note read time** in case file — does Oracle's voice land?
- **Cited contradictions / total contradictions** — is the unit's "material vs. non-material" ranking trustworthy?

Avoid measuring:
- "Engagement" in any consumer-product sense (the user is not here to engage; they're here to read the finding)
- DAU/MAU as a primary metric (a serious user opens 2–3 cases a week, not 20)
- Bounce rate on the marketing site (low bounce = low qualification; we want the wrong users to bounce)

---

## 13. Implementation priorities

If this product is being built from scratch, the implementation priorities, in order:

1. **The case file** — this is the deliverable. Build it first, get Oracle's voice right, make it readable and shareable. Everything else exists to produce this.

2. **The briefing room** — the entry point. Get the warm-dark world established and the case input flow right.

3. **The activation transition** — the moment the metaphor lands hardest. Worth disproportionate care.

4. **The operations room** — the long middle. Worth less polish than the transition that enters it.

5. **The exit transition + filer profiles + marketing site** — extensions of the established world.

The unglamorous screens (settings, billing, account, password recovery) must be in the warm-dark palette and the institutional voice. They break worlds if they fall back to default SaaS. Build them last but build them properly.

---

*End of engineering handoff.*
