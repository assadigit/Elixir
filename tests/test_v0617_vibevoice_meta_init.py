"""V0.6.17 — the transformers-v5 meta-device model init batch.

The operator's V0.6.16 paste-back (the register tolerance working as
designed — the load traceback finally advanced PAST the import):

  File "...\\transformers\\modeling_utils.py", line 4412, in from_pretrained
    model = cls(config, *model_args, **model_kwargs)
  File "C:\\VibeVoice\\vibevoice\\modular\\modeling_vibevoice_streaming_inference.py", line 169
    self.model = VibeVoiceStreamingModel(config)
  File "C:\\VibeVoice\\vibevoice\\modular\\modeling_vibevoice_streaming.py", line 136
    self.noise_scheduler = DPMSolverMultistepScheduler(
  File "C:\\VibeVoice\\vibevoice\\schedule\\dpm_solver.py", line 295
    self.sigmas = self.sigmas.to("cpu")
  NotImplementedError: Cannot copy out of meta tensor; no data!
  ❌ Podcast generation STOPPED at line 1. ❌ No audio file will be produced.

Root cause (verified against the REAL stack — transformers 5.14.1 (the
rig's exact build) + torch + microsoft/VibeVoice @ main + the REAL
2 GB microsoft/VibeVoice-Realtime-0.5B checkpoint, where the traceback
was reproduced BYTE-FOR-BYTE before any fix was written): transformers
v5 instantiates EVERY from_pretrained model inside
`with torch.device("meta")` — unconditionally, because
`low_cpu_mem_usage` was REMOVED in v5 ("Not used anymore -- remove them
from the kwargs", modeling_utils.py:4240) — and torch's device context
redirects device-unspecified factory calls (`torch.tensor`, `linspace`,
`empty`, ...) to the meta device while `torch.from_numpy` is NOT
redirected. transformers' own `meta_device_safe_creation_ops` patches
ONLY `torch.linspace` (identical in 5.14.1 and 5.17.0). VibeVoice-
Realtime's config uses `ddpm_beta_schedule: "cosine"`, so the
scheduler's betas come from `betas_for_alpha_bar(...)` → `torch.tensor`
→ a META tensor, and dpm_solver.py:295's `.to("cpu")` dies.

Fixing that exposed THREE more v5 breakages in the same load/generate
chain (each surfaced by the live end-to-end proof, each fixed and
re-proven until the real checkpoint + the official en-Carter_man.pt
preset produced a real 4.7 s WAV on BOTH 5.14.1 and 5.17.0):

2. tie_weights() called with v5-only kwargs (modeling_utils.py:3319 →
   `self.tie_weights(recompute_mapping=False)`) against the from-source
   no-argument override (modeling_vibevoice_streaming_inference.py:204);
3. _prepare_generation_config() called with v4's second positional +
   three speech ids (line 513) against v5's
   `(generation_config, **kwargs)` signature — the FIRST generate();
4. the official voice presets pickle transformers-4.5x DynamicCache
   internals (`key_cache`/`value_cache` lists), which v5's
   rearchitected cache (CacheLayerMixin layers) rejects on the first
   forward — and VibeVoice's own MockCacheLayer bridge (written for
   4.57) fails v5.14's strict isinstance check.

This file pins the four fixes hermetically (fake-torch / fake-vibevoice
behavioral tests, the _FakeProc pattern from test_v0615/v0616) plus one
LIVE protocol test that spawns the REAL _vibevoice_subprocess.py
against a stub tree whose from_pretrained reproduces the v5 meta-device
init — the exact rig failure, minus the 2 GB model.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIBE_ENGINE_SRC = (PROJECT_ROOT / "core" / "tts" / "vibevoice_engine.py").read_text(
    encoding="utf-8"
)
VIBE_SUB_SRC = (PROJECT_ROOT / "core" / "tts" / "_vibevoice_subprocess.py").read_text(
    encoding="utf-8"
)

VV_STUB_MODULES = (
    "vibevoice",
    "vibevoice.schedule",
    "vibevoice.schedule.dpm_solver",
    "vibevoice.modular",
    "vibevoice.modular.modeling_vibevoice_streaming_inference",
)


@pytest.fixture(autouse=True)
def _clean_vibevoice_stubs():
    """The fake-vibevoice installers write sys.modules entries directly
    (production behaviour in the subprocess); pop them around every test
    so no state leaks."""
    for name in VV_STUB_MODULES:
        sys.modules.pop(name, None)
    yield
    for name in VV_STUB_MODULES:
        sys.modules.pop(name, None)


def _subprocess_module():
    from core.tts import _vibevoice_subprocess as vvs

    return vvs


# ── Fake torch: the device-context semantics that break the scheduler ──────


class _FakeDType:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"torch.{self.name}"


float32 = _FakeDType("float32")


class _FakeTensor:
    """The torch tensor semantics VibeVoice's scheduler touches: device
    tracking, `is_meta`, dtype/device `.to()` — and the fatal meta→cpu
    copy that is the operator's exact crash."""

    def __init__(self, data, dtype=float32, device="cpu"):
        self.data = data
        self.dtype = dtype
        self.device = device

    @property
    def is_meta(self):
        return self.device == "meta"

    def to(self, target):
        if isinstance(target, _FakeDType):
            return _FakeTensor(self.data, target, self.device)
        if isinstance(target, str):
            if self.device == "meta" and target != "meta":
                raise NotImplementedError("Cannot copy out of meta tensor; no data!")
            return _FakeTensor(self.data, self.dtype, target)
        return self


