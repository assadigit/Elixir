"""Phase 2 (Test-Net Deepening) — long-tail coverage for hallucination_detector.py.

``core/summarisation/hallucination_detector.py`` is at 0% in the baseline
suite (109 statements) — it's the facade the standalone Hallucination Audit
dialog calls. This file covers:

  * ``detect_and_filter`` — empty inputs, signal-import failure (fail-open),
    per-bullet dispatch, verdict summary counts
  * ``_check_single_bullet`` — all 4 signals driven with injected fake
    callables: kept (0 failures), flagged (exactly 1), dropped (≥2),
    fail-open exceptions per signal
  * Layer-8 claim-extractor paths (verbatim span found / not found /
    extractor crash → rapidfuzz fallback)
  * ``_rapidfuzz_verbatim_check`` — long-bullet direct compare, short-bullet
    window slide, rapidfuzz-unavailable substring fallback, fail-open

Hermetic: the text_preprocessor signal functions are monkeypatched on the
re-export module (``core.summarisation.text_preprocessor``) so the lazy
``from ... import`` inside ``detect_and_filter`` resolves to fakes;
``_check_single_bullet`` takes its dependencies as parameters (direct
injection — no patching needed).

Run: ``COVERAGE_FILE=.coverage.p2c3 python3 -m pytest tests/test_p2_sumtail_hallucination.py -q --no-cov``
"""

from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.summarisation.hallucination_detector import HallucinationDetector

# ── Shared fixtures ────────────────────────────────────────────────────────

SOURCE = (
    "Orexin neurons in the lateral hypothalamus regulate wakefulness and "
    "appetite. Studies in 1998 showed that orexin deficiency causes "
    "narcolepsy in mice and dogs. The discovery reshaped sleep science."
)

SHORT_SOURCE = "Orexin neurons regulate wakefulness in the lateral hypothalamus region."


class _Signals:
    """Fake triple matching the text_preprocessor signal signatures."""

    def __init__(self, overlap=1.0, sem_grounded=True, sem_sim=0.9, num_valid=True):
        self.overlap = overlap
        self.sem_grounded = sem_grounded
        self.sem_sim = sem_sim
        self.num_valid = num_valid
        self.calls = {"overlap": [], "sem": [], "num": []}

    def compute_source_overlap(self, bullet, source):
        self.calls["overlap"].append(bullet)
        return self.overlap

    def semantic_fact_check(self, bullet, source, threshold=0.42):
        self.calls["sem"].append(bullet)
        return {"best_similarity": self.sem_sim, "is_grounded": self.sem_grounded}

    def verify_numbers_and_quotes(self, bullet, source):
        self.calls["num"].append(bullet)
        return (self.num_valid, [] if self.num_valid else ["number '1998' not found"])


class _ExplodingSignals:
    def compute_source_overlap(self, bullet, source):
        raise RuntimeError("embedder exploded")

    def semantic_fact_check(self, bullet, source, threshold=0.42):
        raise RuntimeError("embedder exploded")

    def verify_numbers_and_quotes(self, bullet, source):
        raise RuntimeError("regex exploded")


class _FakeExtractor:
    """Fake ClaimExtractor for the Layer-8 verbatim path (claims are DICTS —
    the production code calls ``c.get('char_interval')``)."""

    def __init__(self, claims=None, raise_on_extract=False):
        self._claims = claims or []
        self._raise = raise_on_extract

    def extract(self, bullet, source):
        if self._raise:
            raise RuntimeError("langextract crashed")
        return self._claims


# ── 1. detect_and_filter — early returns + fail-open ───────────────────────


class TestDetectAndFilterEarlyReturns:
    def test_no_bullets_returns_empty_report(self):
        det = HallucinationDetector()
        filtered, reports = det.detect_and_filter([], SOURCE)
        assert filtered == []
        assert reports == []

    def test_no_source_returns_bullets_unchanged(self):
        det = HallucinationDetector()
        filtered, reports = det.detect_and_filter(["bullet one"], "")
        assert filtered == ["bullet one"]
        assert reports == []


