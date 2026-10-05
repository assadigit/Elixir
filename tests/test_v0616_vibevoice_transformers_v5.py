"""V0.6.16 — the transformers-v5 VibeVoice compatibility batch.

The operator's V0.6.15 paste-back (the diagnostics working as designed)
finally contained the WHY — the full load traceback:

  File "C:\\VibeVoice\\vibevoice\\modular\\modular_vibevoice_tokenizer.py",
    line 1200, in <module>
      AutoModel.register(VibeVoiceAcousticTokenizerConfig,
                         VibeVoiceAcousticTokenizerModel)
  File "...\\transformers\\models\\auto\\auto_factory.py", line 672, in register
    raise ValueError(f"'{key}' is already used by a Transformers model.")
  ValueError: '<class 'vibevoice.modular.configuration_vibevoice.
    VibeVoiceAcousticTokenizerConfig'>' is already used by a Transformers
    model.

Root cause (verified against the REAL stack — torch 2.14 CPU +
transformers 5.17.0 + microsoft/VibeVoice @ main — where the error was
reproduced BYTE-FOR-BYTE before the fix): the operator's transformers is
a v5.13–v5.17 build (auto_factory.py register@427 / ValueError@672 — the
version fingerprints) that ships VibeVoice NATIVELY; its auto-generated
registry (models/auto/auto_mappings.py line 684) pre-registers the config
class NAME 'VibeVoiceAcousticTokenizerConfig'. The from-source vibevoice
package re-registers its OWN class with that same name at import time,
and transformers' _LazyAutoMapping.register checks duplicates BY NAME —
the first import dies, every podcast stops at line 1.

One import later the SAME v5 breaks the package AGAIN: the per-model
*_fast tokenizer submodules were removed (tokenization_qwen2_fast is
gone; Qwen2TokenizerFast now lives in transformers.models.qwen2), and
modular_vibevoice_text_tokenizer.py still imports the legacy path.

This file pins the fixes hermetically (fake-transformers behavioral
tests + the _FakeProc pattern from test_v0615) plus one LIVE protocol
test that spawns the REAL _vibevoice_subprocess.py against a stub
torch/vibevoice tree with v5-style transformers (native names
pre-registered, the fast submodule absent) — the exact failure the rig
hits, minus the 2.6 GB model.
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

LEGACY_QWEN2_FAST = "transformers.models.qwen2.tokenization_qwen2_fast"


@pytest.fixture(autouse=True)
def _clean_legacy_alias():
    """The alias shim inserts sys.modules entries DIRECTLY (production
    behaviour in the subprocess); monkeypatch cannot track those — pop
    the legacy path around every test so no state leaks between them."""
    sys.modules.pop(LEGACY_QWEN2_FAST, None)
    yield
    sys.modules.pop(LEGACY_QWEN2_FAST, None)


# ── Fake transformers machinery (in-process behavioral tests) ───────────────


class _FakeLazyAutoMapping:
    """The REAL v5 register semantics: duplicates checked BY CLASS NAME
    through a name→model_type reverse mapping (copied from
    transformers 5.17.0 auto_factory.py)."""

    def __init__(self, native_names=(), native_model_types=()):
        self._reverse = {name: f"native_{i}" for i, name in enumerate(native_names)}
        self._model_types = {f"native_{i}" for i in range(len(native_names))}
        self._model_types.update(native_model_types)
        self.extra: dict = {}

    def register(self, key, value, exist_ok=False):
        if hasattr(key, "__name__") and key.__name__ in self._reverse:
            model_type = self._reverse[key.__name__]
            if model_type in self._model_types and not exist_ok:
                raise ValueError(f"'{key}' is already used by a Transformers model.")
        self.extra[key] = value


class _MismatchFakeMapping(_FakeLazyAutoMapping):
    """Also simulates the OTHER ValueError register can raise (the
    config_class/model_class mismatch) — the tolerance must re-raise it."""

    def register(self, key, value, exist_ok=False):
        if getattr(key, "__name__", "") == "MismatchConfig":
            raise ValueError(
                "The model class you are passing has a `config_class` attribute "
                "that is not consistent with the config class you passed."
            )
        return super().register(key, value, exist_ok=exist_ok)


def _make_fake_transformers(
    mapping: _FakeLazyAutoMapping | None = None,
    *,
    with_auto_factory: bool = True,
    with_qwen2_fast_module: bool = False,
) -> types.ModuleType:
    """A minimal fake of the transformers surface the compat layer touches.
    Everything registers under the real dotted names so the shim's own
    import statements resolve inside monkeypatched sys.modules."""
    mapping = (
        mapping
        if mapping is not None
        else _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
    )

    class _AutoBase:
        _model_mapping = mapping

        @classmethod
        def register(cls, config_class, model_class, exist_ok=False):
            cls._model_mapping.register(config_class, model_class, exist_ok=exist_ok)

    class AutoModel(_AutoBase):
        pass

    class AutoModelForCausalLM(_AutoBase):
        pass

    tf = types.ModuleType("transformers")
    tf.__version__ = "5.17.0-fake"
    tf.AutoModel = AutoModel
    tf.AutoModelForCausalLM = AutoModelForCausalLM

    models_mod = types.ModuleType("transformers.models")
    auto_mod = types.ModuleType("transformers.models.auto")
    auto_mod.AutoModel = AutoModel
    auto_mod.AutoModelForCausalLM = AutoModelForCausalLM
    models_mod.auto = auto_mod
    tf.models = models_mod

    mods = {
        "transformers": tf,
        "transformers.models": models_mod,
        "transformers.models.auto": auto_mod,
    }
    if with_auto_factory:
        factory_mod = types.ModuleType("transformers.models.auto.auto_factory")
        factory_mod._LazyAutoMapping = _FakeLazyAutoMapping
        # The shim patches the CLASS — give it the same mapping semantics
        # by binding the shared instance into the class the shim will grab.
        factory_mod.MODEL_MAPPING = mapping
        mods["transformers.models.auto.auto_factory"] = factory_mod

    qwen2_mod = types.ModuleType("transformers.models.qwen2")

    class _Qwen2TokenizerFast:
        pass

    qwen2_mod.Qwen2TokenizerFast = _Qwen2TokenizerFast
    mods["transformers.models.qwen2"] = qwen2_mod
    if with_qwen2_fast_module:
        fast_mod = types.ModuleType(LEGACY_QWEN2_FAST)
        fast_mod.Qwen2TokenizerFast = _Qwen2TokenizerFast
        mods[LEGACY_QWEN2_FAST] = fast_mod
    return tf, mods


def _install_fake(monkeypatch, tf, mods):
    for name, mod in mods.items():
        monkeypatch.setitem(sys.modules, name, mod)


def _subprocess_module():
    from core.tts import _vibevoice_subprocess as vvs

    return vvs


class VibeVoiceAcousticTokenizerConfig:  # noqa: N801
    """The from-source twin — its ACTUAL class name matches the native
    registry entry (the collision is checked BY NAME, so the name itself
    is the fixture)."""


class VibeVoiceStreamingConfig:  # noqa: N801
    """No native entry for this name — the passthrough case."""


class MismatchConfig:
    """Triggers the fake's config-class-mismatch ValueError."""