def _make_fake_torch(broken_empty=False):
    """A fake torch whose `device` context manager redirects
    device-unspecified `tensor`/`empty`/`linspace` factory calls exactly
    like the real one (torch.utils._device.DeviceConstructorSet), while
    `from_numpy` always stays CPU — the asymmetry that singled out the
    scheduler's sigmas."""
    mod = types.ModuleType("torch")
    stack = ["cpu"]

    class _Device:
        def __init__(self, dev):
            self.dev = dev

        def __enter__(self):
            stack.append(self.dev)
            return self

        def __exit__(self, *exc):
            stack.pop()
            return False

    mod.device = _Device
    mod.float32 = float32

    def _tensor(data, dtype=None, device=None):
        return _FakeTensor(data, dtype=dtype or float32, device=device or stack[-1])

    def _empty(n, dtype=None, device=None):
        if broken_empty:
            raise RuntimeError("probe exploded")
        return _FakeTensor([0.0] * n, dtype=dtype or float32, device=device or stack[-1])

    def _linspace(start, end, steps, dtype=None, device=None):
        return _FakeTensor([start] * steps, dtype=dtype or float32, device=device or stack[-1])

    mod.tensor = _tensor
    mod.empty = _empty
    mod.linspace = _linspace
    mod.from_numpy = lambda arr: _FakeTensor(list(arr), device="cpu")
    mod.is_tensor = lambda x: isinstance(x, _FakeTensor)
    return mod


def _install_fake_torch(monkeypatch, broken_empty=False):
    fake = _make_fake_torch(broken_empty=broken_empty)
    monkeypatch.setitem(sys.modules, "torch", fake)
    return fake


# ── Fake vibevoice: the two classes the tolerances wrap ────────────────────


def _make_scheduler_cls():
    """A FRESH scheduler class per test — the guard patches the class
    itself, so a module-level class would leak the wrapper between
    tests (monkeypatch cannot track a direct class-attribute write)."""

    class StubScheduler:
        """Mirrors the real DPMSolverMultistepScheduler.__init__ chain for
        the cosine schedule (dpm_solver.py:230→295): betas via
        torch.tensor — a META tensor under the v5 init context — then the
        fatal `.to("cpu")`."""

        def __init__(self, num_train_timesteps=1000, beta_schedule="cosine", **kwargs):
            import torch

            if beta_schedule == "cosine":
                self.betas = torch.tensor([0.5] * num_train_timesteps, dtype=torch.float32)
            else:
                self.betas = torch.linspace(0.0001, 0.02, num_train_timesteps, dtype=torch.float32)
            # torch.from_numpy is NOT redirected — stays real on the rig
            self.timesteps = torch.from_numpy(list(range(4)))
            self.sigmas = self.betas
            self.sigmas = self.sigmas.to("cpu")  # dpm_solver.py:295

    return StubScheduler


def _make_model_cls():
    """A FRESH model class per test (same leak discipline as the
    scheduler factory)."""

    class StubModel:
        """Mirrors the from-source surfaces the V0.6.17 tolerances touch:
        a no-argument tie_weights override (line 204) and the inherited
        _prepare_generation_config the custom generate calls with v4
        args."""

        def __init__(self):
            self.tied_with = "never"

        def tie_weights(self):
            self.tied_with = "original"
            return "tied"

        def _prepare_generation_config(self, generation_config, **kwargs):
            return generation_config, {"forwarded": kwargs}

        @staticmethod
        def _vibevoice_call(model):
            """The real call shape at line 513: v4's second positional
            plus the three speech ids."""
            return model._prepare_generation_config(
                object(),
                True,
                speech_start_id=1,
                speech_end_id=2,
                speech_diffusion_id=3,
                extra=4,
            )

    return StubModel


def _install_fake_vibevoice(monkeypatch, scheduler_cls=None, model_cls=None):
    dpm = types.ModuleType("vibevoice.schedule.dpm_solver")
    dpm.DPMSolverMultistepScheduler = scheduler_cls or _make_scheduler_cls()
    inference = types.ModuleType("vibevoice.modular.modeling_vibevoice_streaming_inference")
    inference.VibeVoiceStreamingForConditionalGenerationInference = model_cls or _make_model_cls()
    for name, mod in (
        ("vibevoice", types.ModuleType("vibevoice")),
        ("vibevoice.schedule", types.ModuleType("vibevoice.schedule")),
        ("vibevoice.schedule.dpm_solver", dpm),
        ("vibevoice.modular", types.ModuleType("vibevoice.modular")),
        ("vibevoice.modular.modeling_vibevoice_streaming_inference", inference),
    ):
        monkeypatch.setitem(sys.modules, name, mod)
    return dpm, inference


# ── 1. The scheduler meta-init guard ───────────────────────────────────────