class TestDetectAndFilterFailOpen:
    def test_signal_import_failure_returns_all_kept(self, monkeypatch):
        """If the text_preprocessor import fails, all bullets are KEPT with a
        fail-open reason (V13.24.0 contract — never drop on infra failure)."""
        import core.summarisation.text_preprocessor as tp

        monkeypatch.delattr(tp, "compute_source_overlap")
        det = HallucinationDetector()
        filtered, reports = det.detect_and_filter(["bullet one", "bullet two"], SOURCE)
        assert filtered == ["bullet one", "bullet two"]
        assert len(reports) == 2
        for r in reports:
            assert r["action"] == "kept"
            assert "fail-open" in r["reason"]
            assert r["source_overlap"] == 0.0


# ── 2. detect_and_filter — happy paths via patched signals ────────────────


class TestDetectAndFilterVerdicts:
    def _patch(self, monkeypatch, signals):
        import core.summarisation.text_preprocessor as tp

        monkeypatch.setattr(tp, "compute_source_overlap", signals.compute_source_overlap)
        monkeypatch.setattr(tp, "semantic_fact_check", signals.semantic_fact_check)
        monkeypatch.setattr(tp, "verify_numbers_and_quotes", signals.verify_numbers_and_quotes)

    def test_all_grounded_bullets_kept(self, monkeypatch):
        sig = _Signals()
        self._patch(monkeypatch, sig)
        det = HallucinationDetector()
        bullets = ["Orexin neurons regulate wakefulness.", "Orexin deficiency causes narcolepsy."]
        filtered, reports = det.detect_and_filter(bullets, SOURCE, label="Ch1")
        assert filtered == bullets
        assert all(r["action"] == "kept" for r in reports)
        assert all(r["reason"] == "All 4 signals passed" for r in reports)
        # Every signal ran for every bullet
        assert len(sig.calls["overlap"]) == 2
        assert len(sig.calls["sem"]) == 2
        assert len(sig.calls["num"]) == 2

    def test_two_failures_drops_bullet(self, monkeypatch):
        """≥2 failed signals → dropped (removed from filtered)."""
        # overlap 0.1 < 0.25 AND semantic ungrounded (sim 0.2) → 2 failures
        sig = _Signals(overlap=0.1, sem_grounded=False, sem_sim=0.2)
        self._patch(monkeypatch, sig)
        det = HallucinationDetector()
        filtered, reports = det.detect_and_filter(["hallucinated claim"], SOURCE)
        assert filtered == []
        assert reports[0]["action"] == "dropped"
        assert "F4 overlap 10%" in reports[0]["reason"]
        assert "semantic sim 0.20" in reports[0]["reason"]

    def test_one_failure_flags_but_keeps(self, monkeypatch):
        """Exactly 1 failed signal → flagged (kept, needs review).

        The bullet is a verbatim source span (passes signal 4); only the
        numbers/quotes signal fails.
        """
        sig = _Signals(num_valid=False)
        self._patch(monkeypatch, sig)
        det = HallucinationDetector()
        verbatim_bullet = "Orexin neurons in the lateral hypothalamus regulate wakefulness"
        filtered, reports = det.detect_and_filter([verbatim_bullet], SOURCE)
        assert filtered == [verbatim_bullet]
        assert reports[0]["action"] == "flagged"
        assert "numbers/quotes" in reports[0]["reason"]

    def test_verbatim_only_failure_is_flagged(self, monkeypatch):
        """The 4th signal (verbatim grounding) alone failing → flagged."""
        sig = _Signals()
        self._patch(monkeypatch, sig)
        det = HallucinationDetector()
        # A bullet that is topically related but shares no substring windows:
        # pass overlap/sem/num via fakes; verbatim check will fail naturally
        bullet = "Zephyr quantifiers recalibrate holographic tapestry uniquely."
        filtered, reports = det.detect_and_filter([bullet], SOURCE)
        assert filtered == [bullet]  # 1 failure → flagged, kept
        assert reports[0]["action"] == "flagged"
        assert "no verbatim grounding" in reports[0]["reason"]

    def test_semantic_pass_but_below_threshold_counts_as_failure(self, monkeypatch):
        """is_grounded=True but best_similarity < 0.42 → sem_pass forced False.

        The bullet is a verbatim span (signal 4 passes) so semantic is the
        ONLY failure → flagged.
        """
        sig = _Signals(sem_grounded=True, sem_sim=0.30)
        self._patch(monkeypatch, sig)
        det = HallucinationDetector()
        verbatim_bullet = "Orexin neurons in the lateral hypothalamus regulate wakefulness"
        filtered, reports = det.detect_and_filter([verbatim_bullet], SOURCE)
        assert filtered == [verbatim_bullet]
        assert reports[0]["action"] == "flagged"
        assert "semantic sim 0.30" in reports[0]["reason"]


