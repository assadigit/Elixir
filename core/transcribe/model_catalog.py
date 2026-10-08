"""core/transcribe/model_catalog.py -- V0.6.59: the Whisper GGUF catalog.

THE OPERATOR'S REQUEST:
    "Look I alreayd downloaded whisper large v3 from handy computer,
     can you make the backend for it yourself, so i just select the
     gguf modekl."

The GGUF is on disk (handy-computer's Hugging Face repos, verified live
this session: handy-computer/whisper-large-v3-gguf ships whisper-
large-v3-{F16,Q4_K_M,Q5_K_M,Q6_K,Q8_0}.gguf, plus tiny/base/small/
medium/large/large-v2/large-v3-turbo and .en variants). This module is
the BACKEND that makes "just select the file" work:

  read_gguf_header()   -- a REAL GGUF header reader: magic + version +
                          tensor count + every metadata key/value (all
                          13 GGUF value types, string arrays included),
                          streamed (a 3 GB model is never slurped) and
                          byte-capped (a corrupt kv-count cannot hang
                          or drain the disk). Verified this session
                          against the actual handy-computer header:
                          general.architecture = 'whisper',
                          general.name = 'Whisper Large v3',
                          general.size_label = '1.5B'.
  parse_model_filename() -- handy-computer's naming, parsed:
                          whisper-large-v3-turbo-Q5_K_M.gguf ->
                          family 'large-v3-turbo', quant 'Q5_K_M';
                          legacy ggml-*.bin flagged as such.
  scan_model_dirs()    -- every *.gguf (and legacy ggml-*.bin) in a
                          set of directories, described and scored.
  model_search_dirs()  -- where the rig actually keeps models: the
                          exe's dir + exe/models, the saved model's
                          folder, C:\\transcribe.cpp\\models, and
                          ~/Downloads (where a browser download lands).
  resolve_model()      -- THE decision function the engine calls:
                          verify the saved file from its own header
                          (a llama GGUF or a legacy .bin fails in
                          SECONDS, not minutes into the run), and when
                          the saved path is missing, scan and auto-pick
                          the best Whisper GGUF on disk.

Qt-free, stdlib-only leaf (the house pattern: the sandbox has no
PySide6, so all of this is behaviorally testable everywhere).
"""

from __future__ import annotations

import re
import struct
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

# ── The GGUF format (the spec + live verification against
#    handy-computer/whisper-large-v3-gguf this session) ───────────────────────

GGUF_MAGIC = b"GGUF"

#: Fixed byte sizes of the scalar GGUF value types (arrays of these
#: can be skipped with a single bounded read).
_FIXED_TYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

#: How much metadata the reader will walk before declaring the file
#: unparsable (best-effort). Whisper headers are ~1-2 MB (the tokenizer
#: arrays); 4 MB is a pathological-file guard, and it is also the proof
#: the reader never slurps a 3 GB model.
MAX_METADATA_BYTES = 4 * 1024 * 1024

_MAX_KVS = 1024            # whisper-large-v3 ships 68; >1k = corrupt
#: Sanity cap on any ONE array's item count (the byte cap above is the
#: real bound; this keeps a corrupt count field from spinning).
_MAX_ARRAY_ITEMS = 1_000_000
#: Arrays bigger than this are skipped with a summary marker instead
#: of materialized: real whisper files carry tokenizer.ggml.tokens
#: x51,866 (dead weight for the catalog — only general.* matters), and
#: the fresh-eyes review measured a crafted 2M-item array at ~550 ms
#: of CPU on the UI thread. Materializing <=1,000 items keeps the
#: languages/suppress_tokens arrays real (they are small) and bounds
#: the worst case to milliseconds.
_MAX_INLINE_ITEMS = 1_000


class GgufReadError(Exception):
    """Best-effort sentinel: any header-walk problem (truncation, cap
    exceeded, unknown value type) is caught by read_gguf_header and
    turned into ``None`` -- never an exception at a call site."""