class TestSchedulerMetaGuard:
    def test_meta_context_builds_scheduler_on_cpu_with_note(self, monkeypatch, capsys):
        """THE operator defect: under the v5 meta-device init the scheduler
        must be built on real CPU tensors (not crash), with a NOTE."""
        vvs = _subprocess_module()
        fake_torch = _install_fake_torch(monkeypatch)
        dpm, _ = _install_fake_vibevoice(monkeypatch)
        vvs._guard_scheduler_meta_init()

        with fake_torch.device("meta"):
            sch = dpm.DPMSolverMultistepScheduler(num_train_timesteps=8, beta_schedule="cosine")

        assert sch.sigmas.device == "cpu" and not sch.sigmas.is_meta
        assert sch.betas.device == "cpu"
        assert sch.timesteps.device == "cpu"  # from_numpy was real all along
        out = capsys.readouterr().err
        assert "meta-device model init detected" in out
        assert "noise scheduler" in out

    def test_no_meta_context_is_the_untouched_fast_path(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        _install_fake_torch(monkeypatch)
        dpm, _ = _install_fake_vibevoice(monkeypatch)
        vvs._guard_scheduler_meta_init()

        sch = dpm.DPMSolverMultistepScheduler(num_train_timesteps=4)

        assert sch.sigmas.device == "cpu"
        assert "NOTE" not in capsys.readouterr().err  # silent fast path

    def test_unpatched_scheduler_dies_with_the_operators_error(self, monkeypatch):
        """The reproduction pin: WITHOUT the guard the same construction
        raises the operator's exact error (the fix's reason to exist)."""
        fake_torch = _install_fake_torch(monkeypatch)
        dpm, _ = _install_fake_vibevoice(monkeypatch)  # no guard installed

        with fake_torch.device("meta"):
            with pytest.raises(NotImplementedError, match="Cannot copy out of meta tensor"):
                dpm.DPMSolverMultistepScheduler(num_train_timesteps=8, beta_schedule="cosine")

    def test_idempotent_no_double_wrap(self, monkeypatch):
        vvs = _subprocess_module()
        _install_fake_torch(monkeypatch)
        dpm, _ = _install_fake_vibevoice(monkeypatch)
        vvs._guard_scheduler_meta_init()
        wrapped = dpm.DPMSolverMultistepScheduler.__dict__["__init__"]
        vvs._guard_scheduler_meta_init()
        assert dpm.DPMSolverMultistepScheduler.__dict__["__init__"] is wrapped

    def test_missing_dpm_solver_warns_not_raises(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        _install_fake_torch(monkeypatch)  # vibevoice modules absent

        vvs._guard_scheduler_meta_init()  # must not raise

        out = capsys.readouterr().err
        assert "could not install the scheduler meta-init guard" in out
        assert "transformers<5" in out

    def test_probe_failure_falls_back_to_plain_init(self, monkeypatch, capsys):
        """If even the probe cannot run (an exotic torch), the original
        init is called directly — never a crash from the guard itself."""
        vvs = _subprocess_module()
        _install_fake_torch(monkeypatch, broken_empty=True)
        dpm, _ = _install_fake_vibevoice(monkeypatch)
        vvs._guard_scheduler_meta_init()

        sch = dpm.DPMSolverMultistepScheduler(num_train_timesteps=4)  # no meta context

        assert sch.sigmas.device == "cpu"
        assert capsys.readouterr().err == ""


# ── 2. The tie_weights() signature tolerance ───────────────────────────────


class TestTieWeightsTolerance:
    def test_v5_kwargs_dropped_and_original_called(self, monkeypatch):
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_tie_weights_signature()
        model_cls = inference.VibeVoiceStreamingForConditionalGenerationInference

        model = model_cls()
        result = model_cls.tie_weights(model, missing_keys=set(), recompute_mapping=False)

        assert result == "tied"  # the original ran
        assert model.tied_with == "original"

    def test_no_argument_call_passes_through(self, monkeypatch):
        """The v4 shape (transformers 4.x calls tie_weights() bare)."""
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_tie_weights_signature()
        model_cls = inference.VibeVoiceStreamingForConditionalGenerationInference

        assert model_cls.tie_weights(model_cls()) == "tied"

    def test_unknown_kwarg_still_propagates(self, monkeypatch):
        """Surgical tolerance: an UNEXPECTED kwarg must surface loudly (a
        future drift must not be silently swallowed)."""
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_tie_weights_signature()
        model_cls = inference.VibeVoiceStreamingForConditionalGenerationInference

        with pytest.raises(TypeError):
            model_cls.tie_weights(model_cls(), brand_new_v6_kwarg=1)

    def test_no_own_override_is_silent_noop(self, monkeypatch, capsys):
        """A class WITHOUT its own tie_weights (e.g. the test stubs, or a
        future VibeVoice that drops the override — the v5 base accepts
        the kwargs natively) must be left untouched. This is the exact
        regression the v0616 live test caught in the first cut."""
        vvs = _subprocess_module()

        class _BareModel:
            pass

        _install_fake_vibevoice(monkeypatch, model_cls=_BareModel)
        vvs._tolerate_v5_tie_weights_signature()  # must not raise

        assert capsys.readouterr().err == ""

    def test_idempotent(self, monkeypatch):
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_tie_weights_signature()
        wrapped = inference.VibeVoiceStreamingForConditionalGenerationInference.__dict__[
            "tie_weights"
        ]
        vvs._tolerate_v5_tie_weights_signature()
        assert (
            inference.VibeVoiceStreamingForConditionalGenerationInference.__dict__["tie_weights"]
            is wrapped
        )


# ── 3. The _prepare_generation_config() signature tolerance ────────────────


class TestPrepareGenerationConfigTolerance:
    def test_vibevoice_call_shape_tolerated(self, monkeypatch):
        """THE generate-time defect: the real call (config, True,
        speech_*=..., **kwargs) must reach the v5-shaped original with
        the positional and the speech ids dropped, everything else kept."""
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_prepare_generation_config()
        model_cls = inference.VibeVoiceStreamingForConditionalGenerationInference

        model = model_cls()
        _cfg, model_kwargs = model_cls._vibevoice_call(model)

        assert model_kwargs == {"forwarded": {"extra": 4}}

    def test_unpatched_call_dies_with_the_operators_error(self, monkeypatch):
        """The reproduction pin: without the tolerance the v4-shaped call
        TypeErrors against the v5 signature."""
        _, inference = _install_fake_vibevoice(monkeypatch)
        model_cls = inference.VibeVoiceStreamingForConditionalGenerationInference

        with pytest.raises(TypeError, match="positional"):
            model_cls._vibevoice_call(model_cls())

    def test_no_mixin_method_is_silent_noop(self, monkeypatch, capsys):
        vvs = _subprocess_module()

        class _BareModel:
            pass

        _install_fake_vibevoice(monkeypatch, model_cls=_BareModel)
        vvs._tolerate_v5_prepare_generation_config()  # must not raise

        assert capsys.readouterr().err == ""

    def test_idempotent(self, monkeypatch):
        vvs = _subprocess_module()
        _, inference = _install_fake_vibevoice(monkeypatch)
        vvs._tolerate_v5_prepare_generation_config()
        wrapped = inference.VibeVoiceStreamingForConditionalGenerationInference.__dict__[
            "_prepare_generation_config"
        ]
        vvs._tolerate_v5_prepare_generation_config()
        assert (
            inference.VibeVoiceStreamingForConditionalGenerationInference.__dict__[
                "_prepare_generation_config"
            ]
            is wrapped
        )


# ── 4. The legacy preset-cache modernizer ──────────────────────────────────


class _FakeCacheLayer:
    """The installed version's real layer (a CacheLayerMixin)."""


class _FakeModernCache:
    """The installed version's DynamicCache: layers + update()."""

    def __init__(self):
        self.layers = []

    def update(self, key_states, value_states, layer_idx, *args, **kwargs):
        while len(self.layers) <= layer_idx:
            self.layers.append(_FakeCacheLayer())
        self.layers[layer_idx].keys = key_states
        self.layers[layer_idx].values = value_states
        return key_states, value_states


class _FakeLegacyCache:
    """A transformers-4.5x DynamicCache as pickled into the official
    presets (verified against the real en-Carter_man.pt): plain tensor
    lists, no layers attribute."""

    def __init__(self, n_layers=2):
        self._seen_tokens = 3
        self.key_cache = [_FakeTensor([[float(i)]]) for i in range(n_layers)]
        self.value_cache = [_FakeTensor([[float(i) * 2]]) for i in range(n_layers)]


class _FakeOutput:
    """A BaseModelOutputWithPast carrying a cache."""

    def __init__(self, cache):
        self.past_key_values = cache


def _install_fake_cache_utils(monkeypatch, with_classes=True):
    tf = types.ModuleType("transformers")
    cache_utils = types.ModuleType("transformers.cache_utils")
    if with_classes:
        cache_utils.CacheLayerMixin = _FakeCacheLayer
        cache_utils.DynamicCache = _FakeModernCache
    monkeypatch.setitem(sys.modules, "transformers", tf)
    monkeypatch.setitem(sys.modules, "transformers.cache_utils", cache_utils)
    return cache_utils


class TestPresetCacheModernizer:
    @pytest.fixture(autouse=True)
    def _reset_note_flag(self, monkeypatch):
        vvs = _subprocess_module()
        monkeypatch.setattr(vvs, "_LEGACY_CACHE_NOTE_SHOWN", False)

    def test_four_legacy_caches_rebuilt_with_one_note(self, monkeypatch, capsys):
        """THE preset defect: the official preset's four 4.5x caches are
        rebuilt through the installed version's DynamicCache.update(),
        tensors preserved, ONE note for the whole preset."""
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)
        preset = {
            name: _FakeOutput(_FakeLegacyCache(2))
            for name in ("lm", "tts_lm", "neg_lm", "neg_tts_lm")
        }
        original_keys = {name: list(out.past_key_values.key_cache) for name, out in preset.items()}
        original_values = {
            name: list(out.past_key_values.value_cache) for name, out in preset.items()
        }

        vvs._modernize_legacy_preset_cache(fake_torch, preset)

        for name, out in preset.items():
            fresh = out.past_key_values
            assert isinstance(fresh, _FakeModernCache)
            assert len(fresh.layers) == 2
            # the SAME tensors, same order — data untouched
            assert fresh.layers[0].keys is original_keys[name][0]
            assert fresh.layers[1].values is original_values[name][1]
        out = capsys.readouterr().err
        assert "rebuilt 4 legacy voice-preset cache(s)" in out
        assert "v5 cache rearchitecture" in out

    def test_note_fires_once_across_presets(self, monkeypatch, capsys):
        """The preset reloads for EVERY generated line — the NOTE must not
        (113 lines × 4 caches would flood the log)."""
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)

        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": _FakeOutput(_FakeLegacyCache(1))})
        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": _FakeOutput(_FakeLegacyCache(1))})

        assert capsys.readouterr().err.count("rebuilt") == 1

    def test_modern_cache_untouched(self, monkeypatch):
        """A preset re-saved under the installed version (real layers, no
        key_cache) is left alone — the no-double-conversion contract."""
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()

        class _Modern:
            layers = [_FakeCacheLayer()]

        out = _FakeOutput(_Modern())
        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": out})
        assert out.past_key_values is _Modern.__dict__["layers"] or out.past_key_values.layers

    def test_mismatched_lists_untouched(self, monkeypatch):
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)
        legacy = _FakeLegacyCache(2)
        legacy.value_cache = legacy.value_cache[:1]  # mismatch
        out = _FakeOutput(legacy)

        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": out})

        assert out.past_key_values is legacy  # untouched

    def test_non_tensor_layer_warns_and_leaves(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)
        legacy = _FakeLegacyCache(2)
        legacy.key_cache[1] = None  # not a tensor
        out = _FakeOutput(legacy)

        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": out})

        assert out.past_key_values is legacy
        assert "could not rebuild one legacy preset cache" in capsys.readouterr().err

    def test_no_cache_utils_is_silent_noop(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch, with_classes=False)
        out = _FakeOutput(_FakeLegacyCache(1))

        vvs._modernize_legacy_preset_cache(fake_torch, {"lm": out})  # must not raise

        assert out.past_key_values.key_cache  # untouched
        assert capsys.readouterr().err == ""

    def test_preset_without_caches_is_noop(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)

        vvs._modernize_legacy_preset_cache(fake_torch, {"something": object()})

        assert capsys.readouterr().err == ""

    def test_single_output_preset_supported(self, monkeypatch):
        """A preset that is ONE model output (not a dict) is walked too."""
        vvs = _subprocess_module()
        fake_torch = _make_fake_torch()
        _install_fake_cache_utils(monkeypatch)
        out = _FakeOutput(_FakeLegacyCache(3))

        vvs._modernize_legacy_preset_cache(fake_torch, out)

        assert isinstance(out.past_key_values, _FakeModernCache)
        assert len(out.past_key_values.layers) == 3


