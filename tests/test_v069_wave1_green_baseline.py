"""V0.6.9 — Wave 1 (the green-baseline release): the two operator DECISIONS
landed, pinned.

DECISION 1 (VRAM policy, audit Option A "restore"): the V0.5.14 hotfix
(a0b711c) had made ``Converter._enforce_vram_budget`` NON-BLOCKING — an
unconditional ``return None`` ahead of the policy block silenced
``local.vram_overbudget_policy`` for every non-interactive start path
(queue / service dialogs / scripted runs) and left the registered setting
a placebo, with 12 red characterization tests at HEAD (the V0.6.7 audit's
BLOCKER). V0.6.9 restores the V18.20.4.10 enforcement verbatim: the cost
of an estimator false positive is ONE "Proceed anyway" click in the wizard
(the button already exists and stamps
``request.vram_overbudget_acknowledged``). The 12 previously-red tests
(test_converter_phase3_characterization.py::TestVramBudgetPolicies ×8,
test_v1820410_p0_segmentation_vram.py::TestVramPolicy ×4) are the primary
behavioral pins — this file adds the regression guard against a
resurrection of the silent non-blocking path.

DECISION 2 (parenthetical promotion, audit Option A "tighten"): the
V0.5.15 "regex-grounded exemption" (postchecks/field_phases.py) kept any
bullet whose claimed author was merely IN the ``extract_citations``
roster — but a parenthetical-only cited author ("… (Khan 1983) …") lands
in that roster BY CONSTRUCTION, so the exemption defeated exactly the
misattribution drop the V18.20.3.2 veto enforces (the audit's documented
contract conflict — 2 red tests). V0.6.9 tightens the grounding: an
author counts as grounded only when an attribution verb is actually HELD
somewhere (or within the detector's matching range) — a pure
citation-list name no longer counts. Correctly attributed authors remain
safe as a fallback: the detector's own escape (a) never confirms a
promotion for an author who holds an attribution verb in a
surname-matching span, and the tightened exemption still rescues the
rare verb-held-outside-the-range shapes.

Headless: pure-stdlib paths only (no PySide6 import).
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ═══════════════════════════════════════════════════════════════════════════
# DECISION 1 — VRAM enforcement restored (regression guards)
# ═══════════════════════════════════════════════════════════════════════════


class TestVramEnforcementRestored:
    def test_non_blocking_return_is_gone(self):
        """Source pin: the V0.5.14 unconditional proceed must NOT come
        back — every overbudget plan must reach the policy block."""
        import inspect

        from core.pipeline.converter_impl import Converter

        src = inspect.getsource(Converter._enforce_vram_budget)
        assert "NON-BLOCKING — always proceed" not in src
        assert "subprocess.run" not in src  # the V0.5.14 probe died with it
        # The restored policy block reads the setting and decides.
        assert "local.vram_overbudget_policy" in src
        assert "vram_overbudget_acknowledged" in src

    def test_restore_decision_is_documented(self):
        """Provenance pin (Rule 4): the docstring records the operator
        decision + the V0.5.14 history, so a future reader cannot mistake
        the restore for an accident."""
        import inspect

        from core.pipeline.converter_impl import Converter

        doc = inspect.getdoc(Converter._enforce_vram_budget)
        assert "V0.6.9" in doc and "DECISION 1" in doc

    def test_scripted_runs_opt_into_proceed_explicitly(self):
        """The repeatability script cannot ask interactively — it must
        keep its explicit policy=proceed (a WARNING + continue under the
        restored enforcement), never rely on a silent non-blocking path."""
        src = (Path(_project_root) / "scripts" / "repeatability_run.py").read_text(encoding="utf-8")
        assert '"local.vram_overbudget_policy": "proceed"' in src
        assert "V0.5.14: non-blocking" not in src


# ═══════════════════════════════════════════════════════════════════════════
# DECISION 2 — the tightened parenthetical-promotion grounding
# ═══════════════════════════════════════════════════════════════════════════

_SRC_KHAN = (
    "Winnicott Although Winnicott did not use the term identity "
    "specifically, his views on early development are of great "
    "significance to the formation of identity. His work provides the "
    "developmental basis for (1) authenticity; (2) \u201ccorporeality\u201d "
    "(Khan 1983), or a deeply assimilated and personalized bodily "
    "foundation for one's selfexperience; and (3) the experience of "
    "temporal continuity in the self."
)

_BULLET_KHAN = (
    "Khan: Provided the developmental basis for authenticity, "
    "'corporeality' (a deeply assimilated and personalized bodily "
    "foundation for self-experience), and the experience of temporal "
    "continuity in the self."
)


class TestParentheticalGroundingTightened:
    def test_citation_list_name_is_dropped_with_tightened_detail(self):
        """The Khan vector through the FULL ship-time chain: 'Khan' IS in
        the extract_citations roster (the parenthetical "(Khan 1983)"), but
        he never holds an attribution verb anywhere — under the tightened
        grounding that is NOT grounding, so the confirmed promotion is
        DROPPED (severity=fix) with the V0.6.9 detail."""
        from core.summarisation.postchecks import run_post_checks

        report = run_post_checks(
            bullets=[_BULLET_KHAN, "Erikson (1956) defined ego identity."],
            executive_summary="A summary.",
            thorough_summary="A thorough summary of the chapter.",
            source_text=_SRC_KHAN,
        )
        assert all("Khan:" not in b for b in report.bullets)
        promos = [i for i in report.issues if i.detector == "parenthetical_promotion"]
        assert len(promos) == 1
        assert promos[0].severity == "fix"
        # The tightened rationale is visible in the audit trail.
        assert "never holding an attribution verb" in promos[0].detail
        assert "V0.6.9" in promos[0].detail

    def test_correctly_attributed_roster_author_is_never_vetoed(self):
        """The fallback the operator preserved: an author who genuinely
        HOLDS an attribution verb in a surname-matching span is never
        confirmed as a promotion in the first place (the detector's escape
        (a)) — the bullet ships with NO parenthetical_promotion issue at
        all, roster member or not."""
        from core.summarisation.postchecks import run_post_checks

        src = (
            "Mahler formulated the separation-individuation theory. "
            "Mahler's work provides the developmental framework for "
            "psychological birth. Mahler (1968, 1971, 1975) contributed to "
            "object relations theory."
        )
        bullet = "Mahler: Contributed to object relations theory and developmental models."
        report = run_post_checks(
            bullets=[bullet],
            executive_summary="A summary.",
            thorough_summary="A thorough summary.",
            source_text=src,
        )
        assert report.bullets == [bullet]  # kept, untouched
        assert not [i for i in report.issues if i.detector == "parenthetical_promotion"]

    def test_grounding_requires_verb_not_roster_membership_alone(self):
        """Unit pin of the tightened predicate's inputs (the same helper
        the ship-time veto uses): a roster name with NO verb-holding
        anywhere is not grounded even when the roster contains them; a
        verb-holding name is."""
        from core.summarisation.postchecks.attribution import (
            _name_holds_any_attrib_verb,
        )

        # 'Khan' appears ONLY inside the citation parenthetical — no
        # active/possessive/passive-agent verb-holding shape anywhere.
        assert not _name_holds_any_attrib_verb("Khan", _SRC_KHAN)
        # 'Winnicott' holds verbs ("His work provides…" is pronoun-held,
        # but the opening "Winnicott … did not use" is an active-subject
        # shape with 'use' — verify the helper's positive side on a clear
        # active form).
        assert _name_holds_any_attrib_verb(
            "Mahler", "Mahler formulated the separation-individuation theory."
        )

    def test_tightened_exemption_is_wired_in_field_phases(self):
        """Source pin: the V0.5.15 roster-only check is replaced by the
        V0.6.9 roster + verb-holding conjunction (a future refactor must
        not silently drop the second condition)."""
        import inspect

        from core.summarisation.postchecks import field_phases

        src = inspect.getsource(field_phases.postcheck_bullets)
        assert "_v069_grounded" in src
        assert "_name_holds_any_attrib_verb(_claimed, source_text)" in src
        # The old roster-only predicate is gone.
        assert "_v0515_grounded" not in src
