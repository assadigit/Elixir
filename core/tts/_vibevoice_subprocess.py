#!/usr/bin/env python3
"""V11.40.0: VibeVoice persistent subprocess.

Loads the model ONCE and stays alive, reading generation requests from stdin.

V11.58.0: CRITICAL FIX for subprocess CUDA visibility.
The subprocess is a SEPARATE process — it does NOT inherit the main
process's `os.add_dll_directory()` calls. On Windows, torch's CUDA DLLs
(cudart64_12.dll, cublas64_12.dll, etc.) live in `torch/lib/` and must
be registered via `os.add_dll_directory()` BEFORE torch is imported,
otherwise `torch.cuda.is_available()` returns False in the subprocess
even though it returns True in the main process.

The fix: use `torch.utils.cpp_extension` to find and register the DLL
directory, OR manually add `torch/lib/` to the DLL search path. We do
both for robustness.
"""

import json
import logging
import os
import sys
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)

# V11.53.0: Force UTF-8 mode on Windows so print() doesn't crash on Unicode.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        logger.debug("best-effort op failed [_vibevoice_subprocess:module:L34]", exc_info=True)

# V11.58.0/V11.60.0: CRITICAL — register torch's CUDA DLL directory BEFORE
# importing torch. On Windows, the subprocess doesn't inherit the main
# process's os.add_dll_directory() calls, so torch's CUDA DLLs (in
# torch/lib/) aren't found → torch.cuda.is_available() returns False.
#
# V11.60.0: os.add_dll_directory() alone is NOT enough. We ALSO prepend
# torch/lib/ to the PATH environment variable, which is the legacy DLL
# search path and is more reliable on some Windows configurations.
_TORCH_LIB_PATHS = []
try:
    # Find torch's lib directory without importing torch
    import importlib.util as _ilu

    _torch_spec = _ilu.find_spec("torch")
    if _torch_spec and _torch_spec.origin:
        _torch_dir = Path(_torch_spec.origin).parent
        _torch_lib = _torch_dir / "lib"
        if _torch_lib.exists():
            _lib_str = str(_torch_lib)
            _TORCH_LIB_PATHS.append(_lib_str)
            # Method 1: os.add_dll_directory (Python 3.8+)
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(_lib_str)
                except Exception:
                    logger.debug(
                        "best-effort op failed [_vibevoice_subprocess:module:L60]", exc_info=True
                    )
            # Method 2: prepend to PATH (legacy, more reliable)
            _current_path = os.environ.get("PATH", "")
            if _lib_str not in _current_path:
                os.environ["PATH"] = _lib_str + os.pathsep + _current_path
    # Also check for torch's bin directory (some builds)
    if _torch_spec and _torch_spec.origin:
        _torch_bin = Path(_torch_spec.origin).parent / "bin"
        if _torch_bin.exists():
            _bin_str = str(_torch_bin)
            _TORCH_LIB_PATHS.append(_bin_str)
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(_bin_str)
                except Exception:
                    logger.debug(
                        "best-effort op failed [_vibevoice_subprocess:module:L75]", exc_info=True
                    )
            _current_path = os.environ.get("PATH", "")
            if _bin_str not in _current_path:
                os.environ["PATH"] = _bin_str + os.pathsep + _current_path
except Exception:
    logger.debug("best-effort op failed [_vibevoice_subprocess:module:L80]", exc_info=True)

# V11.58.0/V11.60.0: Also check for a TORCH_CUDA_DLL_PATH env var that the
# main process can pass to us (set by vibevoice_engine.py).
_extra_dll = os.environ.get("TORCH_CUDA_DLL_PATH", "")
if _extra_dll:
    for _p in _extra_dll.split(os.pathsep):
        _p = _p.strip()
        if _p and Path(_p).exists():
            _TORCH_LIB_PATHS.append(_p)
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(_p)
                except Exception:
                    logger.debug(
                        "best-effort op failed [_vibevoice_subprocess:module:L94]", exc_info=True
                    )
            # V11.60.0: also prepend to PATH
            _current_path = os.environ.get("PATH", "")
            if _p not in _current_path:
                os.environ["PATH"] = _p + os.pathsep + _current_path

# NOW import torch — it should find its CUDA DLLs
# V11.59.0: CRITICAL — cache the CUDA status HERE, before vibevoice/
# transformers are imported. Those packages load conflicting DLLs that
# break torch.cuda.is_available() later. We use the cached value in the
# load handler instead of re-checking.
try:
    import torch as _torch_early

    _SUBPROCESS_CUDA_OK = bool(_torch_early.cuda.is_available())
    _SUBPROCESS_TORCH_VERSION = _torch_early.__version__
    _SUBPROCESS_CUDA_TAG = getattr(_torch_early.version, "cuda", None)
    _SUBPROCESS_CUDA_DEVICE = _torch_early.cuda.get_device_name(0) if _SUBPROCESS_CUDA_OK else None
except Exception as _e:
    _SUBPROCESS_CUDA_OK = False
    _SUBPROCESS_TORCH_VERSION = "import failed"
    _SUBPROCESS_CUDA_TAG = None
    _SUBPROCESS_CUDA_DEVICE = None
    _SUBPROCESS_IMPORT_ERROR = str(_e)
else:
    _SUBPROCESS_IMPORT_ERROR = None

