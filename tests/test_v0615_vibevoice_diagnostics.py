"""V0.6.15 — the VibeVoice podcast diagnosability + compatibility batch.

The operator's live report: "the app has problem with vibevoice, podcast
tool, it generated text by llm, but vibevoice had error." The LLM script
step worked (V0.6.13 llama.cpp-first); the failure is inside the VibeVoice
subprocess chain — and the live log could not say WHY:

  * the engine DROPPED the subprocess traceback (only the error string
    surfaced — the JSON carries a 500-char traceback nobody logged);
  * torch.load used weights_only=False unconditionally — the official
    VibeVoice demo path is weights_only=True inside safe_globals, and
    torch < 2.6 has no safe_globals at all (AttributeError on the context
    manager itself → a hard generate error);
  * a CPU load (CUDA invisible in the subprocess) silently guaranteed the
    600 s per-line timeout — no warning while there was time to cancel;
  * no free-VRAM pre-flight — with llama-server holding the card for the
    LLM step of the SAME podcast, the 2.6 GB load dies on CUDA OOM with
    nothing naming the likely holder;
  * the podcast log never showed whether the VibeVoice model/voices paths
    were even valid.

This file pins the fixes hermetically (the _FakeProc pattern from
test_v182044) plus one LIVE protocol test that spawns the REAL
_vibevoice_subprocess.py against a stub torch/vibevoice tree — the exact
chain the rig runs, minus the 2.6 GB model.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIBE_ENGINE_SRC = (PROJECT_ROOT / "core" / "tts" / "vibevoice_engine.py").read_text(
    encoding="utf-8"
)
VIBE_SUB_SRC = (PROJECT_ROOT / "core" / "tts" / "_vibevoice_subprocess.py").read_text(
    encoding="utf-8"
)
AUDIO_GEN_SRC = (PROJECT_ROOT / "core" / "podcast" / "audio_generator.py").read_text(
    encoding="utf-8"
)


# ── Fake subprocess machinery (the test_v182044 pattern) ───────────────────


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

    def warnings(self) -> str:
        return "\n".join(msg for msg, lvl in self.lines if lvl == "WARNING")


def _install_fake_popen(monkeypatch, procs: list[_FakeProc]):
    def fake_popen(cmd, **kwargs):
        return procs.pop(0)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)


def _spawned_sub(logs, proc: _FakeProc):
    from core.tts._json_subprocess import PersistentJsonSubprocess

    sub = PersistentJsonSubprocess(
        name="VibeVoice", log=logs, stderr_prefix="[vibevoice]", stderr_level="DEBUG"
    )
    sub.spawn([sys.executable, "fake-script.py"], env={"PATH": ""})
    return sub


@pytest.fixture()
def vibe_engine(tmp_path):
    from core.tts.vibevoice_engine import VibeVoiceEngine

    logs = _LogCollector()
    model_dir = tmp_path / "vibe-model"
    model_dir.mkdir()
    engine = VibeVoiceEngine(model_path=str(model_dir), log_callback=logs)
    return engine, logs


# ── Engine: the load-error path ────────────────────────────────────────────


class TestLoadErrorDiagnostics:
    def test_load_error_forwards_traceback_to_log(self, vibe_engine, monkeypatch):
        """V0.6.15: the subprocess's traceback must reach the live log —
        the old path raised with the error string only, so the operator's
        paste-back never contained the WHY."""
        engine, logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps(
                    {
                        "status": "error",
                        "error": "CUDA init failed",
                        "traceback": (
                            "Traceback (most recent call last):\n"
                            '  File "modeling.py", line 10, in load\n'
                            "RuntimeError: CUDA init failed"
                        ),
                    }
                ),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError, match="Model load failed: CUDA init failed"):
            engine._ensure_model()

        j = logs.joined()
        assert "📋 VibeVoice load traceback:" in j, j
        assert "RuntimeError: CUDA init failed" in j, "the traceback body must be logged"

    def test_load_error_missing_package_appends_install_hint(self, vibe_engine, monkeypatch):
        """V0.6.15: 'No module named vibevoice' is the classic fresh-rig
        load failure — the raise now carries the install command."""
        engine, _logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps(
                    {
                        "status": "error",
                        "error": "No module named 'vibevoice'",
                        "traceback": "ModuleNotFoundError: No module named 'vibevoice'",
                    }
                ),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()
        assert "install VibeVoice: git clone" in str(excinfo.value), str(excinfo.value)
        assert "streamingtts" in str(excinfo.value)

    def test_load_error_other_causes_get_no_install_hint(self, vibe_engine, monkeypatch):
        engine, _logs = vibe_engine
        proc = _FakeProc([json.dumps({"status": "error", "error": "CUDA init failed"})])
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError) as excinfo:
            engine._ensure_model()
        assert "install VibeVoice" not in str(excinfo.value)

    def test_load_error_still_kills_before_raise(self, vibe_engine, monkeypatch):
        """The V18.20.4.4 (W-c2) contract survives the V0.6.15 edit: a
        reported load error must not leave the 2.6 GB child holding VRAM."""
        engine, _logs = vibe_engine
        proc = _FakeProc([json.dumps({"status": "error", "error": "boom"})])
        _install_fake_popen(monkeypatch, [proc])

        with pytest.raises(RuntimeError):
            engine._ensure_model()
        assert proc.killed == 1
        assert engine._sub is None
        assert engine._loaded is False


# ── Engine: the CPU-load warning ───────────────────────────────────────────


class TestCpuLoadWarning:
    def test_cpu_loading_status_logs_warning(self, vibe_engine, monkeypatch):
        """V0.6.15: device=cpu at load is the 600 s per-line timeout in
        slow motion — a WARNING must name it while there is time to cancel.
        Contract: WARNING only — the load itself still completes (fail-soft,
        short lines may still work)."""
        engine, logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "loading", "device": "cpu"}),
                json.dumps({"status": "ready", "device": "cpu"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert engine._loaded is True, "CPU load is a WARNING, never a block"
        w = logs.warnings()
        assert "loading on CPU" in w, w
        assert "600s timeout" in w, w
        assert "gpu_probe.log" in w, w

    def test_cuda_loading_status_no_cpu_warning(self, vibe_engine, monkeypatch):
        engine, logs = vibe_engine
        proc = _FakeProc(
            [
                json.dumps({"status": "loading", "device": "cuda"}),
                json.dumps({"status": "ready", "device": "cuda"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert "loading on CPU" not in logs.warnings()


# ── Engine: the free-VRAM pre-flight ───────────────────────────────────────


class _FakeTorchVram:
    """A torch stand-in for the pre-flight: cuda.is_available()=True and a
    scriptable mem_get_info."""

    def __init__(self, free_bytes: int, total_bytes: int) -> None:
        import types

        self.module = types.ModuleType("torch")
        self.module.__file__ = __file__  # the PATH-builder Path()s must work
        cuda = types.ModuleType("torch.cuda")

        def is_available():
            return True

        def mem_get_info():
            return (free_bytes, total_bytes)

        def get_device_name(idx=0):
            return "FakeGPU"

        class _Props:
            total_memory = total_bytes

            @staticmethod
            def get_device_properties(idx):
                return _Props()

        cuda.is_available = is_available
        cuda.mem_get_info = mem_get_info
        cuda.get_device_name = get_device_name
        self.module.cuda = cuda


class TestVramPreflight:
    def test_low_free_vram_warns_naming_llamacpp(self, vibe_engine, monkeypatch):
        """V0.6.15: < 3.5 GB free → a WARNING that names the likely holders
        (llama.cpp / Ollama) and the CUDA OOM consequence. Fail-soft: the
        spawn still happens."""
        engine, logs = vibe_engine
        low = _FakeTorchVram(free_bytes=1 * 1024**3, total_bytes=12 * 1024**3)
        monkeypatch.setitem(sys.modules, "torch", low.module)
        proc = _FakeProc(
            [
                json.dumps({"status": "ready", "device": "cuda"}),
            ]
        )
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        w = logs.warnings()
        assert "VRAM free" in w, w
        assert "llama.cpp / Ollama" in w, w
        assert "out-of-memory" in w, w
        assert engine._loaded is True, "the pre-flight is a WARNING, never a block"

    def test_healthy_free_vram_logs_info_only(self, vibe_engine, monkeypatch):
        engine, logs = vibe_engine
        ok = _FakeTorchVram(free_bytes=8 * 1024**3, total_bytes=12 * 1024**3)
        monkeypatch.setitem(sys.modules, "torch", ok.module)
        proc = _FakeProc([json.dumps({"status": "ready", "device": "cuda"})])
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert "GPU free VRAM: 8.0 GB" in logs.joined()
        assert "llama.cpp / Ollama" not in logs.warnings()

    def test_no_torch_in_parent_is_silent(self, vibe_engine, monkeypatch):
        """No torch in the app venv → no pre-flight, no failure (the
        sandbox/hermetic case: the load proceeds normally)."""
        engine, logs = vibe_engine
        monkeypatch.setitem(sys.modules, "torch", None)  # import → ImportError
        proc = _FakeProc([json.dumps({"status": "ready", "device": "cuda"})])
        _install_fake_popen(monkeypatch, [proc])

        engine._ensure_model()
        assert engine._loaded is True
        assert "GPU free VRAM" not in logs.joined()


# ── Engine: the generate-error path ────────────────────────────────────────


class TestGenerateErrorDiagnostics:
    def test_generate_error_forwards_traceback(self, vibe_engine, tmp_path):
        engine, logs = vibe_engine

        class _FakeSub:
            alive = True
            eof = False
            returncode = None

            def send(self, cmd):
                return True

            def read_json(self, timeout):
                return {
                    "status": "error",
                    "error": "CUDA out of memory. Tried to allocate 2.60 GiB",
                    "traceback": (
                        "Traceback (most recent call last):\n"
                        "RuntimeError: CUDA out of memory. Tried to allocate 2.60 GiB"
                    ),
                }

            def kill(self, reason=""):
                pass

        engine._sub = _FakeSub()
        engine._loaded = True

        with pytest.raises(RuntimeError, match="VibeVoice generation error"):
            engine.synthesize("hello line", tmp_path / "x.wav", "en-Carter_man", 1.0)
        j = logs.joined()
        assert "📋 VibeVoice generation traceback:" in j, j
        assert "Tried to allocate 2.60 GiB" in j, "the traceback body must be logged"

    def test_generate_error_kill_reason_not_over_truncated(self):
        """V0.6.15: the kill-reason slice widened 80 → 200 chars so the
        'Killing VibeVoice subprocess (reason: …)' line stays useful."""
        assert "err_msg[:200]" in VIBE_ENGINE_SRC


# ── Subprocess: the preset-load fallback chain (source pins) ──────────────


class TestSubprocessPresetLoadChain:
    def test_official_weights_only_true_path_first(self):
        """The OFFICIAL demo order: weights_only=True inside safe_globals
        is tried FIRST; the legacy weights_only=False is the fallback."""
        official = VIBE_SUB_SRC.find("preset_path, map_location=map_loc, weights_only=True")
        fallback = VIBE_SUB_SRC.find("preset_path, map_location=map_loc, weights_only=False")
        assert official != -1, "the official weights_only=True load must exist"
        assert fallback != -1, "the weights_only=False fallback must exist"
        assert official < fallback, "official path first, fallback second"

    def test_torch_below_2_6_attributeerror_branch(self):
        """torch < 2.6 has no torch.serialization.safe_globals at all — the
        AttributeError branch falls back to a plain torch.load instead of
        dying with 'module has no attribute safe_globals'."""
        assert "except AttributeError:" in VIBE_SUB_SRC
        plain = VIBE_SUB_SRC.find("return torch.load(preset_path, map_location=map_loc)")
        assert plain != -1, "the bare torch.load fallback must exist"

    def test_free_vram_reported_with_warning(self):
        """V0.6.15: the CUDA load path reports FREE VRAM (not just total)
        and warns under the ~3.5 GB floor naming llama.cpp / Ollama."""
        assert "MB free / {vram_mb} MB total" in VIBE_SUB_SRC
        assert "llama.cpp / Ollama may be " in VIBE_SUB_SRC

    def test_full_traceback_to_stderr_on_both_handlers(self):
        """The JSON traceback copy is truncated to 500 chars — the full
        traceback must ALSO go to stderr (the parent drains it into the
        live log) on BOTH the load and generate handlers."""
        assert "[SUBPROCESS] TRACEBACK (load):" in VIBE_SUB_SRC
        assert "[SUBPROCESS] TRACEBACK (generate):" in VIBE_SUB_SRC
        # stderr-first, JSON second (the log line precedes the protocol msg)
        tb_idx = VIBE_SUB_SRC.find("[SUBPROCESS] TRACEBACK (load):")
        json_idx = VIBE_SUB_SRC.find('"traceback": traceback.format_exc()[:500]')
        assert tb_idx < json_idx


# ── Audio generator: the config-truth log ─────────────────────────────────


class TestAudioGeneratorConfigTruth:
    def _line(self):
        from core.podcast.script_generator import ScriptLine

        return ScriptLine(host="A", text="Hello world", source_ref="", segment_type="")

    class _Settings:
        def __init__(self, model_path: str, voices_dir: str) -> None:
            self._d = {
                "tts.vibevoice_model_path": model_path,
                "tts.vibevoice_voices_dir": voices_dir,
            }

        def get(self, key, default=""):
            return self._d.get(key, default)

    def test_valid_paths_logged_ok(self, tmp_path, monkeypatch):
        from core.podcast.audio_generator import _synthesize_line

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        logs = _LogCollector()

        out = tmp_path / "line.wav"
        out.write_bytes(b"WAV" * 64)

        class _FakeEngine:
            def synthesize(self, text, out_path, voice, speed):
                return out_path

        monkeypatch.setattr(
            "core.tts.engine_cache.get_vibevoice_engine",
            lambda **kw: _FakeEngine(),
        )
        result = _synthesize_line(
            self._line(),
            out,
            "vibevoice:en-Carter_man",
            self._Settings(str(model_dir), str(voices_dir)),
            logs,
        )
        assert result == out
        j = logs.joined()
        assert f"VibeVoice model: {model_dir} — OK" in j, j
        assert f"VibeVoice voices dir: {voices_dir} — OK" in j, j

    def test_missing_paths_logged_not_found(self, tmp_path, monkeypatch):
        from core.podcast.audio_generator import _synthesize_line

        logs = _LogCollector()
        out = tmp_path / "line.wav"
        out.write_bytes(b"WAV" * 64)

        class _FakeEngine:
            def synthesize(self, text, out_path, voice, speed):
                return out_path

        monkeypatch.setattr(
            "core.tts.engine_cache.get_vibevoice_engine",
            lambda **kw: _FakeEngine(),
        )
        _synthesize_line(
            self._line(),
            out,
            "vibevoice:en-Carter_man",
            self._Settings(str(tmp_path / "gone"), str(tmp_path / "gone2")),
            logs,
        )
        j = logs.joined()
        assert "VibeVoice model:" in j and "— NOT FOUND" in j, j
        assert "VibeVoice voices dir:" in j and "— NOT FOUND" in j, j

    def test_empty_model_path_error_contract_unchanged(self, tmp_path):
        """The pre-existing contract: empty model path → the ERROR line +
        None (no engine spawn)."""
        from core.podcast.audio_generator import _synthesize_line

        logs = _LogCollector()
        result = _synthesize_line(
            self._line(),
            tmp_path / "line.wav",
            "vibevoice:en-Carter_man",
            self._Settings("", ""),
            logs,
        )
        assert result is None
        assert "VibeVoice model path not set" in logs.joined()
        assert "(not set)" in logs.joined()


# ── The LIVE protocol test — the REAL subprocess against a stub stack ──────


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

_STUB_TRANSFORMERS_CACHE_UTILS = '''
class DynamicCache:
    """Stub of transformers.cache_utils.DynamicCache."""


class BaseModelOutputWithPast:
    """Stub of transformers.modeling_outputs.BaseModelOutputWithPast."""
'''

_STUB_TRANSFORMERS_INIT = "from .cache_utils import BaseModelOutputWithPast, DynamicCache\n"

_STUB_MODEL = '''
"""Stub of VibeVoiceStreamingForConditionalGenerationInference."""
from types import SimpleNamespace


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
    def test_real_subprocess_end_to_end_with_stub_stack(self, tmp_path, monkeypatch):
        """Spawns the REAL _vibevoice_subprocess.py (the same spawn, minimal
        env, JSON handshake, preset load via the NEW weights_only=True path,
        generate, save, teardown the rig runs) against a stub torch /
        vibevoice tree — no 2.6 GB model, no GPU, but every protocol byte
        is the real code path. This is the test that would have caught any
        handshake regression and pins the official preset-load order live.
        """
        stub = tmp_path / "stub"
        for sub, name in (
            (_STUB_TORCH, "torch.py"),
            (_STUB_TRANSFORMERS_CACHE_UTILS, "transformers/cache_utils.py"),
            (_STUB_TRANSFORMERS_CACHE_UTILS, "transformers/modeling_outputs.py"),
            (_STUB_TRANSFORMERS_INIT, "transformers/__init__.py"),
            (_STUB_MODEL, "vibevoice/modular/modeling_vibevoice_streaming_inference.py"),
            (_STUB_PROCESSOR, "vibevoice/processor/vibevoice_streaming_processor.py"),
        ):
            p = stub / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(sub.strip() + "\n", encoding="utf-8")
        for init in (
            "vibevoice/__init__.py",
            "vibevoice/modular/__init__.py",
            "vibevoice/processor/__init__.py",
        ):
            (stub / init).write_text("", encoding="utf-8")

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        # The preset is pickled in a CLEAN subprocess (stub transformers on
        # PYTHONPATH) so the test process's module table stays untouched.
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
        # The load went through the REAL handshake, including the new
        # CPU WARNING (stub torch reports no CUDA).
        assert "VibeVoice ready on CPU" in logs.joined()
        assert "loading on CPU" in logs.warnings()
