"""V4.5.0 + V4.7.16 + V11.32.0: NeuTTS-Air engine — voice-cloning TTS via GGUF.

V11.32.0 — GPU-FIRST REWRITE (fixes "still too slow"):
  * Devices are read from settings (``tts.neutts_backbone_device`` /
    ``tts.neutts_codec_device``), defaulting to ``"cuda"`` for BOTH. The
    previous version hard-coded ``backbone="cpu"`` which forced the
    expensive inference onto the CPU (3–5 min/segment). Now the GPU is
    used by default — a ~20× speedup.
  * **In-process mode is the primary path.** The persistent-subprocess
    mode deadlocked on CUDA inference because NeuTTS prints progress /
    warnings to ``stdout`` and the parent only drained ``stdout`` after
    sending a command — the pipe buffer filled (~64 KB on Windows) and
    the child blocked on its next ``print``. The subprocess script now
    redirects library output to ``stderr`` (which is continuously
    drained) and reserves ``stdout`` for the JSON protocol only.
    Subprocess mode is still available via the
    ``tts.neutts_use_subprocess`` setting for environments where the
    app's main torch conflicts with NeuTTS.
  * A CUDA **pre-check** runs before the model is loaded. If CUDA is
    requested but ``torch.cuda.is_available()`` is False, the engine
    logs a clear, actionable message (e.g. "CPU-only torch installed —
    install the CUDA build") and falls back to CPU instead of crashing
    with an opaque "No CUDA GPUs are available".
  * ``torch.cuda.synchronize()`` is called after load and after each
    ``infer()`` to flush pending kernels — prevents stream deadlocks
    that manifested as "hangs after ready".
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from core.tts.engine import LogFn, TTSEngine

_NEUTTS_MAX_CHARS = 400

# V18.20.3.12 (F821 fix): NeuTTSEngine.__init__ logs the version stamp via a
# bare ``_ENGINE_VERSION`` reference (:317), which resolves to THIS module-level
# constant (the class attribute of the same name at :300 is invisible to bare
# lookups from inside methods — the original NameError crash at construction).
# Value identical to the class attribute: "V11.32.3".
_ENGINE_VERSION = "V11.32.3"


def _split_long_line(text: str, max_chars: int = _NEUTTS_MAX_CHARS) -> list[str]:
    """Split a line longer than ``max_chars`` on sentence boundaries."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts = re.split(r"(?<=[\.!?؟])\s+", text)
    chunks: list[str] = []
    current = ""
    for p in parts:
        if not p:
            continue
        if len(current) + len(p) + 1 <= max_chars:
            current = (current + " " + p).strip() if current else p
        else:
            if current:
                chunks.append(current)
            while len(p) > max_chars:
                chunks.append(p[:max_chars])
                p = p[max_chars:].lstrip()
            current = p
    if current:
        chunks.append(current)
    return chunks


def _cuda_available() -> bool:
    """Return True if torch is importable and reports a CUDA GPU.

    V11.32.3: logs the reason if CUDA is unavailable, so we can diagnose
    why the app falls back to CPU.
    """
    try:
        import torch  # type: ignore

        avail = torch.cuda.is_available()
        count = torch.cuda.device_count() if avail else 0
        return bool(avail and count > 0)
    except ImportError:
        return False
    except Exception:
        return False


def _cuda_available_with_reason() -> tuple[bool, str]:
    """V11.32.3: like _cuda_available() but returns a human-readable reason."""
    try:
        import torch  # type: ignore
    except ImportError as e:
        return (False, f"torch not importable: {e}")
    except Exception as e:
        return (False, f"torch import error: {e}")
    try:
        avail = torch.cuda.is_available()
    except Exception as e:
        return (False, f"torch.cuda.is_available() raised: {e}")
    if not avail:
        return (
            False,
            f"torch {torch.__version__}: cuda.is_available()=False "
            f"(CPU-only build? compiled_cuda={getattr(torch.version, 'cuda', None)})",
        )
    try:
        count = torch.cuda.device_count()
    except Exception as e:
        return (False, f"device_count() raised: {e}")
    if count == 0:
        return (False, "cuda.is_available()=True but device_count()=0")
    return (True, f"torch {torch.__version__}: {count} GPU(s), [0]={torch.cuda.get_device_name(0)}")


