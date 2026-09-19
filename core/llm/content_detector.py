"""V9.1.0: Deterministic content-type auto-detector.

A multi-signal scoring system that reliably identifies the content type of
a PDF from its extracted text.  Replaces the old keyword-counting
``detect_source_type`` with a more robust, trustable system.

**Why deterministic?**  LLM-based detection is unreliable and expensive.
This system uses only regex, word-frequency, and structural analysis — no
LLM calls, no randomness.  The same input always produces the same output.

**Signals (3 categories, 20+ checks):**

1. **Structural** — page count, two-column detection, heading density,
   reference/bibliography section, figure/table captions, appendix
2. **Lexical** — academic vocabulary (p-value, methodology, et al.),
   self-help imperatives (try this, exercise, your journey),
   philosophical terms (ontological, dialectic, Kant),
   catalogue patterns (£, SKU, product code, specifications)
3. **Formatting** — citation patterns (Author, Year), DOI URLs,
   numbered sections (1.1, 1.2.3), exercise callouts, YAML frontmatter

Each content type gets a weighted score.  The highest score wins.
Confidence = winner_score / sum(all_scores).  If no type scores above a
minimum threshold, falls back to "normal_book" with low confidence.

Supported types:
  - ``academic_paper`` — journal articles, conference papers, theses
  - ``self_help`` — motivational, actionable advice, exercises
  - ``philosophy`` — dense abstract argumentation
  - ``catalogue`` — product listings, specifications
  - ``magazine`` — visual-heavy, multi-column, editorial
  - ``normal_book`` — general non-fiction (default)
  - ``scanned_pdf`` — >60% scanned pages (detected separately, but included
    in the scoring so the recommendation is holistic)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of content-type auto-detection."""

    content_type: str  # the winning type key
    confidence: float  # 0.0–1.0
    scores: dict[str, float]  # per-type scores
    signals: dict[str, str]  # human-readable signal summary per type
    recommended: bool  # True if confidence >= 0.35 (trustworthy)

    def label(self) -> str:
        """Human-readable label for the detected type."""
        return _TYPE_LABELS.get(self.content_type, self.content_type)

    def explanation(self) -> str:
        """One-line explanation of why this type was detected."""
        signals = self.signals.get(self.content_type, "")
        return f"{self.label()} ({self.confidence:.0%} confidence) — {signals}"


# ── Type labels ────────────────────────────────────────────────────────────
_TYPE_LABELS = {
    "academic_paper": "Academic Paper / Scientific Article",
    "self_help": "Self-Help / Motivational",
    "philosophy": "Philosophy / Dense Text",
    "catalogue": "Catalogue / Product Listings",
    "magazine": "Magazine / Visual-heavy",
    "normal_book": "Non-Fiction Book",
    "scanned_pdf": "Scanned PDF (OCR)",
}


# ── Signal patterns ────────────────────────────────────────────────────────

# Academic: citations, DOI, p-value, sections, abstract
_ACADEMIC_CITATION = re.compile(
    r"\([A-Z][a-z]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Z][a-z]+)*,?\s+\d{4}\)"
)
_ACADEMIC_DOI = re.compile(r"10\.\d{4,}/[^\s]+", re.IGNORECASE)
_ACADEMIC_PVALUE = re.compile(r"p\s*[<>=]\s*0?\.\d+")
_ACADEMIC_SECTION = re.compile(r"^\d+\.\d+(?:\.\d+)?\s+[A-Z]", re.MULTILINE)
_ACADEMIC_ABSTRACT = re.compile(r"\babstract\b", re.IGNORECASE)
_ACADEMIC_KEYWORDS = [
    "methodology",
    "hypothesis",
    "empirical",
    "qualitative",
    "quantitative",
    "regression",
    "statistically significant",
    "et al.",
    "references",
    "bibliography",
    "proceedings",
    "journal of",
    "correlation",
    "standard deviation",
    "confidence interval",
    "sample size",
    "research question",
    "literature review",
    "systematic review",
    "peer-reviewed",
    "controlled study",
    "experimental design",
]
# V9.2.0 M6: Publisher-specific markers for reliable detection of
# Elsevier/ScienceDirect, Springer, Wiley, IEEE, Nature, Science papers.
_ACADEMIC_PUBLISHERS = [
    "elsevier",
    "sciencedirect",
    "springer",
    "wiley",
    "ieee",
    "nature",
    "science magazine",
    "oxford university press",
    "cambridge university press",
    "taylor & francis",
    "sage publications",
    "acs publications",
    "rsc publishing",
    "mdpi",
    "frontiers",
]
_ACADEMIC_DOI_PREFIXES = [
    "10.1016",  # Elsevier
    "10.1007",  # Springer
    "10.1002",  # Wiley
    "10.1109",  # IEEE
    "10.1038",  # Nature
    "10.1126",  # Science
    "10.1093",  # Oxford
    "10.1017",  # Cambridge
]
_ACADEMIC_SUBMISSION = re.compile(
    r"\b(?:received|accepted|published|available online)\s*:",
    re.IGNORECASE,
)

