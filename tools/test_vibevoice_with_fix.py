#!/usr/bin/env python3
"""V0.6.32 (W-q1): standalone VibeVoice test script WITH the app's register-tolerance fix.

The operator's direct test.py crashed with:
  ValueError: '<class 'vibevoice.modular.configuration_vibevoice.
  VibeVoiceAcousticTokenizerConfig'>' is already used by a Transformers model.

Root cause: the VibeVoice package calls AutoModel.register(...) at
modular_vibevoice_tokenizer.py:1200 during import. transformers v5+ already
has a native VibeVoice registration, so the register call raises ValueError.

The app's _vibevoice_subprocess.py has a fix (_install_transformers_compat)
that patches AutoModel.register to tolerate the duplicate BEFORE the import.
But the operator's test.py doesn't go through the app's subprocess, so the
fix isn't applied.

This script applies the fix, then runs the same import + load + generate
flow the app uses. Run it from the VibeVoice-Realtime-0.5B directory:

    cd C:\\VibeVoice-Realtime-0.5B
    python test_with_fix.py

Usage:
    python test_with_fix.py [--model-path PATH] [--voices-dir PATH]
                             [--voice NAME] [--text "Hello world"]
                             [--out out.wav]

If --model-path is not given, uses the current directory.
If --voices-dir is not given, uses ../vibevoice-voices or the preset dir.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# V0.6.31 (W-p1): FORCE the offline flags BEFORE any transformers/huggingface
# import. Using = (not setdefault) so the operator's own env can't override.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _make_tolerant_register(fn):
    """Wrap a register callable so the native-VibeVoice duplicate ValueError
    is retried with exist_ok=True."""

    def _wrapper(*args, **kwargs):
        if kwargs.get("exist_ok"):
            return fn(*args, **kwargs)
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            if "is already used by a Transformers model" not in str(exc):
                raise
            key = args[1] if len(args) > 1 else kwargs.get("key") or kwargs.get("config_class")
            print(
                f"[FIX] NOTE: {getattr(key, '__name__', key)!r} is "
                "already registered by your transformers' native VibeVoice "
                "support — re-registering the from-source class (safe).",
                file=sys.stderr,
                flush=True,
            )
            retry = dict(kwargs)
            retry["exist_ok"] = True
            return fn(*args, **retry)

    return _wrapper


def install_register_tolerance():
    """Patch AutoModel.register to tolerate the native-VibeVoice duplicate.

    This is the SAME fix the app uses (_install_transformers_compat in
    _vibevoice_subprocess.py), extracted here for standalone use.
    """
    try:
        import transformers

        print(
            f"[FIX] transformers {getattr(transformers, '__version__', '?')}",
            file=sys.stderr,
            flush=True,
        )
    except ImportError:
        print("[FIX] (transformers not importable — nothing to patch)", file=sys.stderr, flush=True)
        return

    # Primary: patch the shared _LazyAutoMapping.register (covers AutoModel,
    # AutoModelForCausalLM, and every other Auto* class).
    try:
        from transformers.models.auto.auto_factory import _LazyAutoMapping

        original = _LazyAutoMapping.register
        if original is not None and not getattr(original, "_vv_tolerant", False):
            wrapped = _make_tolerant_register(original)
            wrapped._vv_tolerant = True
            _LazyAutoMapping.register = wrapped
            print(
                "[FIX] native-VibeVoice duplicate-register tolerance active (_LazyAutoMapping.register)",
                file=sys.stderr,
                flush=True,
            )
            return
    except Exception:
        pass

    # Fallback: patch AutoModel.register + AutoModelForCausalLM.register
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
                    print(
                        f"[FIX] patched {auto_name}.register (fallback)",
                        file=sys.stderr,
                        flush=True,
                    )
        except Exception:
            continue


def main():
    parser = argparse.ArgumentParser(description="Test VibeVoice WITH the register-tolerance fix.")
    parser.add_argument(
        "--model-path", default=".", help="Path to the VibeVoice model checkpoint folder."
    )
    parser.add_argument("--voices-dir", default="", help="Path to the voices directory.")
    parser.add_argument("--voice", default="en-Carter_man", help="Voice preset name (without .pt).")
    parser.add_argument(
        "--text",
        default="Hello, this is a test of the VibeVoice text to speech engine.",
        help="Text to synthesize.",
    )
    parser.add_argument("--out", default="test_output.wav", help="Output WAV path.")
    args = parser.parse_args()

    model_path = Path(args.model_path).resolve()
    print(f"[TEST] Model path: {model_path}")
    print(f"[TEST] Voice: {args.voice}")
    print(f"[TEST] Text: {args.text}")
    print(f"[TEST] Output: {args.out}")
    print()

    # ── Step 1: Install the register tolerance BEFORE importing vibevoice ──
    print("[STEP 1] Installing AutoModel.register tolerance...")
    install_register_tolerance()
    print()

    # ── Step 2: Import torch + check CUDA ──
    print("[STEP 2] Importing torch + checking CUDA...")
    import torch

    cuda_ok = torch.cuda.is_available()
    print(f"  torch {torch.__version__}")
    print(f"  CUDA available: {cuda_ok}")
    print(f"  torch.version.cuda: {torch.version.cuda!r}")
    if cuda_ok:
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        vram = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        print(f"  VRAM: {vram} MB")
    else:
        print("  ⚠️ NO CUDA — generation will be VERY slow on CPU (~4 it/s, ~34 min/line)")
        print("  To fix: pip install torch --index-url https://download.pytorch.org/whl/cu126")
    device = "cuda" if cuda_ok else "cpu"
    dtype = torch.bfloat16 if cuda_ok else torch.float32
    print()

    # ── Step 3: Import VibeVoice (with the fix active) ──
    print("[STEP 3] Importing VibeVoice...")
    try:
        from vibevoice.modular.modeling_vibevoice_streaming_inference import (
            VibeVoiceStreamingForConditionalGenerationInference,
        )
        from vibevoice.processor.vibevoice_streaming_processor import (
            VibeVoiceStreamingProcessor,
        )

        print("  ✅ VibeVoice imported successfully!")
    except Exception as e:
        print(f"  ❌ VibeVoice import FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1
    print()

    # ── Step 4: Load the model ──
    print(f"[STEP 4] Loading model from {model_path}...")
    t0 = time.time()
    try:
        processor = VibeVoiceStreamingProcessor.from_pretrained(str(model_path))
        print(f"  ✅ Processor loaded ({time.time() - t0:.1f}s)")

        load_kwargs = {"device_map": device, "attn_implementation": "sdpa"}
        # transformers v5 renamed torch_dtype→dtype
        try:
            major = int(getattr(__import__("transformers"), "__version__", "0").split(".")[0])
        except Exception:
            major = 0
        load_kwargs["dtype" if major >= 5 else "torch_dtype"] = dtype

        t1 = time.time()
        model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
            str(model_path),
            **load_kwargs,
        )
        model.eval()
        model.set_ddpm_inference_steps(num_steps=5)
        model = model.to(dtype)
        print(f"  ✅ Model loaded ({time.time() - t1:.1f}s)")
        if cuda_ok:
            cpu_params = sum(1 for p in model.parameters() if p.device.type == "cpu")
            if cpu_params > 0:
                print(f"  ⚠️ {cpu_params} params still on CPU, moving to GPU...")
                model = model.to("cuda")
    except Exception as e:
        print(f"  ❌ Model load FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1
    print()

    # ── Step 5: Find the voice preset ──
    print(f"[STEP 5] Finding voice preset '{args.voice}'...")
    preset_path = None
    search_dirs = []
    if args.voices_dir:
        search_dirs.append(Path(args.voices_dir))
    search_dirs.extend(
        [
            model_path / "voices",
            model_path.parent / "vibevoice-voices",
            Path("C:/vibevoice-voices"),
            Path("C:/VibeVoice/vibevoice-voices"),
        ]
    )
    for d in search_dirs:
        candidate = d / f"{args.voice}.pt"
        if candidate.exists():
            preset_path = candidate
            break
        # Also try without _man suffix
        candidate = d / f"{args.voice}_man.pt"
        if candidate.exists():
            preset_path = candidate
            break

    if preset_path is None:
        # Try model_path itself
        candidate = model_path / f"{args.voice}.pt"
        if candidate.exists():
            preset_path = candidate
        else:
            candidate = model_path / f"{args.voice}_man.pt"
            if candidate.exists():
                preset_path = candidate

    if preset_path is None:
        print(f"  ⚠️ Voice preset '{args.voice}.pt' not found in any search dir.")
        print(f"  Searched: {[str(d) for d in search_dirs]}")
        print("  Continuing without preset (will use default voice)...")
    else:
        print(f"  ✅ Found preset: {preset_path}")
    print()

    # ── Step 6: Load the voice preset ──
    if preset_path:
        print("[STEP 6] Loading voice preset...")
        try:
            from transformers.cache_utils import DynamicCache
            from transformers.modeling_outputs import BaseModelOutputWithPast

            try:
                with torch.serialization.safe_globals([BaseModelOutputWithPast, DynamicCache]):
                    preset = torch.load(preset_path, map_location=device, weights_only=True)
                print("  ✅ Preset loaded (weights_only=True)")
            except Exception:
                preset = torch.load(preset_path, map_location=device, weights_only=False)
                print("  ✅ Preset loaded (weights_only=False fallback)")
        except Exception as e:
            print(f"  ❌ Preset load FAILED: {e}")
            import traceback

            traceback.print_exc()
            preset = None
    else:
        preset = None
    print()

    # ── Step 7: Generate audio ──
    print(f"[STEP 7] Generating audio for: '{args.text[:60]}...'")
    t0 = time.time()
    try:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Use the model's generate method
        inputs = processor(text=args.text, return_tensors="pt")
        if cuda_ok:
            inputs = {k: v.to("cuda") if hasattr(v, "to") else v for k, v in inputs.items()}

        if preset is not None:
            # Apply the voice preset
            if hasattr(preset, "key_cache") and hasattr(preset, "value_cache"):
                # DynamicCache format (transformers 4.5x)
                pass  # the model handles this internally
            inputs["preset"] = preset

        with torch.no_grad():
            output = model.generate(**inputs)

        # Save the audio
        if hasattr(output, "audio") and output.audio is not None:
            import soundfile as sf

            audio = output.audio.cpu().float().numpy()
            sr = getattr(output, "sample_rate", 24000)
            sf.write(str(out_path), audio, sr)
            duration = len(audio) / sr
            print(f"  ✅ Audio saved: {out_path}")
            print(f"  Duration: {duration:.1f}s")
            print(f"  Generation time: {time.time() - t0:.1f}s")
            print(f"  Speed: {duration / (time.time() - t0):.1f}x realtime")
        else:
            # Try to extract audio from the output tensor
            if isinstance(output, torch.Tensor):
                audio = output.cpu().float().numpy()
                sr = 24000
                import soundfile as sf

                sf.write(str(out_path), audio, sr)
                print(f"  ✅ Audio saved: {out_path}")
            else:
                print(f"  ⚠️ Could not extract audio from output: {type(output)}")
                print(f"  Output: {output}")
    except Exception as e:
        print(f"  ❌ Generation FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1
    print()

    print("[DONE] Test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