def _cuda_summary() -> str:
    """Human-readable CUDA status for logging / diagnostics."""
    try:
        import torch  # type: ignore
    except Exception as e:
        return f"torch not importable ({e})"
    if not torch.cuda.is_available():
        ver = getattr(torch, "__version__", "?")
        return f"torch {ver}: CUDA NOT available (CPU-only build?)"
    try:
        n = torch.cuda.device_count()
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        return f"torch {torch.__version__}: {n} GPU(s); [0]={name} (compute {cap[0]}.{cap[1]})"
    except Exception as e:
        return f"torch {torch.__version__}: CUDA available but query failed ({e})"


def _resolve_devices(backbone: str, codec: str, log) -> tuple[str, str]:
    """Resolve "auto" / validate device choices against actual CUDA availability.

    V11.32.3: uses _cuda_available_with_reason() so the log shows EXACTLY
    why CUDA is (un)available. If CUDA is available but the setting is
    "cpu", AUTO-UPGRADE to "cuda".

    Returns the resolved (backbone, codec) tuple. Logs the decision.
    """
    cuda_ok, cuda_reason = _cuda_available_with_reason()
    log(f"  💻 CUDA check: {cuda_reason}", "INFO")
    log(f"  📋 Raw setting: backbone={backbone!r}, codec={codec!r}", "INFO")

    def _pick(dev: str, label: str) -> str:
        if dev == "auto":
            chosen = "cuda" if cuda_ok else "cpu"
            log(f"  🔧 {label} device: auto → {chosen}", "INFO")
            return chosen
        if dev == "cuda" and not cuda_ok:
            log(
                f"  ⚠️ {label} device requested 'cuda' but CUDA is unavailable — "
                f"falling back to CPU. Reason: {cuda_reason}",
                "WARNING",
            )
            return "cpu"
        # V11.32.2: auto-upgrade CPU → CUDA when a GPU is available.
        if dev == "cpu" and cuda_ok:
            log(
                f"  🚀 {label} device was 'cpu' but CUDA is available — "
                f"AUTO-UPGRADING to 'cuda' for speed. "
                f"(To force CPU, install CPU-only torch.)",
                "WARNING",
            )
            return "cuda"
        log(f"  🔧 {label} device: {dev}", "INFO")
        return dev

    return _pick(backbone, "Backbone"), _pick(codec, "Codec")