class TestDetectAndFilterLayer8:
    def _patch(self, monkeypatch, signals, extractor_cls):
        import core.summarisation.text_preprocessor as tp

        monkeypatch.setattr(tp, "compute_source_overlap", signals.compute_source_overlap)
        monkeypatch.setattr(tp, "semantic_fact_check", signals.semantic_fact_check)
        monkeypatch.setattr(tp, "verify_numbers_and_quotes", signals.verify_numbers_and_quotes)
        import core.grounding.claim_extractor as ce

        monkeypatch.setattr(ce, "ClaimExtractor", extractor_cls)

    def test_layer8_verbatim_span_found(self, monkeypatch):
        sig = _Signals()
        claims = [
            {"char_interval": (0, 20), "text": "Orexin neurons regulate"},
            {"char_interval": None},
        ]
        self._patch(monkeypatch, sig, lambda: _FakeExtractor(claims=claims))
        det = HallucinationDetector()
        filtered, reports = det.detect_and_filter(["Orexin neurons regulate wakefulness."], SOURCE)
        # overlap+sem+num pass; verbatim pass via char_interval → kept
        assert reports[0]["action"] == "kept"

    def test_layer8_no_claims_verbatim_fails(self, monkeypatch):
        sig = _Signals()
        self._patch(monkeypatch, sig, lambda: _FakeExtractor(claims=[]))
        det = HallucinationDetector()
        bullet = "Unrelated quantum entanglement speculation."
        filtered, reports = det.detect_and_filter([bullet], SOURCE)
        # verbatim fails ("no verbatim span") — 1 failure → flagged
        assert reports[0]["action"] == "flagged"
        assert "no verbatim grounding" in reports[0]["reason"]

    def test_layer8_crash_falls_back_to_rapidfuzz(self, monkeypatch):
        sig = _Signals()
        self._patch(monkeypatch, sig, lambda: _FakeExtractor(raise_on_extract=True))
        det = HallucinationDetector()
        # The bullet IS a verbatim span of the source → fallback finds it
        bullet = "Orexin neurons in the lateral hypothalamus regulate wakefulness"
        filtered, reports = det.detect_and_filter([bullet], SOURCE)
        assert reports[0]["action"] == "kept"  # all 4 pass (rapidfuzz fallback)

    def test_claim_extractor_construction_failure_falls_back(self, monkeypatch):
        """ClaimExtractor() raising → claim_extractor stays None → rapidfuzz path."""
        sig = _Signals()

        def _boom():
            raise RuntimeError("langextract not installed")

        self._patch(monkeypatch, sig, _boom)
        det = HallucinationDetector()
        bullet = "Orexin neurons in the lateral hypothalamus regulate wakefulness"
        filtered, reports = det.detect_and_filter([bullet], SOURCE)
        # Signals pass; verbatim via rapidfuzz substring windows also passes
        assert reports[0]["action"] == "kept"


# ── 3. _check_single_bullet — direct injection ─────────────────────────────