# V11.59.0: Log the EARLY CUDA status (before vibevoice/transformers)
try:
    import datetime as _dt

    _probe_log = Path.home() / ".elixir" / "gpu_probe.log"
    _probe_log.parent.mkdir(parents=True, exist_ok=True)
    with open(_probe_log, "a", encoding="utf-8") as _f:
        _f.write(f"\n{'=' * 60}\n")
        _f.write(f"{_dt.datetime.now().isoformat()} — VIBEVOICE SUBPROCESS (early)\n")
        _f.write(f"Python: {sys.executable}\n")
        _f.write(f"torch: {_SUBPROCESS_TORCH_VERSION}\n")
        _f.write(f"torch.version.cuda: {_SUBPROCESS_CUDA_TAG!r}\n")
        _f.write(f"cuda.is_available() [EARLY]: {_SUBPROCESS_CUDA_OK}\n")
        if _SUBPROCESS_CUDA_DEVICE:
            _f.write(f"GPU: {_SUBPROCESS_CUDA_DEVICE}\n")
        _f.write(f"DLL paths registered: {_TORCH_LIB_PATHS}\n")
        if _SUBPROCESS_IMPORT_ERROR:
            _f.write(f"IMPORT ERROR: {_SUBPROCESS_IMPORT_ERROR}\n")
        _f.write("(probe ran BEFORE vibevoice/transformers import)\n")
except Exception:
    logger.debug("best-effort op failed [_vibevoice_subprocess:module:L142]", exc_info=True)


def safe_print(msg, file=None, flush=True):
    """V11.53.0: Print that never crashes on encoding errors.

    On Windows, print() can raise OSError [Errno 22] when the message
    contains Unicode the console can't encode. This wraps print in a
    try/except and falls back to ASCII-safe output.
    """
    f = file or sys.stdout
    try:
        print(msg, file=f, flush=flush)
    except (OSError, UnicodeEncodeError):
        try:
            # Replace non-ASCII chars and retry
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            print(safe, file=f, flush=flush)
        except Exception:
            logger.debug(
                "best-effort op failed [_vibevoice_subprocess:safe_print:L161]", exc_info=True
            )


def _load_voice_preset(torch, preset_path, map_loc, allowed_globals):
    """V0.6.15: the voice-preset torch.load fallback chain.

    1. The OFFICIAL path (the VibeVoice demo): weights_only=True inside
       safe_globals — the safe loader, works on torch >= 2.6 with the
       current presets.
    2. The legacy escape hatch: weights_only=False — needed when a preset
       references globals beyond the two allowed (or a future torch
       restricts the unsafe path differently).
    3. Bare torch.load — torch < 2.6 has no safe_globals at all
       (AttributeError on the context manager itself).
    """
    BaseModelOutputWithPast, DynamicCache = allowed_globals
    try:
        with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
            return torch.load(preset_path, map_location=map_loc, weights_only=True)
    except AttributeError:
        safe_print(
            "[SUBPROCESS] torch.serialization.safe_globals unavailable "
            "(torch < 2.6) — plain torch.load",
            file=sys.stderr,
            flush=True,
        )
        return torch.load(preset_path, map_location=map_loc)
    except Exception:
        safe_print(
            "[SUBPROCESS] weights_only=True preset load failed — retrying with weights_only=False",
            file=sys.stderr,
            flush=True,
        )
        with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
            return torch.load(preset_path, map_location=map_loc, weights_only=False)


# V0.6.16: the transformers-v5 compatibility state. Set once by
# _install_transformers_compat() so a second load command can never
# double-wrap a patch or re-alias a module.
_REGISTER_COMPAT_INSTALLED = False


def _make_tolerant_register(fn):
    """V0.6.16: wrap a register callable so the native-VibeVoice duplicate
    ValueError is retried with exist_ok=True — the from-source class then
    wins, the exact end-state of a transformers WITHOUT native vibevoice.
    Every other ValueError (e.g. the config-class mismatch) propagates
    unchanged; a caller that already passes exist_ok=True goes straight
    through. The retried collision is named in a NOTE line so the live
    log says what happened and that it is safe."""

    def _wrapper(*args, **kwargs):
        if kwargs.get("exist_ok"):
            return fn(*args, **kwargs)
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            if "is already used by a Transformers model" not in str(exc):
                raise
            key = args[1] if len(args) > 1 else kwargs.get("key") or kwargs.get("config_class")
            safe_print(
                f"[SUBPROCESS] NOTE: {getattr(key, '__name__', key)!r} is "
                "already registered by your transformers' native VibeVoice "
                "support — re-registering the from-source class (safe: the "
                "app instantiates the from-source classes directly).",
                file=sys.stderr,
                flush=True,
            )
            retry = dict(kwargs)
            retry["exist_ok"] = True
            return fn(*args, **retry)

    return _wrapper


def _patch_lazy_auto_mapping_register():
    """V0.6.16 primary patch: the shared _LazyAutoMapping.register — the
    single choke point every Auto*.register call flows through (AutoModel,
    AutoModelForCausalLM and the rest). Returns True when patched."""
    try:
        from transformers.models.auto.auto_factory import _LazyAutoMapping

        original = _LazyAutoMapping.register
    except Exception:
        return False
    if original is None or getattr(original, "_vv_tolerant", False):
        return False
    wrapped = _make_tolerant_register(original)
    wrapped._vv_tolerant = True
    _LazyAutoMapping.register = wrapped
    return True


def _patch_auto_classmethods(transformers):
    """V0.6.16 fallback patch: the documented AutoModel.register /
    AutoModelForCausalLM.register classmethods — used only when the
    private _LazyAutoMapping path moved (a future transformers layout).
    Returns the patched names."""
    patched = []
    for auto_name in ("AutoModel", "AutoModelForCausalLM"):
        try:
            auto_cls = getattr(transformers, auto_name, None)
            original = getattr(auto_cls, "register", None) if auto_cls else None
            if auto_cls is not None and original is not None:
                func = getattr(original, "__func__", original)
                if not getattr(func, "_vv_tolerant", False):
                    wrapped = _make_tolerant_register(func)
                    wrapped._vv_tolerant = True
                    auto_cls.register = classmethod(wrapped)
                    patched.append(f"{auto_name}.register")
        except Exception:
            continue
    return patched