# ── 5. The version-gated dtype kwarg ───────────────────────────────────────


class TestTransformersMajor:
    def _with_version(self, monkeypatch, version):
        vvs = _subprocess_module()
        tf = types.ModuleType("transformers")
        if version is not None:
            tf.__version__ = version
        monkeypatch.setitem(sys.modules, "transformers", tf)
        return vvs

    @pytest.mark.parametrize(
        ("version", "expected"),
        [("5.14.1", 5), ("5.17.0", 5), ("5.18.0.dev0", 5), ("4.57.1", 4), ("4.51.3", 4)],
    )
    def test_version_parsing(self, monkeypatch, version, expected):
        assert self._with_version(monkeypatch, version)._transformers_major() == expected

    def test_garbage_version_is_zero(self, monkeypatch):
        assert self._with_version(monkeypatch, "not.a.version")._transformers_major() == 0

    def test_no_transformers_is_zero(self, monkeypatch):
        vvs = self._with_version(monkeypatch, None)
        monkeypatch.setattr(
            sys, "modules", {k: v for k, v in sys.modules.items() if k != "transformers"}
        )
        assert vvs._transformers_major() == 0


# ── Engine: the defense-in-depth meta hint ─────────────────────────────────


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, data: str) -> int:
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        return None


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _FakeStderr:
    def __iter__(self):
        return iter(())