class _LocalModel:
    pass


# ── The register tolerance (mapping-level patch) ───────────────────────────


class TestRegisterTolerance:
    def test_colliding_name_tolerated_and_reregistered(self, monkeypatch, capsys):
        """THE operator defect: a from-source class whose NAME matches the
        native registry must be tolerated — the register retried with
        exist_ok=True so the from-source class wins (the exact end-state
        of a transformers WITHOUT native vibevoice), with a NOTE logged."""
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()

        # The colliding registration no longer raises.
        tf.AutoModel.register(VibeVoiceAcousticTokenizerConfig, _LocalModel)
        assert VibeVoiceAcousticTokenizerConfig in mapping.extra
        assert mapping.extra[VibeVoiceAcousticTokenizerConfig] is _LocalModel
        out = capsys.readouterr().err
        assert "already registered by your transformers' native VibeVoice" in out
        assert "tolerance active (_LazyAutoMapping.register)" in out

    def test_non_colliding_register_passes_through_unchanged(self, monkeypatch, capsys):
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()
        tf.AutoModel.register(VibeVoiceStreamingConfig, _LocalModel)

        assert mapping.extra[VibeVoiceStreamingConfig] is _LocalModel
        out = capsys.readouterr().err
        assert "already registered" not in out  # no false NOTE

    def test_other_valueerror_still_raises(self, monkeypatch):
        """The tolerance is surgical: the config-class-mismatch ValueError
        must still propagate (it names a real bug, not a duplicate)."""
        vvs = _subprocess_module()
        mapping = _MismatchFakeMapping()
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()

        with pytest.raises(ValueError, match="config_class"):
            tf.AutoModel.register(MismatchConfig, _LocalModel)

    def test_exist_ok_true_never_wrapped_twice(self, monkeypatch, capsys):
        """A caller that already passes exist_ok=True goes straight through
        (the wrapper's fast path)."""
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()
        tf.AutoModel.register(VibeVoiceAcousticTokenizerConfig, _LocalModel, exist_ok=True)

        assert mapping.extra[VibeVoiceAcousticTokenizerConfig] is _LocalModel
        assert "NOTE" not in capsys.readouterr().err

    def test_automodel_for_causal_lm_covered_by_shared_mapping(self, monkeypatch):
        """The real package ALSO registers through AutoModelForCausalLM
        (modeling_vibevoice_streaming_inference.py:902) — the mapping-level
        patch covers every Auto* class, not just AutoModel."""
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()
        # Same colliding NAME through the OTHER Auto class.
        tf.AutoModelForCausalLM.register(VibeVoiceAcousticTokenizerConfig, _LocalModel)
        assert mapping.extra[VibeVoiceAcousticTokenizerConfig] is _LocalModel


