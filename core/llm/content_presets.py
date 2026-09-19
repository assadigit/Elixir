"""

V3.10.0: Content-type presets — per-source-type configurations.

Each preset controls:
- PROMPT: additional instructions injected into the summarization prompt
- TONE: tone preservation instruction
- MAX_BULLETS: recommended bullet count
- MIN_BULLETS: minimum bullets expected
- BULLET_STYLE: "actionable" (self-help), "conceptual" (academic), "nuanced" (philosophy)
- PRESERVE_DOMAIN_TERMS: if True, don't simplify academic/technical jargon
- NARRATIVE_FILTER_STRICTNESS: "strict" (normal), "lenient" (philosophy — keep abstract)
- MIN_SEGMENT_TOKENS: segmentation threshold
- READING_LEVEL_TARGET: target grade level for simplification

This is the SINGLE source of truth for content-type-specific behavior.
The summarizer, segmenter, and preprocessor all read from these presets.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContentPreset:
    """Configuration preset for a specific content type."""

    name: str
    label: str  # Human-readable label for UI
    description: str  # Short description for UI tooltip

    # Prompt configuration
    prompt_addendum: str  # Additional instructions appended to the main prompt
    tone_instruction: str  # Tone preservation instruction

    # Bullet configuration
    max_bullets: int = 25
    min_bullets: int = 10
    bullet_style: str = "conceptual"  # "actionable", "conceptual", "nuanced"

    # Filter configuration
    preserve_domain_terms: bool = False  # Don't simplify jargon
    narrative_filter_strictness: str = "strict"  # "strict", "lenient"

    # Segmentation configuration
    min_segment_tokens: int = 250

    # Reading level
    reading_level_target: int = 8  # target grade level

    # Coverage threshold (how much of the source must be covered)
    coverage_threshold: float = 0.80

    # V8.0.0 #5: Per-preset output + OCR defaults
    # These control what outputs + OCR behavior the preset recommends.
    # The wizard can read these to pre-fill the output selection.
    force_ocr_all_pages: bool = False  # True for scanned/OCR-heavy presets
    extract_images: bool = False  # True for magazine/catalogue — image gallery
    skip_summaries: bool = False  # True for catalogue — summaries aren't useful
    recommended_outputs: list = None  # list of output keys to enable by default

    def __post_init__(self):
        if self.recommended_outputs is None:
            self.recommended_outputs = ["chapter_summaries", "keypoints"]


# ════════════════════════════════════════════════════════════════════════════
# Preset Definitions
# ════════════════════════════════════════════════════════════════════════════

_NORMAL_BOOK = ContentPreset(
    name="normal_book",
    label="Non-Fiction Book",
    description="General non-fiction (business, psychology, management). Balanced detail and readability.",
    prompt_addendum="",
    tone_instruction=(
        "\nTONE: Preserve the author's voice and emphasis. "
        "Maintain the same level of formality as the source.\n"
    ),
    max_bullets=25,
    min_bullets=10,
    bullet_style="conceptual",
    preserve_domain_terms=False,
    narrative_filter_strictness="strict",
    min_segment_tokens=250,
    reading_level_target=8,
    coverage_threshold=0.80,
)

_ACADEMIC_PAPER = ContentPreset(
    name="academic_paper",
    label="Academic Paper",
    description="Formal academic paper with citations, section numbering, and technical terminology.",
    prompt_addendum=(
        "\nACADEMIC MODE: This is an academic paper.\n"
        "- Preserve all citations in Author (Year) or [N] format.\n"
        "- Preserve technical terminology exactly as written — do NOT simplify.\n"
        "- Preserve section structure (1.1, 1.2, 2.3.1) in your summary.\n"
        "- Include methodology, results, and conclusions as separate concepts.\n"
        "- If the paper has an abstract, treat it as the executive summary.\n"
    ),
    tone_instruction=(
        "\nTONE: Use formal academic language. Preserve citations and technical precision. "
        "Do NOT simplify domain-specific terminology.\n"
    ),
    max_bullets=30,  # More bullets for academic detail
    min_bullets=12,
    bullet_style="conceptual",
    preserve_domain_terms=True,  # Don't simplify jargon
    narrative_filter_strictness="strict",
    min_segment_tokens=80,  # Lower threshold — academic sections can be short
    reading_level_target=12,  # Academic is inherently higher level
    coverage_threshold=0.85,
)

_SELF_HELP = ContentPreset(
    name="self_help",
    label="Self-Help / Motivational",
    description="Motivational books with exercises, action items, and transformative language.",
    prompt_addendum=(
        "\nSELF-HELP MODE: This is a motivational/self-help book.\n"
        "- Preserve the author's motivational tone and rhetorical emphasis.\n"
        "- Capture ALL exercises, action items, and 'Try This' callouts.\n"
        "- Frame bullets as actionable advice where possible.\n"
        "- Preserve transformative language ('transform', 'empower', 'achieve').\n"
        "- The summary should inspire action, not just list facts.\n"
    ),
    tone_instruction=(
        "\nTONE: Preserve the author's motivational tone and rhetorical emphasis. "
        "The summary should inspire action, not just list facts.\n"
    ),
    max_bullets=25,
    min_bullets=10,
    bullet_style="actionable",  # Action-oriented bullets
    preserve_domain_terms=False,
    narrative_filter_strictness="strict",
    min_segment_tokens=250,
    reading_level_target=7,  # Simpler — self-help should be accessible
    coverage_threshold=0.80,
)

_PHILOSOPHY = ContentPreset(
    name="philosophy",
    label="Philosophy / Dense Text",
    description="Philosophy and dense abstract texts with complex arguments and long paragraphs.",
    prompt_addendum=(
        "\nPHILOSOPHY MODE: This is a philosophical/dense text.\n"
        "- Preserve the logical chain of arguments — do NOT oversimplify.\n"
        "- Keep abstract concepts intact (e.g., 'phenomenology', 'determinism').\n"
        "- Write longer bullets (20-40 words) to preserve nuance.\n"
        "- Capture the author's reasoning steps, not just conclusions.\n"
        "- Do NOT drop bullets that seem 'narrative' — they may contain philosophical arguments.\n"
    ),
    tone_instruction=(
        "\nTONE: Preserve the author's philosophical precision and argumentative structure. "
        "Do NOT simplify abstract terminology.\n"
    ),
    max_bullets=20,  # Fewer but longer bullets
    min_bullets=8,
    bullet_style="nuanced",  # Longer, nuanced bullets
    preserve_domain_terms=True,  # Keep philosophical terms
    narrative_filter_strictness="lenient",  # Don't drop abstract arguments
    min_segment_tokens=400,  # Longer passages — philosophy has long paragraphs
    reading_level_target=10,  # Philosophy is inherently complex
    coverage_threshold=0.75,  # Lower — nuance matters more than keyword coverage
)

_CATALOGUE = ContentPreset(
    name="catalogue",
    label="Catalogue / Listings",
    description="Product catalogues or listing documents. Image gallery + specs, no summaries.",
    prompt_addendum="\nCATALOGUE MODE: Extract product names, categories, and key specifications.\n",
    tone_instruction="\nTONE: Neutral, factual listing style.\n",
    max_bullets=15,
    min_bullets=5,
    bullet_style="conceptual",
    preserve_domain_terms=False,
    narrative_filter_strictness="strict",
    min_segment_tokens=100,
    reading_level_target=8,
    coverage_threshold=0.70,
    # V8.0.0 #5: catalogue-specific behavior
    extract_images=True,  # crop images from pages for the gallery
    skip_summaries=True,  # summaries aren't useful for catalogues
    recommended_outputs=["full_markdown", "screenshots"],
)

_MAGAZINE = ContentPreset(
    name="magazine",
    label="Magazine / Visual",
    description="Magazine or visual-heavy publication. Image gallery + layout-preserved markdown + OCR.",
    prompt_addendum=(
        "\nMAGAZINE MODE: This is a magazine or visual-heavy publication.\n"
        "- Extract article text via OCR (visual layout matters).\n"
        "- Preserve article structure (title, subtitle, body, captions).\n"
        "- Capture image captions and pull quotes.\n"
        "- Do NOT summarise — preserve the full article text.\n"
        "- Note page numbers for each article.\n"
    ),
    tone_instruction="\nTONE: Preserve the magazine's editorial voice and style.\n",
    max_bullets=20,
    min_bullets=5,
    bullet_style="conceptual",
    preserve_domain_terms=False,
    narrative_filter_strictness="lenient",  # keep visual/layout descriptions
    min_segment_tokens=150,
    reading_level_target=8,
    coverage_threshold=0.70,
    # V8.0.0 #5: magazine-specific behavior
    extract_images=True,  # image gallery
    skip_summaries=False,  # still summarize articles
    recommended_outputs=["full_markdown", "screenshots", "chapter_summaries"],
)

_SCANNED = ContentPreset(
    name="scanned_pdf",
    label="Scanned PDF (OCR)",
    description="Scanned document with no extractable text. Forces full-OCR mode.",
    prompt_addendum="\nSCANNED MODE: All text extracted via OCR. Watch for OCR errors (scannoons).\n",
    tone_instruction="\nTONE: Preserve the original text as accurately as OCR allows.\n",
    max_bullets=25,
    min_bullets=10,
    bullet_style="conceptual",
    preserve_domain_terms=False,
    narrative_filter_strictness="strict",
    min_segment_tokens=250,
    reading_level_target=8,
    coverage_threshold=0.75,  # lower — OCR errors reduce coverage
    # V8.0.0 #5: scanned-specific behavior
    force_ocr_all_pages=True,  # force full OCR
    recommended_outputs=["full_markdown", "chapter_summaries", "keypoints"],
)


# ════════════════════════════════════════════════════════════════════════════
# Preset Registry
# ════════════════════════════════════════════════════════════════════════════

_PRESETS: dict[str, ContentPreset] = {
    "normal_book": _NORMAL_BOOK,
    "academic_paper": _ACADEMIC_PAPER,
    "self_help": _SELF_HELP,
    "philosophy": _PHILOSOPHY,
    "catalogue": _CATALOGUE,
    "magazine": _MAGAZINE,  # V8.0.0 #5
    "scanned_pdf": _SCANNED,  # V8.0.0 #5
}


def get_content_preset(source_type: str) -> ContentPreset:
    """Get the content preset for a source type.

    Falls back to normal_book if the source type is unknown.
    """
    return _PRESETS.get(source_type, _NORMAL_BOOK)


def get_all_presets() -> dict[str, ContentPreset]:
    """Get all available presets (for UI population)."""
    return _PRESETS.copy()


def detect_source_type(text: str) -> str:
    """V3.10.0: Auto-detect source type from text content.

    Uses keyword heuristics to guess the content type if the user
    hasn't explicitly set it. Called when source_type is "normal_book"
    and the user hasn't manually selected a type.
    """
    if not text or len(text) < 500:
        return "normal_book"

    text_lower = text[:10000].lower()  # Check first 10K chars

    # Academic paper indicators
    academic_score = 0
    academic_indicators = [
        "abstract",
        "methodology",
        "hypothesis",
        "et al.",
        "references",
        "doi",
        "arxiv",
        "journal of",
        "proceedings",
        "citations",
        "empirical",
        "qualitative",
        "quantitative",
        "regression analysis",
        "p < 0.05",
        "p<0.05",
        "statistically significant",
    ]
    for indicator in academic_indicators:
        if indicator in text_lower:
            academic_score += 1
    if academic_score >= 3:
        return "academic_paper"

    # Self-help indicators
    self_help_score = 0
    self_help_indicators = [
        "transform your",
        "empower yourself",
        "achieve your goals",
        "exercise:",
        "try this:",
        "action item:",
        "worksheet:",
        "takeaway:",
        "practice:",
        "homework:",
        "motivation",
        "mindset",
        "success",
        "breakthrough",
        "chapter exercise",
        "your journey",
        "step-by-step",
    ]
    for indicator in self_help_indicators:
        if indicator in text_lower:
            self_help_score += 1
    if self_help_score >= 3:
        return "self_help"

    # Philosophy indicators
    philosophy_score = 0
    philosophy_indicators = [
        "epistemology",
        "metaphysics",
        "ontological",
        "phenomenology",
        "existentialism",
        "nihilism",
        "determinism",
        "a priori",
        "dialectic",
        "syllogism",
        "categorical imperative",
        "moral relativism",
        "virtue ethics",
        "deontology",
        "nietzsche",
        "kant",
        "hegel",
        "sartre",
        "aristotle",
    ]
    for indicator in philosophy_indicators:
        if indicator in text_lower:
            philosophy_score += 1
    if philosophy_score >= 2:
        return "philosophy"

    return "normal_book"


def detect_scanned_pdf(scanned_page_count: int, total_pages: int) -> bool:
    """V8.0.0 #5: Auto-detect if a PDF is predominantly scanned.

    Called by the converter after the analyzer runs. If >60% of pages are
    scanned (no extractable text), the source_type is overridden to
    "scanned_pdf" which forces full-OCR mode.

    Args:
        scanned_page_count: number of pages the analyzer flagged as scanned.
        total_pages: total pages in the PDF.

    Returns:
        True if the PDF should be treated as a scanned document.
    """
    if total_pages == 0:
        return False
    ratio = scanned_page_count / total_pages
    return ratio >= 0.60