class _Reader:
    """A bounded binary reader over an open file handle. Enforces the
    metadata byte cap so a corrupt length field can neither loop
    forever nor read the disk dry."""

    __slots__ = ("_fh", "_left")

    def __init__(self, fh, cap: int) -> None:
        self._fh = fh
        self._left = cap

    def read(self, n: int) -> bytes:
        if n < 0:
            raise GgufReadError("negative length")
        if n > self._left:
            raise GgufReadError("metadata byte cap exceeded")
        data = self._fh.read(n)
        if len(data) != n:
            raise GgufReadError("truncated header")
        self._left -= n
        return data

    def read_str(self) -> str:
        (n,) = struct.unpack("<Q", self.read(8))
        if n > self._left:
            raise GgufReadError("string length exceeds cap")
        return self.read(n).decode("utf-8", errors="replace")

    def skip_array(self, elem_type: int, count: int) -> None:
        """Skip a fixed-size-element array in ONE bounded seek (string
        arrays still walk item by item — their lengths are per-item)."""
        if elem_type == 8:
            for _ in range(count):
                (n,) = struct.unpack("<Q", self.read(8))
                self.read(n)  # cap-checked; raises past the budget
            return
        size = _FIXED_TYPE_SIZES.get(elem_type)
        if size is None:
            raise GgufReadError(f"unknown array element type {elem_type}")
        self.read(size * count)


def _read_value(r: _Reader, vtype: int) -> Any:
    if vtype == 8:  # STRING
        return r.read_str()
    if vtype == 9:  # ARRAY
        (et,) = struct.unpack("<I", r.read(4))
        (count,) = struct.unpack("<Q", r.read(8))
        if et == 9:
            raise GgufReadError("nested arrays are not in whisper metadata")
        if count > _MAX_ARRAY_ITEMS:
            raise GgufReadError("array item count exceeds cap")
        if count > _MAX_INLINE_ITEMS:
            # Skip (bounded by the byte cap) and leave a summary marker:
            # the catalog only consumes general.* / whisper.* scalars,
            # and materializing tokenizer-scale arrays is UI-thread time
            # (the fresh-eyes review's pathological-freeze finding).
            r.skip_array(et, count)
            return f"<array skipped: {count} items>"
        return [_read_value(r, et) for _ in range(count)]
    if vtype == 0:  # UINT8
        return r.read(1)[0]
    if vtype == 1:  # INT8
        return struct.unpack("<b", r.read(1))[0]
    if vtype == 2:  # UINT16
        return struct.unpack("<H", r.read(2))[0]
    if vtype == 3:  # INT16
        return struct.unpack("<h", r.read(2))[0]
    if vtype == 4:  # UINT32
        return struct.unpack("<I", r.read(4))[0]
    if vtype == 5:  # INT32
        return struct.unpack("<i", r.read(4))[0]
    if vtype == 6:  # FLOAT32
        return struct.unpack("<f", r.read(4))[0]
    if vtype == 7:  # BOOL (1 byte)
        return r.read(1)[0] != 0
    if vtype == 10:  # UINT64
        return struct.unpack("<Q", r.read(8))[0]
    if vtype == 11:  # INT64
        return struct.unpack("<q", r.read(8))[0]
    if vtype == 12:  # FLOAT64
        return struct.unpack("<d", r.read(8))[0]
    raise GgufReadError(f"unknown value type {vtype}")


def read_gguf_header(path) -> dict | None:
    """Read a GGUF file's header (magic, version, tensor count, and the
    metadata key/values) WITHOUT loading the file.

    Returns {"version", "tensor_count", "kv_count", "metadata": {...}}
    or None for: missing file, not-a-GGUF (no magic), truncated/
    corrupt header, caps exceeded. Best-effort: never raises.
    """
    try:
        with open(path, "rb") as fh:
            r = _Reader(fh, MAX_METADATA_BYTES)
            if r.read(4) != GGUF_MAGIC:
                return None
            (version,) = struct.unpack("<I", r.read(4))
            if not (1 <= version <= 99):
                return None
            (tensor_count,) = struct.unpack("<Q", r.read(8))
            (kv_count,) = struct.unpack("<Q", r.read(8))
            if kv_count > _MAX_KVS:
                return None
            metadata: dict[str, Any] = {}
            for _ in range(kv_count):
                key = r.read_str()
                (vtype,) = struct.unpack("<I", r.read(4))
                metadata[key] = _read_value(r, vtype)
            return {
                "version": version,
                "tensor_count": tensor_count,
                "kv_count": kv_count,
                "metadata": metadata,
            }
    except (GgufReadError, OSError, struct.error, ValueError, OverflowError):
        return None
    except Exception:  # pragma: no cover - absolute best-effort
        return None