def _tolerate_native_vibevoice_register():
    """V0.6.16: survive transformers' NATIVE VibeVoice registrations.

    transformers v5.13+ ships VibeVoice natively (models/vibevoice*), and
    its auto-generated registry (models/auto/auto_mappings.py) already
    contains the config-class NAME 'VibeVoiceAcousticTokenizerConfig'.
    The from-source vibevoice package re-registers its OWN class with
    that same name at import time (modular/modular_vibevoice_tokenizer.py:
    'AutoModel.register(...)'), and transformers' _LazyAutoMapping.register
    checks duplicates BY NAME — so the very first import dies with

      ValueError: '<class 'vibevoice.modular.configuration_vibevoice.
      VibeVoiceAcousticTokenizerConfig'>' is already used by a
      Transformers model.

    which killed every podcast at line 1 (the operator's V0.6.15 report:
    the script generated fine, VibeVoice errored). The mapping entry is
    cosmetic for us — the streaming inference path instantiates its
    classes directly and never resolves them through AutoModel — so the
    duplicate is made harmless: the register call is retried with
    exist_ok=True and a NOTE is logged.

    Belt and braces: the primary patch is the shared mapping register
    (covers AutoModel, AutoModelForCausalLM and every other Auto* class
    the package may register through); if that private path ever moves,
    the documented classmethods are patched instead. If neither can be
    patched the load proceeds unpatched — the V0.6.15 traceback
    diagnostics then still show the original error. Never raises.
    """
    try:
        import transformers

        safe_print(
            f"[SUBPROCESS] transformers {getattr(transformers, '__version__', '?')}",
            file=sys.stderr,
            flush=True,
        )
    except Exception:
        # No transformers at all → the vibevoice import itself will fail
        # with the V0.6.15 install hint; nothing for us to patch.
        safe_print(
            "[SUBPROCESS] (transformers not importable — no register patch needed)",
            file=sys.stderr,
            flush=True,
        )
        return

    if _patch_lazy_auto_mapping_register():
        safe_print(
            "[SUBPROCESS] native-VibeVoice duplicate-register tolerance active "
            "(_LazyAutoMapping.register)",
            file=sys.stderr,
            flush=True,
        )
        return
    patched = _patch_auto_classmethods(transformers)
    if patched:
        safe_print(
            "[SUBPROCESS] native-VibeVoice duplicate-register tolerance active "
            f"({', '.join(patched)})",
            file=sys.stderr,
            flush=True,
        )
    else:
        safe_print(
            "[SUBPROCESS] WARNING: could not install the duplicate-register "
            'tolerance — if the load fails with "is already used by a '
            "Transformers model\", pin 'transformers<5.13' or update the "
            "VibeVoice checkout",
            file=sys.stderr,
            flush=True,
        )


# V0.6.16: the legacy submodule paths the from-source VibeVoice package
# imports that transformers v5 REMOVED (the classes still exist, moved
# into the model package itself). (legacy path, package, class name).
_LEGACY_TOKENIZER_MODULES = [
    (
        "transformers.models.qwen2.tokenization_qwen2_fast",
        "transformers.models.qwen2",
        "Qwen2TokenizerFast",
    ),
]


def _alias_legacy_tokenizer_modules():
    """V0.6.16: alias the tokenizer submodules transformers v5 removed.

    transformers v5 dropped the per-model ``*_fast`` tokenizer submodules —
    e.g. ``transformers.models.qwen2.tokenization_qwen2_fast`` no longer
    exists, but ``Qwen2TokenizerFast`` is still importable from
    ``transformers.models.qwen2`` directly. The from-source vibevoice
    package still imports the legacy path
    (modular/modular_vibevoice_text_tokenizer.py), which dies with
    ModuleNotFoundError right AFTER the register fix unblocks the first
    import — the second act of the same v5 breakage (proven live against
    transformers 5.17.0). Each legacy path is pre-registered in sys.modules
    as a one-attribute alias module built from the package's own class;
    when the REAL module exists (transformers < 5) nothing is aliased at
    all. Never raises.
    """
    import importlib
    import types

    for legacy_path, package_name, class_name in _LEGACY_TOKENIZER_MODULES:
        if legacy_path in sys.modules:
            continue
        try:
            importlib.import_module(legacy_path)
            continue  # the real module exists — nothing to alias
        except ImportError:
            pass
        try:
            package = importlib.import_module(package_name)
            real_class = getattr(package, class_name, None)
        except Exception:
            continue  # the vibevoice import will surface the real error
        if real_class is None:
            continue
        alias = types.ModuleType(legacy_path)
        setattr(alias, class_name, real_class)
        sys.modules[legacy_path] = alias
        safe_print(
            f"[SUBPROCESS] NOTE: aliased {legacy_path} (removed in "
            f"transformers v5) — {class_name} taken from {package_name}",
            file=sys.stderr,
            flush=True,
        )