class _FakeProc:
    def __init__(self, lines: list[str]) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(lines)
        self.stderr = _FakeStderr()
        self.killed = 0
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def kill(self) -> None:
        self.killed += 1
        self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        self._alive = False
        return 0

    @property
    def returncode(self) -> int:
        return 0 if not self._alive else None  # type: ignore[return-value]


class _LogCollector:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def __call__(self, msg: str, level: str = "INFO") -> None:
        self.lines.append((msg, level))

    def joined(self) -> str:
        return "\n".join(msg for msg, _lvl in self.lines)


@pytest.fixture()
def vibe_engine(tmp_path):
    from core.tts.vibevoice_engine import VibeVoiceEngine

    logs = _LogCollector()
    model_dir = tmp_path / "vibe-model"
    model_dir.mkdir()
    engine = VibeVoiceEngine(model_path=str(model_dir), log_callback=logs)
    return engine, logs


class TestEngineMetaHint:
    def test_meta_tensor_error_appends_meta_hint(self, vibe_engine, monkeypatch):
        """If the subprocess-side guard could not be installed (a future
        VibeVoice layout change), the engine's raise must still name the
        meta-device init as the cause and the two outs."""
        engine, _logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps(
                    {
                        "status": "error",
                        "error": "Model load failed: Cannot copy out of meta tensor; no data!",
                    }
                )
            ]
        )
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()

        msg = str(excinfo.value)
        assert "meta tensor" in msg
        assert "meta-device model init" in msg
        assert "transformers<5" in msg

    def test_other_load_errors_get_no_meta_hint(self, vibe_engine, monkeypatch):
        engine, _logs = vibe_engine
        proc = _FakeProc([json.dumps({"status": "error", "error": "CUDA init failed"})])
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()

        assert "meta-device" not in str(excinfo.value)


# ── Source pins: the ordering that makes the fixes work ────────────────────


class TestSourcePins:
    def test_guards_installed_after_import_before_from_pretrained(self):
        """All three wraps need the vibevoice import resolved (they wrap
        its classes) but must precede from_pretrained (the load dies
        inside it). One line too late is a dead load. The search is
        scoped to the load handler — the function DEFINITIONS live above
        it and would collide with a whole-file index."""
        handler = VIBE_SUB_SRC[VIBE_SUB_SRC.index('action == "load"') :]
        compat_idx = handler.index("_install_transformers_compat()")
        import_idx = handler.index(
            "from vibevoice.modular.modeling_vibevoice_streaming_inference import"
        )
        guard_idx = handler.index("_guard_scheduler_meta_init()")
        tie_idx = handler.index("_tolerate_v5_tie_weights_signature()")
        gen_idx = handler.index("_tolerate_v5_prepare_generation_config()")
        load_idx = handler.index(
            "VibeVoiceStreamingForConditionalGenerationInference.from_pretrained("
        )
        assert compat_idx < import_idx < guard_idx < tie_idx < gen_idx < load_idx

    def test_all_four_fixes_defined_and_wired(self):
        for name in (
            "_guard_scheduler_meta_init",
            "_tolerate_v5_tie_weights_signature",
            "_tolerate_v5_prepare_generation_config",
            "_modernize_legacy_preset_cache",
        ):
            assert f"def {name}(" in VIBE_SUB_SRC
            assert f"{name}(" in VIBE_SUB_SRC  # called
        assert "_modernize_legacy_preset_cache(torch, cached_prompt)" in VIBE_SUB_SRC

    def test_dtype_kwarg_gated_on_major(self):
        assert '"dtype" if _transformers_major() >= 5 else "torch_dtype"' in VIBE_SUB_SRC

    def test_engine_meta_hint_wired_into_raise(self):
        assert '_meta_hint = ""' in VIBE_ENGINE_SRC
        assert '"meta tensor" in _load_err' in VIBE_ENGINE_SRC
        assert "{_install_hint}{_native_hint}{_meta_hint}" in VIBE_ENGINE_SRC


