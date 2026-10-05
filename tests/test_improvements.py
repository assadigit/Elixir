"""V18.2.18: Tests for the improvement ideas (bold-name attribution,
grammatical coherence, Lists & Frameworks setting).

Tests verify:
1. verify_bold_name_attribution catches the V18.2.15 Khan error
2. verify_bold_name_attribution doesn't false-positive on correct bold-name bullets
3. detect_grammatical_incoherence catches the V18.2.15 broken Key Distinctions bullet
4. detect_grammatical_incoherence doesn't false-positive on clean bullets
"""

from __future__ import annotations

# Load postchecks directly from file (bypass package __init__)
import sys as _sys
from importlib.util import module_from_spec as _mfs
from importlib.util import spec_from_file_location as _spec
from pathlib import Path as _Path

# V0.18 (Phase 5.2): postchecks.py moved VERBATIM into the postchecks
# package as orchestrator.py (same re-export surface).
_postchecks_path = (
    _Path(__file__).resolve().parent.parent
    / "core"
    / "summarisation"
    / "postchecks"
    / "orchestrator.py"
)
# V18.2.27 (warnings fix): use importlib.util spec + exec_module instead of
# the deprecated SourceFileLoader.load_module() (removed in Python 3.15).
_spec_obj = _spec("_improvements_postchecks", str(_postchecks_path))
_pc = _mfs(_spec_obj)
_sys.modules["_improvements_postchecks"] = _pc
_spec_obj.loader.exec_module(_pc)

verify_bold_name_attribution = _pc.verify_bold_name_attribution
detect_grammatical_incoherence = _pc.detect_grammatical_incoherence


# ═══════════════════════════════════════════════════════════════════════════
# Improvement 1: verify_bold_name_attribution
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyBoldNameAttribution:
    """V18.2.18 Improvement 1: Bold-name attribution verification."""

    def test_khan_error_caught(self):
        """The V18.2.15 Khan error is caught.

        Summary: "**Khan**: Provided the developmental basis for authenticity..."
        Source: "Winnicott... His work provides the developmental basis for
        (1) authenticity; (2) 'corporeality' (Khan 1983)..."
        Khan is only cited for the term, not the work → FLAG.
        """
        # Construct the source to match the V18.2.15 structure.
        source = (
            "Winnicott Although Winnicott did not use the term identity "
            "specifically, his views on early development are of great "
            "significance to the formation of identity. His work provides "
            'the developmental basis for (1) authenticity; (2) "corporeality" '
            "(Khan 1983), or a deeply assimilated and personalized bodily "
            "foundation for one's self-experience; and (3) the experience of "
            "temporal continuity in the self."
        )
        summary = "- **Khan**: Provided the developmental basis for authenticity, corporeality, and temporal continuity."
        _, issues = verify_bold_name_attribution(summary, source, "bullet[khan]", None)
        # Should flag the subject mismatch.
        subject_issues = [i for i in issues if "subject mismatch" in i.detail]
        assert len(subject_issues) >= 1, (
            f"Expected subject mismatch flag but got: {[i.detail for i in issues]}"
        )

    def test_correct_bold_name_not_flagged(self):
        """A correct bold-name bullet (author IS the subject) → no flag."""
        source = "Winnicott proposed the true self concept. His work addresses authenticity."
        summary = "- **Winnicott**: Proposed the true self concept and authenticity."
        _, issues = verify_bold_name_attribution(summary, source, "bullet[0]", None)
        # Winnicott is the subject, so no subject-mismatch flag.
        subject_issues = [i for i in issues if "subject mismatch" in i.detail]
        assert subject_issues == []

    def test_unknown_author_flagged(self):
        """Bold-name author not in source → FLAG."""
        source = "Erikson defined ego identity in 1956."
        summary = "- **Fabricator**: Invented a theory not in the source text at all."
        _, issues = verify_bold_name_attribution(summary, source, "bullet[0]", None)
        # Should flag that the author isn't in the source.
        unknown_issues = [i for i in issues if "not found in source" in i.detail]
        assert len(unknown_issues) >= 1

    def test_no_bold_name_no_issues(self):
        """Text without bold-name bullets → no issues."""
        source = "The theory is well-established."
        summary = "The theory is well-established."
        _, issues = verify_bold_name_attribution(summary, source, "exec", None)
        assert issues == []

    def test_failopen_on_empty(self):
        assert verify_bold_name_attribution("", "source", "exec")[1] == []
        assert verify_bold_name_attribution("summary", "", "exec")[1] == []

    def test_agnostic_works_on_any_discipline(self):
        """The detector works across disciplines — any **Author**: claim."""
        # Biology
        bio_src = "Darwin proposed natural selection as the mechanism of evolution."
        bio_sum = "- **Darwin**: Proposed natural selection as the mechanism of evolution."
        _, bio_issues = verify_bold_name_attribution(bio_sum, bio_src, "bullet[0]", None)
        subject_issues = [i for i in bio_issues if "subject mismatch" in i.detail]
        assert subject_issues == []  # Darwin IS the subject


# ═══════════════════════════════════════════════════════════════════════════
# Improvement 2: detect_grammatical_incoherence
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectGrammaticalIncoherence:
    """V18.2.18 Improvement 2: Grammatical coherence check."""

    def test_broken_key_distinctions_bullet_caught(self):
        """The V18.2.15 broken bullet is caught.

        "Identity and Kernberg both crisis of adolescence versus identity
        diffusion: Erikson described..." — disjoint subject-object.
        """
        text = "- Identity and Kernberg both crisis of adolescence versus identity diffusion: Erikson described the usual identity crisis of adolescence."
        _, issues = detect_grammatical_incoherence(text, "key_distinctions[0]")
        # Should flag the disjoint subject-object pattern.
        disjoint_issues = [i for i in issues if "disjoint" in i.detail]
        assert len(disjoint_issues) >= 1, (
            f"Expected disjoint flag but got: {[i.detail for i in issues]}"
        )

    def test_merged_sentences_caught(self):
        """Period+Capital with no space is caught."""
        text = "The theory is well established.The evidence supports it."
        _, issues = detect_grammatical_incoherence(text, "exec")
        merged_issues = [i for i in issues if "merged sentences" in i.detail]
        assert len(merged_issues) >= 1

    def test_clean_text_no_issues(self):
        """Clean, well-formed text → no issues."""
        text = "Erikson (1956) defined ego identity as persistent sameness within oneself and sharing of essential character with others."
        _, issues = detect_grammatical_incoherence(text, "exec")
        # Should have no grammar issues (it's well-formed).
        grammar_issues = [i for i in issues if i.detector == "grammar"]
        assert grammar_issues == []

    def test_failopen_on_empty(self):
        assert detect_grammatical_incoherence("", "exec")[1] == []
        assert detect_grammatical_incoherence(None, "exec")[1] == []  # type: ignore

    def test_agnostic_works_on_any_discipline(self):
        """The detector works on any discipline — grammar is universal."""
        # Biology
        bio = "Darwin proposed natural selection. The mechanism explains adaptation."
        _, bio_issues = detect_grammatical_incoherence(bio, "exec")
        grammar = [i for i in bio_issues if i.detector == "grammar"]
        assert grammar == []
        # History
        hist = "The treaty was signed in 1648. It ended the war."
        _, hist_issues = detect_grammatical_incoherence(hist, "exec")
        grammar = [i for i in hist_issues if i.detector == "grammar"]
        assert grammar == []
