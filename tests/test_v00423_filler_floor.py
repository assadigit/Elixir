"""V0.4.23 (audit V0.4.22, backlog #4): the citation-adjacency filler floor.

7 of the 40 V0.4.22 shipped bullets asserted the FACT OF BEING CITED
("is recognized for his important contributions…", "is cited in a list of
sources…", "The text notes…") instead of any content. The floor rejects
them at gap-fill acceptance time; content bullets survive.
"""

from __future__ import annotations

from core.summarisation.post_processing import is_citation_filler_bullet

# The 7 filler shapes shipped by the V0.4.22 run (placeholder-ized).
SHIPPED_FILLERS = [
    "One theorist: He is recognized for his important contributions to the "
    "field, with specific citations provided for his works in 1976, 1980b, "
    "1981, and 1987.",
    "A second theorist is cited in a list of sources alongside other investigators.",
    "A third theorist is listed among specific authors within the chapter's references.",
    "A fourth: Cited as one of the primary sources for the chapter.",
    "The text notes a fifth theorist alongside several other contributors.",
    "A sixth theorist appears in a list of sources for the section.",
    "A seventh is acknowledged among the investigators cited in the review.",
]

CONTENT_BULLETS = [
    "Knight distinguished borderline patients from psychotics and neurotics on structural grounds.",
    "The synthesizing theorist derived his framework by integrating "
    "attachment theory with separation-individuation.",
    "The 1968 study of fifty-three hospitalized patients yielded four "
    "subcategories via cluster analysis.",
    "A gap-fill bullet may cite a name in passing (1969) while carrying a "
    "real claim about the mechanism described.",
]


class TestFillerDetector:
    def test_all_shipped_fillers_flagged(self):
        for b in SHIPPED_FILLERS:
            assert is_citation_filler_bullet(b), b[:60]

    def test_content_bullets_survive(self):
        for b in CONTENT_BULLETS:
            assert not is_citation_filler_bullet(b), b[:60]

    def test_short_and_empty_never_flagged(self):
        assert not is_citation_filler_bullet("")
        assert not is_citation_filler_bullet("Too short to judge.")
        assert not is_citation_filler_bullet(None)  # type: ignore[arg-type]


class TestGapFillBatchWiring:
    """The batch gap-fill path drops filler bullets and reports them in the
    round telemetry."""

    def _run_batch(self, raw_response):
        from core.summarisation.gap_fill_batch import batch_gap_fill

        logs: list[tuple[str, str]] = []

        def log(msg, level="INFO"):
            logs.append((level, msg))

        def call_llm(prompt, **_kw):
            return raw_response

        def check_coverage(analysis, text):
            # after the round: Fillerone still "missing" (its bullet was a
            # filler — dropped), Contenttwo covered
            covered = ["Contenttwo"] if "Contenttwo" in text else []
            return {"total": 2, "covered": covered, "missing": ["Fillerone"]}

        bullets: list[str] = []
        analysis = (
            "## Citations (sorted by mention count)\n"
            "**Total unique authors: 2**\n\n"
            "1. **Fillerone** (2 mentions): 1976, 1980\n"
            "2. **Contenttwo** (2 mentions): 1968\n"
        )
        missing = ["Fillerone", "Contenttwo"]
        det_authors = ["Fillerone", "Contenttwo"]

        batch_gap_fill(
            heading="Chapter",
            content=(
                "Fillerone (1976) described the mechanism of retreat. "
                "Contenttwo (1968) studied fifty-three hospitalized patients."
            ),
            bullets=bullets,
            missing=missing,
            analysis=analysis,
            det_authors=det_authors,
            check_coverage=check_coverage,
            call_llm=call_llm,
            temperature=0.2,
            strip_thinking=lambda t: t,
            filter_thinking_bullets=lambda bl, concepts=None, source_text="": list(bl),
            log=log,
        )
        return bullets, logs

    def test_filler_dropped_content_kept(self):
        raw = (
            "- Fillerone: He is recognized for his important contributions "
            "to the field, with specific citations provided for his works.\n"
            "- Contenttwo (1968) studied fifty-three hospitalized patients "
            "and established objective criteria.\n"
        )
        bullets, logs = self._run_batch(raw)
        assert len(bullets) == 1
        assert "Contenttwo" in bullets[0]
        # the drop is visible
        assert any("filler floor" in m for _lvl, m in logs)
        # the telemetry line carries filler=
        assert any("filler=1" in m for _lvl, m in logs)