def _install_transformers_compat():
    """V0.6.16: the transformers-v5 compatibility layer for the from-source
    VibeVoice package — both shims proven against the REAL stack (torch
    2.14 CPU + transformers 5.17.0 + microsoft/VibeVoice @ main, the
    operator's exact failure reproduced first):

    1. _tolerate_native_vibevoice_register() — the native-VibeVoice
       duplicate registration that kills the import at
       modular_vibevoice_tokenizer.py:1200;
    2. _alias_legacy_tokenizer_modules() — the removed *_fast tokenizer
       submodule paths that kill it at
       modular_vibevoice_text_tokenizer.py one import later.

    Idempotent; never raises.
    """
    global _REGISTER_COMPAT_INSTALLED
    if _REGISTER_COMPAT_INSTALLED:
        return
    _REGISTER_COMPAT_INSTALLED = True
    _tolerate_native_vibevoice_register()
    _alias_legacy_tokenizer_modules()


def _transformers_major():
    """V0.6.17: the transformers MAJOR version (0 when unimportable) —
    gates the from_pretrained kwarg names: v5 renamed `torch_dtype` to
    `dtype` (the rig's log shows the deprecation warning on every load),
    while v4 does not know `dtype` at all (it would leak into the model
    kwargs and TypeError)."""
    try:
        import transformers

        return int(getattr(transformers, "__version__", "0").split(".")[0])
    except Exception:
        return 0


def _meta_default_device_active(torch):
    """V0.6.17 probe: is a meta-device init context active right now?

    transformers>=5 instantiates every from_pretrained model inside
    `with torch.device("meta")` (unconditionally — `low_cpu_mem_usage`
    was REMOVED in v5, so it cannot be turned off), and torch's device
    context redirects every device-unspecified tensor FACTORY call
    (`torch.tensor`, `torch.linspace`, `torch.empty`, ...) to the meta
    device. `torch.from_numpy` is NOT redirected — which is exactly why
    the operator's crash singled out the scheduler's `sigmas` (a
    `torch.tensor` chain) while its `timesteps` (`from_numpy`) stayed
    real.
    """
    try:
        return bool(torch.empty(0).is_meta)
    except Exception:
        return False


def _guard_scheduler_meta_init():
    """V0.6.17: keep VibeVoice's noise scheduler REAL under transformers
    v5 meta-device model init.

    transformers v5 builds every from_pretrained model on the meta device
    (`get_init_context` → `torch.device("meta")`) so parameters exist
    only as shapes until the checkpoint streams in — and its own
    `meta_device_safe_creation_ops` patches ONLY `torch.linspace` against
    that (identical in 5.14.1 and 5.17.0; `torch.arange` deliberately
    not patched, `torch.tensor`/`as_tensor` not patched at all).
    VibeVoice-Realtime's config uses `ddpm_beta_schedule: "cosine"`, so
    the scheduler's betas come from `betas_for_alpha_bar(...)` →
    `torch.tensor(...)` → a META tensor, and dpm_solver.py:295's
    `.to("cpu")` dies with

      NotImplementedError: Cannot copy out of meta tensor; no data!

    (the operator's V0.6.16 paste-back: the podcast stopped at line 1
    with no audio; reproduced byte-for-byte against transformers 5.14.1
    + torch + microsoft/VibeVoice @ main + the real 2 GB checkpoint
    before this fix was written).

    The guard wraps `DPMSolverMultistepScheduler.__init__`: when a meta
    context is active it re-enters `with torch.device("cpu")` around the
    original init. torch keeps a SINGLE DeviceContext at the bottom of
    the function-mode stack, so the nested CPU context REPLACES the meta
    one for the duration and every factory call produces a real CPU
    tensor — proven live for BOTH mechanisms: the v5 `torch.device`
    context manager AND the accelerate-style
    `torch.utils._device.DeviceContext` that transformers v4 + device_map
    uses. The scheduler holds no checkpoint state (zero scheduler keys
    in model.safetensors — verified), so it MUST be built real at init
    time; parameters and buffers stay on the meta path and are
    materialized by from_pretrained as usual.

    Fast path: no meta context (older stacks) → the original init runs
    untouched. Idempotent; never raises — an unpatchable scheduler only
    means the load fails with the original error, which the V0.6.15
    traceback diagnostics then name in the log.
    """
    try:
        from vibevoice.schedule.dpm_solver import DPMSolverMultistepScheduler
    except Exception:
        safe_print(
            "[SUBPROCESS] WARNING: could not install the scheduler "
            'meta-init guard — if the load fails with "Cannot copy out '
            'of meta tensor", update the VibeVoice checkout or pin '
            "'transformers<5'",
            file=sys.stderr,
            flush=True,
        )
        return
    original = DPMSolverMultistepScheduler.__dict__.get("__init__")
    if original is None or getattr(original, "_vv_meta_guard", False):
        # No own __init__ to guard (or already guarded) — nothing to do.
        return

    def _meta_guarded_init(self, *args, **kwargs):
        import torch

        if not _meta_default_device_active(torch):
            return original(self, *args, **kwargs)
        safe_print(
            "[SUBPROCESS] NOTE: meta-device model init detected "
            "(transformers v5) — building the VibeVoice noise scheduler "
            "on real CPU tensors",
            file=sys.stderr,
            flush=True,
        )
        # The nested CPU device context replaces the meta one at the
        # bottom of torch's mode stack (the single-DeviceContext
        # invariant) for the duration of the scheduler init.
        with torch.device("cpu"):
            return original(self, *args, **kwargs)

    _meta_guarded_init._vv_meta_guard = True
    DPMSolverMultistepScheduler.__init__ = _meta_guarded_init


