"""
Narrative analysis tools: framing shift, language drift, contradiction detection,
certainty inflation, and narrative compression.

Operates on content already stored in persistent memory by Ghost.
All analysis is pure-Python — no external ML dependencies required.
"""

import json
import re
from collections import Counter, defaultdict
from typing import Optional

from crewai.tools import BaseTool

from memory.persistent_memory import retrieve_findings

# ---------------------------------------------------------------------------
# Epistemic hedge lexicon — words that signal uncertainty about a claim.
# Grouped by how much certainty they convey (low → high).
# ---------------------------------------------------------------------------
_HEDGE_TIERS: dict[str, list[str]] = {
    "speculation": [
        "allegedly", "reportedly", "rumored", "unconfirmed", "purportedly",
        "supposedly", "accused of", "alleged", "claimed", "asserted",
        "according to claims", "some say", "it is said",
    ],
    "possibility": [
        " may ", " might ", " could ", "possibly", "perhaps", "conceivably",
        "appears to", "seems to", "seems like", "it is possible", "it may be",
    ],
    "probability": [
        "likely", "probably", "presumably", "apparently", "according to",
        "sources say", "sources close to", "believed to", "expected to",
        "is thought to", "is understood to",
    ],
    # "assertion" = absence of hedges — not a word list, used as a label
}

_ALL_HEDGES: list[str] = [h for tier in _HEDGE_TIERS.values() for h in tier]

# Intensifiers that push claims toward certainty without adding evidence
_CERTAINTY_INFLATORS: list[str] = [
    "definitively", "conclusively", "undeniably", "unquestionably",
    "it is clear that", "it is obvious that", "it is well known",
    "everyone knows", "of course", "naturally", "inevitably",
    "it is a fact", "confirmed", "proven", "established",
]

# Tokens used to extract named entities (crude but dependency-free)
_ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
_NUMBER_CONTEXT = re.compile(
    r"([A-Za-z ]{0,30})\b(\d[\d,\.]*(?:\s*(?:million|billion|thousand|percent|%))?)\b([A-Za-z ,]{0,30})"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_corpus(topic: str, n: int = 60) -> list[dict]:
    """Pull findings from memory, group by source URL, sort by timestamp."""
    raw = retrieve_findings(topic, topic=topic, n_results=n)
    # Merge chunks from the same URL into one document
    by_url: dict[str, dict] = {}
    for f in raw:
        url = f.get("source_url", "unknown")
        if url not in by_url:
            by_url[url] = {"content": "", "timestamp": f.get("timestamp", ""), "url": url}
        by_url[url]["content"] += " " + f.get("content", "")
    docs = list(by_url.values())
    docs.sort(key=lambda d: d.get("timestamp", ""))
    return docs


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def _hedge_score(text: str) -> dict:
    """Count hedge markers per tier in a text block."""
    lower = text.lower()
    scores: dict[str, int] = {tier: 0 for tier in _HEDGE_TIERS}
    scores["inflators"] = 0
    for tier, words in _HEDGE_TIERS.items():
        for w in words:
            scores[tier] += lower.count(w)
    for w in _CERTAINTY_INFLATORS:
        scores["inflators"] += lower.count(w)
    total_sentences = max(len(_sentences(text)), 1)
    scores["hedge_density"] = round(
        sum(scores[t] for t in _HEDGE_TIERS) / total_sentences, 3
    )
    return scores


def _top_terms(text: str, n: int = 20) -> list[tuple[str, int]]:
    """Most frequent non-trivial tokens."""
    stop = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "this", "that", "these",
        "those", "it", "its", "not", "no", "also", "said", "says", "which",
        "who", "he", "she", "they", "we", "you", "i", "his", "her", "their",
        "our", "your", "my", "one", "two", "about", "after", "before",
        "more", "other", "than", "up", "out", "if", "then", "when", "there",
        "all", "any", "can", "into", "over", "such", "been", "just",
    }
    tokens = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return Counter(t for t in tokens if t not in stop).most_common(n)


def _extract_entities(text: str) -> set[str]:
    return {m.group(1) for m in _ENTITY_PATTERN.finditer(text) if len(m.group(1)) > 3}