# ── The LIVE protocol test — the REAL subprocess against a v5-style stack ──

_STUB_TORCH = '''
"""Stub torch — the v0616 surface PLUS the device-context semantics that
break VibeVoice's scheduler under transformers v5 meta-device init."""
import contextlib
import pickle
import sys

_device_stack = ["cpu"]


class device:
    """Context manager redirecting device-unspecified factory calls (the
    real torch.utils._device mechanism behind `with torch.device(...)`)."""

    def __init__(self, dev):
        self.dev = dev

    def __enter__(self):
        _device_stack.append(self.dev)
        return self

    def __exit__(self, *exc):
        _device_stack.pop()
        return False


class _DType:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"torch.{self.name}"


float32 = _DType("float32")
float16 = _DType("float16")
bfloat16 = _DType("bfloat16")


class _Tensor:
    def __init__(self, data, dtype=float32, device=None):
        self.data = data
        self.dtype = dtype
        self.device = device if device is not None else _device_stack[-1]

    @property
    def is_meta(self):
        return self.device == "meta"

    def to(self, target):
        if isinstance(target, _DType):
            return _Tensor(self.data, target, self.device)
        if isinstance(target, str):
            if self.device == "meta" and target != "meta":
                raise NotImplementedError("Cannot copy out of meta tensor; no data!")
            t = _Tensor(self.data, self.dtype)
            t.device = target
            return t
        return self


def tensor(data, dtype=None, device=None):
    return _Tensor(data, dtype=dtype or float32, device=device)


def empty(n, dtype=None, device=None):
    return _Tensor([0.0] * n, dtype=dtype or float32, device=device)


def linspace(start, end, steps, dtype=None, device=None):
    return _Tensor([start] * steps, dtype=dtype or float32, device=device)


def from_numpy(arr):
    return _Tensor(list(arr), device="cpu")  # never redirected — the real asymmetry


def is_tensor(x):
    return isinstance(x, _Tensor)


class _Version:
    cuda = "12.6-stub"


class _CUDA:
    @staticmethod
    def is_available():
        return False

    @staticmethod
    def get_device_name(idx=0):
        raise RuntimeError("no cuda in stub")


version = _Version()
cuda = _CUDA()


class _Serialization:
    @staticmethod
    @contextlib.contextmanager
    def safe_globals(globals_list):
        yield


serialization = _Serialization()


def load(path, map_location=None, weights_only=False):
    with open(path, "rb") as f:
        return pickle.load(f)


__version__ = "2.9.0-stub"
'''

_STUB_TF_INIT = """
__version__ = "5.17.0-stub"
"""

_STUB_TF_CACHE_UTILS = '''
class CacheLayerMixin:
    """Stub of the v5 cache layer base (cache_utils.py)."""


class _DynamicLayer(CacheLayerMixin):
    def __init__(self):
        self.keys = None
        self.values = None


class DynamicCache:
    """Stub of the v5 DynamicCache: a layers list populated via update()."""

    def __init__(self):
        self.layers = []

    def update(self, key_states, value_states, layer_idx, *args, **kwargs):
        while len(self.layers) <= layer_idx:
            self.layers.append(_DynamicLayer())
        self.layers[layer_idx].keys = key_states
        self.layers[layer_idx].values = value_states
        return key_states, value_states
'''

_STUB_TF_MODELING_OUTPUTS = '''
class BaseModelOutputWithPast:
    """Stub of transformers.modeling_outputs.BaseModelOutputWithPast."""
'''

_STUB_TF_AUTO_MAPPINGS = """
CONFIG_MAPPING_NAMES = {"qwen2": "Qwen2Config"}
MODEL_MAPPING_NAMES = {"qwen2": "Qwen2Model"}
"""

_STUB_TF_AUTO_FACTORY = '''
"""Stub of transformers.models.auto.auto_factory (no native VibeVoice
names — the V0.6.16 collision is that file's concern)."""
from .auto_mappings import CONFIG_MAPPING_NAMES, MODEL_MAPPING_NAMES


class _LazyAutoMapping:
    def __init__(self, config_mapping, model_mapping):
        self._config_mapping = config_mapping
        self._reverse_config_mapping = {v: k for k, v in config_mapping.items()}
        self._model_mapping = model_mapping
        self._extra_content = {}

    def register(self, key, value, exist_ok=False):
        if hasattr(key, "__name__") and key.__name__ in self._reverse_config_mapping:
            model_type = self._reverse_config_mapping[key.__name__]
            if model_type in self._model_mapping and not exist_ok:
                raise ValueError(f"'{key}' is already used by a Transformers model.")
        self._extra_content[key] = value


MODEL_MAPPING = _LazyAutoMapping(CONFIG_MAPPING_NAMES, MODEL_MAPPING_NAMES)


class _BaseAutoModelClass:
    _model_mapping = MODEL_MAPPING

    @classmethod
    def register(cls, config_class, model_class, exist_ok=False):
        cls._model_mapping.register(config_class, model_class, exist_ok=exist_ok)


class AutoModel(_BaseAutoModelClass):
    pass


class AutoModelForCausalLM(_BaseAutoModelClass):
    pass
'''

_STUB_TF_AUTO_INIT = "from .auto_factory import AutoModel, AutoModelForCausalLM  # noqa: F401\n"

_STUB_TF_QWEN2_INIT = """
class Qwen2TokenizerFast:
    pass


class Qwen2Tokenizer:
    pass


class Qwen2Config:
    pass
"""