# The persistent subprocess script. V11.32.0: library output is forced
# to stderr so stdout is reserved exclusively for the JSON protocol —
# this prevents the buffer-fill deadlock that hung CUDA inference.
_PERSISTENT_SCRIPT = r'''
import sys, os, json, traceback

# ── V11.32.0: reserve stdout for JSON protocol ──────────────────────
# Libraries (NeuTTS, torch, transformers, phonemizer) love to print
# progress bars and warnings to stdout. On Windows the pipe buffer is
# ~64 KB; once it fills, the child blocks on the next print() and the
# parent (which only drains stdout after sending a command) deadlocks.
# Redirect the libraries' stdout to stderr; we write JSON with a saved
# handle to the real stdout.
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr

def send(obj):
    """Write one JSON message on the protocol pipe."""
    _REAL_STDOUT.write(json.dumps(obj) + "\n")
    _REAL_STDOUT.flush()

# Setup
project_path = sys.argv[1] if len(sys.argv) > 1 else r"G:\Program Files\neutts-air"
gguf_path = sys.argv[2] if len(sys.argv) > 2 else ""
backbone_device = sys.argv[3] if len(sys.argv) > 3 else "cpu"
codec_device = sys.argv[4] if len(sys.argv) > 4 else "cuda"
language = sys.argv[5] if len(sys.argv) > 5 else "en-us"

sys.path.insert(0, project_path)
os.chdir(project_path)

import soundfile as sf
import numpy as np

send({"status": "loading"})

try:
    from neutts import NeuTTS
    tts = NeuTTS(
        backbone_repo=gguf_path,
        backbone_device=backbone_device,
        codec_device=codec_device,
        language=language,
    )
    # V11.32.0: flush any pending CUDA kernels before declaring ready.
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        logger.debug("best-effort op failed [neutts_engine:send:L227]", exc_info=True)
    send({"status": "ready"})
except Exception as e:
    send({"status": "error", "error": str(e), "traceback": traceback.format_exc()})
    sys.exit(1)

# Reference cache — encode each voice only once
# V9.0.0 P3-6: capped to prevent unbounded memory growth on long conversions
_ref_cache = {}
_REF_CACHE_MAX = 50

# Main loop: read JSON commands from stdin
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        cmd = json.loads(line)
    except json.JSONDecodeError:
        continue

    if cmd.get("action") == "quit":
        break
    if cmd.get("action") != "generate":
        continue

    text = cmd.get("text", "")
    ref_wav = cmd.get("ref_wav", "")
    ref_text = cmd.get("ref_text", "")
    out_path = cmd.get("out_path", "")

    try:
        # Encode reference (cached)
        if ref_wav not in _ref_cache:
            if len(_ref_cache) >= _REF_CACHE_MAX:
                _ref_cache.pop(next(iter(_ref_cache)), None)
            ref_codes = tts.encode_reference(ref_wav)
            _ref_cache[ref_wav] = ref_codes
        else:
            ref_codes = _ref_cache[ref_wav]

        # Generate
        audio = tts.infer(text=text, ref_codes=ref_codes, ref_text=ref_text)
        # V11.32.0: synchronize CUDA so the tensor is fully materialised
        # before we pull it to the CPU. Prevents partial-read hangs.
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.synchronize()
        except Exception:
            logger.debug("best-effort op failed [neutts_engine:send:L277]", exc_info=True)
        if hasattr(audio, "cpu"):
            audio = audio.cpu().numpy()
        else:
            audio = np.asarray(audio)

        sf.write(out_path, audio, 24000)
        send({"status": "ok", "out_path": out_path, "duration": len(audio)/24000})
    except Exception as e:
        send({"status": "error", "error": str(e), "traceback": traceback.format_exc()})
'''