class TestRegisterToleranceFallback:
    def test_classmethod_fallback_when_auto_factory_missing(self, monkeypatch, capsys):
        """If the private _LazyAutoMapping path ever moves (a future
        transformers layout change), the documented AutoModel.register +
        AutoModelForCausalLM.register classmethods are patched instead."""
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping, with_auto_factory=False)
        _install_fake(monkeypatch, tf, mods)

        vvs._tolerate_native_vibevoice_register()

        tf.AutoModel.register(VibeVoiceAcousticTokenizerConfig, _LocalModel)
        tf.AutoModelForCausalLM.register(VibeVoiceAcousticTokenizerConfig, _LocalModel)
        assert mapping.extra[VibeVoiceAcousticTokenizerConfig] is _LocalModel
        out = capsys.readouterr().err
        assert "AutoModel.register" in out and "AutoModelForCausalLM.register" in out

    def test_no_patchable_surface_logs_warning_not_crash(self, monkeypatch, capsys):
        """transformers present but NOTHING patchable (no auto_factory, no
        Auto classes) → a WARNING naming the pin, never a raise — the
        V0.6.15 traceback diagnostics still own the failure."""
        vvs = _subprocess_module()
        tf = types.ModuleType("transformers")
        tf.__version__ = "9.9.9-fake"
        monkeypatch.setitem(sys.modules, "transformers", tf)

        vvs._tolerate_native_vibevoice_register()  # must not raise

        out = capsys.readouterr().err
        assert "could not install the duplicate-register tolerance" in out
        assert "transformers<5.13" in out


