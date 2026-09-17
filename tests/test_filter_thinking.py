"""V18.15.3 (Phase 5 Stage 3, Batch 4.6) — filter_thinking characterization tests.

Byte-for-byte stability gate for ``filter_thinking_bullets`` extracted from
``Summarizer._filter_thinking_bullets``. Mocks ``post_processing.classify_bullets``
(lazy import inside the function) + a fake quarantine object.

Branches covered:
1. classify returns no drops → filtered returned, no quarantine.add, no _last_quarantined
2. always_drop=True drop → quarantine.add called, dropped counter
3. conservative mode + always_drop=False → bullet kept (added back), "kept" log suffix
4. quality scoring (concepts provided) → low-score bullets dropped + quality_scorer quarantine
5. conservative mode keeps ALL bullets (no score trim)
6. _last_quarantined rebuilt from quarantine.entries when summary non-empty
7. quarantine.summary() empty → no _last_quarantined set

Run: pytest tests/test_filter_thinking.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E: pass
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules['tiktoken'] = tk

from core.summarisation import filter_thinking as ft_mod


class _FakeQuarantine:
    def __init__(self):
        self.entries = []
        self._summary = {}

    def add(self, bullet, stage="", reason="", chapter="", actually_dropped=False, **kw):
        self.entries.append(_QEntry(bullet, stage, reason, actually_dropped))

    def summary(self):
        return dict(self._summary)


class _QEntry:
    def __init__(self, bullet, stage, reason, actually_dropped):
        self.bullet = bullet
        self.stage = stage
        self.reason = reason
        self.actually_dropped = actually_dropped


def _patch_classify(monkeypatch, kept, drops):
    """Replace post_processing.classify_bullets with a canned result."""
    import core.summarisation.post_processing as pp
    monkeypatch.setattr(pp, "classify_bullets",
                        lambda bullets, concepts=None, source_text="": (list(kept), list(drops)))


class TestFilterThinkingBullets:

    def test_no_drops_returns_filtered_no_quarantine_add(self, monkeypatch):
        q = _FakeQuarantine()
        last_set = {"v": None}
        _patch_classify(monkeypatch, kept=["good bullet"], drops=[])
        result = ft_mod.filter_thinking_bullets(
            ["good bullet"], concepts=None, source_text="",
            quarantine=q, log=lambda m, l="INFO": None,
            set_last_quarantined=lambda v: last_set.__setitem__("v", v),
        )
        assert result == ["good bullet"]
        assert q.entries == []
        assert last_set["v"] is None  # not set (summary empty)

    def test_always_drop_true_logged_and_counted(self, monkeypatch):
        q = _FakeQuarantine()
        drops = [("leaky bullet", "thinking", "prompt leakage", True)]
        _patch_classify(monkeypatch, kept=["kept bullet"], drops=drops)
        logs = []
        result = ft_mod.filter_thinking_bullets(
            ["kept bullet", "leaky bullet"], concepts=None,
            quarantine=q, log=lambda m, l="INFO": logs.append((m, l)),
        )
        assert result == ["kept bullet"]
        assert len(q.entries) == 1
        assert q.entries[0].actually_dropped is True
        assert q.entries[0].stage == "thinking"
        # dropped counter → DEBUG log
        debugs = [m for m, l in logs if l == "DEBUG"]
        assert any("Filtered 1 thinking" in m for m in debugs)

    def test_conservative_mode_keeps_gated_drops(self, monkeypatch):
        """conservative_drops=True + always_drop=False → bullet kept, 'kept' suffix."""
        q = _FakeQuarantine()
        drops = [("narrative bp", "narrative", "story bullet", False)]
        _patch_classify(monkeypatch, kept=["good"], drops=drops)
        result = ft_mod.filter_thinking_bullets(
            ["good", "narrative bp"], concepts=None,
            conservative_drops=True,
            quarantine=q, log=lambda m, l="INFO": None,
        )
        # gated drop kept (len > 2)
        assert "narrative bp" in result
        # quarantine logged with "kept — conservative mode" suffix
        assert len(q.entries) == 1
        assert "kept — conservative mode" in q.entries[0].reason
        assert q.entries[0].actually_dropped is False

    def test_conservative_mode_short_bullet_not_kept_back(self, monkeypatch):
        """conservative + always_drop=False but bullet len <= 2 → NOT added back."""
        q = _FakeQuarantine()
        drops = [("ab", "narrative", "short", False)]  # len == 2
        _patch_classify(monkeypatch, kept=["good"], drops=drops)
        result = ft_mod.filter_thinking_bullets(
            ["good", "ab"], concepts=None, conservative_drops=True,
            quarantine=q, log=lambda m, l="INFO": None,
        )
        assert "ab" not in result  # too short to keep back

    def test_quality_scoring_drops_low_score(self, monkeypatch):
        """concepts provided → bullets scored, <25 dropped, quality_scorer logged."""
        q = _FakeQuarantine()
        _patch_classify(monkeypatch, kept=["high", "low"], drops=[])
        # score: "high"=80, "low"=10 → low dropped
        def score(bullet, concepts=None, source_text=""):
            return 80 if bullet == "high" else 10
        result = ft_mod.filter_thinking_bullets(
            ["high", "low"], concepts=["c1"], source_text="src",
            quarantine=q, score_bullet=score, max_bullets_per_chapter=30,
            log=lambda m, l="INFO": None,
        )
        assert result == ["high"]
        # quality_scorer quarantine entry for "low"
        qs = [e for e in q.entries if e.stage == "quality_scorer"]
        assert len(qs) == 1
        assert qs[0].bullet == "low"
        assert "Quality score 10/100 < 25" in qs[0].reason

    def test_quality_scoring_conservative_keeps_all(self, monkeypatch):
        """conservative mode → quality scoring runs but ALL bullets kept."""
        q = _FakeQuarantine()
        _patch_classify(monkeypatch, kept=["high", "low"], drops=[])
        def score(bullet, concepts=None, source_text=""):
            return 80 if bullet == "high" else 10
        result = ft_mod.filter_thinking_bullets(
            ["high", "low"], concepts=["c1"], source_text="src",
            conservative_drops=True,
            quarantine=q, score_bullet=score, max_bullets_per_chapter=30,
            log=lambda m, l="INFO": None,
        )
        # conservative → both kept (score trim bypassed)
        assert set(result) == {"high", "low"}
        # but quality_scorer entries still logged
        qs = [e for e in q.entries if e.stage == "quality_scorer"]
        assert len(qs) == 1

    def test_last_quarantined_rebuilt_from_entries(self, monkeypatch):
        """quarantine.summary() non-empty → _last_quarantined rebuilt."""
        q = _FakeQuarantine()
        q._summary = {"thinking": 1}  # non-empty summary → triggers rebuild path
        long_bullet = "leaky bullet here with more than 80 chars " * 2
        drops = [(long_bullet, "thinking", "leak", True)]
        _patch_classify(monkeypatch, kept=[], drops=drops)
        last_set = {"v": None}
        ft_mod.filter_thinking_bullets(
            [long_bullet], concepts=None,
            quarantine=q, log=lambda m, l="INFO": None,
            set_last_quarantined=lambda v: last_set.__setitem__("v", v),
        )
        assert last_set["v"] is not None
        assert len(last_set["v"]) == 1  # one drop → one quarantine entry
        # tuple of (bullet[:80], stage)
        b, s = last_set["v"][0]
        assert s == "thinking"
        assert len(b) <= 80

    def test_quarantine_summary_empty_no_last_set(self, monkeypatch):
        """summary empty → set_last_quarantined NOT called, no INFO log."""
        q = _FakeQuarantine()
        q._summary = {}  # empty
        _patch_classify(monkeypatch, kept=["good"], drops=[])
        last_set = {"v": None}
        logs = []
        ft_mod.filter_thinking_bullets(
            ["good"], concepts=None, quarantine=q,
            log=lambda m, l="INFO": logs.append((m, l)),
            set_last_quarantined=lambda v: last_set.__setitem__("v", v),
        )
        assert last_set["v"] is None
        infos = [m for m, l in logs if l == "INFO"]
        assert infos == []

    def test_no_concepts_skips_quality_scoring(self, monkeypatch):
        """concepts=None → quality scoring block skipped entirely."""
        q = _FakeQuarantine()
        _patch_classify(monkeypatch, kept=["a", "b"], drops=[])
        score_calls = {"n": 0}
        def score(b, concepts=None, source_text=""):
            score_calls["n"] += 1
            return 50
        result = ft_mod.filter_thinking_bullets(
            ["a", "b"], concepts=None,  # None → skip scoring
            quarantine=q, score_bullet=score, max_bullets_per_chapter=30,
            log=lambda m, l="INFO": None,
        )
        assert set(result) == {"a", "b"}
        assert score_calls["n"] == 0  # never called