def _tolerate_v5_tie_weights_signature():
    """V0.6.17: survive transformers v5's tie_weights() call signature.

    transformers v5's init_weights() invokes the model's tie_weights with
    v5-only kwargs (modeling_utils.py:3319 →
    ``self.tie_weights(recompute_mapping=False)``; the v5 base signature
    is ``tie_weights(missing_keys=None, recompute_mapping=True)``), but
    the from-source VibeVoice override
    (modeling_vibevoice_streaming_inference.py:204) is ``def
    tie_weights(self)`` — no arguments at all. The load therefore dies
    with

      TypeError: ...tie_weights() got an unexpected keyword argument
      'recompute_mapping'

    one layer AFTER the scheduler guard unblocks the meta-init crash
    (proven live against transformers 5.14.1 + the real checkpoint: the
    operator's rig would hit this exact TypeError next).

    The wrapper accepts and drops the two known v5-only kwargs and
    forwards to the original override, whose tying logic (lm_head ←
    embed_tokens under tie_word_embeddings — a no-op for
    VibeVoice-Realtime, whose config sets it false) does not use them.
    Any OTHER unexpected kwarg still propagates — a future incompatibility
    must surface loudly in the V0.6.15 traceback diagnostics, not be
    silently swallowed. No-op on transformers v4 (which calls
    tie_weights() with no arguments). Idempotent; never raises.
    """
    try:
        from vibevoice.modular.modeling_vibevoice_streaming_inference import (
            VibeVoiceStreamingForConditionalGenerationInference,
        )
    except Exception:
        return  # the load's own import error will name the real problem
    original = VibeVoiceStreamingForConditionalGenerationInference.__dict__.get("tie_weights")
    if original is None or getattr(original, "_vv_tie_tolerant", False):
        # No own override to tolerate (the v5 base accepts the kwargs
        # natively) or already tolerated — nothing to do.
        return

    def _tolerant_tie_weights(self, *args, **kwargs):
        kwargs.pop("missing_keys", None)
        kwargs.pop("recompute_mapping", None)
        return original(self, *args, **kwargs)

    _tolerant_tie_weights._vv_tie_tolerant = True
    VibeVoiceStreamingForConditionalGenerationInference.tie_weights = _tolerant_tie_weights


def _tolerate_v5_prepare_generation_config():
    """V0.6.17: survive the v5 signature change in
    GenerationMixin._prepare_generation_config (the generate-time act of
    the same v5 breakage — surfaced by the live end-to-end proof against
    transformers 5.14.1 + the real checkpoint once the load was fixed).

    The from-source package (developed against transformers 4.5x) calls

      self._prepare_generation_config(generation_config, True,
          speech_start_id=..., speech_end_id=...,
          speech_diffusion_id=..., **kwargs)

    but v5's signature is ``_prepare_generation_config(self,
    generation_config, **kwargs)`` — the second positional TypeErrors
    with "takes 2 positional arguments but 3 were given" the moment a
    podcast's first line calls model.generate().

    What the dropped arguments mean (both verified against the 4.51.3
    source): the positional is v4's ``use_model_defaults`` — consulted
    ONLY when generation_config is None, which VibeVoice never does (it
    builds one right above the call); the three speech ids are re-set on
    the returned generation_config by the caller on the very next lines.
    Dropping exactly those is therefore semantically identical on v4 and
    v5 alike; any OTHER unexpected argument still propagates so a future
    drift surfaces loudly. Installed on the model class (shadows the
    mixin; the global GenerationMixin is untouched). Idempotent; never
    raises.
    """
    try:
        from vibevoice.modular.modeling_vibevoice_streaming_inference import (
            VibeVoiceStreamingForConditionalGenerationInference,
        )
    except Exception:
        return  # the load's own import error will name the real problem
    original = getattr(
        VibeVoiceStreamingForConditionalGenerationInference,
        "_prepare_generation_config",
        None,
    )
    if original is None or getattr(original, "_vv_prepare_gen_tolerant", False):
        return  # nothing to shadow (e.g. a stub without the mixin)

    def _tolerant_prepare_generation_config(self, generation_config=None, *args, **kwargs):
        kwargs.pop("speech_start_id", None)
        kwargs.pop("speech_end_id", None)
        kwargs.pop("speech_diffusion_id", None)
        return original(self, generation_config, **kwargs)

    _tolerant_prepare_generation_config._vv_prepare_gen_tolerant = True
    VibeVoiceStreamingForConditionalGenerationInference._prepare_generation_config = (
        _tolerant_prepare_generation_config
    )


# V0.6.17: the legacy-preset NOTE fires once per process — the preset is
# re-loaded for EVERY generated line and the conversion is deterministic.
_LEGACY_CACHE_NOTE_SHOWN = False


def _legacy_cache_needs_rebuild(cache, cache_layer_mixin):
    """V0.6.17 helper: is this KV cache a transformers-4.5x pickle (plain
    `key_cache` tensor lists) rather than the installed version's real
    CacheLayerMixin layers?"""
    if not hasattr(cache, "key_cache"):
        return False  # not the 4.x cache format at all
    layers = getattr(cache, "layers", None)
    return not (layers and len(layers) and isinstance(layers[0], cache_layer_mixin))


def _rebuild_legacy_preset_cache(torch, cache_cls, old):
    """V0.6.17 helper: one legacy 4.5x cache → the installed version's
    format, layer-by-layer through `cache_cls.update()` (real
    CacheLayerMixin layers; the tensors themselves untouched). Returns
    the rebuilt cache, or None when the shape is not the plain paired
    4.x format. Raises on a non-tensor layer — the caller names it."""
    keys = list(getattr(old, "key_cache", None) or [])
    values = list(getattr(old, "value_cache", None) or [])
    if not keys or len(keys) != len(values):
        return None
    fresh = cache_cls()
    for idx, (k, v) in enumerate(zip(keys, values, strict=True)):
        if not (torch.is_tensor(k) and torch.is_tensor(v)):
            raise TypeError(f"layer {idx} is not a tensor pair")
        fresh.update(k, v, idx)
    return fresh