_STUB_TF_QWEN2_FAST = """
from . import Qwen2TokenizerFast  # noqa: F401  (the real module exists — no alias)
"""

_STUB_DPM_SOLVER = '''
"""Stub of vibevoice/schedule/dpm_solver.py — the exact tensor chain that
dies under the v5 meta-device init for the cosine schedule."""
import torch


def betas_for_alpha_bar(num_diffusion_timesteps):
    # the real cosine path (dpm_solver.py:230-268) ends in torch.tensor —
    # a META tensor under the v5 init context
    return torch.tensor([0.5] * num_diffusion_timesteps, dtype=torch.float32)


class DPMSolverMultistepScheduler:
    def __init__(self, num_train_timesteps=1000, beta_schedule="linear", prediction_type="epsilon"):
        if beta_schedule == "cosine":
            self.betas = betas_for_alpha_bar(num_train_timesteps)
        else:
            self.betas = torch.linspace(0.0001, 0.02, num_train_timesteps, dtype=torch.float32)
        # torch.from_numpy is NOT redirected by the device context — this
        # stayed real on the rig while the sigmas chain died
        self.timesteps = torch.from_numpy(list(range(4)))
        self.sigmas = self.betas
        self.sigmas = self.sigmas.to("cpu")  # dpm_solver.py:295 — the operator's crash
'''

_STUB_MODEL = '''
"""Stub of vibevoice/modular/modeling_vibevoice_streaming_inference.py —
mirrors the v5-breaking surfaces: the scheduler built inside the model
__init__ (streaming.py:136), the no-argument tie_weights override
(:204), and the v4-shaped _prepare_generation_config call (:513)."""
from types import SimpleNamespace


class VibeVoiceStreamingConfig:
    pass


class VibeVoiceStreamingForConditionalGenerationInference:
    def __init__(self):
        from vibevoice.schedule.dpm_solver import DPMSolverMultistepScheduler

        self.noise_scheduler = DPMSolverMultistepScheduler(
            num_train_timesteps=1000,
            beta_schedule="cosine",
            prediction_type="v_prediction",
        )

    @classmethod
    def from_pretrained(cls, model_path, **kwargs):
        """Mirrors transformers v5: get_init_context instantiates the model
        inside `with torch.device("meta")` (modeling_utils.py:4412), then
        init_weights calls tie_weights(recompute_mapping=False) (:3319)."""
        import sys

        import torch

        kwarg = "dtype" if "dtype" in kwargs else ("torch_dtype" if "torch_dtype" in kwargs else "?")
        print(f"[STUB] from_pretrained dtype kwarg: {kwarg}", file=sys.stderr, flush=True)
        with torch.device("meta"):
            model = cls()
        model.tie_weights(recompute_mapping=False)
        return model

    def tie_weights(self):
        # the real from-source override takes no arguments
        return "tied"

    def _prepare_generation_config(self, generation_config, **kwargs):
        # the v5 GenerationMixin signature (generation/utils.py:1733)
        return generation_config, {"forwarded": kwargs}

    def generate(self, **kwargs):
        # the real package's v4-shaped call (line 513) — TypeErrors
        # against the v5 signature unless the tolerance is installed
        import numpy as np

        _cfg, model_kwargs = self._prepare_generation_config(
            object(),
            True,
            speech_start_id=1,
            speech_end_id=2,
            speech_diffusion_id=3,
        )
        assert model_kwargs == {"forwarded": {}}, "tolerance dropped more than it should"
        return SimpleNamespace(speech_outputs=[np.zeros(24000, dtype=np.float32)])

    def eval(self):
        return self

    def set_ddpm_inference_steps(self, num_steps=5):
        return None

    def to(self, target):
        return self

    def parameters(self):
        return []

    @property
    def device(self):
        return "cpu"
'''

_STUB_PROCESSOR = '''
"""Stub of VibeVoiceStreamingProcessor — reports the preset cache state
so the live test can prove the modernization reached the generate path."""
import sys

import soundfile as sf


class _Tokenizer:
    pass


class VibeVoiceStreamingProcessor:
    def __init__(self):
        self.tokenizer = _Tokenizer()

    @classmethod
    def from_pretrained(cls, model_path):
        return cls()

    def process_input_with_cached_prompt(
        self, text="", cached_prompt=None, padding=True,
        return_tensors="pt", return_attention_mask=True,
    ):
        import torch

        cache = cached_prompt.get("lm") if isinstance(cached_prompt, dict) else None
        pkv = getattr(cache, "past_key_values", None)
        modern = pkv is not None and hasattr(pkv, "layers") and not hasattr(pkv, "key_cache")
        print(
            f"[STUB] preset cache state: {'modern' if modern else 'LEGACY'}",
            file=sys.stderr,
            flush=True,
        )
        return {
            "input_ids": torch._Tensor([[1, 2, 3]]),
            "attention_mask": torch._Tensor([[1, 1, 1]]),
        }

    def save_audio(self, speech, output_path="", **kwargs):
        sf.write(output_path, speech, 24000)
        return output_path
'''


