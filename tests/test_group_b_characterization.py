"""V18.19.1.4 (Phase 3 / Debt D2): Group B characterization tests.

Group B is the ~188-line inline block in ``Summarizer.__init__``
(summarizer.py:408-596) that the prior session deliberately left inline because
it "needs characterization tests first" before it can be extracted to an 8th
sub-constructor ``_init_quality_params()``.

This file LOCKS the current behavior of the load-bearing Group B decisions so a
future extraction is a safe, byte-for-byte-equivalent refactor:

  1. IQ2_S overrides          — V18.15.4.0 (deadline 2400s) + V18.15.6.0 (timeout 1200s)
  2. IQ2_XXS overrides        — V18.2.33 (timeout 300s, deadline 1200s)
  3. max_output_tokens cap    — V18.2.37d / V18.3.6 (8192 for low-bit/small)
  4. max_output_tokens force  — 16000 for full-precision large models
  5. max_bullets_per_chapter  — 99999 (no cap, V13.45.5)
  6. primary_model default    — "gemma3:12b" when empty
  7. academic_rigor auto-enable (academic_paper + large full-precision model)
  8. academic_rigor NOT auto-enabled for low-bit/small models
  9. compact_summaries cap    — min(orig, 2048)
  10. overdeliver_target clamp — [coverage_threshold, 1.0]
  11. model profile assignment — Qwen → thinking_strip_aggressive
  12. heavy_model fallback    — heavy == primary → None
  13. per-model temperature enforcement (model_temperatures setting)

These tests are TEST-ONLY (no production code changed). They construct a real
``Summarizer`` with a ``_FakeSettings`` stand-in (so they're hermetic — no
dependency on ``~/.elixir/settings.json``) and assert the resulting
instance attributes.

Run: ``pytest tests/test_group_b_characterization.py -v``
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── Minimal heavy-dep stub (matches test_anti_hallucination.py pattern) ────
# tiktoken is the ONLY stub Summarizer's import chain needs at load time.
# torch/spacy/sentence_transformers are imported lazily inside methods with
# try/except ImportError guards. We deliberately do NOT stub rapidfuzz / PIL /
# pdfplumber etc. — those bare stubs would pollute sys.modules and break
# downstream tests (test_conversion_modules::test_empty_summaries imports
# core.pdf → pypdf/rapidfuzz and needs the real or absent modules, not bare
from core.models import ConversionRequest
from core.summarisation.summarizer import Summarizer

# ═══════════════════════════════════════════════════════════════════════════
# Hermetic Settings stand-in + Summarizer factory
# ═══════════════════════════════════════════════════════════════════════════

# The IQ2_S model from the project's golden-standard test rig.
IQ2_S_MODEL = "Qwen3.8-27B-UD-IQ2_S-Instruct-Vision-No-think-DynamicV3-Unsloth:latest"
# A low-bit-but-not-IQ2_S model (Q2_K suffix) → exercises the IQ2_XXS branch.
IQ2_XXS_MODEL = "some-model-name-Q2_K:latest"
# A full-precision large model (14B ≥ 13B threshold, not low-bit).
LARGE_FP_MODEL = "qwen2.5:14b"


class _FakeSettings:
    """Stand-in for ``utils.settings.Settings``.

    Returns controlled values from ``.get(key, default)`` so tests are hermetic
    (no dependency on ``~/.elixir/settings.json``). The defaults below
    give ``is_local=True`` (provider=ollama) and a non-zero timeout/deadline so
    the IQ2_S/IQ2_XXS override branches are exercisable.
    """

    _DEFAULTS = {
        "summarisation.provider": "ollama",
        "local.http_timeout_sec": 600,
        "local.chapter_deadline_sec": 600,
        "model_temperatures": {},
    }

    def __init__(self, overrides=None):
        self._values = dict(self._DEFAULTS)
        if overrides:
            self._values.update(overrides)

    def get(self, key, default=None):
        return self._values.get(key, default)


def _make_summarizer(monkeypatch, model="gemma3:12b", settings_overrides=None, **req_fields):
    """Construct a Summarizer with a hermetic _FakeSettings.

    Patches BOTH ``core.summarisation.summarizer.Settings`` (the top-level
    import used at __init__ line 394) AND ``utils.settings.Settings`` (re-imported
    at __init__ line 437 for per-model temperature enforcement). Without both
    patches the real Settings() would read ~/.elixir/settings.json and
    the tests would be filesystem-state-dependent.
    """
    fake = _FakeSettings(settings_overrides)
    # Settings is instantiated (called), so patch to a zero-arg factory.
    monkeypatch.setattr("core.summarisation.summarizer.Settings", lambda: fake)
    monkeypatch.setattr("utils.settings.Settings", lambda: fake)

    req = ConversionRequest(input_path=Path("/tmp/x.pdf"), output_dir=Path("/tmp/out"))
    req.summarisation_model = model
    for k, v in req_fields.items():
        setattr(req, k, v)

    return Summarizer(
        request=req,
        log_callback=lambda m, l="INFO": None,
        language="en",
        claim_extractor=None,
    )


@pytest.fixture(autouse=True)
def _reset_runtime_singletons():
    """Reset the module-level mutable singletons that Summarizer construction pollutes.

    V18.19.1.4 (debt D3 mitigation): constructing a Summarizer initializes several
    module-level singletons across content_judge_impl / text_preprocessor_impl /
    llm_provider_impl (the ``_warned_*`` flags, ``_st_model``, ``_keep_alive_cache``,
    ``_SPACY_NLP``). Without resetting, these leak into downstream tests and trigger
    order-dependent failures (e.g. test_conversion_modules::test_empty_summaries
    fails when run after these tests). This fixture mirrors the pattern in
    test_embedder_optional.py. The ROOT cause (re-export attribute-rebinding not
    propagating to impl-module globals, debt D3/W1) is documented in the worklog
    SWOT and deferred to a golden-master pass that centralizes all 5 singletons
    into one ``_runtime_state._State`` object.
    """
    # Snapshot before yield, reset after. Use defensive try/except because not all
    # impl modules are guaranteed to be importable in every test-env stub config.
    yield
    try:
        from core.summarisation import content_judge_impl

        content_judge_impl._warned_embedding_disabled = False
        content_judge_impl._warned_semantic_fallback = False
        content_judge_impl._st_model = None
    except Exception:
        pass
    try:
        from core.summarisation import text_preprocessor_impl

        text_preprocessor_impl._warned_no_embed_model = False
        if hasattr(text_preprocessor_impl, "_SPACY_NLP"):
            text_preprocessor_impl._SPACY_NLP = None
    except Exception:
        pass
    try:
        from core.llm import llm_provider_impl

        llm_provider_impl._keep_alive_cache = None
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# 1. IQ2_S overrides (V18.15.4.0 + V18.15.6.0)
# ═══════════════════════════════════════════════════════════════════════════


class TestIQ2SOverrides:
    """V18.15.4.0: deadline raised to 2400s for IQ2_S 27B.
    V18.15.6.0: HTTP timeout raised to 1200s for IQ2_S 27B."""

    def test_iq2_s_deadline_raised_to_2400(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_S_MODEL)
        assert s.local_chapter_deadline == 2400, (
            "V18.15.4.0: IQ2_S 27B chapter deadline must be raised to 2400s"
        )

    def test_iq2_s_timeout_raised_to_1200(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_S_MODEL)
        assert s.timeout == 1200, "V18.15.6.0: IQ2_S 27B HTTP timeout must be raised to 1200s"

    def test_iq2_s_academic_rigor_not_auto_enabled(self, monkeypatch):
        """IQ2_S is low-bit → academic_rigor must NOT auto-enable (even for academic_paper)."""
        s = _make_summarizer(monkeypatch, model=IQ2_S_MODEL, source_type="academic_paper")
        assert s.academic_rigor is False, (
            "Low-bit quant (IQ2_S) must not auto-enable academic_rigor"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. IQ2_XXS overrides (V18.2.33) — low-bit but NOT IQ2_S
# ═══════════════════════════════════════════════════════════════════════════


class TestIQ2XXSOverrides:
    """V18.2.33: HTTP timeout reduced to 300s for IQ2_XXS; deadline raised to 1200s."""

    def test_iq2_xxs_timeout_reduced_to_300(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_XXS_MODEL)
        assert s.timeout == 300, (
            "V18.2.33: IQ2_XXS (non-IQ2_S low-bit) timeout must be reduced to 300s"
        )

    def test_iq2_xxs_deadline_raised_to_1200(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_XXS_MODEL)
        assert s.local_chapter_deadline == 1200, (
            "V18.2.33: IQ2_XXS chapter deadline must be raised to 1200s"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. max_output_tokens capping (V18.2.37d / V18.3.6)
# ═══════════════════════════════════════════════════════════════════════════


class TestMaxOutputTokensCapping:
    """V18.2.37d + V18.3.6: low-bit OR small models cap output at 8192.
    Full-precision large models force output to at least 16000."""

    def test_low_bit_model_caps_output_to_8192(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            summarisation_max_output_tokens=16000,
        )
        assert s.request.summarisation_max_output_tokens == 8192, (
            "Low-bit quant (26758 ctx cap) must cap output to 8192"
        )

    def test_small_model_caps_output_to_8192(self, monkeypatch):
        # gemma3:12b is classified small (12B < 13B threshold)
        s = _make_summarizer(
            monkeypatch,
            model="gemma3:12b",
            summarisation_max_output_tokens=16000,
        )
        assert s.request.summarisation_max_output_tokens == 8192, (
            "Small model (<13B) must cap output to 8192"
        )

    def test_low_bit_output_already_under_cap_unchanged(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            summarisation_max_output_tokens=4096,
        )
        assert s.request.summarisation_max_output_tokens == 4096, (
            "Output already ≤ 8192 must not be raised (cap only fires when > 8192)"
        )

    def test_full_precision_large_model_forces_output_to_16000(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            summarisation_max_output_tokens=4096,
        )
        assert s.request.summarisation_max_output_tokens == 16000, (
            "Full-precision large model (≥13B, not low-bit) must force output to 16000"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. max_bullets_per_chapter (V13.45.5 — no hard cap)
# ═══════════════════════════════════════════════════════════════════════════


class TestMaxBulletsPerChapter:
    """V13.45.5: REMOVED the hard-coded bullet cap. Set to 99999 (effectively unlimited)."""

    def test_max_bullets_is_99999_default(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_S_MODEL)
        assert s.max_bullets_per_chapter == 99999, (
            "V13.45.5: max_bullets_per_chapter must be 99999 (no hard cap)"
        )

    def test_max_bullets_unaffected_by_compact_mode(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            compact_summaries=True,
        )
        assert s.max_bullets_per_chapter == 99999, (
            "Even in compact mode, bullets must not be capped (only output tokens shrink)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. primary_model default
# ═══════════════════════════════════════════════════════════════════════════


class TestPrimaryModelDefault:
    def test_empty_model_defaults_to_gemma3(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model="")
        assert s.primary_model == "gemma3:12b", (
            "Empty summarisation_model must default to 'gemma3:12b'"
        )

    def test_explicit_model_preserved(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=LARGE_FP_MODEL)
        assert s.primary_model == LARGE_FP_MODEL


# ═══════════════════════════════════════════════════════════════════════════
# 6-7. academic_rigor auto-enable
# ═══════════════════════════════════════════════════════════════════════════


class TestAcademicRigorAutoEnable:
    """academic_rigor auto-enables for academic_paper source when the model is
    full-precision AND large (≥13B). Low-bit / small models do NOT auto-enable."""

    def test_auto_enables_for_academic_paper_with_large_fp_model(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            source_type="academic_paper",
        )
        assert s.academic_rigor is True, (
            "academic_paper + full-precision large model must auto-enable academic_rigor"
        )

    def test_not_auto_enabled_for_normal_book(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            source_type="normal_book",
        )
        assert s.academic_rigor is False

    def test_not_auto_enabled_for_low_bit_even_if_academic(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            source_type="academic_paper",
        )
        assert s.academic_rigor is False, (
            "Low-bit quant must NOT auto-enable academic_rigor (would over-stress the model)"
        )

    def test_explicit_academic_rigor_respected(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            source_type="normal_book",
            academic_rigor=True,
        )
        assert s.academic_rigor is True, (
            "Explicit academic_rigor=True from request must be honored even for low-bit"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 8. compact_summaries mode (V10.20.0)
# ═══════════════════════════════════════════════════════════════════════════


class TestCompactSummaries:
    """V10.20.0: compact_summaries caps output at min(orig, 2048).

    NOTE (debt D10, FIXED in V18.20.1.0): compact_summaries caps to 2048 FIRST,
    and the subsequent max_output_tokens-capping block USED TO force full-precision
    large models back up to 16000 — defeating the compact mode. V18.20.1.0 (D10)
    fixed this: the 16000-force now respects the compact cap. These tests lock
    the FIXED behavior.
    """

    def test_compact_caps_output_to_2048_for_low_bit(self, monkeypatch):
        # Low-bit model: the 8192-cap branch only caps DOWN (never forces UP),
        # so compact's 2048 cap survives.
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            summarisation_max_output_tokens=16000,
            compact_summaries=True,
        )
        assert s.request.summarisation_max_output_tokens == 2048, (
            "compact_summaries + low-bit model must cap output to 2048 "
            "(the 8192-cap branch does not force UP)"
        )

    def test_compact_survives_large_model_force(self, monkeypatch):
        # V18.20.1.0 (D10 fix): full-precision large model + compact_summaries
        # → the 2048 cap SURVIVES (the 16000-force is skipped when compact is on).
        # Pre-V18.20.1.0 this was a latent bug: compact set 2048, then 16000-force
        # raised it back to 16000, defeating compact mode. Now fixed.
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            summarisation_max_output_tokens=16000,
            compact_summaries=True,
        )
        assert s.request.summarisation_max_output_tokens == 2048, (
            "V18.20.1.0 (D10 fix): compact_summaries' 2048 cap must survive the "
            "16000-force for full-precision large models. The user's explicit "
            "compact_summaries=True request is respected for ALL model classes."
        )

    def test_compact_does_not_raise_smaller_output(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=IQ2_S_MODEL,
            summarisation_max_output_tokens=1024,
            compact_summaries=True,
        )
        # min(1024, 2048) = 1024, and low-bit branch doesn't force UP → stays 1024
        assert s.request.summarisation_max_output_tokens == 1024, (
            "Output already ≤ 2048 must not be raised by compact_summaries"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9. overdeliver_target clamping
# ═══════════════════════════════════════════════════════════════════════════


class TestOverdeliverClamping:
    """overdeliver_target is clamped to [coverage_threshold, 1.0]."""

    def test_overdeliver_target_clamped_to_max_1(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            overdeliver_enabled=True,
            overdeliver_target=1.5,
        )
        assert s.overdeliver_target <= 1.0

    def test_overdeliver_target_at_least_coverage_threshold(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            coverage_threshold=0.85,
            overdeliver_enabled=True,
            overdeliver_target=0.5,
        )
        assert s.overdeliver_target >= s.coverage_threshold, (
            "overdeliver_target must not fall below coverage_threshold"
        )

    def test_overdeliver_disabled_uses_coverage_threshold(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            coverage_threshold=0.80,
            overdeliver_enabled=False,
            overdeliver_target=0.95,
        )
        assert s._effective_target == s.coverage_threshold, (
            "When overdeliver disabled, _effective_target must equal coverage_threshold"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 10. model profile assignment
# ═══════════════════════════════════════════════════════════════════════════


class TestModelProfileAssignment:
    """The model profile (from core.llm.model_profiles) drives thinking-strip
    aggressiveness and per-model prompt suffixes."""

    def test_qwen_iq2_s_gets_qwen_profile(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=IQ2_S_MODEL)
        assert s.profile is not None
        assert s.profile.name == "Qwen3.5-9B", (
            "IQ2_S Qwen model must resolve to the Qwen3.5-9B profile"
        )
        assert s.profile.thinking_strip_aggressive is True, (
            "Qwen profile must set thinking_strip_aggressive (the model emits CoT)"
        )

    def test_unknown_model_profile_is_none_or_handled(self, monkeypatch):
        # An unrecognized model name should not crash __init__ — profile is optional.
        s = _make_summarizer(monkeypatch, model="totally-unknown-model:99b")
        # profile may be None or a generic profile — the key invariant is no crash.
        assert hasattr(s, "profile")


# ═══════════════════════════════════════════════════════════════════════════
# 11. heavy_model fallback
# ═══════════════════════════════════════════════════════════════════════════


class TestHeavyModelFallback:
    """When heavy_model equals primary_model (or is empty), heavy fallback is disabled."""

    def test_heavy_equals_primary_disables_fallback(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            heavy_model=LARGE_FP_MODEL,
        )
        assert s.heavy_model is None, (
            "heavy_model == primary_model must disable fallback (set to None)"
        )

    def test_empty_heavy_model_disables_fallback(self, monkeypatch):
        s = _make_summarizer(monkeypatch, model=LARGE_FP_MODEL, heavy_model="")
        assert s.heavy_model is None

    def test_distinct_heavy_model_preserved(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model="gemma3:12b",
            heavy_model=LARGE_FP_MODEL,
        )
        assert s.heavy_model == LARGE_FP_MODEL


# ═══════════════════════════════════════════════════════════════════════════
# 12. per-model temperature enforcement (model_temperatures setting)
# ═══════════════════════════════════════════════════════════════════════════


class TestPerModelTemperatureEnforcement:
    """If Settings().model_temperatures defines a (min_temp, rec_temp) for a
    model pattern, and the request temperature is below min, it's raised."""

    def test_temperature_below_min_is_raised(self, monkeypatch):
        # qwen2.5 pattern → min 0.6, rec 0.6; request temp 0.2 < 0.6 → raised to 0.6
        overrides = {"model_temperatures": {"qwen2.5": (0.6, 0.6)}}
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            temperature=0.2,
            settings_overrides=overrides,
        )
        assert s.temperature == 0.6, (
            "Per-model temperature enforcement must raise 0.2 → 0.6 for qwen2.5"
        )

    def test_temperature_above_min_unchanged(self, monkeypatch):
        overrides = {"model_temperatures": {"qwen2.5": (0.6, 0.6)}}
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            temperature=0.8,
            settings_overrides=overrides,
        )
        assert s.temperature == 0.8, "Temperature already ≥ model min must not be lowered"

    def test_no_model_temperatures_setting_leaves_temp_unchanged(self, monkeypatch):
        s = _make_summarizer(
            monkeypatch,
            model=LARGE_FP_MODEL,
            temperature=0.2,
        )
        assert s.temperature == 0.2