def gguf_magic(path) -> bool:
    """True when the file starts with the GGUF magic (cheap 4-byte read
    -- the distinction between 'not a GGUF' and 'GGUF but unparsable'
    matters: the first is a hard error, the second proceeds with a
    warning)."""
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == GGUF_MAGIC
    except Exception:
        return False


# ── Filename parsing: handy-computer's naming, exactly ─────────────────────

_QUANT_RE = re.compile(r"^(q\d+[_a-z0-9.]*|iq\d+[_a-z0-9.]*|f16|f32|bf16)$")
_MODEL_PREFIXES = ("whisper-", "whisper_", "ggml-", "ggml_")


def parse_model_filename(filename: str | Path) -> dict:
    """Parse a whisper model FILENAME into family / quant / language.

    The shapes (handy-computer's Hugging Face filenames, pulled live
    this session):
      whisper-large-v3-Q8_0.gguf          -> large-v3 / Q8_0
      whisper-large-v3-turbo-Q5_K_M.gguf  -> large-v3-turbo / Q5_K_M
      whisper-large-v3-F16.gguf           -> large-v3 / F16
      whisper-tiny.en-Q8_0.gguf           -> tiny / Q8_0 / language en
      ggml-large-v3.bin                   -> large-v3 / (legacy ggml)
    Non-whisper prefixes (Qwen3-ASR-...) yield family None.
    """
    out = {"family": None, "quant": None, "language": None, "legacy_ggml": False}
    if not filename:
        return out
    stem = str(filename)
    lowered = stem.lower()
    for ext in (".gguf", ".bin", ".pt", ".pth", ".onnx"):
        if lowered.endswith(ext):
            stem = stem[: -len(ext)]
            lowered = lowered[: -len(ext)]
            break
    prefix = None
    for cand in _MODEL_PREFIXES:
        if lowered.startswith(cand):
            prefix = cand
            break
    if prefix is None:
        return out
    rest = stem[len(prefix):]
    legacy = prefix.startswith("ggml")
    tokens = rest.split("-") if "-" in rest else [rest]
    family_tokens: list[str] = []
    quant = None
    for tok in tokens:
        if _QUANT_RE.fullmatch(tok.lower()):
            q = tok.upper()
            quant = "F16" if q == "F16" else ("F32" if q == "F32" else ("BF16" if q == "BF16" else q))
            break  # everything after the quant token is variant noise
        family_tokens.append(tok)
    family = "-".join(family_tokens) if family_tokens else None
    language = None
    if family and family.lower().endswith(".en"):
        family = family[:-3]
        language = "en"
    if family == "":
        family = None
    out["family"] = family
    out["quant"] = quant
    out["language"] = language
    out["legacy_ggml"] = legacy
    return out


# ── Model descriptions ──────────────────────────────────────────────────────

#: general.file_type (the ggml ftype enum) -> quant name, for files
#: whose FILENAME carries no quant (the header still knows).
FILE_TYPE_QUANT = {
    1: "F16",
    2: "BF16",
    3: "Q4_0",
    4: "Q4_1",
    7: "Q8_0",
    8: "Q5_0",
    9: "Q5_1",
    10: "Q2_K",
    11: "Q3_K_S",
    12: "Q3_K_M",
    13: "Q3_K_L",
    14: "Q4_K_S",
    15: "Q4_K_M",
    16: "Q5_K_S",
    17: "Q5_K_M",
    18: "Q6_K",
}


def _fmt_bytes(num_bytes: int) -> str:
    """Human-readable size (the engine's display convention; the leaf
    keeps its own copy so it never imports the engine)."""
    try:
        gb = num_bytes / (1024**3)
        if gb >= 1.0:
            return f"{gb:.1f} GB"
        mb = num_bytes / (1024**2)
        if mb >= 1.0:
            return f"{mb:.1f} MB"
        return f"{max(0, num_bytes)} B"
    except Exception:
        return "?"