class TestLiveSubprocessProtocol:
    @pytest.mark.skipif(
        sys.platform not in ("linux", "win32", "darwin"), reason="unsupported platform"
    )
    def test_real_subprocess_survives_the_v5_meta_init(self, tmp_path, monkeypatch):
        """The REAL _vibevoice_subprocess.py against a v5-style stub stack:
        from_pretrained instantiates the model inside a meta-device
        context (the exact rig mechanism), the model __init__ builds the
        scheduler whose cosine betas go meta, tie_weights is called with
        v5 kwargs, generate makes the v4-shaped call, and the voice
        preset pickles 4.5x-format caches.

        First asserted: WITHOUT the V0.6.17 fixes the stub stack dies
        with the operator's EXACT error (the stub is proven to reproduce
        the defect). Then: the real engine + real subprocess must reach
        READY and synthesize audio, with every NOTE line in the drained
        stderr."""
        stub = tmp_path / "stub"
        for sub, name in (
            (_STUB_TORCH, "torch.py"),
            (_STUB_TF_INIT, "transformers/__init__.py"),
            (_STUB_TF_CACHE_UTILS, "transformers/cache_utils.py"),
            (_STUB_TF_MODELING_OUTPUTS, "transformers/modeling_outputs.py"),
            (_STUB_TF_AUTO_MAPPINGS, "transformers/models/auto/auto_mappings.py"),
            (_STUB_TF_AUTO_FACTORY, "transformers/models/auto/auto_factory.py"),
            (_STUB_TF_AUTO_INIT, "transformers/models/auto/__init__.py"),
            (_STUB_TF_QWEN2_INIT, "transformers/models/qwen2/__init__.py"),
            (_STUB_TF_QWEN2_FAST, "transformers/models/qwen2/tokenization_qwen2_fast.py"),
            (_STUB_DPM_SOLVER, "vibevoice/schedule/dpm_solver.py"),
            (_STUB_MODEL, "vibevoice/modular/modeling_vibevoice_streaming_inference.py"),
            (_STUB_PROCESSOR, "vibevoice/processor/vibevoice_streaming_processor.py"),
        ):
            p = stub / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sub.strip() + "\n", encoding="utf-8")
        for init, text in (
            ("transformers/models/__init__.py", ""),
            ("vibevoice/__init__.py", ""),
            ("vibevoice/schedule/__init__.py", ""),
            ("vibevoice/modular/__init__.py", ""),
            ("vibevoice/processor/__init__.py", ""),
        ):
            (stub / init).write_text(text, encoding="utf-8")

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        mk = tmp_path / "make_preset.py"
        mk.write_text(
            "import pickle, sys\n"
            "import torch\n"
            "from transformers.cache_utils import DynamicCache\n"
            "from transformers.modeling_outputs import BaseModelOutputWithPast\n"
            "\n"
            "def make_legacy():\n"
            "    c = DynamicCache()\n"
            "    # the 4.5x pickled state: plain tensor lists, no layers\n"
            "    c.key_cache = [torch._Tensor([[1.0]]) for _ in range(2)]\n"
            "    c.value_cache = [torch._Tensor([[2.0]]) for _ in range(2)]\n"
            "    c._seen_tokens = 1\n"
            "    return c\n"
            "\n"
            "preset = {}\n"
            "for name in ('lm', 'tts_lm', 'neg_lm', 'neg_tts_lm'):\n"
            "    out = BaseModelOutputWithPast()\n"
            "    out.past_key_values = make_legacy()\n"
            "    preset[name] = out\n"
            f"with open(r'{voices_dir / 'en-Carter_man.pt'}', 'wb') as f:\n"
            "    pickle.dump(preset, f)\n",
            encoding="utf-8",
        )
        env = {k: v for k, v in __import__("os").environ.items()}
        env["PYTHONPATH"] = str(stub)
        r = subprocess.run([sys.executable, str(mk)], env=env, capture_output=True)
        assert r.returncode == 0, r.stderr.decode()

        # Step 1 — the stub stack WITHOUT the V0.6.17 fixes dies with the
        # operator's exact error (the reproduction proof).
        no_fix = tmp_path / "no_fix.py"
        no_fix.write_text(
            "import sys\n"
            f"sys.path.insert(0, r'{stub}')\n"
            "from vibevoice.modular.modeling_vibevoice_streaming_inference import (\n"
            "    VibeVoiceStreamingForConditionalGenerationInference,\n"
            ")\n"
            "VibeVoiceStreamingForConditionalGenerationInference.from_pretrained('stub')\n",
            encoding="utf-8",
        )
        r = subprocess.run([sys.executable, str(no_fix)], env=env, capture_output=True)
        assert r.returncode != 0, "the stub stack must reproduce the defect unpatched"
        assert b"Cannot copy out of meta tensor" in r.stderr, r.stderr.decode()

        # Step 2 — the REAL engine + REAL subprocess (all four fixes
        # inside) must survive the same stack and synthesize audio.
        monkeypatch.setenv("PYTHONPATH", str(stub))

        from core.tts.vibevoice_engine import VibeVoiceEngine

        logs = _LogCollector()
        engine = VibeVoiceEngine(
            model_path=str(model_dir),
            voices_dir=str(voices_dir),
            default_voice="en-Carter_man",
            log_callback=logs,
        )
        out = tmp_path / "line.wav"
        try:
            result = engine.synthesize("hello line", out, "en-Carter_man", 1.0)
        finally:
            engine._cleanup()

        assert result == out, logs.joined()
        assert out.exists() and out.stat().st_size > 44
        j = logs.joined()
        # The load survived the v5 meta-device init and reached READY.
        assert "VibeVoice ready on CPU" in j
        # Every V0.6.17 line the operator will see on the rig.
        assert "transformers 5.17.0-stub" in j
        assert "meta-device model init detected" in j
        assert "building the VibeVoice noise scheduler on real CPU tensors" in j
        assert "rebuilt 4 legacy voice-preset cache(s)" in j
        # The modernized cache reached the generate path (the stub
        # processor reports what it was handed).
        assert "[STUB] preset cache state: modern" in j
        # The v5 dtype kwarg name was used (no deprecation warning path).
        assert "[STUB] from_pretrained dtype kwarg: dtype" in j