def _extract_number_claims(text: str) -> list[tuple[str, str, str]]:
    """Return (left_context, number, right_context) tuples."""
    return [(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
            for m in _NUMBER_CONTEXT.finditer(text)]


def _split_thirds(docs: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    n = len(docs)
    if n < 3:
        return docs, [], docs
    t = n // 3
    return docs[:t], docs[t: 2 * t], docs[2 * t:]


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

class NarrativeAnalysisTool(BaseTool):
    name: str = "narrative_analysis"
    description: str = (
        "Run five narrative analysis passes on all stored research findings for a topic:\n"
        "1. CERTAINTY INFLATION — tracks how hedge language changes across the coverage timeline. "
        "Detects when speculative claims harden into stated facts without new evidence.\n"
        "2. FRAMING SHIFT — compares the most distinctive terms used in early vs late coverage "
        "to surface vocabulary changes that signal a reframing of the story.\n"
        "3. CONTRADICTION DETECTION — extracts numerical claims and flags sources that report "
        "different values for the same apparent fact.\n"
        "4. LANGUAGE DRIFT — identifies terms that appear in early coverage and disappear later, "
        "and new terms that enter late coverage but weren't used at the start.\n"
        "5. NARRATIVE COMPRESSION — finds named entities prominent in early sources that drop "
        "out of later coverage, indicating which parts of the story were quietly dropped.\n\n"
        "Input: JSON with 'topic' (str) and optional 'n_sources' (int, default 60). "
        "Returns a structured Markdown report section for each analysis."
    )

    def _run(self, query: str) -> str:
        try:
            params = json.loads(query) if query.strip().startswith("{") else {"topic": query}
            topic = params.get("topic", query)
            n = int(params.get("n_sources", 60))
        except (json.JSONDecodeError, ValueError):
            topic, n = query, 60

        docs = _load_corpus(topic, n)
        if not docs:
            return f"No stored findings for topic '{topic}'. Run Ghost extraction first."

        total = len(docs)
        early, mid, late = _split_thirds(docs)

        report_sections = [
            f"# Narrative Analysis: {topic}",
            f"*Corpus: {total} sources | Early: {len(early)} | Mid: {len(mid)} | Late: {len(late)}*\n",
        ]

        report_sections.append(self._certainty_inflation(docs, early, late))
        report_sections.append(self._framing_shift(early, late))
        report_sections.append(self._contradiction_detection(docs))
        report_sections.append(self._language_drift(early, late))
        report_sections.append(self._narrative_compression(early, late))

        return "\n\n---\n\n".join(report_sections)

    # ── Analysis 1: Certainty Inflation ─────────────────────────────────────

    def _certainty_inflation(
        self, docs: list[dict], early: list[dict], late: list[dict]
    ) -> str:
        lines = ["## 1. Certainty Inflation"]

        if len(docs) < 2:
            return "\n".join(lines) + "\nInsufficient sources for timeline analysis."

        # Score each document
        scored = []
        for doc in docs:
            s = _hedge_score(doc["content"])
            scored.append({
                "url": doc["url"],
                "ts": doc.get("timestamp", "")[:10],
                "hedge_density": s["hedge_density"],
                "speculation": s["speculation"],
                "possibility": s["possibility"],
                "probability": s["probability"],
                "inflators": s["inflators"],
            })

        early_density = (
            sum(s["hedge_density"] for s in scored[: len(early)]) / max(len(early), 1)
        )
        late_density = (
            sum(s["hedge_density"] for s in scored[-len(late) :]) / max(len(late), 1)
        )
        delta = round(early_density - late_density, 3)
        direction = "DECREASING" if delta > 0.01 else "INCREASING" if delta < -0.01 else "STABLE"

        lines += [
            f"**Hedge density trend: {direction}**",
            f"- Early coverage avg hedge density: `{early_density:.3f}` hedges/sentence",
            f"- Late coverage avg hedge density:  `{late_density:.3f}` hedges/sentence",
            f"- Delta: `{delta:+.3f}` ({'certainty increased' if delta > 0 else 'uncertainty increased' if delta < 0 else 'no change'})",
            "",
        ]

        # Find the single sharpest certainty jump
        if len(scored) > 2:
            max_jump = max(
                range(1, len(scored)),
                key=lambda i: scored[i - 1]["hedge_density"] - scored[i]["hedge_density"],
            )
            lines.append(
                f"**Sharpest certainty jump**: between source {max_jump} ({scored[max_jump-1]['ts']}) "
                f"and source {max_jump+1} ({scored[max_jump]['ts']}) — "
                f"hedge density dropped from `{scored[max_jump-1]['hedge_density']:.3f}` "
                f"to `{scored[max_jump]['hedge_density']:.3f}`"
            )
            lines.append(
                f"  - Before: `{scored[max_jump-1]['url']}`\n"
                f"  - After:  `{scored[max_jump]['url']}`"
            )

        # Inflator usage
        inflator_heavy = [s for s in scored if s["inflators"] > 0]
        if inflator_heavy:
            lines.append(
                f"\n**Certainty inflators** found in {len(inflator_heavy)} source(s) "
                f"(words like 'confirmed', 'it is clear that', 'everyone knows'):"
            )
            for s in inflator_heavy[:5]:
                lines.append(f"  - `{s['url']}` ({s['ts']}) — {s['inflators']} inflator(s)")

        return "\n".join(lines)

    # ── Analysis 2: Framing Shift ────────────────────────────────────────────

    def _framing_shift(self, early: list[dict], late: list[dict]) -> str:
        lines = ["## 2. Framing Shift"]

        if not early or not late:
            return "\n".join(lines) + "\nInsufficient sources for early/late comparison."

        early_text = " ".join(d["content"] for d in early)
        late_text = " ".join(d["content"] for d in late)

        early_freq = dict(_top_terms(early_text, 40))
        late_freq = dict(_top_terms(late_text, 40))

        all_terms = set(early_freq) | set(late_freq)
        shifts = []
        for term in all_terms:
            e = early_freq.get(term, 0)
            l = late_freq.get(term, 0)
            if e + l < 3:
                continue
            # Relative shift: how much did proportion change?
            e_norm = e / max(sum(early_freq.values()), 1)
            l_norm = l / max(sum(late_freq.values()), 1)
            delta = l_norm - e_norm
            shifts.append((term, e, l, round(delta * 10000, 1)))  # scaled for readability

        shifts.sort(key=lambda x: abs(x[3]), reverse=True)

        gained = [(t, e, l, d) for t, e, l, d in shifts if d > 0][:10]
        lost = [(t, e, l, d) for t, e, l, d in shifts if d < 0][:10]

        lines.append("\n**Terms that gained prominence in late coverage** (entered or grew):")
        for term, e, l, d in gained:
            lines.append(f"  - `{term}` — early: {e}, late: {l} (+{d})")

        lines.append("\n**Terms that lost prominence in late coverage** (faded or disappeared):")
        for term, e, l, d in lost:
            lines.append(f"  - `{term}` — early: {e}, late: {l} ({d})")

        return "\n".join(lines)

    # ── Analysis 3: Contradiction Detection ─────────────────────────────────

    def _contradiction_detection(self, docs: list[dict]) -> str:
        lines = ["## 3. Contradiction Detection"]

        # Group numerical claims by their context keywords
        claim_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)

        for doc in docs:
            for left, number, right in _extract_number_claims(doc["content"]):
                # Use the left context as a rough claim key (normalized)
                key = re.sub(r"\s+", " ", left.lower().strip())[-40:]
                if len(key) > 5:
                    claim_groups[key].append((number, doc["url"]))

        contradictions = []
        for context, claims in claim_groups.items():
            numbers = {c[0] for c in claims}
            if len(numbers) > 1:  # same context, different numbers
                contradictions.append((context, claims))

        if not contradictions:
            lines.append("No numerical contradictions detected in the corpus.")
        else:
            lines.append(
                f"**{len(contradictions)} potential numerical contradiction(s) detected:**\n"
            )
            for context, claims in sorted(contradictions, key=lambda x: -len(x[1]))[:10]:
                lines.append(f"**Context:** `...{context}...`")
                for number, url in claims[:6]:
                    lines.append(f"  - `{number}` — {url}")
                lines.append("")

        # Also flag direct claim conflicts (sentences that contradict each other on named facts)
        # Simple heuristic: same entity + "did not" vs "did" / "is not" vs "is"
        negation_pairs = []
        all_sentences = []
        for doc in docs:
            for sent in _sentences(doc["content"]):
                all_sentences.append((sent, doc["url"]))

        for i, (s1, u1) in enumerate(all_sentences):
            lower1 = s1.lower()
            entities1 = _extract_entities(s1)
            if not entities1:
                continue
            for s2, u2 in all_sentences[i + 1: i + 100]:
                if u1 == u2:
                    continue
                entities2 = _extract_entities(s2)
                shared = entities1 & entities2
                if not shared:
                    continue
                lower2 = s2.lower()
                # One affirms, one negates
                if (
                    ("did not" in lower1 and "did not" not in lower2)
                    or ("is not" in lower1 and "is not" not in lower2)
                    or ("never" in lower1 and "never" not in lower2)
                ) and any(e.lower() in lower2 for e in shared):
                    negation_pairs.append((shared, s1, u1, s2, u2))
                    if len(negation_pairs) >= 5:
                        break
            if len(negation_pairs) >= 5:
                break

        if negation_pairs:
            lines.append(f"\n**Affirmation/negation conflicts ({len(negation_pairs)} found):**")
            for entities, s1, u1, s2, u2 in negation_pairs:
                lines.append(
                    f"\n*Shared entities: {', '.join(list(entities)[:3])}*\n"
                    f"  - CLAIM A (`{u1}`): _{s1[:200]}_\n"
                    f"  - CLAIM B (`{u2}`): _{s2[:200]}_"
                )

        return "\n".join(lines)

    # ── Analysis 4: Language Drift ───────────────────────────────────────────

    def _language_drift(self, early: list[dict], late: list[dict]) -> str:
        lines = ["## 4. Language Drift"]

        if not early or not late:
            return "\n".join(lines) + "\nInsufficient sources for drift analysis."

        early_text = " ".join(d["content"] for d in early)
        late_text = " ".join(d["content"] for d in late)

        early_vocab = set(re.findall(r"\b[a-z]{5,}\b", early_text.lower()))
        late_vocab = set(re.findall(r"\b[a-z]{5,}\b", late_text.lower()))

        early_terms = dict(_top_terms(early_text, 60))
        late_terms = dict(_top_terms(late_text, 60))

        # Terms in top early vocab that vanish from late entirely
        abandoned = [
            (t, c) for t, c in early_terms.items()
            if t not in late_vocab and c >= 3
        ]
        # Terms in top late vocab that were absent from early entirely
        emerged = [
            (t, c) for t, c in late_terms.items()
            if t not in early_vocab and c >= 3
        ]

        abandoned.sort(key=lambda x: -x[1])
        emerged.sort(key=lambda x: -x[1])

        lines.append(
            f"**Vocabulary abandoned by late coverage** "
            f"(present in early, absent in late — {len(abandoned)} terms):"
        )
        for term, count in abandoned[:15]:
            lines.append(f"  - `{term}` (appeared {count}x in early)")

        lines.append(
            f"\n**Vocabulary that emerged in late coverage** "
            f"(absent in early, present in late — {len(emerged)} terms):"
        )
        for term, count in emerged[:15]:
            lines.append(f"  - `{term}` (appeared {count}x in late)")

        if abandoned and emerged:
            lines.append(
                f"\n*Drift summary: the early corpus used language like "
                f"{', '.join(f'`{t}`' for t, _ in abandoned[:5])}; "
                f"late coverage replaced it with "
                f"{', '.join(f'`{t}`' for t, _ in emerged[:5])}.*"
            )

        return "\n".join(lines)

    # ── Analysis 5: Narrative Compression ───────────────────────────────────

    def _narrative_compression(self, early: list[dict], late: list[dict]) -> str:
        lines = ["## 5. Narrative Compression"]

        if not early or not late:
            return "\n".join(lines) + "\nInsufficient sources for compression analysis."

        early_text = " ".join(d["content"] for d in early)
        late_text = " ".join(d["content"] for d in late)

        early_entities = Counter(
            e for d in early for e in _extract_entities(d["content"])
        )
        late_entities = Counter(
            e for d in late for e in _extract_entities(d["content"])
        )

        # Entities prominent in early coverage that are absent or rare in late
        dropped = [
            (entity, count, late_entities.get(entity, 0))
            for entity, count in early_entities.items()
            if count >= 3 and late_entities.get(entity, 0) == 0
        ]
        diminished = [
            (entity, early_count, late_count)
            for entity, early_count in early_entities.items()
            if early_count >= 4
            and (late_count := late_entities.get(entity, 0)) > 0
            and early_count / max(late_count, 1) >= 3
        ]
        # Entities that gained prominence late (new actors entering the narrative)
        amplified = [
            (entity, early_entities.get(entity, 0), late_count)
            for entity, late_count in late_entities.items()
            if late_count >= 4 and early_entities.get(entity, 0) == 0
        ]

        dropped.sort(key=lambda x: -x[1])
        diminished.sort(key=lambda x: -(x[1] - x[2]))
        amplified.sort(key=lambda x: -x[2])

        lines.append(
            f"**Entities dropped from narrative entirely** "
            f"(in early coverage, absent from late — {len(dropped)} found):"
        )
        for entity, early_n, _ in dropped[:20]:
            lines.append(f"  - **{entity}** — mentioned {early_n}x early, 0x late")

        lines.append(
            f"\n**Entities significantly diminished** "
            f"(mentioned far less in late coverage — {len(diminished)} found):"
        )
        for entity, early_n, late_n in diminished[:10]:
            lines.append(
                f"  - **{entity}** — {early_n}x early → {late_n}x late "
                f"(ratio {early_n//max(late_n,1)}:1)"
            )

        lines.append(
            f"\n**New entities amplified in late coverage** "
            f"(absent early, prominent late — {len(amplified)} found):"
        )
        for entity, _, late_n in amplified[:10]:
            lines.append(f"  - **{entity}** — 0x early, {late_n}x late")

        if dropped or diminished:
            dropped_names = [e for e, _, _ in dropped[:5]]
            lines.append(
                f"\n*Compression summary: {len(dropped)} entities were dropped entirely. "
                f"The most significant losses are: "
                f"{', '.join(f'**{e}**' for e in dropped_names)}. "
                f"These represent the parts of the story that the consensus narrative discarded.*"
            )

        return "\n".join(lines)
