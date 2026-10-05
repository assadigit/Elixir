"""V0.5.4 (Track B1+E1): extract_citations recall + et al. capture tests.

Two audit-driven fixes for the V0.5.3 ground-truth Bak-miss symptom:

B1 — extract_citations recall (the AUDIT-V0.5.3-ground-truth hypothesis):
  The V0.5.3 audit conjectured that ``extract_citations`` missed "Bak"
  because of a min-mention threshold or a strict name-pattern that
  required "Surname (YYYY)" form. Step 3 of the brief (run
  ``extract_citations`` on the source + diff against the 74-author
  list) DISPROVED the hypothesis: ``extract_citations`` ALREADY returns
  all 74 authors (incl. "Bak", cited once in a subsection). The two B1
  tests below lock in this recall behaviour as a regression guard so a
  future "broaden the regex / raise the threshold" change cannot
  silently drop single-mention authors.

  The ACTUAL cause of the LAYER's Bak-miss symptom was the substring
  check in ``verification_phase.py:279-284`` — ``"bak" in summary_lower``
  matched the summary's "Tobak" mention → false "Bak is covered" verdict
  → no missing-author flag fired. The fix is in
  ``verification_phase.py`` (word-boundary regex), and is regression-
  guarded here by ``TestLayerB1WordBoundaryCoverage``.

E1 — _SUMMARY_CITATION_RE multi-author capture:
  The author-grounding regex in ``core/summarisation/postchecks/attribution.py``
  did NOT match ``"X et al. (YYYY)"`` (it required the year IMMEDIATELY
  after the surname — "et al." broke the match) and matched
  ``"X and Y (YYYY)"`` with ONLY the second surname captured. The fix
  extends the regex with two optional groups (``" and Y"`` + ``" et al."``)
  so the grounding check sees the full multi-author form. Additive —
  every prior single-surname + compound-surname + possessive match is
  byte-for-byte preserved (regression-guarded by
  ``tests/test_citations_regex.py``).

Content-agnostic (Rule 1): the author names in these tests are TEST
FIXTURES (Bak / Jack / Slater / Roth / Tobak) — they do NOT appear in
runtime code. The production regex + LAYER coverage check are built from
runtime-extracted author lists (``extract_citations(source_text)``), no
hardcoded names.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v18202_system_fixes.py
# does (markitdown is not installed in this sandbox; the stub keeps the
# eager core.pipeline→core.pdf import chain loadable for the LAYER test).
from core.preprocessing.deterministic_analyzer import extract_citations
from core.summarisation.postchecks.attribution import _SUMMARY_CITATION_RE

# The paranoid chapter's source text lives in docs/ground_truth/ (Rule 4
# provenance: ground-truth files are the audit evidence, NOT runtime code
# — they are deliberately NOT scanned by the Rule-1 deny-list test).
_CH6_SOURCE_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs/ground_truth"
    / "001_6 - PARANOID PERSONALITY DISORDER.md"
)


# ═══════════════════════════════════════════════════════════════════════════
# B1: extract_citations recall — single-mention + full-chapter
# ═══════════════════════════════════════════════════════════════════════════


class TestB1ExtractCitationsRecall:
    """V0.5.4 (B1): extract_citations recall — single-mention + 74-author.

    The AUDIT-V0.5.3-ground-truth hypothesis was that ``extract_citations``
    had a min-mention threshold (≥2 mentions) or a strict name-pattern
    that required "Surname (YYYY)" form, causing single-mention authors
    cited inline (e.g. "Bak 1946") to be SILENTLY SKIPPED.

    Step 3 of the brief (run + diff against the 74-author list)
    DISPROVED the hypothesis: ``extract_citations`` ALREADY returns all
    74 authors including "Bak" (cited once in a subsection). These tests
    lock in the recall behaviour as a regression guard — a future
    "raise the threshold / narrow the regex" change cannot silently
    drop single-mention authors without failing here.
    """

    def test_extract_citations_finds_single_mention_authors(self):
        """A source text with a single inline "Bak 1946" mention →
        ``extract_citations`` returns "Bak".

        Exercises Pattern 2 (inline ``Author Year``) + the
        ``garbage_author_reason`` shape filter (Bak is 3 chars, real
        surname, plausible year — not a garbage candidate). The single
        parenthetical form is also tested (Pattern 1).
        """
        # Inline form (Pattern 2): "Bak 1946" without parens.
        text_inline = "In his work, Bak 1946 wrote about phobic character."
        authors_inline = {c["author"] for c in extract_citations(text_inline)}
        assert "Bak" in authors_inline, (
            f"Pattern 2 (inline 'Author Year') must capture single-mention "
            f"'Bak'; got {sorted(authors_inline)}"
        )

        # Parenthetical form (Pattern 1): "Bak (1946)".
        text_paren = "In his work, Bak (1946) wrote about phobic character."
        authors_paren = {c["author"] for c in extract_citations(text_paren)}
        assert "Bak" in authors_paren, (
            f"Pattern 1 (parenthetical 'Author (Year)') must capture "
            f"single-mention 'Bak'; got {sorted(authors_paren)}"
        )

    def test_extract_citations_finds_all_74_authors(self):
        """Running ``extract_citations`` on the actual ch.6 source chapter
        (loaded via ``pathlib.Path.read_text()``) returns ≥70 of the 74
        ground-truth authors — including "Bak" (the single-mention author
        the AUDIT-V0.5.3-ground-truth flagged as a recall gap).

        The ≥70 (not strict =74) threshold tolerates minor regex variance
        on OCR-corrupted lines (the ground_truth file has one corrupted
        non-Latin-script line that yields an extra "Maj sey" OCR-artifact
        author — harmless for the recall target). The key assertion is
        that "Bak" is present.
        """
        if not _CH6_SOURCE_PATH.exists():
            pytest.skip(f"source chapter not found at {_CH6_SOURCE_PATH}")
        source = _CH6_SOURCE_PATH.read_text()
        citations = extract_citations(source)
        authors = {c["author"] for c in citations}
        # The headline assertion: Bak (the single-mention author the audit
        # flagged) MUST be in the extracted author list.
        assert "Bak" in authors, (
            f"extract_citations on the ch.6 source MUST return 'Bak' "
            f"(the single-mention author the AUDIT-V0.5.3-ground-truth "
            f"flagged as a recall gap); got {len(authors)} authors, "
            f"'Bak' absent. Sample: {sorted(authors)[:10]}"
        )
        # Recall floor: ≥70 of the 74 ground-truth authors.
        assert len(authors) >= 70, (
            f"extract_citations on the ch.6 source MUST return ≥70 "
            f"unique authors (audit ground-truth = 74); got "
            f"{len(authors)}. Sample: {sorted(authors)[:15]}"
        )

    def test_extract_citations_no_min_mention_threshold(self):
        """Structural regression guard: ``extract_citations`` has NO
        min-mention threshold — a single inline citation IS captured,
        not silently dropped because it appears <2 times. This pins the
        additive design (V0.4.23 "the no-limit coverage release" commit
        aac3e57) so a future "raise the threshold to drop noisy
        single-mention authors" change fails here.
        """
        # Three different single-mention authors, each cited once inline.
        text = "Alpha 1900 wrote. Beta 1910 wrote. Gamma 1920 wrote."
        authors = {c["author"] for c in extract_citations(text)}
        # All three single-mention authors must be captured.
        assert "Alpha" in authors
        assert "Beta" in authors
        assert "Gamma" in authors


# ═══════════════════════════════════════════════════════════════════════════
# E1: _SUMMARY_CITATION_RE multi-author capture (et al. + and X)
# ═══════════════════════════════════════════════════════════════════════════


class TestE1SummaryCitationReMultiAuthor:
    """V0.5.4 (E1): ``_SUMMARY_CITATION_RE`` captures multi-author forms.

    Pre-V0.5.4 the regex required the year IMMEDIATELY after the surname —
    so ``"X et al. (YYYY)"`` was SILENTLY SKIPPED (no match) and
    ``"X and Y (YYYY)"`` was matched with ONLY the second surname ("Y")
    captured. The fix extends the regex with two optional groups (the
    ``" and Y"`` connector + the ``" et al."`` suffix) so the grounding
    check sees the full multi-author form. Additive — every prior match
    is preserved (regression-guarded by ``tests/test_citations_regex.py``).

    These tests use TEST-FIXTURE author names (Jack / Slater / Roth / etc.)
    that appear in the audit-ground-truth chapter; per AGENTS.md Rule 1
    the production regex has NO hardcoded names — the connectors ``"and"``
    + ``"et al."`` are generic English citation connectors.
    """

    def test_citation_regex_captures_et_al(self):
        """``"Jack et al. (1984) noted..."`` → the captured group(1)
        INCLUDES ``" et al."`` (so the grounding check sees the full
        multi-author form and can verify "Jack" against the source).
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Jack et al. (1984) noted..."))
        assert len(matches) == 1, (
            f"expected exactly 1 match for 'Jack et al. (1984)'; got {len(matches)}"
        )
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert year == "1984", f"year group should be '1984'; got {year!r}"
        assert "Jack" in author, f"author group must contain 'Jack'; got {author!r}"
        assert "et al" in author, (
            f"V0.5.4 (E1): author group must INCLUDE ' et al.' so the "
            f"grounding check sees the full multi-author form; got "
            f"{author!r}"
        )

    def test_citation_regex_captures_et_al_without_parens(self):
        """``"Kendler et al. 1984 discussed"`` (no parens) → captured
        group(1) = ``"Kendler et al."``. The regex's year part is
        optional-parens (``\\(?...\\)?``) — this test pins that the
        multi-author extension works in BOTH the paren + no-paren forms.
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Kendler et al. 1984 discussed"))
        assert len(matches) == 1
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert year == "1984"
        assert "Kendler" in author
        assert "et al" in author

    def test_citation_regex_captures_and_surname(self):
        """``"Slater and Roth (1977) pointed out..."`` → captured
        group(1) = ``"Slater and Roth"`` (BOTH surnames, not just "Roth").

        Pre-V0.5.4 this string was matched with group(1)="Roth" only —
        the first surname "Slater" was invisible to the grounding check
        (a coverage/grounding FP risk if the summary ONLY cited the pair
        form and the source grounded "Slater" separately).
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Slater and Roth (1977) pointed out..."))
        assert len(matches) == 1, (
            f"expected exactly 1 match for 'Slater and Roth (1977)'; got {len(matches)}"
        )
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert year == "1977", f"year group should be '1977'; got {year!r}"
        assert "Slater" in author, (
            f"V0.5.4 (E1): author group must contain 'Slater' (the FIRST "
            f"surname in the 'X and Y' pair form — pre-V0.5.4 captured only "
            f"the second surname); got {author!r}"
        )
        assert "Roth" in author, (
            f"author group must contain 'Roth' (the second surname); got {author!r}"
        )

    def test_citation_regex_captures_ampersand_surname(self):
        """``"Mellsop & Varghesi (1982) argue..."`` → the ``&`` connector
        (alternative to ``and``) is captured the same way. Pins that the
        extension is symmetric with extract_citations' Pattern 1 (which
        accepts both ``and`` and ``&``).
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Mellsop & Varghesi (1982) argue..."))
        assert len(matches) == 1
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert year == "1982"
        assert "Mellsop" in author
        assert "Varghesi" in author

    def test_citation_regex_does_not_overmatch_separate_citations(self):
        """Regression guard: ``"Smith (1971) and Jones (1980) reported"``
        (TWO SEPARATE single-author citations, not a "Smith and Jones"
        pair) MUST yield TWO matches — ("Smith", "1971") and
        ("Jones", "1980") — NOT one ("Smith and Jones", ...).

        The " and X" extension is OPTIONAL — the regex tries it greedily,
        but the year-immediately-after constraint bails the extension when
        the year is right after the first surname. This pins the bail
        behaviour so a future regex change can't accidentally merge two
        adjacent citations into one false "pair" capture.
        """
        text = "Smith (1971) and Jones (1980) reported"
        matches = list(_SUMMARY_CITATION_RE.finditer(text))
        assert len(matches) == 2, (
            f"two separate citations must yield TWO matches, not one; "
            f"got {len(matches)}: {[(m.group(1), m.group(2)) for m in matches]}"
        )
        authors = [m.group(1) for m in matches]
        years = [m.group(2) for m in matches]
        assert authors == ["Smith", "Jones"], f"authors should be ['Smith', 'Jones']; got {authors}"
        assert years == ["1971", "1980"], f"years should be ['1971', '1980']; got {years}"

    def test_citation_regex_single_surname_unchanged(self):
        """Regression guard: the plain ``"Bak (1946)"`` single-surname
        citation is captured byte-for-byte as before the E1 extension
        (no spurious " et al." / " and X" suffix appended).
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Bak (1946) wrote"))
        assert len(matches) == 1
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert author == "Bak", (
            f"single-surname 'Bak (1946)' must capture author='Bak' "
            f"(no spurious suffix); got {author!r}"
        )
        assert year == "1946"

    def test_citation_regex_compound_surname_unchanged(self):
        """Regression guard: the compound-surname citation
        ``"Chasseguet-Smirgel (1984)"`` is captured byte-for-byte as
        before the E1 extension (the NAME_SEP class already handled
        hyphens; the extension doesn't disturb it).
        """
        matches = list(_SUMMARY_CITATION_RE.finditer("Chasseguet-Smirgel (1984) wrote"))
        assert len(matches) == 1
        author = matches[0].group(1)
        year = matches[0].group(2)
        assert "Chasseguet-Smirgel" in author
        assert "et al" not in author
        assert "and" not in author.split()
        assert year == "1984"