def _preset_cache_outputs(preset):
    """V0.6.17 helper: the model outputs inside a voice preset — the four
    BaseModelOutputWithPast entries of a dict preset, or a preset that is
    a single output itself."""
    if isinstance(preset, dict):
        return [v for v in preset.values() if hasattr(v, "past_key_values")]
    return [preset] if hasattr(preset, "past_key_values") else []


def _modernize_legacy_preset_cache(torch, preset):
    """V0.6.17: rebuild transformers-4.5x voice-preset KV caches in the
    installed transformers' format.

    The official voice presets are pickled against transformers 4.5x
    DynamicCache internals — plain ``key_cache``/``value_cache`` tensor
    lists (verified against the real en-Carter_man.pt: four
    BaseModelOutputWithPast entries — lm/tts_lm/neg_lm/neg_tts_lm — each
    carrying a 4.x-format DynamicCache). transformers v5 rearchitected
    the cache (a ``layers`` list of CacheLayerMixin objects), and
    VibeVoice's own bridge for that (``_ensure_cache_has_layers`` —
    MockCacheLayer wrappers, written for transformers 4.57) no longer
    satisfies v5.14's strict isinstance check, so the first model
    forward dies with

      ValueError: `get_seq_length` can only be called on Attention
      layers, and the current Cache seem to only contain LinearAttention
      layers.

    (surfaced by the live end-to-end proof against transformers 5.14.1 +
    the real checkpoint + the official preset — the operator's rig hits
    it on the FIRST generated line once the load is fixed).

    Each legacy cache is rebuilt by _rebuild_legacy_preset_cache; a
    preset already in the new format is left alone, so presets re-saved
    under v5 keep working. Best-effort: any unexpected shape is left
    untouched so the original behavior (and the V0.6.15 traceback
    diagnostics) plays out. Never raises.
    """
    global _LEGACY_CACHE_NOTE_SHOWN
    try:
        from transformers.cache_utils import CacheLayerMixin, DynamicCache
    except Exception:
        return  # no transformers cache classes — the load path names it
    rebuilt = 0
    for out in _preset_cache_outputs(preset):
        old = getattr(out, "past_key_values", None)
        if old is None or not _legacy_cache_needs_rebuild(old, CacheLayerMixin):
            continue
        try:
            fresh = _rebuild_legacy_preset_cache(torch, DynamicCache, old)
        except Exception:
            safe_print(
                "[SUBPROCESS] WARNING: could not rebuild one legacy "
                "preset cache — leaving it untouched",
                file=sys.stderr,
                flush=True,
            )
            continue
        if fresh is not None:
            out.past_key_values = fresh
            rebuilt += 1
    if rebuilt and not _LEGACY_CACHE_NOTE_SHOWN:
        _LEGACY_CACHE_NOTE_SHOWN = True
        safe_print(
            f"[SUBPROCESS] NOTE: rebuilt {rebuilt} legacy voice-preset "
            "cache(s) into the installed transformers' format (v5 cache "
            "rearchitecture; further conversions are silent)",
            file=sys.stderr,
            flush=True,
        )


