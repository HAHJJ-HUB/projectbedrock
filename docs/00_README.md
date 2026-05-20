# The Casefilers — Documentation Package

*Five canonical documents. Version 1.0.*

---

## What this is

This package is the complete canonical documentation for **The Casefilers**, a four-filer underground public-source intelligence unit. It contains five documents, each written to stand alone for the person it's handed to.

Hand the right document to the right person. They will not need the others.

---

## The five documents

### 1. Brand Bible
**`01_brand_bible.md`**

The master document. What the product is, who it's for, the voice register, the design logic. Everything else descends from this. **Read first.**

*Audience: founders, lead designers, anyone joining the project.*

---

### 2. Oracle Voice Guide
**`02_oracle_voice_guide.md`**

The style guide for the unit's writing voice across three registers: Oracle's voice (findings, margin notes), the institutional voice (the unit speaking), and the filer working voice (logs, status). Specimen passages, vocabulary tables, the "voice test."

*Audience: copywriters, prompt engineers, model fine-tuners, anyone whose output appears in the product as text.*

---

### 3. Illustrator Brief
**`03_illustrator_brief.md`**

Specifications for the four filer portraits. Composition rules, the "distinguishable at 24px" test, the hand-paper economy, deliverables, style references.

*Audience: the illustrator commissioned to produce or revise the filer portraits.*

---

### 4. Marketing One-Pager
**`04_marketing_onepager.md`**

The public-facing copy and pitch. Hero, tagline, four filer role lines, "how it works," audience-specific copy, press kit boilerplate, social bios, channel guidance.

*Audience: marketers, growth team, anyone writing copy or pitching the product publicly.*

---

### 5. Engineering Handoff
**`05_engineering_handoff.md`**

The full implementation specification. Color hex values, typography tokens, layout rules, state specifications, transition timings, edge cases, mobile rules.

*Audience: engineers building the product.*

---

## How the documents relate

```
                    ┌──────────────────────┐
                    │   01 Brand Bible     │
                    │   (the source)       │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────────┐    ┌────────────────┐
│ 02 Voice     │    │ 03 Illustrator   │    │ 05 Engineering │
│ Guide        │    │ Brief            │    │ Handoff        │
└──────────────┘    └──────────────────┘    └────────────────┘
        │
        └────────────────► 04 Marketing One-Pager
                           (uses the institutional voice
                            from the voice guide)
```

When documents disagree, the **Brand Bible** is correct. The four supporting documents are detailed specifications; the Brand Bible is the source of truth.

---

## Things that are deliberately *not* in this package

- A pricing strategy (open question, see Brand Bible §17)
- An access-flow specification (depends on pricing decision)
- A sample case file (must be built as a real artifact, not specified in advance)
- A fundraising deck (downstream of brand work, not core to it)
- Technical architecture (a separate engineering decision)

These are deliberately left to be built by the team using this package as a foundation. The package gives you the brand, the voice, the visual language, and the implementation tokens. Everything else is yours to build on top.

---

## A note on revisions

This is Version 1.0. Future revisions should:

1. Update the **Brand Bible** first, then propagate changes to the supporting documents.
2. Never let a supporting document drift from the Brand Bible without resolving the conflict at the source.
3. Maintain a changelog at the end of each document for major revisions.

---

*The unit is in Room 7. The file is on the table. Get to work.*