def describe_model_file(path) -> dict:
    """Everything known about ONE model file, from its name AND its
    bytes: family/quant (filename), architecture/name/params (GGUF
    header), size, verified flag. Best-effort: never raises."""
    p = Path(path)
    fname = parse_model_filename(p.name)
    info: dict[str, Any] = {
        "path": str(p),
        "name": p.name,
        "size_bytes": 0,
        "size_text": "?",
        "family": fname["family"],
        "quant": fname["quant"],
        "language": fname["language"],
        "legacy_ggml": fname["legacy_ggml"],
        "is_gguf": False,
        "verified": False,
        "architecture": None,
        "meta_name": None,
        "size_label": None,
        "gguf_version": None,
    }
    try:
        info["size_bytes"] = p.stat().st_size
        info["size_text"] = _fmt_bytes(info["size_bytes"])
    except OSError:
        pass
    if not gguf_magic(p):
        return info
    info["is_gguf"] = True
    header = read_gguf_header(p)
    if header is None:
        return info
    meta = header["metadata"]
    info["gguf_version"] = header["version"]
    info["architecture"] = meta.get("general.architecture")
    info["meta_name"] = meta.get("general.name")
    info["size_label"] = meta.get("general.size_label")
    info["verified"] = info["architecture"] == "whisper"
    if not info["quant"]:
        info["quant"] = FILE_TYPE_QUANT.get(meta.get("general.file_type"))
    return info


def format_model_display(info: dict) -> str:
    """The combo-entry line (dialog-facing): name · quant · size · proof."""
    bits: list[str] = []
    if info.get("meta_name"):
        bits.append(str(info["meta_name"]))
    elif info.get("family"):
        bits.append(f"whisper-{info['family']}")
    else:
        bits.append(str(info.get("name") or "?"))
    if info.get("quant"):
        bits.append(str(info["quant"]))
    bits.append(str(info.get("size_text") or "?"))
    if info.get("verified"):
        bits.append("header-verified")
    elif info.get("legacy_ggml"):
        bits.append("legacy ggml .bin")
    return " · ".join(bits)


def format_model_line(info: dict) -> str:
    """The live-log [MODEL] line (engine-facing). Honest about what the
    header actually said vs. what was only guessed from the name."""
    name = info.get("name") or Path(info.get("path") or "?").name
    size = info.get("size_text") or "?"
    tail = " - the model file reloads on every run"
    if info.get("verified"):
        parts = []
        if info.get("meta_name"):
            parts.append(str(info["meta_name"]))
        if info.get("quant"):
            parts.append(str(info["quant"]))
        if info.get("size_label"):
            parts.append(str(info["size_label"]))
        parts.append("GGUF header verified (architecture: whisper)")
        return f"  [MODEL] {name} ({size}) - " + " · ".join(parts) + tail
    if info.get("legacy_ggml"):
        return (
            f"  [MODEL] {name} ({size}) - legacy ggml .bin "
            f"(transcribe-cli.exe loads .gguf){tail}"
        )
    if info.get("is_gguf"):
        return (
            f"  [MODEL] {name} ({size}) - GGUF header not parsable "
            f"(proceeding; the CLI is the final authority){tail}"
        )
    return f"  [MODEL] {name} ({size}) - not a GGUF{tail}"