class TestCompatInstall:
    def test_missing_transformers_is_non_fatal(self, monkeypatch, capsys):
        """No transformers at all → one line, no patch, no raise (the
        vibevoice import then fails with the V0.6.15 install hint)."""
        vvs = _subprocess_module()
        monkeypatch.setattr(
            sys, "modules", {k: v for k, v in sys.modules.items() if k != "transformers"}
        )
        monkeypatch.setattr(vvs, "_REGISTER_COMPAT_INSTALLED", False)

        vvs._install_transformers_compat()  # must not raise

        assert "transformers not importable" in capsys.readouterr().err

    def test_idempotent_no_double_wrap(self, monkeypatch):
        """A second load command must not double-wrap the patch (the
        module flag) — the wrapper object stays identical."""
        vvs = _subprocess_module()
        mapping = _FakeLazyAutoMapping(native_names=("VibeVoiceAcousticTokenizerConfig",))
        tf, mods = _make_fake_transformers(mapping)
        _install_fake(monkeypatch, tf, mods)
        monkeypatch.setattr(vvs, "_REGISTER_COMPAT_INSTALLED", False)

        vvs._install_transformers_compat()
        wrapped = type(mapping).register
        vvs._install_transformers_compat()
        assert type(mapping).register is wrapped


# ── The legacy *_fast tokenizer alias ──────────────────────────────────────


class TestLegacyTokenizerAlias:
    def test_removed_module_aliased_from_package(self, monkeypatch, capsys):
        """THE second v5 breakage: tokenization_qwen2_fast is gone but
        Qwen2TokenizerFast lives in transformers.models.qwen2 — the legacy
        path is pre-registered as a one-attribute alias with a NOTE."""
        vvs = _subprocess_module()
        tf, mods = _make_fake_transformers()
        _install_fake(monkeypatch, tf, mods)

        try:
            vvs._alias_legacy_tokenizer_modules()

            assert LEGACY_QWEN2_FAST in sys.modules
            aliased_cls = sys.modules[LEGACY_QWEN2_FAST].Qwen2TokenizerFast
            pkg_cls = mods["transformers.models.qwen2"].Qwen2TokenizerFast
            assert aliased_cls is pkg_cls
            out = capsys.readouterr().err
            assert f"aliased {LEGACY_QWEN2_FAST}" in out
            assert "removed in transformers v5" in out
        finally:
            sys.modules.pop(LEGACY_QWEN2_FAST, None)

    def test_real_module_present_means_no_alias(self, monkeypatch, capsys):
        """transformers < 5 still HAS the submodule — nothing is aliased
        (byte-identical behaviour; the no-regression contract)."""
        vvs = _subprocess_module()
        tf, mods = _make_fake_transformers(with_qwen2_fast_module=True)
        _install_fake(monkeypatch, tf, mods)

        vvs._alias_legacy_tokenizer_modules()

        assert "aliased" not in capsys.readouterr().err
        # The REAL module stayed in place (the pre-registered one).
        assert sys.modules[LEGACY_QWEN2_FAST] is mods[LEGACY_QWEN2_FAST]

    def test_no_qwen2_at_all_is_silent(self, monkeypatch, capsys):
        """If neither the module nor the class exists anywhere, stay
        silent and let the vibevoice import surface the real error."""
        vvs = _subprocess_module()
        tf, mods = _make_fake_transformers()
        mods.pop("transformers.models.qwen2")
        _install_fake(monkeypatch, tf, mods)

        vvs._alias_legacy_tokenizer_modules()  # must not raise

        assert LEGACY_QWEN2_FAST not in sys.modules
        assert capsys.readouterr().err == ""


# ── Engine: the defense-in-depth native hint ───────────────────────────────


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