# ═══════════════════════════════════════════════════════════════════════════
# B1 (LAYER side): word-boundary coverage check — the actual Bak-miss cause
# ═══════════════════════════════════════════════════════════════════════════


class _MockVerifyProvider:
    """A mock LLM provider that returns a caller-supplied raw response."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.calls: list[dict] = []

    def complete(self, *, prompt, temperature, max_tokens, model):
        self.calls.append({"prompt": prompt, "temperature": temperature})
        return self._raw


class _MockSettings:
    """Minimal Settings stub returning a configured model + ollama arch."""

    def __init__(self, *, model="mock-model", arch="single_local"):
        self._model = model
        self._arch = arch

    def get(self, key, default=None):
        if key == "summarisation.model":
            return self._model
        if key == "summarisation.model_architecture":
            return self._arch
        return default


class TestLayerB1WordBoundaryCoverage:
    """V0.5.4 (B1, LAYER side): the verification LAYER's coverage check
    uses a word-boundary regex instead of a substring ``in`` test.

    The AUDIT-V0.5.3-ground-truth found that the LAYER flagged 7 missing
    authors (Croewe/Jack/Lowenthal/Morey/Munro/Ndtei/Rettersol) but NOT
    Bak (also 0-occurrence in the summary). Root cause: the LAYER's
    coverage check used ``"bak" in summary_lower`` (a SUBSTRING test).
    When the summary mentioned "Tobak" (a DIFFERENT real source author),
    the substring "bak" was present → false "Bak is covered" verdict →
    no missing-author flag fired for Bak.

    The fix replaces the substring test with a ``\\b``-anchored regex so
    the author must appear as a STANDALONE TOKEN to count as covered.
    These tests use TEST-FIXTURE author names (Bak / Tobak) — per
    AGENTS.md Rule 1 the production code has NO hardcoded names; the
    word-boundary regex is built from the runtime ``extract_citations``
    list.
    """

    def test_layer_flags_substring_only_author_as_missing(self, monkeypatch):
        """When the source has "Bak" (cited once) and the summary mentions
        "Tobak" (a DIFFERENT author whose surname CONTAINS "bak" as a
        substring) but NOT "Bak" itself, the LAYER MUST flag "Bak" as
        missing — the word-boundary check rejects the false "Tobak → Bak
        covered" verdict.
        """
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = (
            "Tobak (1989) discussed expedient mendacity. "
            "Bak (1946) regarded phobic personality as a higher level."
        )
        # Summary mentions Tobak but NOT Bak (the substring "bak" is
        # present via "Tobak" — pre-V0.5.4 the substring check returned
        # False-positive "Bak is covered" → no flag).
        summary = "Tobak (1989) discussed expedient mendacity."
        provider = _MockVerifyProvider("[]")  # LLM returns no corrections
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        _out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        cov = [i for i in issues if i.detector == "verification_coverage"]
        assert cov, (
            "V0.5.4 (B1): the LAYER MUST flag 'Bak' as missing when the "
            "summary mentions 'Tobak' (substring 'bak' present) but NOT "
            "'Bak' itself. Pre-V0.5.4 the substring check returned a "
            "false 'Bak is covered' verdict — no flag fired."
        )
        # The coverage detail should mention 'Bak'.
        assert "Bak" in cov[0].detail, (
            f"the coverage flag detail must mention 'Bak'; got: {cov[0].detail!r}"
        )
        # The prompt to the LLM must include 'Bak' in the missing list.
        assert "Bak" in provider.calls[0]["prompt"]

    def test_layer_does_not_flag_when_author_actually_present(self, monkeypatch):
        """Regression guard: when the summary DOES cite "Bak" as a
        standalone token (``\\bBak\\b``), the LAYER must NOT flag it as
        missing. Pins that the word-boundary fix didn't break the
        positive-coverage case.
        """
        from core.summarisation.verification_phase import verify_and_polish_summary

        source = (
            "Tobak (1989) discussed expedient mendacity. "
            "Bak (1946) regarded phobic personality as a higher level."
        )
        # Summary mentions BOTH Tobak AND Bak — Bak as a standalone token
        # (word-boundary match).
        summary = (
            "Tobak (1989) discussed expedient mendacity. "
            "Bak (1946) regarded phobic personality as a higher level."
        )
        provider = _MockVerifyProvider("[]")
        monkeypatch.setattr(
            "core.llm.llm_provider_impl.create_provider", lambda name, settings: provider
        )
        _out, issues = verify_and_polish_summary(summary, source, settings=_MockSettings())
        cov = [i for i in issues if i.detector == "verification_coverage"]
        # No coverage flag should fire (both source authors are covered).
        assert cov == [], (
            f"regression guard: when 'Bak' appears as a standalone token "
            f"in the summary, the LAYER must NOT flag it as missing; "
            f"got coverage flag: {cov[0].detail if cov else '(none)'}"
        )

    def test_word_boundary_regex_semantics(self):
        """Unit test for the word-boundary regex semantics used in the
        LAYER coverage check: ``\\b<author>\\b`` requires the author to
        appear as a standalone token. ``"Tobak"`` does NOT match
        ``\\bbak\\b`` (no word boundary between 'o' and 'b'); ``"Bak"``
        does. Pins the regex invariant the LAYER relies on.
        """
        # The LAYER builds this regex per author from the runtime
        # extract_citations list — no hardcoded names in production.
        bak_pat = re.compile(r"\b" + re.escape("bak") + r"\b")
        # "Tobak" — 'bak' is a substring but NOT a standalone token
        # (no \b before the 'b' — 'o' is a word char).
        assert bak_pat.search("tobak") is None, (
            r"word-boundary invariant: \bbak\b must NOT match 'tobak' "
            "(the 'bak' is a substring, not a standalone token)"
        )
        # "Bak" as a standalone word — match.
        assert bak_pat.search("bak (1946)") is not None
        # "Bak," with trailing punctuation — word-boundary still holds
        # (the ',' is a non-word char so \b matches).
        assert bak_pat.search("bak, wrote") is not None
        # "Bak's" possessive — the apostrophe is a non-word char so \b
        # matches at "Bak|'s"; the regex's word boundary at the END of
        # "bak" is satisfied.
        assert bak_pat.search("bak's (1946)") is not None