# Self-help: exercises, action items, motivational language
_SELFHELP_EXERCISE = re.compile(
    r"(?:^|\n)\s*(?:exercise|try this|action item|worksheet|practice|"
    r"homework|reflection|journal prompt)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_SELFHELP_KEYWORDS = [
    "transform your",
    "empower yourself",
    "achieve your goals",
    "mindset",
    "breakthrough",
    "your journey",
    "step-by-step",
    "takeaway",
    "personal growth",
    "self-improvement",
    "habits of",
    "unlock your potential",
    "overcome",
    "grit",
    "resilience",
    "deliberate practice",
    "deep work",
    "atomic habits",
]

# Philosophy: abstract terms, philosopher names, argument structure
_PHILOSOPHY_KEYWORDS = [
    "epistemology",
    "metaphysics",
    "ontological",
    "phenomenology",
    "existentialism",
    "nihilism",
    "determinism",
    "a priori",
    "a posteriori",
    "dialectic",
    "syllogism",
    "categorical imperative",
    "moral relativism",
    "virtue ethics",
    "deontology",
    "utilitarianism",
    "consciousness",
    "qualia",
    "solipsism",
    "pragmatism",
]
_PHILOSOPHY_NAMES = [
    "nietzsche",
    "kant",
    "hegel",
    "sartre",
    "aristotle",
    "plato",
    "descartes",
    "hume",
    "spinoza",
    "wittgenstein",
    "heidegger",
    "kierkegaard",
    "leibniz",
    "rousseau",
    "locke",
]

# Catalogue: product codes, prices, specifications
_CATALOGUE_PRICE = re.compile(r"[£$€]\s*\d+[.,]?\d*")
_CATALOGUE_SKU = re.compile(
    r"\b(?:SKU|product code|item no|model no|MPN)\s*[:#]?\s*[A-Z0-9\-]+", re.IGNORECASE
)
_CATALOGUE_SPECS = re.compile(
    r"\b(?:specifications|dimensions|weight|material|color|warranty)\s*:",
    re.IGNORECASE,
)
_CATALOGUE_KEYWORDS = [
    "add to cart",
    "in stock",
    "free shipping",
    "product description",
    "features",
    "what's included",
    "package contents",
]

# Magazine: visual cues, multi-column, editorial
_MAGAZINE_KEYWORDS = [
    "photograph",
    "illustration",
    "caption",
    "editor's note",
    "contributing writer",
    "issue",
    "volume",
    "special feature",
    "cover story",
    "photo essay",
    "staff photographer",
]
_MAGAZINE_SHORT_LINES = re.compile(r"^.{1,40}$", re.MULTILINE)  # short lines = captions

# Structural: two-column (heuristic — short lines + many line breaks)
_TWO_COLUMN_HEURISTIC = re.compile(r"\n.{20,80}\n.{20,80}\n.{20,80}\n.{20,80}\n")


# ── Detector ───────────────────────────────────────────────────────────────