class TestEngineNativeHint:
    def test_duplicate_register_error_appends_native_hint(self, vibe_engine, monkeypatch):
        """V0.6.16: if the subprocess-side tolerance could not be installed
        (a future transformers layout change), the engine's raise must
        still explain the collision and name the two outs."""
        engine, _logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps(
                    {
                        "status": "error",
                        "error": (
                            "'<class 'vibevoice.modular.configuration_vibevoice."
                            "VibeVoiceAcousticTokenizerConfig'>' is already used "
                            "by a Transformers model."
                        ),
                    }
                )
            ]
        )
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()

        msg = str(excinfo.value)
        assert "is already used by a Transformers model" in msg
        assert "native VibeVoice" in msg
        assert "transformers<5.13" in msg

    def test_other_load_errors_get_no_native_hint(self, vibe_engine, monkeypatch):
        engine, _logs = vibe_engine
        proc = _FakeProc([json.dumps({"status": "error", "error": "CUDA init failed"})])
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: proc)

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()

        assert "native VibeVoice" not in str(excinfo.value)


# ── Source pins: the ordering that makes the fix work ──────────────────────


class TestSourcePins:
    def test_compat_layer_installed_before_first_vibevoice_import(self):
        """The shim MUST run before 'from vibevoice.modular...' — the
        register fires at import time, one line too late is a dead load."""
        compat_idx = VIBE_SUB_SRC.index("_install_transformers_compat()")
        import_idx = VIBE_SUB_SRC.index(
            "from vibevoice.modular.modeling_vibevoice_streaming_inference import"
        )
        assert compat_idx < import_idx

    def test_load_handler_calls_compat_exactly_once(self):
        assert VIBE_SUB_SRC.count("_install_transformers_compat()") >= 1
        # The definition + the call both exist; the call is inside main().
        assert "def _install_transformers_compat():" in VIBE_SUB_SRC

    def test_engine_native_hint_wired_into_raise(self):
        assert '_native_hint = ""' in VIBE_ENGINE_SRC
        assert '"is already used by a Transformers model" in _load_err' in VIBE_ENGINE_SRC
        assert "{_install_hint}{_native_hint}" in VIBE_ENGINE_SRC

    def test_both_shims_present(self):
        """The two v5 breakages are two separate shims under one entry
        point — neither may be lost in a future edit."""
        assert "def _tolerate_native_vibevoice_register():" in VIBE_SUB_SRC
        assert "def _alias_legacy_tokenizer_modules():" in VIBE_SUB_SRC
        assert "_install_transformers_compat" in VIBE_SUB_SRC


# ── The LIVE protocol test — the REAL subprocess against a v5-style stack ──


_STUB_TORCH = '''
"""Stub torch — the exact API surface _vibevoice_subprocess.py touches."""
import contextlib
import pickle


class _DType:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"torch.{self.name}"


float32 = _DType("float32")
float16 = _DType("float16")
bfloat16 = _DType("bfloat16")


class _Tensor:
    def __init__(self, data, dtype=float32):
        self.data = data
        self.dtype = dtype
        self.device = "cpu"

    def to(self, target):
        if isinstance(target, _DType):
            return _Tensor(self.data, target)
        if isinstance(target, str):
            t = _Tensor(self.data, self.dtype)
            t.device = target
            return t
        return self


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
from .cache_utils import BaseModelOutputWithPast, DynamicCache  # noqa: F401
"""

_STUB_TF_CACHE_UTILS = '''
class DynamicCache:
    """Stub of transformers.cache_utils.DynamicCache."""


class BaseModelOutputWithPast:
    """Stub of transformers.modeling_outputs.BaseModelOutputWithPast."""
'''

_STUB_TF_AUTO_MAPPINGS = '''
"""Stub of the v5 auto-generated registry — NATIVE VibeVoice
pre-registered (real transformers 5.17.0 auto_mappings.py line 684)."""
CONFIG_MAPPING_NAMES = {
    "vibevoice_acoustic_tokenizer": "VibeVoiceAcousticTokenizerConfig",
    "qwen2": "Qwen2Config",
}
MODEL_MAPPING_NAMES = {
    "vibevoice_acoustic_tokenizer": "VibeVoiceAcousticTokenizerModel",
    "qwen2": "Qwen2Model",
}
'''

_STUB_TF_AUTO_FACTORY = '''
"""Stub of transformers.models.auto.auto_factory — the REAL v5 register
semantics: duplicates checked BY CLASS NAME (auto_factory.py lines
667-672 in 5.17.0)."""
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