def format_model_tooltip(info: dict) -> str:
    """The GGUF combo's per-item tooltip (dialog-facing, V0.6.60):
    everything the catalog knows about ONE file, one fact per line --
    what the file's OWN header proved, vs. what was only guessed from
    its name. Qt-free so the behavior is hermetically pinnable."""
    lines: list[str] = [format_model_display(info)]
    if info.get("path"):
        lines.append(f"File: {info['path']}")
    if info.get("size_bytes"):
        lines.append(f"Size: {info['size_text']} ({info['size_bytes']:,} bytes)")
    if info.get("meta_name"):
        lines.append(f"Model: {info['meta_name']}")
    if info.get("size_label"):
        lines.append(f"Parameters: {info['size_label']}")
    if info.get("quant"):
        lines.append(f"Quantization: {info['quant']}")
    if info.get("language"):
        lines.append(f"Language: {info['language']} (English-only variant)")
    if info.get("architecture"):
        lines.append(f"Architecture: {info['architecture']} (read from the GGUF header)")
    if info.get("gguf_version"):
        lines.append(f"GGUF version: {info['gguf_version']}")
    if info.get("family"):
        lines.append(f"Family: {info['family']}")
    if info.get("verified"):
        lines.append("✓ header-verified — the engine re-checks this file before every run")
    elif info.get("legacy_ggml"):
        lines.append("⚠ legacy ggml .bin — transcribe-cli.exe loads .gguf")
    elif info.get("is_gguf"):
        lines.append("? header not parsable — the CLI is the final authority")
    return "\n".join(lines)


# ── Scanning: what "just select the gguf" selects FROM ──────────────────────

#: The rig's documented layout (the engine's DEFAULT model path — the
#: SSOT cross-pin in the tests keeps the two in lockstep).
DEFAULT_MODELS_DIR = r"C:\transcribe.cpp\models"
DEFAULT_MODEL_NAME = "whisper-large-v3-Q8_0.gguf"

#: family -> preference rank (higher = picked first by the scan).
_FAMILY_RANK = {
    "large-v3": 60,
    "large-v3-turbo": 55,
    "large-v2": 50,
    "large": 50,
    "medium": 40,
    "small": 30,
    "base": 20,
    "tiny": 10,
}


def _scan_score(info: dict) -> tuple[int, int]:
    s = _FAMILY_RANK.get(str(info.get("family")), 5)
    if info.get("name") == DEFAULT_MODEL_NAME:
        s += 1000  # the documented default wins outright
    if info.get("language") == "en":
        s -= 1  # multilingual variants preferred for auto-pick
    if info.get("legacy_ggml"):
        s -= 500  # never auto-pick a legacy .bin over a .gguf
    return (s, int(info.get("size_bytes") or 0))