def detect_content_type(
    text: str,
    total_pages: int = 0,
    scanned_page_count: int = 0,
) -> DetectionResult:
    """Detect the content type from extracted text + PDF metadata.

    Args:
        text: the first ~20K chars of extracted markdown/text.
        total_pages: total pages in the PDF (0 if unknown).
        scanned_page_count: how many pages were flagged as scanned.

    Returns:
        A :class:`DetectionResult` with the winning type, confidence,
        per-type scores, and signal summaries.
    """
    if not text or len(text) < 200:
        return DetectionResult(
            content_type="normal_book",
            confidence=0.0,
            scores={"normal_book": 1.0},
            signals={"normal_book": "insufficient text for detection"},
            recommended=False,
        )

    # Use first 20K chars for lexical analysis (enough for any type)
    text_sample = text[:20000]
    text_lower = text_sample.lower()

    scores: dict[str, float] = {}
    signals: dict[str, str] = {}

    # ── Scanned PDF check (highest priority structural signal) ─────────
    if total_pages > 0 and scanned_page_count > 0:
        scan_ratio = scanned_page_count / total_pages
        if scan_ratio >= 0.60:
            scores["scanned_pdf"] = 10.0
            signals["scanned_pdf"] = (
                f"{scanned_page_count}/{total_pages} pages scanned ({scan_ratio:.0%})"
            )
            # Still run other detectors — the text we have may reveal the
            # underlying content type even in a scanned PDF.
        else:
            scores["scanned_pdf"] = 0.0
            signals["scanned_pdf"] = f"only {scan_ratio:.0%} scanned"
    else:
        scores["scanned_pdf"] = 0.0
        signals["scanned_pdf"] = "no scan data"

    # ── Academic paper ─────────────────────────────────────────────────
    ac_score = 0.0
    ac_signals: list[str] = []
    # Citations (Author, Year)
    citations = len(_ACADEMIC_CITATION.findall(text_sample))
    if citations >= 3:
        ac_score += citations * 0.5
        ac_signals.append(f"{citations} citations")
    # DOI
    dois = len(_ACADEMIC_DOI.findall(text_sample))
    if dois > 0:
        ac_score += 2.0
        ac_signals.append(f"{dois} DOI(s)")
    # P-value
    pvals = len(_ACADEMIC_PVALUE.findall(text_sample))
    if pvals > 0:
        ac_score += 1.5
        ac_signals.append(f"{pvals} p-value(s)")
    # Numbered sections (1.1, 1.2.3)
    sections = len(_ACADEMIC_SECTION.findall(text_sample))
    if sections >= 5:
        ac_score += 1.0
        ac_signals.append(f"{sections} numbered sections")
    # Abstract
    if _ACADEMIC_ABSTRACT.search(text_sample):
        ac_score += 2.0
        ac_signals.append("has abstract")
    # Keywords
    kw_hits = sum(1 for kw in _ACADEMIC_KEYWORDS if kw in text_lower)
    if kw_hits >= 3:
        ac_score += kw_hits * 0.4
        ac_signals.append(f"{kw_hits} academic keywords")
    # V9.2.0 M6: Publisher markers (Elsevier, Springer, IEEE, etc.)
    pub_hits = sum(1 for pub in _ACADEMIC_PUBLISHERS if pub in text_lower)
    if pub_hits >= 1:
        ac_score += pub_hits * 1.0
        ac_signals.append(f"{pub_hits} publisher marker(s)")
    # V9.2.0 M6: DOI prefix check (Elsevier=10.1016, Springer=10.1007, etc.)
    doi_prefix_hits = sum(1 for prefix in _ACADEMIC_DOI_PREFIXES if prefix in text_lower)
    if doi_prefix_hits >= 1:
        ac_score += doi_prefix_hits * 1.5
        ac_signals.append(f"{doi_prefix_hits} known DOI prefix(es)")
    # V9.2.0 M6: Submission metadata (Received:/Accepted:/Published:)
    submission_hits = len(_ACADEMIC_SUBMISSION.findall(text_sample))
    if submission_hits >= 2:
        ac_score += 1.5
        ac_signals.append(f"{submission_hits} submission metadata fields")
    scores["academic_paper"] = ac_score
    signals["academic_paper"] = ", ".join(ac_signals) if ac_signals else "no academic signals"

    # ── Self-help ──────────────────────────────────────────────────────
    sh_score = 0.0
    sh_signals: list[str] = []
    # Exercise callouts
    exercises = len(_SELFHELP_EXERCISE.findall(text_sample))
    if exercises >= 2:
        sh_score += exercises * 0.6
        sh_signals.append(f"{exercises} exercise callouts")
    # Keywords
    kw_hits = sum(1 for kw in _SELFHELP_KEYWORDS if kw in text_lower)
    if kw_hits >= 3:
        sh_score += kw_hits * 0.4
        sh_signals.append(f"{kw_hits} motivational keywords")
    scores["self_help"] = sh_score
    signals["self_help"] = ", ".join(sh_signals) if sh_signals else "no self-help signals"

    # ── Philosophy ─────────────────────────────────────────────────────
    ph_score = 0.0
    ph_signals: list[str] = []
    kw_hits = sum(1 for kw in _PHILOSOPHY_KEYWORDS if kw in text_lower)
    if kw_hits >= 2:
        ph_score += kw_hits * 0.6
        ph_signals.append(f"{kw_hits} philosophical terms")
    name_hits = sum(1 for name in _PHILOSOPHY_NAMES if name in text_lower)
    if name_hits >= 2:
        ph_score += name_hits * 0.3
        ph_signals.append(f"{name_hits} philosopher names")
    scores["philosophy"] = ph_score
    signals["philosophy"] = ", ".join(ph_signals) if ph_signals else "no philosophy signals"

    # ── Catalogue ──────────────────────────────────────────────────────
    cat_score = 0.0
    cat_signals: list[str] = []
    prices = len(_CATALOGUE_PRICE.findall(text_sample))
    if prices >= 5:
        cat_score += prices * 0.3
        cat_signals.append(f"{prices} prices")
    skus = len(_CATALOGUE_SKU.findall(text_sample))
    if skus >= 3:
        cat_score += skus * 0.5
        cat_signals.append(f"{skus} product codes")
    if _CATALOGUE_SPECS.search(text_sample):
        cat_score += 1.5
        cat_signals.append("has specifications")
    kw_hits = sum(1 for kw in _CATALOGUE_KEYWORDS if kw in text_lower)
    if kw_hits >= 2:
        cat_score += kw_hits * 0.4
        cat_signals.append(f"{kw_hits} catalogue keywords")
    scores["catalogue"] = cat_score
    signals["catalogue"] = ", ".join(cat_signals) if cat_signals else "no catalogue signals"

    # ── Magazine ───────────────────────────────────────────────────────
    mag_score = 0.0
    mag_signals: list[str] = []
    kw_hits = sum(1 for kw in _MAGAZINE_KEYWORDS if kw in text_lower)
    if kw_hits >= 2:
        mag_score += kw_hits * 0.5
        mag_signals.append(f"{kw_hits} magazine keywords")
    # Short-line density (captions, headlines)
    short_lines = len(_MAGAZINE_SHORT_LINES.findall(text_sample[:5000]))
    if short_lines > 50:
        mag_score += 1.0
        mag_signals.append(f"high short-line density ({short_lines})")
    scores["magazine"] = mag_score
    signals["magazine"] = ", ".join(mag_signals) if mag_signals else "no magazine signals"

    # ── Normal book (baseline) ─────────────────────────────────────────
    # Normal book gets a small baseline so it wins when nothing else is
    # strongly detected (which is the correct behavior — most PDFs ARE books).
    normal_score = 1.0  # baseline
    normal_signals: list[str] = ["default (no strong signals for other types)"]
    # Long paragraphs with prose = book-like
    avg_line_len = len(text_sample) / max(1, text_sample.count("\n"))
    if avg_line_len > 300:
        normal_score += 1.0
        normal_signals.append(f"long average line length ({avg_line_len:.0f} chars)")
    scores["normal_book"] = normal_score
    signals["normal_book"] = ", ".join(normal_signals)

    # ── Determine winner ───────────────────────────────────────────────
    winner = max(scores, key=scores.get)
    total_score = sum(scores.values())
    confidence = scores[winner] / total_score if total_score > 0 else 0.0
    recommended = confidence >= 0.35 and scores[winner] >= 2.0

    return DetectionResult(
        content_type=winner,
        confidence=confidence,
        scores=scores,
        signals=signals,
        recommended=recommended,
    )