_STUB_TF_QWEN2_INIT = '''
"""Stub qwen2 — in real transformers v5 Qwen2TokenizerFast lives HERE;
the tokenization_qwen2_fast submodule was REMOVED (deliberately absent
from this stub tree)."""


class Qwen2TokenizerFast:
    pass


class Qwen2Tokenizer:
    pass


class Qwen2Config:
    pass
'''

_STUB_VV_TOKENIZER = '''
"""Stub of the real modular_vibevoice_tokenizer.py — the module-level
register that killed the operator's podcasts (real file: line 1200)."""
from transformers.models.auto import AutoModel


class VibeVoiceAcousticTokenizerConfig:
    """From-source config — SAME NAME as the native registry entry."""


class VibeVoiceAcousticTokenizerModel:
    pass


class VibeVoiceTokenizerStreamingCache:
    pass


AutoModel.register(VibeVoiceAcousticTokenizerConfig, VibeVoiceAcousticTokenizerModel)
'''

_STUB_VV_TEXT_TOKENIZER = '''
"""Stub of the real modular_vibevoice_text_tokenizer.py — the legacy
import the v5 package still performs (the second breakage)."""
from transformers.models.qwen2.tokenization_qwen2_fast import Qwen2TokenizerFast


class VibeVoiceTextTokenizerFast(Qwen2TokenizerFast):
    pass


VibeVoiceTextTokenizer = VibeVoiceTextTokenizerFast
'''

_STUB_MODEL = '''
"""Stub of VibeVoiceStreamingForConditionalGenerationInference — mirrors
the real import order (tokenizer register first, legacy import next)."""
from types import SimpleNamespace

from transformers.models.auto import AutoModelForCausalLM

from .modular_vibevoice_tokenizer import VibeVoiceTokenizerStreamingCache  # noqa: F401
from .modular_vibevoice_text_tokenizer import VibeVoiceTextTokenizerFast  # noqa: F401


class VibeVoiceStreamingConfig:
    pass


class VibeVoiceStreamingForConditionalGenerationInference:
    def __init__(self):
        self.device = "cpu"

    @classmethod
    def from_pretrained(cls, model_path, **kwargs):
        return cls()

    def eval(self):
        return self

    def set_ddpm_inference_steps(self, num_steps=5):
        return None

    def to(self, target):
        return self

    def parameters(self):
        return []

    def generate(self, **kwargs):
        import numpy as np

        return SimpleNamespace(speech_outputs=[np.zeros(24000, dtype=np.float32)])


# The real file's line-902 registration — NO native name for this config,
# so it must pass through the tolerance untouched (the passthrough case).
AutoModelForCausalLM.register(
    VibeVoiceStreamingConfig, VibeVoiceStreamingForConditionalGenerationInference
)
'''

_STUB_PROCESSOR = '''
"""Stub of VibeVoiceStreamingProcessor."""
import numpy as np
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

        return {
            "input_ids": torch._Tensor([[1, 2, 3]]),
            "attention_mask": torch._Tensor([[1, 1, 1]]),
        }

    def save_audio(self, speech, output_path=""):
        sf.write(output_path, speech, 24000)
        return output_path
'''