def scan_model_dirs(dirs: Iterable[str | Path]) -> list[dict]:
    """Find every candidate model file in the given directories,
    described (header read) and ranked (best first).

    Rules: .gguf files must carry the GGUF magic; non-whisper
    architectures are EXCLUDED (a llama GGUF must never be auto-picked);
    legacy ggml-*.bin files are included but flagged and ranked last.
    Best-effort: missing dirs, unreadable entries -> skipped silently.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for d in dirs:
        try:
            dp = Path(d)
            if not dp.is_dir():
                continue
            entries = sorted(dp.iterdir())
        except Exception:
            continue
        for entry in entries:
            try:
                key = str(entry)
                if key in seen:
                    continue
                suffix = entry.suffix.lower()
                if suffix not in (".gguf", ".bin"):
                    continue
                if not entry.is_file():
                    continue
                info = describe_model_file(entry)
                seen.add(key)
                if info["legacy_ggml"]:
                    out.append(info)  # listed (flagged), ranked last
                    continue
                if not info["is_gguf"]:
                    continue  # junk wearing a .gguf extension
                if info["architecture"] not in (None, "whisper"):
                    continue  # a GGUF, but not a Whisper one
                out.append(info)
            except Exception:
                continue
    out.sort(key=_scan_score, reverse=True)
    return out


def model_search_dirs(
    exe_path: str | None = None,
    saved_model: str | None = None,
    home: str | None = None,
    extra_dirs: Sequence[str | Path] = (),
) -> list[str]:
    """Where the rig actually keeps models, deduped, existing-only:

      1. the CLI exe's own folder (+ its models/ and models/whisper/)
      2. the SAVED model's folder (whatever the operator last picked)
      3. C:\\transcribe.cpp\\models (the documented default layout)
      4. ~/Downloads (where a handy-computer browser download lands)
      5. any extra dirs (the caller's)

    Best-effort: never raises, missing dirs are simply not returned.
    """
    candidates: list[Path] = []
    if exe_path:
        try:
            exe_dir = Path(exe_path).parent
            candidates += [exe_dir, exe_dir / "models", exe_dir / "models" / "whisper"]
        except Exception:
            pass
    if saved_model:
        try:
            candidates.append(Path(saved_model).parent)
        except Exception:
            pass
    candidates.append(Path(DEFAULT_MODELS_DIR))
    try:
        home_dir = Path(home) if home else Path.home()
        candidates.append(home_dir / "Downloads")
    except Exception:
        pass
    for d in extra_dirs:
        try:
            candidates.append(Path(d))
        except Exception:
            pass
    out: list[str] = []
    seen: set[str] = set()
    for d in candidates:
        try:
            if not d.is_dir():
                continue
            key = str(d)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
        except Exception:
            continue
    return out


# ── Validation + resolution: the engine's decision ─────────────────────────

_NOT_FOUND_TEMPLATE = (
    "Whisper model file not found at: {path}\n\n"
    "The app scanned the disk for Whisper .gguf models and found none.\n"
    "FIX: download a Whisper GGUF (e.g. whisper-large-v3-Q8_0.gguf from\n"
    "handy-computer/whisper-large-v3-gguf on Hugging Face), then either\n"
    "put it in C:\\transcribe.cpp\\models\\ or pick it in the 'GGUF model'\n"
    "dropdown / click the 'Model' button in the Transcribe Service dialog\n"
    "to browse for the file you downloaded. The dropdown lists every\n"
    "Whisper model found on disk."
)

_WRONG_ARCH_TEMPLATE = (
    "The selected model file is NOT a Whisper model: {name}\n"
    'Its GGUF header says general.architecture = "{arch}" (expected "whisper").\n'
    "FIX: pick a Whisper .gguf — e.g. handy-computer/whisper-large-v3-gguf\n"
    "on Hugging Face (whisper-large-v3-Q8_0.gguf, ~1.6 GB)."
)

_NOT_GGUF_TEMPLATE = (
    "The selected model file is not a GGUF: {name}\n"
    "(no GGUF magic header — legacy ggml-*.bin files cannot be loaded by\n"
    "transcribe-cli.exe). FIX: download the .gguf — e.g. handy-computer/\n"
    "whisper-large-v3-gguf on Hugging Face — and select it."
)


def validate_whisper_model(path) -> tuple[bool, dict | None, str | None]:
    """The fail-fast gate. Returns (ok, info, problem).

      ok=True, problem=None     -> run it (info.verified says whether the
                                   header PROVED it is whisper)
      ok=False, problem=str     -> a hard, actionable error (seconds,
                                   not minutes into a run)
    """
    p = Path(path)
    try:
        if not p.exists():
            return (False, None, f"model file not found: {p}")
        if not p.is_file():
            return (False, None, f"model path is not a file: {p}")
    except OSError as e:
        return (False, None, f"model file not accessible: {e}")
    if not gguf_magic(p):
        return (False, None, _NOT_GGUF_TEMPLATE.format(name=p.name))
    header = read_gguf_header(p)
    if header is not None:
        arch = header["metadata"].get("general.architecture")
        if arch is not None and arch != "whisper":
            info = describe_model_file(p)
            return (False, info, _WRONG_ARCH_TEMPLATE.format(name=p.name, arch=arch))
    # GGUF magic present; metadata unparsable or arch key absent:
    # proceed honestly unverified (the CLI is the final authority).
    return (True, describe_model_file(p), None)


def resolve_model(
    saved_path: str | None,
    search_dirs: Sequence[str | Path] = (),
    extra_scan_dirs: Sequence[str | Path] = (),
    exe_path: str | None = None,
    home: str | None = None,
) -> dict:
    """THE decision function the engine calls before every run.

    Returns one of:
      {"path": str, "source": "setting"|"scan", "persist": bool,
       "info": {...}, "log_lines": [str, ...]}
      {"error": str, "log_lines": [...]}

    Policy:
      - saved file exists -> VERIFY it from its own header. Wrong
        architecture / not a GGUF -> hard error (fail fast). Valid ->
        used verbatim. Unparsable metadata -> proceed with a WARN line.
      - saved file missing -> scan the search dirs (+ the standard
        locations); auto-pick the best Whisper GGUF; persist=True so
        the engine saves it back to settings (self-healing).
      - nothing found -> the actionable not-found error.
    Best-effort: never raises (garbage in, dicts out).
    """
    try:
        return _resolve_model_impl(
            saved_path,
            search_dirs=search_dirs,
            extra_scan_dirs=extra_scan_dirs,
            exe_path=exe_path,
            home=home,
        )
    except Exception as e:  # absolute best-effort
        return {"error": f"model resolution failed unexpectedly: {e}", "log_lines": []}


def _resolve_model_impl(
    saved_path: str | None,
    search_dirs: Sequence[str | Path],
    extra_scan_dirs: Sequence[str | Path],
    exe_path: str | None,
    home: str | None,
) -> dict:
    saved = str(saved_path) if saved_path else None

    # A saved path that EXISTS is verified from its own header; a saved
    # path that does NOT exist (stale setting, moved file) falls through
    # to the scan — only a wrong-FILE is a hard error, a missing PATH
    # is exactly what the scan is for.
    saved_exists = False
    if saved:
        try:
            saved_exists = Path(saved).is_file()
        except Exception:
            saved_exists = False

    if saved and saved_exists:
        ok, info, problem = validate_whisper_model(saved)
        if not ok:
            return {"error": problem, "log_lines": []}
        if info and info.get("verified"):
            return {
                "path": saved,
                "source": "setting",
                "persist": False,
                "info": info,
                "log_lines": [
                    "  [MODEL] using saved model: "
                    f"{info.get('name') or Path(saved).name} — GGUF header "
                    "verified (architecture: whisper)"
                ],
            }
        # Proceeding unverified: say so in the log.
        warn = (
            "  [WARN] "
            f"{info.get('name') if info else Path(saved).name}: GGUF header "
            "not parsable — proceeding unverified (the CLI is the final "
            "authority)"
        )
        return {
            "path": saved,
            "source": "setting",
            "persist": False,
            "info": info or {},
            "log_lines": [warn],
        }

    # Saved path missing (or none saved): scan the disk.
    dirs: list[str | Path] = list(search_dirs)
    try:
        dirs += model_search_dirs(exe_path=exe_path, saved_model=saved, home=home)
    except Exception:
        pass
    dirs += list(extra_scan_dirs)
    found = scan_model_dirs(dirs)
    # AUTO-PICK gate (the fresh-eyes review's finding): only files with
    # the GGUF magic are auto-picked + persisted — a legacy ggml-*.bin
    # sitting alone in a models dir is NOT silently persisted as "the
    # model" (transcribe-cli.exe cannot load it).
    pickable = [i for i in found if i.get("is_gguf")]
    if not pickable:
        if found:
            legacy = ", ".join(i.get("name") or "?" for i in found[:4])
            return {
                "error": (
                    "No loadable Whisper .gguf found — only legacy ggml-*.bin "
                    f"file(s) were discovered ({legacy}). transcribe-cli.exe "
                    "loads .gguf. FIX: download a Whisper GGUF (e.g. "
                    "whisper-large-v3-Q8_0.gguf from handy-computer/"
                    "whisper-large-v3-gguf on Hugging Face) and select it."
                ),
                "log_lines": [],
            }
        return {
            "error": _NOT_FOUND_TEMPLATE.format(path=saved or "(no model selected)"),
            "log_lines": [],
        }
    best = pickable[0]
    names = ", ".join(i.get("name") or "?" for i in pickable[:8])
    more = f" (+{len(pickable) - 8} more)" if len(pickable) > 8 else ""
    if saved:
        lead = f"  [MODEL-SCAN] saved model not found: {saved} — scanning the disk"
    else:
        lead = "  [MODEL-SCAN] no model was selected — scanning the disk"
    if best.get("verified"):
        verdict = "GGUF header verified (architecture: whisper)"
    else:
        verdict = "GGUF header not parsable — the CLI is the final authority"
    return {
        "path": best["path"],
        "source": "scan",
        "persist": True,
        "info": best,
        "log_lines": [
            lead,
            f"  [MODEL-SCAN] found {len(pickable)} model file(s): {names}{more}",
            f"  [MODEL-SCAN] using: {best.get('name')} — saved to settings ({verdict})",
        ],
    }
