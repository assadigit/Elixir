"""V0.4.23 (audit V0.4.22, backlog #3): active-subject veto precision.

Both V0.4.22 misfires killed TRUE bullets:
  * the attachment-theory bullet (the source writes "AuthorS (1972, 1976)
    derived his ideas … by synthesizing AuthorB's (1969, 1973) attachment
    theory, AuthorM's (1975, 1978) separation-individuation theory …" —
    the possessive IS the attribution, but the veto demanded a VERB and
    matched a nearby AuthorM clause);
  * the et-al subject parse ("AuthorG et al." → surname "al.").

The veto's real regression vectors (the parenthetical promotions) must
STILL fire.
"""

from __future__ import annotations

from core.summarisation.postcheck_detectors import detect_parenthetical_promotion

# The V0.4.22 misfire, placeholder-ized: the synthesizing theorist's
# sentence attributes attachment theory to the claimed author possessively.
SRC_ATTACHMENT = (
    "Intro prose about the pre-borderline literature and its synthesis. "
    "The synthesizing theorist (1972, 1976) derived his ideas regarding the "
    "diagnosis by synthesizing AuthorB's (1969, 1973) attachment theory, "
    "AuthorM's (1975, 1978) separation-individuation theory, and the "
    "observational stance of a third school (1960, 1965)."
)
BULLET_ATTACHMENT = (
    "AuthorB: provided the attachment theory (1969, 1973) that the "
    "synthesizing theorist incorporated into his diagnostic framework."
)

# The real promotion vector (kept from V18.20.3.2 — must still fire).
SRC_PROMOTION = (
    "By integrating the works of Klein (1948) with his own views, Kernberg "
    "formulated a three-step process of identity formation. The first step "
    "in the process is introjection."
)
BULLET_PROMOTION = (
    "Klein: Contributed to the formulation of a three-step process of "
    "identity formation by integrating his 1948 work within Kernberg's "
    "theoretical framework."
)

# The see-also-only author (kept from V18.20.3.2 — must still fire).
SRC_SEEALSO = (
    "Juxtaposed to the driving pressure of this identity theme is a second "
    "force, which, according to Lichtenstein, is the longing to abandon the "
    "human quality of identity (see also Searles 1960 in this connection)."
)
BULLET_SEEALSO = (
    "Searles: Identified a force juxtaposed to the driving pressure of the "
    "identity theme, specifically the longing to abandon the human quality "
    "of identity, in connection with Lichtenstein's views."
)


class TestVetoPrecision:
    def test_attachment_theory_bullet_not_vetoed(self):
        """The V0.4.22 misfire: possessive attribution ("AuthorB's (1969,
        1973) attachment theory") IS attribution — the TRUE bullet ships."""
        assert detect_parenthetical_promotion(BULLET_ATTACHMENT, SRC_ATTACHMENT) is None

    def test_local_overlap_blocks_wrong_clause_confirmation(self):
        """A holder whose OWN clause carries unrelated content must not
        confirm the veto — even when the 2-sentence span overlaps the
        claim's words from a DIFFERENT clause."""
        source = (
            "AuthorX (1970) formulated the framework of drive theory in "
            "detail. AuthorB, whose attachment theory became central to "
            "later synthesis, appears only in citation lists here, and "
            "his colleague published nothing on drives."
        )
        bullet = (
            "AuthorB: provided the attachment theory (1969) that later "
            "synthesis incorporated into its framework."
        )
        assert detect_parenthetical_promotion(bullet, source) is None

    def test_real_promotion_still_vetoed(self):
        result = detect_parenthetical_promotion(BULLET_PROMOTION, SRC_PROMOTION)
        assert result == ("Klein", "Kernberg")

    def test_see_also_promotion_still_vetoed(self):
        result = detect_parenthetical_promotion(BULLET_SEEALSO, SRC_SEEALSO)
        assert result is not None
        assert result[0] == "Searles"

    def test_et_al_subject_parse(self):
        """'AuthorG et al.:' — the surname is the token BEFORE 'et al.'
        (the old last-token parse yielded 'al.')."""
        source = (
            "In 1968 a research group undertook a study of fifty-three "
            "hospitalized patients to establish objective criteria. Cluster "
            "analysis of their data yielded four subcategories of the "
            "syndrome. Their work remains a landmark."
        )
        bullet = (
            "AuthorG et al.: cluster analysis of their data yielded four "
            "subcategories of the borderline syndrome in fifty-three "
            "hospitalized patients."
        )
        # The source attributes the subcategories to the GROUP (pronoun
        # "their"); the bullet claims it for AuthorG et al. — the veto must
        # at minimum PARSE the surname correctly (no crash, no 'al.' match).
        result = detect_parenthetical_promotion(bullet, source)
        assert result is None or "al" not in result[0]

    def test_possessive_attribution_matches_helper(self):
        from core.summarisation.postchecks.attribution import (
            _possessive_attribution_matches,
        )

        span = "by synthesizing AuthorB's (1969, 1973) attachment theory, AuthorM's theory"
        claim = "provided the attachment theory (1969, 1973) for the synthesis"
        assert _possessive_attribution_matches("AuthorB", span, claim)
        # a NON-adjacent noun phrase does not match
        assert not _possessive_attribution_matches("AuthorM", span, claim)
        # a citation-only mention is not an attribution
        assert not _possessive_attribution_matches("Searles", "(see also Searles 1960)", claim)

    def test_bullet_with_verb_escape_still_not_vetoed(self):
        """The standing escape: the claimed author HOLDS an attribution
        verb in the matched span."""
        source = "AuthorB (1969) provided the foundational attachment account."
        bullet = "AuthorB: provided the foundational attachment account (1969)."
        assert detect_parenthetical_promotion(bullet, source) is None