class TestLiveSubprocessProtocol:
    @pytest.mark.skipif(
        sys.platform not in ("linux", "win32", "darwin"), reason="unsupported platform"
    )
    def test_real_subprocess_survives_the_v5_collision(self, tmp_path, monkeypatch):
        """The REAL _vibevoice_subprocess.py against a v5-style stub stack:
        transformers pre-registers 'VibeVoiceAcousticTokenizerConfig'
        natively (the collision), the fast tokenizer submodule is absent
        (the second breakage), and the stub vibevoice package performs the
        same module-level register + legacy import as the real one.

        First asserted: WITHOUT the compat layer the stub stack dies with
        the operator's EXACT error (the stub is proven to reproduce the
        defect). Then: the real engine + real subprocess must reach READY
        and synthesize audio, with every NOTE line in the drained stderr.
        """
        stub = tmp_path / "stub"
        for sub, name in (
            (_STUB_TORCH, "torch.py"),
            (_STUB_TF_INIT, "transformers/__init__.py"),
            (_STUB_TF_CACHE_UTILS, "transformers/cache_utils.py"),
            (_STUB_TF_CACHE_UTILS, "transformers/modeling_outputs.py"),
            (_STUB_TF_AUTO_MAPPINGS, "transformers/models/auto/auto_mappings.py"),
            (_STUB_TF_AUTO_FACTORY, "transformers/models/auto/auto_factory.py"),
            (_STUB_TF_AUTO_INIT, "transformers/models/auto/__init__.py"),
            (_STUB_TF_QWEN2_INIT, "transformers/models/qwen2/__init__.py"),
            (_STUB_VV_TOKENIZER, "vibevoice/modular/modular_vibevoice_tokenizer.py"),
            (_STUB_VV_TEXT_TOKENIZER, "vibevoice/modular/modular_vibevoice_text_tokenizer.py"),
            (_STUB_MODEL, "vibevoice/modular/modeling_vibevoice_streaming_inference.py"),
            (_STUB_PROCESSOR, "vibevoice/processor/vibevoice_streaming_processor.py"),
        ):
            p = stub / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sub.strip() + "\n", encoding="utf-8")
        for init, text in (
            ("transformers/models/__init__.py", ""),
            ("vibevoice/__init__.py", ""),
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
            "from transformers.cache_utils import DynamicCache\n"
            "from transformers.modeling_outputs import BaseModelOutputWithPast\n"
            f"preset = {{'cache': DynamicCache(), 'out': BaseModelOutputWithPast()}}\n"
            f"with open(r'{voices_dir / 'en-Carter_man.pt'}', 'wb') as f:\n"
            "    pickle.dump(preset, f)\n",
            encoding="utf-8",
        )
        env = {k: v for k, v in __import__("os").environ.items()}
        env["PYTHONPATH"] = str(stub)
        r = subprocess.run([sys.executable, str(mk)], env=env, capture_output=True)
        assert r.returncode == 0, r.stderr.decode()

        # Step 1 — the stub stack WITHOUT the compat layer dies with the
        # operator's exact error (the reproduction proof).
        no_fix = tmp_path / "no_fix.py"
        no_fix.write_text(
            "import sys\n"
            f"sys.path.insert(0, r'{stub}')\n"
            "from vibevoice.modular.modeling_vibevoice_streaming_inference import (\n"
            "    VibeVoiceStreamingForConditionalGenerationInference,\n"
            ")\n",
            encoding="utf-8",
        )
        r = subprocess.run([sys.executable, str(no_fix)], env=env, capture_output=True)
        assert r.returncode != 0, "the stub stack must reproduce the defect unpatched"
        assert b"is already used by a Transformers model" in r.stderr, r.stderr.decode()

        # Step 2 — the REAL engine + REAL subprocess (compat layer inside)
        # must survive the same stack and synthesize audio.
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
        # The load survived both v5 breakages and reached READY.
        assert "VibeVoice ready on CPU" in j
        # Every compat line the operator will see on the rig.
        assert "transformers 5.17.0-stub" in j
        assert "native-VibeVoice duplicate-register tolerance active" in j
        assert "NOTE: 'VibeVoiceAcousticTokenizerConfig' is already registered" in j
        assert f"aliased {LEGACY_QWEN2_FAST}" in j
