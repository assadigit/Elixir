"""V11.40.0: VibeVoice-Realtime-0.5B engine — high-quality English TTS.

Uses the ``vibevoice`` package from Microsoft's GitHub. The model loads
in a persistent subprocess (to avoid CUDA thread deadlocks) and stays
alive for all subsequent generations.

Speed: ~0.6x realtime (slower than Kokoro but higher quality + voice cloning)
VRAM: ~2.6 GB
Voices: 25 presets (7 English: Carter, Davis, Emma, Frank, Grace, Mike, Samuel)

Install:
  git clone https://github.com/microsoft/VibeVoice.git
  cd VibeVoice
  pip install -e ".[streamingtts]"

Settings:
  tts.vibevoice_model_path: path to the model folder
  tts.vibevoice_voices_dir: path to the voice presets folder
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.tts._json_subprocess import PersistentJsonSubprocess
from core.tts.engine import LogFn, TTSEngine

logger = logging.getLogger(__name__)

# V18.20.4.4 (W-c2): timeout bounds as module constants — testable seams
# (the values are UNCHANGED from the old inline literals; no cap changes).
# The shared base makes both timeouts REAL: a silent-but-alive child can
# no longer block a readline() past the deadline.
VIBEVOICE_LOAD_TIMEOUT_S = 300  # was the inline `300` in _ensure_model
VIBEVOICE_LINE_TIMEOUT_S = 600  # was the inline `600` in synthesize

# V0.6.15: free-VRAM pre-flight floor. The model is ~2.6 GB on VRAM plus
# activations; below this the load usually dies on CUDA OOM — most often
# with llama.cpp / Ollama still holding the card (the operator's rig runs
# llama-server for the LLM step of the same podcast). Fail-soft: a WARNING,
# never a block.
VIBEVOICE_MIN_FREE_VRAM_GB = 3.5


# All 25 voice presets from the VibeVoice GitHub repo
VIBEVOICE_VOICES = [
    # English (7 voices)
    ("en-Carter_man", "Carter", "Male", "English"),
    ("en-Davis_man", "Davis", "Male", "English"),
    ("en-Emma_woman", "Emma", "Female", "English"),
    ("en-Frank_man", "Frank", "Male", "English"),
    ("en-Grace_woman", "Grace", "Female", "English"),
    ("en-Mike_man", "Mike", "Male", "English"),
    ("en-Samuel_man", "Samuel", "Male", "English"),
    # Other languages
    ("de-Spk0_man", "German Male 1", "Male", "German"),
    ("de-Spk1_woman", "German Female 1", "Female", "German"),
    ("fr-Spk0_man", "French Male 1", "Male", "French"),
    ("fr-Spk1_woman", "French Female 1", "Female", "French"),
    ("it-Spk0_woman", "Italian Female 1", "Female", "Italian"),
    ("it-Spk1_man", "Italian Male 1", "Male", "Italian"),
    ("jp-Spk0_man", "Japanese Male 1", "Male", "Japanese"),
    ("jp-Spk1_woman", "Japanese Female 1", "Female", "Japanese"),
    ("kr-Spk0_woman", "Korean Female 1", "Female", "Korean"),
    ("kr-Spk1_man", "Korean Male 1", "Male", "Korean"),
    ("nl-Spk0_man", "Dutch Male 1", "Male", "Dutch"),
    ("nl-Spk1_woman", "Dutch Female 1", "Female", "Dutch"),
    ("pl-Spk0_man", "Polish Male 1", "Male", "Polish"),
    ("pl-Spk1_woman", "Polish Female 1", "Female", "Polish"),
    ("pt-Spk0_woman", "Portuguese Female 1", "Female", "Portuguese"),
    ("pt-Spk1_man", "Portuguese Male 1", "Male", "Portuguese"),
    ("sp-Spk0_woman", "Spanish Female 1", "Female", "Spanish"),
    ("sp-Spk1_man", "Spanish Male 1", "Male", "Spanish"),
]

# English voices only (for the TTS dialog English section)
VIBEVOICE_ENGLISH_VOICES = [v for v in VIBEVOICE_VOICES if v[3] == "English"]


class VibeVoiceEngine(TTSEngine):
    """V11.40.0: VibeVoice-Realtime-0.5B engine.

    High-quality English TTS with voice presets. Slower than Kokoro
    (0.6x realtime) but better quality + 25 voice options.

    Uses a persistent subprocess to avoid CUDA thread deadlocks.
    """

    def __init__(
        self,
        model_path: str = "",
        voices_dir: str = "",
        default_voice: str = "en-Carter_man",
        log_callback: LogFn | None = None,
    ) -> None:
        super().__init__(log_callback)
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._model_path = model_path
        self._voices_dir = voices_dir
        self._default_voice = default_voice
        self._sub: PersistentJsonSubprocess | None = None  # V18.20.4.4 (O-c2)
        self._loaded = False
        self._device = "unknown"  # V11.42.0: track device for proof file
        self.last_error: str | None = None

    def _preflight_vram(self) -> None:
        """V0.6.15: free-VRAM pre-flight (fail-soft, best-effort — no torch
        in the parent means no check, never a failure). The live report
        "the podcast generated the text but VibeVoice had an error" is most
        often the 2.6 GB load dying on CUDA out-of-memory while llama.cpp /
        Ollama still hold the card. Naming the likely holders turns a raw
        CUDA blob into an actionable log line."""
        try:
            import torch as _torch_preflight

            if _torch_preflight.cuda.is_available():
                _free_b, _total_b = _torch_preflight.cuda.mem_get_info()
                _free_gb = _free_b / (1024**3)
                self.log(f"  🎮 GPU free VRAM: {_free_gb:.1f} GB", "INFO")
                if _free_gb < VIBEVOICE_MIN_FREE_VRAM_GB:
                    self.log(
                        f"  ⚠️ Only {_free_gb:.1f} GB VRAM free — VibeVoice needs "
                        f"~{VIBEVOICE_MIN_FREE_VRAM_GB} GB. llama.cpp / Ollama may "
                        f"still be holding the GPU; free VRAM (or close them) or "
                        f"the model load may fail with CUDA out-of-memory.",
                        "WARNING",
                    )
        except Exception:
            logger.debug(
                "best-effort op failed [vibevoice_engine:_preflight_vram]",
                exc_info=True,
            )

    def get_device(self) -> str:
        """V11.42.0: Return the device (cuda/cpu) the engine is using."""
        return self._device

    def _ensure_model(self) -> None:
        """Start the persistent subprocess and load the model.

        V11.57.0: NO automatic restart. If the subprocess died, the
        podcast FAILS — no retry loop, no "resetting". The user's
        requirement: "podcast must never change model or speaker. either
        success or fail." Restarting the subprocess on every line was
        causing the death spiral (30-60s model reload × every line).
        Now if the process is dead, we raise immediately.
        """
        # V11.57.0: if the process died, FAIL — don't restart.
        # The restart loop was the "resetting" problem.
        if self._loaded and self._sub is not None:
            if self._sub.alive:
                return  # still alive — reuse
            else:
                # Process died — DON'T restart. Fail the podcast.
                exit_code = self._sub.returncode
                self._loaded = False
                self._sub = None
                self._device = "unknown"
                raise RuntimeError(
                    f"VibeVoice subprocess crashed (exit code {exit_code}). "
                    f"The podcast has failed — no automatic restart "
                    f"(to avoid the reloading death spiral). "
                    f"Check the live log for the crash reason. "
                    f"If this keeps happening, VibeVoice may not work "
                    f"on your system — use Kokoro voices instead."
                )

        if self._loaded:
            return

        if not self._model_path:
            raise ValueError("VibeVoice model path not set")

        import sys
        import time

        self._preflight_vram()  # V0.6.15: the free-VRAM warning, fail-soft

        script_path = str(Path(__file__).parent / "_vibevoice_subprocess.py")
        self.log("  🔄 Starting VibeVoice persistent subprocess...", "INFO")

        # V11.61.0: CRITICAL — give the subprocess a CLEAN environment.
        # The main process's os.environ contains PySide6/Qt DLL paths that
        # POISON torch's CUDA detection in the subprocess. The subprocess
        # is a fresh Python process — it should work like the CLI (where
        # CUDA works), but the inherited environment breaks it.
        #
        # We build a minimal environment with ONLY:
        # - System essentials (SYSTEMROOT, TEMP, etc.)
        # - Python path
        # - torch/lib prepended to PATH (NOT the main process's PATH which
        #   may contain PySide6/Qt DLL directories)
        # - TORCH_CUDA_DLL_PATH (for the subprocess to register)
        env = {}

        # Copy ONLY essential system variables (NOT PATH — we rebuild it)
        _ESSENTIAL_VARS = [
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "USERNAME",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
            "OS",
            "COMPUTERNAME",
            "HOMEDRIVE",
            "HOMEPATH",
            "PYTHONPATH",  # so the subprocess can find the project modules
        ]
        for var in _ESSENTIAL_VARS:
            if var in os.environ:
                env[var] = os.environ[var]

        env["PYTHONUNBUFFERED"] = "1"
        if sys.platform == "win32":
            env["PYTHONIOENCODING"] = "utf-8"

        # V11.61.0: Build a CLEAN PATH with ONLY:
        # 1. torch/lib (FIRST — so CUDA DLLs are found before anything else)
        # 2. System32 + Windows directories (essential for Windows)
        # 3. Python directory (so python.exe dependencies work)
        # NO PySide6/Qt paths — those break CUDA.
        _clean_path_parts = []

        # Add torch/lib first
        try:
            import torch as _torch_for_dlls

            _torch_lib = str(Path(_torch_for_dlls.__file__).parent / "lib")
            if Path(_torch_lib).exists():
                _clean_path_parts.append(_torch_lib)
                env["TORCH_CUDA_DLL_PATH"] = _torch_lib
        except Exception:
            logger.debug(
                "best-effort op failed [vibevoice_engine:_ensure_model:L187]", exc_info=True
            )

        # Add essential Windows directories
        if sys.platform == "win32":
            _systemroot = os.environ.get("SYSTEMROOT", r"C:\Windows")
            _clean_path_parts.extend(
                [
                    os.path.join(_systemroot, "System32"),
                    _systemroot,
                    os.path.join(_systemroot, "System32", "Wbem"),
                ]
            )

        # Add Python directory
        _python_dir = str(Path(sys.executable).parent)
        _clean_path_parts.append(_python_dir)

        # Add Python Scripts directory
        _python_scripts = str(Path(sys.executable).parent / "Scripts")
        if Path(_python_scripts).exists():
            _clean_path_parts.append(_python_scripts)

        env["PATH"] = os.pathsep.join(_clean_path_parts)

        # V18.20.4.4 (O-c2): spawn via the shared base — REAL timeouts and
        # the neutts quit→wait→kill teardown contract written once. The
        # clean-env logic above is untouched.
        sub = PersistentJsonSubprocess(
            name="VibeVoice", log=self.log, stderr_prefix="[vibevoice]", stderr_level="INFO"
        )
        sub.spawn([sys.executable, script_path], env=env)
        self._sub = sub

        # Send load command
        if not sub.send(
            {
                "action": "load",
                "model_path": str(self._model_path),
            }
        ):
            self._kill_subprocess("cannot send load command")
            raise RuntimeError("VibeVoice subprocess not accepting the load command")

        # Wait for "ready" (timeout 300s — model is 2.6 GB, loading can
        # take a while on first load from disk; a REAL timeout now: the
        # base's queue-based reader means a silent child cannot block
        # the handshake forever)
        start = time.time()
        while True:
            remaining = VIBEVOICE_LOAD_TIMEOUT_S - (time.time() - start)
            if remaining <= 0:
                break
            msg = sub.read_json(remaining)
            if msg is None:
                break
            status = msg.get("status", "")
            if status == "loading":
                _load_dev = msg.get("device", "?")
                self.log(f"  🔄 Model loading (device: {_load_dev})...", "INFO")
                # V0.6.15: a CPU load is the 600 s per-line timeout in slow
                # motion — name it while the user can still cancel instead
                # of waiting an hour for line 1 to die.
                if _load_dev == "cpu":
                    self.log(
                        "  ⚠️ VibeVoice is loading on CPU — generation is "
                        "~100x slower and each line will likely hit the "
                        "600s timeout. Check the GPU/torch install "
                        "(details: ~/.elixir/gpu_probe.log).",
                        "WARNING",
                    )
            elif status == "ready":
                self._device = msg.get("device", "unknown")
                self.log(f"  ✅ VibeVoice ready on {self._device.upper()}", "INFO")
                self._loaded = True
                return
            elif status == "error":
                # V0.6.15: forward the subprocess traceback — the old path
                # dropped it, so the live log showed the WHAT ("Model load
                # failed: …") but never the WHY. The traceback is the line
                # the operator pastes back.
                _load_err = msg.get("error", "unknown")
                _load_tb = (msg.get("traceback") or "").strip()
                if _load_tb:
                    self.log(f"  📋 VibeVoice load traceback:\n{_load_tb}", "ERROR")
                # V18.20.4.4 (W-c2): kill before raising — a reported load
                # error can leave the subprocess alive holding VRAM.
                self._kill_subprocess(f"load error: {_load_err}")
                # V0.6.15: when the vibevoice package itself is missing,
                # append the install command — the single most common
                # fresh-rig load failure and fully actionable.
                _install_hint = ""
                if (
                    "No module named 'vibevoice'" in _load_err
                    or 'No module named "vibevoice"' in _load_err
                ):
                    _install_hint = (
                        " — install VibeVoice: git clone "
                        "https://github.com/microsoft/VibeVoice.git && "
                        'cd VibeVoice && pip install -e ".[streamingtts]"'
                    )
                # V0.6.16: the native-VibeVoice duplicate registration —
                # transformers v5.13+ pre-registers the same config names
                # the from-source package registers at import time and the
                # load dies with "'...' is already used by a Transformers
                # model." The subprocess now tolerates this automatically;
                # this hint only fires if the tolerance itself could not
                # be installed (a future transformers layout change).
                _native_hint = ""
                if "is already used by a Transformers model" in _load_err:
                    _native_hint = (
                        " — your transformers already ships native VibeVoice "
                        "classes and the from-source VibeVoice package re-"
                        "registers them; update Elixir to the latest build "
                        "(it tolerates this) or pin 'transformers<5.13'"
                    )
                # V0.6.17: the meta-device model init — transformers v5
                # builds every model on the meta device and VibeVoice's
                # noise scheduler cannot survive it (its cosine-schedule
                # betas become meta tensors; dpm_solver.py:295 dies with
                # "Cannot copy out of meta tensor; no data!" — the
                # operator's V0.6.16 paste-back). The subprocess now
                # guards this automatically; this hint only fires if the
                # guard itself could not be installed (e.g. a future
                # VibeVoice layout change).
                _meta_hint = ""
                if "meta tensor" in _load_err:
                    _meta_hint = (
                        " — transformers v5's meta-device model init broke "
                        "the VibeVoice noise scheduler; update Elixir to "
                        "the latest build (it guards this) or pin "
                        "'transformers<5'"
                    )
                raise RuntimeError(
                    f"Model load failed: {_load_err}{_install_hint}{_native_hint}{_meta_hint}"
                )

        # V18.20.4.4 (W-c2): kill the still-loading subprocess before
        # raising. Previously this path raised with the handle still set
        # and `self._loaded` False — the 2.6 GB model kept running while
        # the next `_ensure_model()` overwrote the handle and ORPHANED the
        # old process (VRAM lock — T-c1).
        if sub.eof or not sub.alive:
            self._kill_subprocess("stdout closed during model load")
        else:
            self._kill_subprocess(f"model load not ready (timeout, {VIBEVOICE_LOAD_TIMEOUT_S}s)")
        raise RuntimeError("VibeVoice subprocess failed to load model (timeout)")

    def synthesize(
        self,
        text: str,
        out_path: Path,
        voice: str | None = None,
        speed: float = 1.0,
        style: str = "natural",
    ) -> Path | None:
        """Synthesize text to a WAV file using VibeVoice.

        V11.40.1: Added guardrails (explicit verification), emotion support
        via cfg_scale + text prefix, and tokenization progress.

        Args:
            text: Text to synthesize.
            out_path: Path to save the WAV file.
            voice: Voice preset name (e.g. "en-Carter_man").
            speed: Ignored (VibeVoice doesn't support speed control).
            style: Speaking style ("natural", "enthusiastic", "calm", etc.)
        """
        if not text or not text.strip():
            return None
        try:
            self._ensure_model()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Strip "vibevoice:" prefix if present
            voice_name = voice or self._default_voice
            if voice_name and voice_name.startswith("vibevoice:"):
                voice_name = voice_name[len("vibevoice:") :]

            # V11.40.1: GUARDRAIL — explicitly verify we're using VibeVoice
            self.log("  ═══ VibeVoiceEngine.synthesize ═══", "INFO")
            self.log("  ✅ Engine: VibeVoice (NOT Kokoro)", "INFO")
            self.log(f"  ✅ Voice preset: {voice_name}", "INFO")
            self.log(f"  ✅ Model path: {self._model_path}", "INFO")
            self.log(f"  ✅ Text length: {len(text)} chars", "INFO")

            # V11.40.1: emotion/tone control via cfg_scale + text prefix
            # VibeVoice-Realtime doesn't have native emotion params, but:
            # - cfg_scale controls how closely to match the voice preset
            # - text prefixes can influence prosody (the LLM understands them)
            style_profiles = {
                "natural": (1.5, ""),
                "enthusiastic": (2.0, "[enthusiastic] "),
                "calm": (1.0, "[calm, soothing] "),
                "inspiring": (2.0, "[inspiring] "),
                "authoritative": (1.8, "[authoritative] "),
                "friendly": (1.5, "[friendly] "),
                "dramatic": (2.5, "[dramatic] "),
            }
            cfg_scale, emotion_prefix = style_profiles.get(style, style_profiles["natural"])
            synth_text = text
            if emotion_prefix:
                synth_text = emotion_prefix + text

            # V11.40.1: tokenization progress estimate
            # VibeVoice uses Qwen2.5 tokenizer, ~1 token per 4 chars
            est_tokens = max(1, len(synth_text) // 4)
            self.log(f"  📊 Text: {len(synth_text)} chars ≈ {est_tokens} tokens", "INFO")
            self.log(f"  🎭 Style: {style} (cfg_scale={cfg_scale})", "INFO")

            self.log("  🎙️ Generating (VibeVoice ~0.6x realtime — please be patient)...", "INFO")

            import time

            # Send generate command with style parameters
            # V18.20.4.4 (O-c2): via the shared base (send is fail-soft).
            cmd = {
                "action": "generate",
                "text": synth_text,
                "voice": voice_name,
                "voices_dir": str(self._voices_dir),
                "out_path": str(out_path),
                "cfg_scale": cfg_scale,
            }
            if not self._sub.send(cmd):
                # send() already logged; kill + raise (V11.57.0 no-restart).
                self._kill_subprocess("send failed (subprocess gone)")
                raise RuntimeError(
                    "VibeVoice subprocess not accepting commands. "
                    "Podcast failed — no retry (to avoid the reloading "
                    "death spiral)."
                )

            # Wait for response (timeout 600s = 10 min per line)
            # V11.49.0: increased from 120s — VibeVoice at 0.6x realtime
            # on GPU can take ~90s for a 60s clip, and on CPU it's far
            # worse. 120s was causing "stuck at 1/277" timeouts.
            # V18.20.4.4: the timeout is REAL now — the base's queue-based
            # reader means a silent-but-alive child cannot block a
            # readline() forever; the loop polls in ≤5s slices so the
            # periodic "Still generating..." progress line survives.
            start = time.time()
            last_progress_time = start
            progress_shown = False
            while True:
                remaining = VIBEVOICE_LINE_TIMEOUT_S - (time.time() - start)
                if remaining <= 0:
                    self.log(f"  ❌ Subprocess timed out ({VIBEVOICE_LINE_TIMEOUT_S}s)", "ERROR")
                    self._kill_subprocess(f"timeout ({VIBEVOICE_LINE_TIMEOUT_S}s)")
                    # V11.57.0: RAISE — don't return None.
                    raise RuntimeError(
                        "VibeVoice subprocess timed out (600s). Podcast failed — "
                        "no retry (to avoid the reloading death spiral)."
                    )
                msg = self._sub.read_json(min(remaining, 5.0))
                if msg is None:
                    if self._sub.eof or not self._sub.alive:
                        self.log("  ❌ Subprocess crashed unexpectedly", "ERROR")
                        self._kill_subprocess("stdout closed (subprocess crashed)")
                        # V11.57.0: RAISE — don't return None. Returning None
                        # lets the podcast continue to the next line, which
                        # tries to restart the subprocess → death spiral.
                        raise RuntimeError(
                            "VibeVoice subprocess crashed. Podcast failed — "
                            "no retry (to avoid the reloading death spiral). "
                            "Check the live log for the crash reason."
                        )
                    # V11.62.0: periodic progress — friendly, no scary
                    # numbers. Just elapsed time so the user knows it works.
                    now = time.time()
                    if now - last_progress_time > 5:
                        elapsed = now - start
                        self.log(f"  ⏳ Still generating... ({elapsed:.0f}s elapsed)", "INFO")
                        last_progress_time = now
                    continue
                status = msg.get("status", "")
                if status == "generating":
                    # V11.62.0: friendlier progress message — don't show
                    # the scary token counter.
                    if not progress_shown:
                        self.log(
                            "  ⏳ Generating speech (this takes a "
                            "few seconds on GPU, longer on CPU)...",
                            "INFO",
                        )
                        progress_shown = True
                elif status == "ok":
                    gen_time = time.time() - start
                    duration = msg.get("duration", 0)
                    self.log(
                        f"  ✅ VibeVoice complete: {duration}s audio in {gen_time:.1f}s", "INFO"
                    )
                    # V11.55.0: check subprocess health after generation
                    if self._sub and not self._sub.alive:
                        self.log(
                            f"  ⚠️ Subprocess died after generation "
                            f"(exit code {self._sub.returncode})",
                            "WARNING",
                        )
                        self._kill_subprocess("died after ok")
                    if out_path.exists():
                        file_size = out_path.stat().st_size
                        self.log(f"  ✅ Verified: {out_path.name} ({file_size // 1024} KB)", "INFO")
                        return out_path
                    self.log("  ❌ File not written", "ERROR")
                    raise RuntimeError("VibeVoice: file not written")
                elif status == "error":
                    err_msg = msg.get("error", "unknown")
                    # V0.6.15: forward the subprocess traceback (was dropped
                    # — same diagnosability gap as the load-error path).
                    _gen_tb = (msg.get("traceback") or "").strip()
                    if _gen_tb:
                        self.log(f"  📋 VibeVoice generation traceback:\n{_gen_tb}", "ERROR")
                    self.log(f"  ❌ Generation error: {err_msg}", "ERROR")
                    self._kill_subprocess(f"generation error: {err_msg[:200]}")
                    # V11.57.0: RAISE — don't return None.
                    raise RuntimeError(f"VibeVoice generation error: {err_msg}")
        except RuntimeError:
            # V11.57.0: re-raise RuntimeErrors (our intentional failures)
            # so they propagate to the audio generator and stop the podcast.
            raise
        except Exception as e:
            self.last_error = str(e)
            self.log(f"  ❌ VibeVoice error: {e}", "ERROR")
            logger.exception("VibeVoiceEngine.synthesize failed")
            # V11.57.0: raise — don't return None.
            raise

    def _kill_subprocess(self, reason: str = "") -> None:
        """V11.55.0: Kill the subprocess and mark as not loaded.

        Called when the subprocess crashes, times out, or produces an error.
        This ensures the next call to _ensure_model() will start a FRESH
        subprocess instead of trying to reuse a dead/zombie one.

        V18.20.4.4 (O-c2): delegates the kill/reap to the shared base
        (``PersistentJsonSubprocess.kill`` — idempotent, logs the reason
        in the same "🔧 Killing VibeVoice subprocess (reason: …)" shape).
        """
        sub = self._sub
        if sub is not None:
            sub.kill(reason)
        self._sub = None
        self._loaded = False
        self._device = "unknown"

    def _cleanup(self) -> None:
        """V18.20.4.4 (O-c2): graceful quit → kill via the shared base."""
        sub = self._sub
        if sub is not None:
            sub.close()
        self._sub = None
        self._loaded = False

    def __del__(self):
        try:
            self._cleanup()
        except Exception:
            logger.debug("best-effort op failed [vibevoice_engine:__del__:L486]", exc_info=True)