class NeuTTSEngine(TTSEngine):
    """Voice-cloning TTS via NeuTTS-Air GGUF.

    V11.32.3: GPU-first with IMMEDIATE resolution. The constructor reads
    settings, checks CUDA, and resolves the device RIGHT AWAY (not
    lazily) so the log output appears before NeuTTS prints its own
    "Loading backbone from: ... on cpu/cuda" line. This makes it
    impossible to miss which device is being used.
    """

    # V11.32.3: version stamp — printed at construction so we can verify
    # the correct (non-cached) code is running.
    _ENGINE_VERSION = "V11.32.3"

    def __init__(
        self,
        gguf_path: Path,
        neutts_project_path: Path,
        backbone_device: str = "cuda",
        codec_device: str = "cuda",
        language: str = "en-us",
        log_callback: LogFn | None = None,
    ) -> None:
        super().__init__(log_callback)
        self.gguf_path = Path(gguf_path)
        self.neutts_project_path = Path(neutts_project_path)

        # V11.32.3: version stamp — proves this code is running.
        self.log(f"  ═══ NeuTTSEngine {_ENGINE_VERSION} ═══", "INFO")

        # V11.32.0: read device preferences from settings if available,
        # falling back to the constructor args.
        self._backbone_pref = self._read_setting("tts.neutts_backbone_device", backbone_device)
        self._codec_pref = self._read_setting("tts.neutts_codec_device", codec_device)
        self.log(
            f"  📋 Settings read: backbone_pref={self._backbone_pref!r}, "
            f"codec_pref={self._codec_pref!r}",
            "INFO",
        )

        # V11.32.3: NEUTTS_FORCE_CUDA env var — belt-and-suspenders override.
        # If set to "1", forces both devices to "cuda" regardless of settings.
        force_cuda = os.environ.get("NEUTTS_FORCE_CUDA", "").strip() == "1"
        if force_cuda:
            self.log("  🔧 NEUTTS_FORCE_CUDA=1 → forcing both devices to 'cuda'", "WARNING")
            self._backbone_pref = "cuda"
            self._codec_pref = "cuda"

        # V11.32.3: resolve devices IMMEDIATELY (not lazily) so the log
        # appears before NeuTTS's own "Loading backbone..." line.
        self.backbone_device, self.codec_device = _resolve_devices(
            self._backbone_pref, self._codec_pref, self.log
        )
        self.log(
            f"  ✅ FINAL DECISION: backbone={self.backbone_device!r}, codec={self.codec_device!r}",
            "INFO",
        )

        self.language = language
        self._voice_manager = None

        # V11.32.0: choose the Python interpreter for subprocess mode.
        self._venv_python = self.neutts_project_path / "venv" / "Scripts" / "python.exe"
        import sys as _sys

        current_python = Path(_sys.executable)
        if current_python.exists():
            self._venv_python = current_python
            self.log(f"  ℹ️ Interpreter: {current_python.name}", "DEBUG")

        # Subprocess vs in-process selection.
        self._use_subprocess = self._read_setting("tts.neutts_use_subprocess", False)

        self._process: subprocess.Popen | None = None
        self._model_loaded = False
        self._cuda_failed = False
        # In-process mode state.
        self._inprocess_tts = None
        self._inprocess_mode = False
        self._inprocess_ref_codes = {}  # cache: voice_name → ref_codes

    @staticmethod
    def _read_setting(key: str, default):
        """Read a setting without crashing if Settings isn't ready."""
        try:
            from utils.settings import Settings

            val = Settings().get(key, default)
            return val
        except Exception as e:
            # V11.32.3: log the exception so we know why the default is used.
            import logging as _lg

            _lg.getLogger(__name__).debug(
                "Settings read failed for %s: %s — using default %r", key, e, default
            )
            return default

    def _resolve_devices_now(self) -> tuple[str, str]:
        """V11.32.3: devices are now resolved in __init__. This method
        is kept for backward compat — just returns the cached values."""
        return self.backbone_device, self.codec_device

    @property
    def voice_manager(self):
        if self._voice_manager is None:
            from core.tts.voice_manager import VoiceManager

            self._voice_manager = VoiceManager(log_callback=self.log)
        return self._voice_manager

    def _resolve_reference(self, voice_name: str) -> tuple[str, str]:
        """Resolve a voice name to (ref_wav_path, ref_text)."""
        ref_wav, ref_text = self.voice_manager.get_voice(voice_name)
        if ref_wav is None or not Path(ref_wav).exists():
            raise FileNotFoundError(
                f"Reference voice '{voice_name}' not found. Add voices in Settings → TTS → Voices."
            )
        return (ref_wav, ref_text)

    # ── in-process mode (primary) ───────────────────────────────────────

    def _init_inprocess(self) -> None:
        """Load NeuTTS directly in the current process.

        V11.32.0: devices are resolved from settings (default CUDA) with
        a real CUDA pre-check and graceful CPU fallback.
        """
        if self._inprocess_tts is not None:
            return

        bb_dev, cd_dev = self._resolve_devices_now()

        self.log("  🔄 Loading NeuTTS in-process…", "INFO")
        self.log(f"     Project: {self.neutts_project_path}", "DEBUG")
        self.log(f"     Model: {self.gguf_path.name}", "DEBUG")
        self.log(f"     Backbone: {bb_dev}, Codec: {cd_dev}", "INFO")

        import os
        import sys

        project_str = str(self.neutts_project_path)
        if project_str not in sys.path:
            sys.path.insert(0, project_str)

        old_cwd = os.getcwd()
        try:
            os.chdir(project_str)
            from neutts import NeuTTS

            try:
                self._inprocess_tts = NeuTTS(
                    backbone_repo=str(self.gguf_path),
                    backbone_device=bb_dev,
                    codec_device=cd_dev,
                    language=self.language,
                )
                # Flush any pending CUDA kernels before declaring success.
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                except Exception:
                    logger.debug(
                        "best-effort op failed [neutts_engine:_init_inprocess:L452]", exc_info=True
                    )
            except Exception as dev_err:
                msg = str(dev_err).lower()
                # "No CUDA GPUs are available" / "cuda" / "gpu" → retry CPU.
                if ("cuda" in msg or "gpu" in msg or "device" in msg) and (
                    bb_dev == "cuda" or cd_dev == "cuda"
                ):
                    self.log(
                        f"  ⚠️ CUDA load failed ({dev_err}); retrying on CPU. "
                        f"This will be slow (3–5 min/segment). Install the "
                        f"CUDA build of torch to use the GPU.",
                        "WARNING",
                    )
                    self.backbone_device = "cpu"
                    self.codec_device = "cpu"
                    self._inprocess_tts = NeuTTS(
                        backbone_repo=str(self.gguf_path),
                        backbone_device="cpu",
                        codec_device="cpu",
                        language=self.language,
                    )
                else:
                    raise

            self._inprocess_mode = True
            # V11.32.1: bold, unmissable device banner so the user can
            # verify at a glance whether the GPU is actually in use.
            bb_final = self.backbone_device
            cd_final = self.codec_device
            if bb_final == "cuda" and cd_final == "cuda":
                self.log("  ╔══════════════════════════════════════════════╗", "INFO")
                self.log("  ║  🚀 NeuTTS loaded on GPU (CUDA) — FAST mode  ║", "INFO")
                self.log("  ╚══════════════════════════════════════════════╝", "INFO")
            elif bb_final == "cpu":
                self.log("  ╔═══════════════════════════════════════════════════╗", "WARNING")
                self.log("  ║  🐌 NeuTTS on CPU — SLOW (3-5 min/segment)        ║", "WARNING")
                self.log("  ║  Set backbone device to GPU in Settings → TTS     ║", "WARNING")
                self.log("  ╚═══════════════════════════════════════════════════╝", "WARNING")
            else:
                self.log(f"  🔧 NeuTTS loaded: backbone={bb_final}, codec={cd_final}", "INFO")
        finally:
            os.chdir(old_cwd)

    def _synthesize_inprocess(
        self,
        text: str,
        out_path: Path,
        voice: str | None,
        speed: float,
    ) -> None:
        """Synthesize using in-process NeuTTS (no subprocess)."""
        import numpy as np
        import soundfile as sf

        if self._inprocess_tts is None:
            self._init_inprocess()

        voice = voice or "dave"
        ref_wav, ref_text = self._resolve_reference(voice)
        ref_txt_path = ref_wav.replace(".wav", ".txt")
        if Path(ref_txt_path).exists():
            ref_text = Path(ref_txt_path).read_text(encoding="utf-8").strip()
        if not ref_text:
            ref_text = "This is a reference voice sample."

        # Cache ref_codes per voice (encoding is expensive).
        if voice not in self._inprocess_ref_codes:
            self.log(f"  🎙️ NeuTTS: encoding reference voice '{voice}'…", "INFO")
            self.log(f"     ref_wav: {ref_wav}", "INFO")  # V11.34.1: INFO not DEBUG
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(str(self.neutts_project_path))
                ref_wav_abs = str(Path(ref_wav).resolve())
                self._inprocess_ref_codes[voice] = self._inprocess_tts.encode_reference(ref_wav_abs)
            finally:
                os.chdir(old_cwd)

        ref_codes = self._inprocess_ref_codes[voice]

        # Split long text into chunks.
        chunks = _split_long_line(text, max_chars=_NEUTTS_MAX_CHARS)
        if not chunks:
            chunks = [text]

        import os

        if len(chunks) == 1:
            dev_tag = self.backbone_device.upper()
            self.log(f"  🎙️ NeuTTS [{dev_tag}]: generating {len(text)} chars…", "INFO")
            old_cwd = os.getcwd()
            try:
                os.chdir(str(self.neutts_project_path))
                audio = self._inprocess_tts.infer(
                    text=chunks[0], ref_codes=ref_codes, ref_text=ref_text
                )
                # V11.32.0: sync CUDA before reading the tensor.
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                except Exception:
                    logger.debug(
                        "best-effort op failed [neutts_engine:_synthesize_inprocess:L561]",
                        exc_info=True,
                    )
            finally:
                os.chdir(old_cwd)
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            sf.write(str(out_path), audio, 24000)
        else:
            dev_tag = self.backbone_device.upper()
            self.log(f"  🎙️ NeuTTS [{dev_tag}]: {len(text)} chars in {len(chunks)} chunks…", "INFO")
            chunk_paths = []
            with tempfile.TemporaryDirectory(prefix="neutts_") as tmp:
                for i, chunk in enumerate(chunks):
                    self.log(
                        f"  🎙️ NeuTTS [{dev_tag}]: chunk {i + 1}/{len(chunks)} "
                        f"({len(chunk)} chars)…",
                        "INFO",
                    )
                    cp = Path(tmp) / f"chunk_{i:02d}.wav"
                    old_cwd = os.getcwd()
                    try:
                        os.chdir(str(self.neutts_project_path))
                        audio = self._inprocess_tts.infer(
                            text=chunk, ref_codes=ref_codes, ref_text=ref_text
                        )
                        try:
                            import torch

                            if torch.cuda.is_available():
                                torch.cuda.synchronize()
                        except Exception:
                            logger.debug(
                                "best-effort op failed [neutts_engine:_synthesize_inprocess:L589]",
                                exc_info=True,
                            )
                    finally:
                        os.chdir(old_cwd)
                    if hasattr(audio, "cpu"):
                        audio = audio.cpu().numpy()
                    sf.write(str(cp), audio, 24000)
                    if cp.exists():
                        chunk_paths.append(cp)

                if not chunk_paths:
                    raise RuntimeError("NeuTTS produced no audio")

                if len(chunk_paths) == 1:
                    import shutil

                    shutil.copy2(chunk_paths[0], out_path)
                else:
                    self.log(f"  🎙️ NeuTTS: stitching {len(chunk_paths)} chunks…", "INFO")
                    audio_parts = [sf.read(str(p))[0] for p in chunk_paths]
                    silence = np.zeros(int(24000 * 0.15), dtype=audio_parts[0].dtype)
                    stitched = [audio_parts[0]]
                    for part in audio_parts[1:]:
                        stitched.append(silence)
                        stitched.append(part)
                    sf.write(str(out_path), np.concatenate(stitched), 24000)

    # ── subprocess mode (opt-in) ────────────────────────────────────────

    def _ensure_process(self) -> None:
        """Start the persistent subprocess and wait for model to load."""
        if self._process is not None and self._model_loaded:
            return

        if not self._venv_python.exists():
            raise FileNotFoundError(f"NeuTTS Python interpreter not found: {self._venv_python}")

        bb_dev, cd_dev = self._resolve_devices_now()
        self.log("  🔄 Starting NeuTTS persistent subprocess…", "INFO")
        self.log(f"     Python: {self._venv_python.name}", "DEBUG")
        self.log(f"     Model: {self.gguf_path.name}", "DEBUG")
        self.log(f"     Backbone: {bb_dev}, Codec: {cd_dev}", "DEBUG")

        cmd = [
            str(self._venv_python),
            "-u",  # V11.32.0: unbuffered stdout/stderr
            "-c",
            _PERSISTENT_SCRIPT,
            str(self.neutts_project_path),
            str(self.gguf_path),
            bb_dev,
            cd_dev if not self._cuda_failed else "cpu",
            self.language,
        ]

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        env["PYTHONUNBUFFERED"] = "1"  # V11.32.0

        kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "env": env,
            "bufsize": 1,  # V11.32.0: line-buffered
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(cmd, **kwargs)

        # Drain stderr continuously so it never fills the pipe buffer.
        def drain_stderr():
            if self._process and self._process.stderr:
                for line in self._process.stderr:
                    self.log(f"  [neutts] {line.rstrip()}", "DEBUG")

        threading.Thread(target=drain_stderr, daemon=True).start()

        self.log("  ⏳ Waiting for NeuTTS model to load (this takes ~30s)…", "INFO")
        try:
            msg = self._read_json_line()
            if msg is None:
                raise RuntimeError("NeuTTS subprocess closed stdout before loading")
            if msg.get("status") == "error":
                raise RuntimeError(f"NeuTTS load error: {msg.get('error', 'unknown')}")
            if msg.get("status") == "loading":
                msg = self._read_json_line()
                if msg is None:
                    raise RuntimeError("NeuTTS subprocess closed during loading")
                if msg.get("status") == "error":
                    raise RuntimeError(f"NeuTTS load error: {msg.get('error', 'unknown')}")
                if msg.get("status") != "ready":
                    raise RuntimeError(f"NeuTTS unexpected status: {msg}")
            self._model_loaded = True
            # V11.32.1: device banner for subprocess mode too.
            bb_f = self.backbone_device
            cd_f = self.codec_device if not self._cuda_failed else "cpu"
            if bb_f == "cuda" and cd_f == "cuda":
                self.log("  ╔══════════════════════════════════════════════╗", "INFO")
                self.log("  ║  🚀 NeuTTS loaded on GPU (CUDA) — FAST mode  ║", "INFO")
                self.log("  ╚══════════════════════════════════════════════╝", "INFO")
            elif bb_f == "cpu":
                self.log("  ╔═══════════════════════════════════════════════════╗", "WARNING")
                self.log("  ║  🐌 NeuTTS on CPU — SLOW (3-5 min/segment)        ║", "WARNING")
                self.log("  ║  Set backbone device to GPU in Settings → TTS     ║", "WARNING")
                self.log("  ╚═══════════════════════════════════════════════════╝", "WARNING")
            self.log("  ✅ NeuTTS model loaded — ready for generation", "INFO")
        except RuntimeError as e:
            if "No CUDA" in str(e) and not self._cuda_failed:
                self._cuda_failed = True
                self.log(
                    "  ⚠️ CUDA unavailable for subprocess — retrying with CPU codec "
                    "(slower but works)",
                    "WARNING",
                )
                self._cleanup_process()
                self._ensure_process()
            else:
                self._cleanup_process()
                raise

    def _cleanup_process(self) -> None:
        """Kill the subprocess."""
        if self._process:
            try:
                if self._process.stdin and not self._process.stdin.closed:
                    self._process.stdin.write('{"action": "quit"}\n')
                    self._process.stdin.flush()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception as _e:
                    logger.debug("ignored %s: %s", type(_e).__name__, _e)
            self._process = None
            self._model_loaded = False

    def _read_json_line(self, timeout: int = 120) -> dict | None:
        """Read a JSON line from the subprocess stdout.

        V11.32.0: the subprocess now reserves stdout for JSON only (all
        library output goes to stderr), so every line should be JSON.
        Non-JSON lines are still tolerated for safety.
        """
        start = time.time()
        while True:
            if self._process is None or self._process.poll() is not None:
                return None
            line = self._process.stdout.readline()
            if not line:
                if time.time() - start > timeout:
                    return None
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line:
                continue
            if not line.startswith("{"):
                self.log(f"  [neutts] {line}", "DEBUG")
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                self.log(f"  [neutts] {line}", "DEBUG")
                continue

    def _synthesize_subprocess(
        self,
        text: str,
        out_path: Path,
        voice: str | None,
        speed: float,
    ) -> None:
        """Synthesize text via the persistent subprocess."""
        import numpy as np
        import soundfile as sf

        voice = voice or "dave"
        ref_wav, ref_text = self._resolve_reference(voice)

        ref_txt_path = ref_wav.replace(".wav", ".txt")
        if Path(ref_txt_path).exists():
            ref_text = Path(ref_txt_path).read_text(encoding="utf-8").strip()
        if not ref_text:
            ref_text = "This is a reference voice sample."

        chunks = _split_long_line(text, max_chars=_NEUTTS_MAX_CHARS)
        if not chunks:
            chunks = [text]

        dev_tag = self.backbone_device.upper() if self.backbone_device else "?"
        if len(chunks) == 1:
            self.log(f"  🎙️ NeuTTS [{dev_tag}]: generating {len(text)} chars…", "INFO")
            self._generate_one(chunks[0], out_path, ref_wav, ref_text)
        else:
            self.log(f"  🎙️ NeuTTS [{dev_tag}]: {len(text)} chars in {len(chunks)} chunks…", "INFO")
            chunk_paths: list[Path] = []
            with tempfile.TemporaryDirectory(prefix="neutts_") as tmp:
                for i, chunk in enumerate(chunks):
                    self.log(f"  🎙️ NeuTTS [{dev_tag}]: chunk {i + 1}/{len(chunks)}…", "INFO")
                    cp = Path(tmp) / f"chunk_{i:02d}.wav"
                    self._generate_one(chunk, cp, ref_wav, ref_text)
                    if cp.exists():
                        chunk_paths.append(cp)

            if not chunk_paths:
                raise RuntimeError("NeuTTS produced no audio")

            if len(chunk_paths) == 1:
                import shutil

                shutil.copy2(chunk_paths[0], out_path)
            else:
                audio_parts = [sf.read(str(p))[0] for p in chunk_paths]
                sample_rate = 24000
                silence = np.zeros(int(sample_rate * 0.15), dtype=audio_parts[0].dtype)
                stitched = [audio_parts[0]]
                for part in audio_parts[1:]:
                    stitched.append(silence)
                    stitched.append(part)
                sf.write(str(out_path), np.concatenate(stitched), sample_rate)

    def _generate_one(
        self,
        text: str,
        out_path: Path,
        ref_wav: str,
        ref_text: str,
    ) -> None:
        """Send one generation command to the persistent subprocess."""
        self._ensure_process()

        cmd = json.dumps(
            {
                "action": "generate",
                "text": text,
                "ref_wav": ref_wav,
                "ref_text": ref_text,
                "out_path": str(out_path),
            }
        )

        self._process.stdin.write(cmd + "\n")
        self._process.stdin.flush()

        msg = self._read_json_line(timeout=180)
        if msg is None:
            raise RuntimeError("NeuTTS subprocess timed out (180s) — likely CUDA hang")

        if msg.get("status") == "error":
            raise RuntimeError(f"NeuTTS error: {msg.get('error', 'unknown')}")

        if not out_path.exists():
            raise RuntimeError("NeuTTS reported success but no output file")

    # ── public entry point ──────────────────────────────────────────────

    def _synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None,
        speed: float,
    ) -> None:
        """Synthesize text.

        V11.32.0: in-process is the default (subprocess mode hung on
        CUDA inference due to a stdout-buffer deadlock). Subprocess mode
        is opt-in via ``tts.neutts_use_subprocess``.
        """
        # If in-process mode is already active, keep using it.
        if self._inprocess_mode:
            self._synthesize_inprocess(text, out_path, voice, speed)
            return

        # If a subprocess is already loaded, keep using it.
        if self._process is not None and self._model_loaded:
            self._synthesize_subprocess(text, out_path, voice, speed)
            return

        # Choose the primary mode from settings.
        if self._use_subprocess and self._venv_python.exists():
            try:
                self._synthesize_subprocess(text, out_path, voice, speed)
                return
            except Exception as e:
                self.log(f"  ⚠️ NeuTTS subprocess failed: {e}", "WARNING")
                self.log("  🔄 Falling back to in-process mode…", "INFO")
                self._cleanup_process()

        # Primary / fallback: in-process mode.
        self._init_inprocess()
        self._synthesize_inprocess(text, out_path, voice, speed)

    def __del__(self):
        # V11.36.2: guard against __init__ failing before _process is set.
        try:
            if hasattr(self, "_process") and self._process:
                self._cleanup_process()
        except Exception:
            logger.debug("best-effort op failed [neutts_engine:__del__:L904]", exc_info=True)
