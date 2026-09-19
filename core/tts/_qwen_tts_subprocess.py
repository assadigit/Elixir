#!/usr/bin/env python3
"""V11.38.6: Qwen3-TTS persistent subprocess.

This script loads the model ONCE and stays alive, reading generation
requests from stdin. This avoids reloading the 4.5GB model for every
chunk — the #1 cause of slowness.

Protocol:
  1. Parent writes {"action": "load", "model_path": "..."} to stdin
  2. Subprocess loads model, writes {"status": "ready"} to stdout
  3. Parent writes {"action": "generate", "text": "...", "speaker": "...",
     "language": "...", "out_path": "..."} to stdin
  4. Subprocess generates, writes {"status": "ok", "duration": 12.5} to stdout
  5. Repeat step 3 for each chunk
  6. Parent writes {"action": "quit"} to stdin to close

This keeps the model in VRAM across multiple generations.
"""

import json
import os
import sys
import traceback


def main():
    model = None
    model_path = None

    # Read commands line by line from stdin
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
                print(
                    json.dumps({"status": "error", "error": f"Model path not found: {model_path}"}),
                    flush=True,
                )
                continue

            try:
                import torch
                from qwen_tts import Qwen3TTSModel

                device = "cuda" if torch.cuda.is_available() else "cpu"
                # V11.38.7: use fp16 instead of bf16 for 2-4x speedup on RTX 3060.
                # RTX 3060 (Ampere, compute 8.6) has fast fp16 tensor cores but
                # slow bf16 tensor cores.
                dtype = torch.float16 if device == "cuda" else torch.float32

                print(
                    json.dumps({"status": "loading", "device": device, "model_path": model_path}),
                    flush=True,
                )

                model = Qwen3TTSModel.from_pretrained(
                    model_path,
                    device_map=f"{device}:0" if device == "cuda" else "cpu",
                    dtype=dtype,
                )

                # Get available speakers
                try:
                    speakers = list(model.get_supported_speakers())
                except Exception:
                    speakers = []

                print(
                    json.dumps(
                        {
                            "status": "ready",
                            "device": device,
                            "speakers": speakers,
                        }
                    ),
                    flush=True,
                )

            except Exception as e:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                        }
                    ),
                    flush=True,
                )

        elif action == "generate":
            if model is None:
                print(
                    json.dumps({"status": "error", "error": "Model not loaded. Send load first."}),
                    flush=True,
                )
                continue

            text = cmd.get("text", "")
            speaker = cmd.get("speaker", "Vivian")
            language = cmd.get("language", "English")
            out_path = cmd.get("out_path", "")

            if not text or not out_path:
                print(
                    json.dumps({"status": "error", "error": "Missing text or out_path"}), flush=True
                )
                continue

            try:
                import soundfile as sf

                print(json.dumps({"status": "generating", "text_len": len(text)}), flush=True)

                wavs, sr = model.generate_custom_voice(
                    text=text,
                    language=language,
                    speaker=speaker,
                )

                if wavs and len(wavs) > 0:
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    sf.write(out_path, wavs[0], sr)
                    if os.path.exists(out_path):
                        duration = len(wavs[0]) / sr
                        print(
                            json.dumps(
                                {
                                    "status": "ok",
                                    "out_path": out_path,
                                    "duration": round(duration, 1),
                                    "sample_rate": sr,
                                }
                            ),
                            flush=True,
                        )
                    else:
                        print(
                            json.dumps({"status": "error", "error": "File not written"}), flush=True
                        )
                else:
                    print(json.dumps({"status": "error", "error": "No audio produced"}), flush=True)

            except Exception as e:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": str(e),
                            "traceback": traceback.format_exc()[:500],
                        }
                    ),
                    flush=True,
                )

        elif action == "batch_generate":
            # V11.38.6: batch generation — pass multiple texts at once.
            # The model generates them in parallel (much faster than sequential).
            if model is None:
                print(
                    json.dumps({"status": "error", "error": "Model not loaded. Send load first."}),
                    flush=True,
                )
                continue

            items = cmd.get("items", [])  # list of {text, speaker, out_path}
            if not items:
                print(json.dumps({"status": "error", "error": "No items"}), flush=True)
                continue

            try:
                import soundfile as sf

                texts = [item["text"] for item in items]
                speakers = [item.get("speaker", "Vivian") for item in items]
                out_paths = [item["out_path"] for item in items]

                print(json.dumps({"status": "generating", "batch_size": len(items)}), flush=True)

                wavs, sr = model.generate_custom_voice(
                    text=texts,
                    language=[language] * len(items),
                    speaker=speakers,
                )

                if wavs:
                    for _i, (wav, out_path) in enumerate(zip(wavs, out_paths, strict=False)):
                        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                        sf.write(out_path, wav, sr)
                    print(
                        json.dumps(
                            {
                                "status": "ok",
                                "count": len(wavs),
                                "sample_rate": sr,
                            }
                        ),
                        flush=True,
                    )
                else:
                    print(json.dumps({"status": "error", "error": "No audio produced"}), flush=True)

            except Exception as e:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "error": str(e),
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