def main():
    model = None
    processor = None
    model_path = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            continue

        action = cmd.get("action", "")

        if action == "quit":
            break

        elif action == "load":
            model_path = cmd.get("model_path", "")
            if not model_path or not os.path.exists(model_path):
                safe_print(
                    json.dumps({"status": "error", "error": f"Model path not found: {model_path}"})
                )
                continue

            try:
                import torch

                # V0.6.16: transformers v5 (the operator's rig runs it)
                # breaks the from-source vibevoice import twice — the
                # native-VibeVoice duplicate registration AND the removed
                # *_fast tokenizer submodule. Install the compat layer
                # BEFORE the first import.
                _install_transformers_compat()
                from vibevoice.modular.modeling_vibevoice_streaming_inference import (
                    VibeVoiceStreamingForConditionalGenerationInference,
                )
                from vibevoice.processor.vibevoice_streaming_processor import (
                    VibeVoiceStreamingProcessor,
                )

                # V0.6.17: transformers v5 breaks the VibeVoice chain in
                # three MORE places beyond the V0.6.16 import fixes — the
                # meta-device model init (the scheduler's cosine betas
                # become meta tensors; dpm_solver.py:295 dies with
                # "Cannot copy out of meta tensor"), the tie_weights()
                # call signature, and the _prepare_generation_config()
                # call signature (the first generate()). Wrap all three
                # AFTER the vibevoice import and BEFORE from_pretrained.
                _guard_scheduler_meta_init()
                _tolerate_v5_tie_weights_signature()
                _tolerate_v5_prepare_generation_config()

                # V11.59.0: Use the CACHED CUDA status from the early torch
                # import (before vibevoice/transformers were imported).
                # Those packages load conflicting DLLs that break
                # torch.cuda.is_available() — re-checking here returns False
                # even though CUDA worked at import time.
                cuda_ok = _SUBPROCESS_CUDA_OK
                # Also check the live value for diagnostic logging
                live_cuda = torch.cuda.is_available()
                safe_print(
                    f"[SUBPROCESS] CUDA cached (early): {_SUBPROCESS_CUDA_OK}", file=sys.stderr
                )
                safe_print(
                    f"[SUBPROCESS] CUDA live (after vv import): {live_cuda}", file=sys.stderr
                )
                safe_print(
                    f"[SUBPROCESS] torch.version.cuda = {torch.version.cuda!r}", file=sys.stderr
                )
                if _SUBPROCESS_CUDA_DEVICE:
                    safe_print(
                        f"[SUBPROCESS] GPU (cached): {_SUBPROCESS_CUDA_DEVICE}", file=sys.stderr
                    )
                if cuda_ok != live_cuda:
                    safe_print(
                        f"[SUBPROCESS] WARNING: CUDA status changed! "
                        f"Early={cuda_ok}, Live={live_cuda}. "
                        f"vibevoice/transformers imports broke CUDA. "
                        f"Using cached value: {cuda_ok}.",
                        file=sys.stderr,
                    )
                if cuda_ok:
                    device = "cuda"
                    if _SUBPROCESS_CUDA_DEVICE:
                        safe_print(f"[SUBPROCESS] GPU: {_SUBPROCESS_CUDA_DEVICE}", file=sys.stderr)
                    try:
                        vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
                        # V0.6.15: FREE memory too — total alone hides the
                        # llama.cpp / Ollama VRAM hold that kills the load.
                        _free_b, _total_b = torch.cuda.mem_get_info()
                        free_mb = _free_b // (1024 * 1024)
                        safe_print(
                            f"[SUBPROCESS] VRAM: {free_mb} MB free / {vram_mb} MB total",
                            file=sys.stderr,
                        )
                        if free_mb < 3584:
                            safe_print(
                                f"[SUBPROCESS] WARNING: only {free_mb} MB VRAM free — "
                                f"VibeVoice needs ~2.6 GB. llama.cpp / Ollama may be "
                                f"holding the GPU; the load may fail with CUDA "
                                f"out-of-memory.",
                                file=sys.stderr,
                            )
                        else:
                            safe_print(
                                f"[SUBPROCESS] Forcing ALL layers on GPU ({vram_mb} MB)",
                                file=sys.stderr,
                            )
                    except Exception:
                        safe_print(
                            "[SUBPROCESS] (could not read VRAM — using cached device)",
                            file=sys.stderr,
                        )
                    device_map = "cuda:0"
                    dtype = torch.bfloat16
                else:
                    device = "cpu"
                    safe_print(
                        f"[SUBPROCESS] WARNING: CUDA NOT available - VibeVoice will run on CPU "
                        f"(~100x slower). torch.version.cuda={torch.version.cuda!r}. "
                        f"If None, you have the CPU-only torch build: reinstall with "
                        f"pip install torch --index-url https://download.pytorch.org/whl/cu126",
                        file=sys.stderr,
                    )
                    device_map = "cpu"
                    # bfloat16 is poorly supported on CPU; use float32 there.
                    dtype = torch.float32
                safe_print(json.dumps({"status": "loading", "device": device}))

                processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
                # V0.6.17: transformers v5 renamed `torch_dtype`→`dtype`
                # (the rig's log showed the deprecation warning on every
                # load); v4 does not accept `dtype` — gate on the major.
                load_kwargs = {
                    "device_map": device_map,
                    "attn_implementation": "sdpa",
                }
                load_kwargs["dtype" if _transformers_major() >= 5 else "torch_dtype"] = dtype
                model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                    model_path,
                    **load_kwargs,
                )
                model.eval()
                model.set_ddpm_inference_steps(num_steps=5)
                model = model.to(dtype)
                # V11.43.3: verify parameters are on the expected device.
                if cuda_ok:
                    cpu_params = sum(1 for p in model.parameters() if p.device.type == "cpu")
                    if cpu_params > 0:
                        safe_print(
                            f"[SUBPROCESS] WARNING: {cpu_params} params still on CPU, moving to GPU",
                            file=sys.stderr,
                        )
                        model = model.to("cuda")

                safe_print(json.dumps({"status": "ready", "device": device}))

            except Exception as e:
                # V0.6.15: full traceback to stderr as well (the JSON copy is
                # truncated to 500 chars — the live log keeps the whole story).
                safe_print("[SUBPROCESS] TRACEBACK (load):", file=sys.stderr, flush=True)
                safe_print(traceback.format_exc(), file=sys.stderr, flush=True)
                safe_print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": str(e),
                            "traceback": traceback.format_exc()[:500],
                        }
                    )
                )

        elif action == "generate":
            if model is None or processor is None:
                safe_print(json.dumps({"status": "error", "error": "Model not loaded"}))
                continue

            text = cmd.get("text", "")
            voice_name = cmd.get("voice", "en-Carter_man")
            voices_dir = cmd.get("voices_dir", "")
            out_path = cmd.get("out_path", "")
            cfg_scale = cmd.get("cfg_scale", 1.5)  # V11.40.1: emotion control

            if not text or not out_path:
                safe_print(json.dumps({"status": "error", "error": "Missing text or out_path"}))
                continue

            try:
                import time as _time

                import soundfile as sf
                import torch
                from transformers.cache_utils import DynamicCache
                from transformers.modeling_outputs import BaseModelOutputWithPast

                # V11.59.0: use the CACHED CUDA status, not the live one.
                # torch.cuda.is_available() returns False here because
                # vibevoice/transformers imports broke it.
                cuda_ok = _SUBPROCESS_CUDA_OK
                safe_print(
                    f"[SUBPROCESS] generate: text_len={len(text)}, "
                    f"cuda={cuda_ok} (cached), device={model.device if hasattr(model, 'device') else '?'}",
                    file=sys.stderr,
                    flush=True,
                )

                # Find voice preset
                voices_path = Path(voices_dir)
                preset_path = voices_path / f"{voice_name}.pt"
                if not preset_path.exists():
                    # Try to find any .pt file
                    pt_files = list(voices_path.rglob("*.pt"))
                    if pt_files:
                        preset_path = pt_files[0]
                    else:
                        safe_print(
                            json.dumps(
                                {
                                    "status": "error",
                                    "error": f"Voice preset not found: {preset_path}",
                                }
                            ),
                            flush=True,
                        )
                        continue

                # V11.41.8: use the correct map_location based on device
                map_loc = "cuda" if cuda_ok else "cpu"
                t0 = _time.time()
                cached_prompt = _load_voice_preset(
                    torch,
                    preset_path,
                    map_loc,
                    (BaseModelOutputWithPast, DynamicCache),
                )
                # V0.6.17: the official presets pickle transformers-4.5x
                # DynamicCache internals; v5's rearchitected cache rejects
                # them on the first forward. Rebuild before use.
                _modernize_legacy_preset_cache(torch, cached_prompt)
                safe_print(
                    f"[SUBPROCESS] voice preset loaded in {_time.time() - t0:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )

                # Prepare inputs
                t0 = _time.time()
                inputs = processor.process_input_with_cached_prompt(
                    text=text,
                    cached_prompt=cached_prompt,
                    padding=True,
                    return_tensors="pt",
                    return_attention_mask=True,
                )
                # V11.41.8: use correct device + dtype
                dev = "cuda" if cuda_ok else "cpu"
                dt = torch.bfloat16 if dev == "cuda" else torch.float32
                inputs = {
                    k: v.to(dev).to(dt)
                    if hasattr(v, "to")
                    and torch.is_tensor(v)
                    and v.dtype in (torch.float32, torch.float16)
                    else (v.to(dev) if hasattr(v, "to") else v)
                    for k, v in inputs.items()
                }
                safe_print(
                    f"[SUBPROCESS] input processed in {_time.time() - t0:.1f}s, "
                    f"dev={dev}, dtype={dt}",
                    file=sys.stderr,
                    flush=True,
                )

                # V11.50.0: verify model params are on the expected device
                if cuda_ok:
                    cpu_params = sum(1 for p in model.parameters() if p.device.type == "cpu")
                    if cpu_params > 0:
                        safe_print(
                            f"[SUBPROCESS] ⚠️ {cpu_params} params on CPU — forcing to GPU",
                            file=sys.stderr,
                            flush=True,
                        )
                        model = model.to("cuda")

                safe_print(json.dumps({"status": "generating", "text_len": len(text)}), flush=True)

                # Generate (V11.40.1: use cfg_scale from command for emotion control)
                t0 = _time.time()
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=None,
                    cfg_scale=cfg_scale,
                    tokenizer=processor.tokenizer,
                    generation_config={"do_sample": False},
                    verbose=False,
                    all_prefilled_outputs=cached_prompt,
                )
                gen_time = _time.time() - t0
                safe_print(
                    f"[SUBPROCESS] model.generate() done in {gen_time:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )

                # Save audio
                t0 = _time.time()
                processor.save_audio(outputs.speech_outputs[0], output_path=out_path)
                if os.path.exists(out_path):
                    audio_data, sr = sf.read(out_path)
                    duration = len(audio_data) / sr
                    rtf = gen_time / duration if duration > 0 else 0

                    # V11.52.0/V11.65.0: Upsampling DISABLED.
                    # The 48kHz upsampling via scipy was causing audio
                    # distortion (sounding like a "ghoul/mountain troll").
                    # VibeVoice's native 24kHz output is kept as-is.
                    # The clarity improvement wasn't worth the distortion risk.
                    # To re-enable: uncomment the block below.
                    #
                    # TARGET_SR = 48000
                    # if sr < TARGET_SR:
                    #     try:
                    #         from scipy.signal import resample_poly
                    #         if audio_data.ndim == 1:
                    #             up = resample_poly(audio_data, TARGET_SR, sr)
                    #         else:
                    #             up = resample_poly(audio_data, TARGET_SR, sr, axis=0)
                    #         max_val = _np.max(_np.abs(up))
                    #         if max_val > 0.99:
                    #             up = up * (0.99 / max_val)
                    #         sf.write(out_path, up.astype(_np.float32), TARGET_SR)
                    #         sr = TARGET_SR
                    #         duration = len(up) / sr
                    #     except Exception:
                    #         pass

                    safe_print(
                        f"[SUBPROCESS] audio saved in {_time.time() - t0:.1f}s — "
                        f"{duration:.1f}s audio, {rtf:.1f}x realtime, "
                        f"{sr}Hz (native, no upsampling)",
                        file=sys.stderr,
                        flush=True,
                    )
                    safe_print(
                        json.dumps(
                            {
                                "status": "ok",
                                "out_path": out_path,
                                "duration": round(duration, 1),
                                "sample_rate": sr,
                                "gen_time": round(gen_time, 1),
                            }
                        ),
                        flush=True,
                    )
                else:
                    safe_print(
                        json.dumps({"status": "error", "error": "File not written"}), flush=True
                    )

            except Exception as e:
                # V0.6.15: the FULL traceback also goes to stderr — the
                # parent's stderr drain logs it live with the [vibevoice]
                # prefix, so the JSON's 500-char truncation is no longer
                # the only copy the operator can paste back.
                safe_print("[SUBPROCESS] TRACEBACK (generate):", file=sys.stderr, flush=True)
                safe_print(traceback.format_exc(), file=sys.stderr, flush=True)
                safe_print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": str(e),
                            "traceback": traceback.format_exc()[:500],
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