class TestCheckSingleBullet:
    def test_all_signals_pass_kept(self):
        sig = _Signals()
        det = HallucinationDetector()
        report = det._check_single_bullet(
            "Orexin regulates wakefulness.",
            SOURCE,
            sig.compute_source_overlap,
            sig.semantic_fact_check,
            sig.verify_numbers_and_quotes,
        )
        assert report["action"] == "kept"
        assert report["bullet"] == "Orexin regulates wakefulness."
        assert report["source_overlap"] == 1.0
        assert report["semantic_similarity"] == 0.9

    def test_signal_exceptions_fail_open(self):
        """Every signal raising → all fail-open → kept (never drop on crash)."""
        det = HallucinationDetector()
        sig = _ExplodingSignals()
        report = det._check_single_bullet(
            "any bullet",
            SOURCE,
            sig.compute_source_overlap,
            sig.semantic_fact_check,
            sig.verify_numbers_and_quotes,
        )
        # overlap=1.0 fail-open, sem pass fail-open, num pass fail-open —
        # only the verbatim check can fail → at most 1 failure → flagged/kept
        assert report["action"] in ("kept", "flagged")

    def test_numbers_reasons_included_in_report(self):
        """The C4 failure reason text is surfaced in the report (flag case:
        bullet is a verbatim span so only numbers fails)."""
        sig = _Signals(num_valid=False)
        det = HallucinationDetector()
        report = det._check_single_bullet(
            "Orexin neurons in the lateral hypothalamus regulate wakefulness",
            SOURCE,
            sig.compute_source_overlap,
            sig.semantic_fact_check,
            sig.verify_numbers_and_quotes,
        )
        assert report["action"] == "flagged"
        assert "1998" in report["reason"]

    def test_three_failures_dropped_with_truncated_reasons(self):
        sig = _Signals(overlap=0.0, sem_grounded=False, sem_sim=0.0, num_valid=False)
        det = HallucinationDetector()
        report = det._check_single_bullet(
            "fabricated",
            SOURCE,
            sig.compute_source_overlap,
            sig.semantic_fact_check,
            sig.verify_numbers_and_quotes,
        )
        assert report["action"] == "dropped"
        assert report["reason"].startswith("Dropped:")


# ── 4. _rapidfuzz_verbatim_check ───────────────────────────────────────────


class TestRapidfuzzVerbatimCheck:
    def test_long_bullet_direct_partial_ratio(self):
        """bullet ≥ 80 chars → direct partial_ratio against the whole source."""
        det = HallucinationDetector()
        long_bullet = (
            "Orexin neurons in the lateral hypothalamus regulate wakefulness and "
            "appetite according to the foundational studies of the late 1990s."
        )
        assert det._rapidfuzz_verbatim_check(long_bullet, SOURCE) is True

    def test_short_bullet_window_slide_hit(self):
        """bullet < 80 chars → sliding window finds the verbatim span."""
        det = HallucinationDetector()
        assert det._rapidfuzz_verbatim_check("Orexin neurons regulate wakefulness.", SOURCE) is True

    def test_short_bullet_window_slide_miss(self):
        det = HallucinationDetector()
        assert (
            det._rapidfuzz_verbatim_check(
                "Zephyr quantifiers recalibrate holographic tapestry.", SOURCE
            )
            is False
        )

    def test_rapidfuzz_unavailable_substring_fallback(self, monkeypatch):
        """rapidfuzz import blocked → lowercase substring check."""
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        det = HallucinationDetector()
        bullet = "Orexin neurons in the lateral"  # contiguous span, case-insensitive
        assert det._rapidfuzz_verbatim_check(bullet, SOURCE) is True
        assert det._rapidfuzz_verbatim_check("xyzzy not present", SOURCE) is False

    def test_window_path_exception_fail_open(self):
        """A non-string bullet in the rapidfuzz window path → len() raises
        TypeError → outer except → fail-open True."""
        det = HallucinationDetector()
        assert det._rapidfuzz_verbatim_check(12345, SOURCE) is True

    def test_substring_fallback_exception_fail_open(self, monkeypatch):
        """rapidfuzz blocked + a non-string bullet → .lower() raises
        AttributeError inside the substring check → fail-open True."""
        monkeypatch.setitem(sys.modules, "rapidfuzz", None)
        det = HallucinationDetector()
        assert det._rapidfuzz_verbatim_check(12345, SOURCE) is True

    def test_empty_source_window_loop_fails_closed(self):
        """Empty source → window loop never runs → False (verifiably ungrounded)."""
        det = HallucinationDetector()
        assert det._rapidfuzz_verbatim_check("short bullet", "") is False


# ── 5. Thresholds documented in the class ─────────────────────────────────


class TestClassThresholds:
    def test_threshold_constants(self):
        assert HallucinationDetector.OVERLAP_THRESHOLD == 0.25
        assert HallucinationDetector.SEMANTIC_THRESHOLD == 0.42  # V13.22.0 relaxed
        assert HallucinationDetector.PARTIAL_RATIO_THRESHOLD == 0.50
