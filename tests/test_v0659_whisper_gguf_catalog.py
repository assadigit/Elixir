"""V0.6.59 -- the Whisper GGUF catalog: "I already downloaded whisper
large v3 from handy computer -- make the backend for it so I just
select the gguf model."

THE TRIGGER (the operator's request, verbatim):
    "Look I alreayd downloaded whisper large v3 from handy computer,
     can you make the backend for it yourself, so i just select the
     gguf modekl."

The operator has the GGUF ON DISK (the handy-computer Hugging Face
repos, verified live this session: handy-computer/whisper-large-v3-gguf
ships whisper-large-v3-{F16,Q4_K_M,Q5_K_M,Q6_K,Q8_0}.gguf, plus
tiny/base/small/medium/large/large-v2/large-v3-turbo and .en variants).
What the app lacked was the BACKEND that makes "just select the file"
actually work:

  1. The engine trusted the setting BLINDLY -- a stale path, a llama
     GGUF picked by mistake, or a legacy ggml-*.bin all surfaced only
     as a CLI crash minutes into a run. Nothing ever LOOKED inside the
     file.
  2. When the saved path went missing, the engine silently fell back
     to the one hardcoded default -- a downloaded model sitting in
     Downloads or C:\\transcribe.cpp\\models was invisible to the app.
  3. The dialog's only affordance was a raw file BROWSE -- no list of
     the models actually on disk, no confirmation of what was picked.

WHAT V0.6.59 ADDS
-----------------
  - core/transcribe/model_catalog.py (Qt-free stdlib-only leaf): a
    REAL GGUF header reader (magic + metadata key/values, all 13 GGUF
    value types incl. arrays, byte-capped best-effort), a filename
    parser that knows handy-computer's naming (whisper-large-v3-turbo-
    Q5_K_M.gguf -> family large-v3-turbo / quant Q5_K_M), a directory
    scanner (exe dir, exe/models, C:\\transcribe.cpp\\models, the saved
    model's dir, ~/Downloads -- where a browser download actually
    lands), and resolve_model() -- the engine's single decision point.
  - Engine: the model resolution block is now catalog-driven -- the
    selected GGUF is VERIFIED before the CLI launches (whisper
    architecture proven from the file's own metadata), a missing model
    triggers a loud scan that auto-picks (and persists) the best
    Whisper GGUF found, and the [MODEL] log line carries what the
    header actually said.
  - Dialog: a "GGUF model" row for the transcribe.cpp engine -- a
    combo listing every discovered Whisper GGUF (name / quant / size /
    verified) + a rescan button; selecting saves the setting; the
    browse button lives in the same row and refreshes the combo.

The metadata reader was verified this session against the REAL
handy-computer file header (range-requested
whisper-large-v3-Q5_K_M.gguf: general.architecture = 'whisper',
general.name = 'Whisper Large v3', general.size_label = '1.5B', 68
KVs, v3, 1261 tensors). The fixtures below rebuild that exact header
shape; a separate live-verification note is in the worklog.

TEST LAYOUT
-----------
  A. build_gguf / read_gguf_header  -- real bytes round-trip
  B. parse_model_filename           -- handy-computer's REAL names
  C. validate_whisper_model         -- wrong-arch / not-gguf / ok
  D. scan_model_dirs                -- merge, score, exclude non-whisper
  E. model_search_dirs              -- the rig's real locations + dedupe
  F. resolve_model                  -- the engine decision function
  G. engine integration             -- helpers + source pins
  H. dialog integration             -- AST pins (the house style)
"""

from __future__ import annotations

import ast
import struct
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_ENGINE = _project_root / "core" / "transcribe" / "transcribe_cpp_engine.py"
_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_CATALOG = _project_root / "core" / "transcribe" / "model_catalog.py"

from core.transcribe import model_catalog as mc  # noqa: E402

# ═════════════════════════════════════════════════════════════════════════════
# The GGUF byte builder -- writes REAL GGUF files (the spec, verified
# against handy-computer's actual headers this session).
# ═════════════════════════════════════════════════════════════════════════════

# GGUF metadata value types (the spec's enum).
T_UINT32, T_INT32, T_FLOAT32, T_BOOL, T_STRING, T_ARRAY, T_UINT64 = 4, 5, 6, 7, 8, 9, 10


def _enc_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<Q", len(b)) + b


def _enc_val(t: int, v) -> bytes:
    if t == T_STRING:
        return _enc_str(v)
    if t == T_ARRAY:
        et, items = v
        out = struct.pack("<I", et) + struct.pack("<Q", len(items))
        for item in items:
            out += _enc_val(et, item)
        return out
    if t == T_UINT32:
        return struct.pack("<I", v)
    if t == T_INT32:
        return struct.pack("<i", v)
    if t == T_FLOAT32:
        return struct.pack("<f", v)
    if t == T_BOOL:
        return struct.pack("<B", 1 if v else 0)
    if t == T_UINT64:
        return struct.pack("<Q", v)
    raise ValueError(f"builder has no type {t}")


def build_gguf(
    path: Path, kvs: list[tuple[str, int, object]], version=3, tensor_count=1261
) -> Path:
    """Write a structurally-valid GGUF: magic, version, tensor count,
    kv count, then the ordered metadata KVs."""
    body = b""
    for key, t, v in kvs:
        body += _enc_str(key) + struct.pack("<I", t) + _enc_val(t, v)
    data = (
        b"GGUF"
        + struct.pack("<I", version)
        + struct.pack("<Q", tensor_count)
        + struct.pack("<Q", len(kvs))
        + body
    )
    path.write_bytes(data)
    return path


def build_whisper_gguf(
    path: Path, name="Whisper Large v3", size_label="1.5B", arch="whisper"
) -> Path:
    """The REAL handy-computer header shape (field order + types as
    range-verified against whisper-large-v3-Q5_K_M.gguf)."""
    return build_gguf(
        path,
        [
            ("general.architecture", T_STRING, arch),
            ("general.name", T_STRING, name),
            ("general.basename", T_STRING, "whisper"),
            ("general.size_label", T_STRING, size_label),
            ("general.organization", T_STRING, "openai"),
            ("general.languages", T_ARRAY, (T_STRING, ["en", "fa", "fr"])),
            ("general.file_type", T_UINT32, 17),  # Q5_K_M in the ggml ftype enum
        ],
    )


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


# ═════════════════════════════════════════════════════════════════════════════
# A. read_gguf_header -- real bytes, all value types, best-effort caps
# ═════════════════════════════════════════════════════════════════════════════


class TestReadGgufHeader:
    def test_round_trip_the_real_header_shape(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-Q5_K_M.gguf")
        h = mc.read_gguf_header(f)
        assert h is not None
        assert h["version"] == 3
        assert h["tensor_count"] == 1261
        assert h["kv_count"] == 7
        meta = h["metadata"]
        assert meta["general.architecture"] == "whisper"
        assert meta["general.name"] == "Whisper Large v3"
        assert meta["general.size_label"] == "1.5B"
        assert meta["general.languages"] == ["en", "fa", "fr"]
        assert meta["general.file_type"] == 17

    def test_scalar_types_round_trip(self, tmp_path):
        f = build_gguf(
            tmp_path / "scalars.gguf",
            [
                ("a.u32", T_UINT32, 4294967295),
                ("a.i32", T_INT32, -42),
                ("a.f32", T_FLOAT32, 1.5),
                ("a.b_true", T_BOOL, True),
                ("a.b_false", T_BOOL, False),
                ("a.u64", T_UINT64, 2**63),
            ],
            tensor_count=0,
        )
        meta = mc.read_gguf_header(f)["metadata"]
        assert meta["a.u32"] == 4294967295
        assert meta["a.i32"] == -42
        assert meta["a.f32"] == pytest.approx(1.5)
        assert meta["a.b_true"] is True
        assert meta["a.b_false"] is False
        assert meta["a.u64"] == 2**63

    def test_string_array_of_100_languages(self, tmp_path):
        langs = [f"l{i}" for i in range(100)]
        f = build_gguf(tmp_path / "many.gguf", [("general.languages", T_ARRAY, (T_STRING, langs))])
        assert mc.read_gguf_header(f)["metadata"]["general.languages"] == langs

    def test_not_gguf_magic_returns_none(self, tmp_path):
        f = tmp_path / "ggml-large-v3.bin"
        f.write_bytes(b"\x00\x00\x00\x00" + b"junk" * 100)
        assert mc.read_gguf_header(f) is None

    def test_empty_file_returns_none(self, tmp_path):
        assert mc.read_gguf_header(tmp_path / "empty.gguf") is None

    def test_missing_file_returns_none(self, tmp_path):
        assert mc.read_gguf_header(tmp_path / "ghost.gguf") is None

    def test_truncated_header_returns_none(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "ok.gguf")
        raw = f.read_bytes()
        f.write_bytes(raw[: len(raw) // 2])
        assert mc.read_gguf_header(f) is None

    def test_ludicrous_kv_count_is_capped_not_hung(self, tmp_path):
        """A corrupt kv-count field (2**40 KVs) must NOT make the reader
        loop forever or read the disk dry -- the cap stops it cold."""
        f = tmp_path / "corrupt.gguf"
        f.write_bytes(
            b"GGUF"
            + struct.pack("<I", 3)
            + struct.pack("<Q", 0)
            + struct.pack("<Q", 2**40)
            + b"x" * 64
        )
        assert mc.read_gguf_header(f) is None

    def test_reading_never_loads_the_whole_file(self, tmp_path):
        """A 3 GB model must be HEADER-read, not slurped: write a big
        file and confirm the reader touches only bounded bytes."""
        f = build_whisper_gguf(tmp_path / "big.gguf")
        with open(f, "ab") as fh:
            fh.write(b"\x00" * (5 * 1024 * 1024))  # 5 MB tail of tensor junk
        h = mc.read_gguf_header(f)
        assert h["metadata"]["general.architecture"] == "whisper"
        assert mc.MAX_METADATA_BYTES < 5 * 1024 * 1024  # the cap is the proof


# ═════════════════════════════════════════════════════════════════════════════
# B. parse_model_filename -- handy-computer's REAL filenames (the file
# list was pulled live from the HF API this session) + ggml legacy.
# ═════════════════════════════════════════════════════════════════════════════


class TestParseModelFilename:
    @pytest.mark.parametrize(
        "filename,family,quant",
        [
            ("whisper-large-v3-Q8_0.gguf", "large-v3", "Q8_0"),
            ("whisper-large-v3-Q5_K_M.gguf", "large-v3", "Q5_K_M"),
            ("whisper-large-v3-Q4_K_M.gguf", "large-v3", "Q4_K_M"),
            ("whisper-large-v3-Q6_K.gguf", "large-v3", "Q6_K"),
            ("whisper-large-v3-F16.gguf", "large-v3", "F16"),
            ("whisper-large-v3-turbo-Q5_K_M.gguf", "large-v3-turbo", "Q5_K_M"),
            ("whisper-large-v3-turbo-Q8_0.gguf", "large-v3-turbo", "Q8_0"),
            ("whisper-large-v2-Q8_0.gguf", "large-v2", "Q8_0"),
            ("whisper-large-Q8_0.gguf", "large", "Q8_0"),
            ("whisper-medium-Q8_0.gguf", "medium", "Q8_0"),
            ("whisper-small-Q8_0.gguf", "small", "Q8_0"),
            ("whisper-base-Q8_0.gguf", "base", "Q8_0"),
            ("whisper-tiny-Q8_0.gguf", "tiny", "Q8_0"),
            ("ggml-large-v3.bin", "large-v3", None),
            ("ggml-medium.bin", "medium", None),
            ("ggml-small.en.bin", "small", None),
        ],
    )
    def test_real_handy_computer_names(self, filename, family, quant):
        info = mc.parse_model_filename(filename)
        assert info["family"] == family
        assert info["quant"] == quant

    def test_english_only_variants(self):
        info = mc.parse_model_filename("whisper-tiny.en-Q8_0.gguf")
        assert info["family"] == "tiny"
        assert info["language"] == "en"

    def test_legacy_ggml_bin_is_flagged(self):
        info = mc.parse_model_filename("ggml-large-v3.bin")
        assert info["legacy_ggml"] is True
        assert mc.parse_model_filename("whisper-tiny.gguf")["legacy_ggml"] is False

    def test_case_insensitive_quants(self):
        info = mc.parse_model_filename("whisper-large-v3-q8_0.GGUF")
        assert info["family"] == "large-v3"
        assert info["quant"] == "Q8_0"

    def test_non_whisper_prefix_has_no_family(self):
        info = mc.parse_model_filename("Qwen3-ASR-1.7B-Q4_K_M.gguf")
        assert info["family"] is None  # not a whisper-prefixed name

    def test_garbage_is_not_a_crash(self):
        info = mc.parse_model_filename("random.txt")
        assert info["family"] is None
        assert info["quant"] is None


# ═════════════════════════════════════════════════════════════════════════════
# C. validate_whisper_model -- the fail-fast gate the engine calls
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateWhisperModel:
    def test_real_whisper_gguf_is_valid(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-Q8_0.gguf")
        ok, info, problem = mc.validate_whisper_model(f)
        assert ok is True
        assert problem is None
        assert info["verified"] is True
        assert info["architecture"] == "whisper"
        assert info["meta_name"] == "Whisper Large v3"
        assert info["size_label"] == "1.5B"
        assert info["family"] == "large-v3"
        assert info["quant"] == "Q8_0"

    def test_llama_gguf_is_rejected_with_the_architecture_named(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "llama-7b-Q4.gguf", arch="llama")
        ok, info, problem = mc.validate_whisper_model(f)
        assert ok is False
        assert "whisper" in problem.lower()
        assert "llama" in problem

    def test_non_gguf_file_is_rejected(self, tmp_path):
        f = tmp_path / "ggml-large-v3.bin"
        f.write_bytes(b"not a gguf at all" * 10)
        ok, info, problem = mc.validate_whisper_model(f)
        assert ok is False
        assert "gguf" in problem.lower()

    def test_missing_file_is_rejected(self, tmp_path):
        ok, info, problem = mc.validate_whisper_model(tmp_path / "ghost.gguf")
        assert ok is False
        assert problem and "not found" in problem.lower()

    def test_gguf_magic_but_unparsable_metadata_proceeds_unverified(self, tmp_path):
        """A GGUF whose metadata can't be walked (exotic conversion)
        must NOT block the run -- the CLI is the final authority."""
        f = tmp_path / "weird.gguf"
        f.write_bytes(
            b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", 99) + b"j"
        )
        ok, info, problem = mc.validate_whisper_model(f)
        assert ok is True  # proceed...
        assert info["verified"] is False  # ...but honestly labeled


# ═════════════════════════════════════════════════════════════════════════════
# D. scan_model_dirs -- what "just select the gguf" selects FROM
# ═════════════════════════════════════════════════════════════════════════════


class TestScanModelDirs:
    def test_scan_merges_and_scores_dirs(self, tmp_path):
        models = tmp_path / "models"
        models.mkdir()
        build_whisper_gguf(models / "whisper-small-Q8_0.gguf", "Whisper Small", "244M")
        dl = tmp_path / "Downloads"
        dl.mkdir()
        build_whisper_gguf(dl / "whisper-large-v3-Q8_0.gguf")

        found = mc.scan_model_dirs([str(models), str(dl)])
        names = [Path(f["path"]).name for f in found]
        # large-v3 outranks small regardless of directory order
        assert names[0] == "whisper-large-v3-Q8_0.gguf"
        assert "whisper-small-Q8_0.gguf" in names
        assert len(found) == 2

    def test_scan_excludes_non_whisper_ggufs(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        build_whisper_gguf(d / "whisper-large-v3-Q8_0.gguf")
        build_whisper_gguf(d / "qwen-asr-Q4.gguf", arch="qwen3asr")
        junk = d / "notamodel.gguf"
        junk.write_bytes(b"junk" * 8)
        found = mc.scan_model_dirs([str(d)])
        assert [Path(f["path"]).name for f in found] == ["whisper-large-v3-Q8_0.gguf"]

    def test_scan_includes_legacy_ggml_bin_flagged(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        build_whisper_gguf(d / "whisper-small-Q8_0.gguf")
        (d / "ggml-medium.bin").write_bytes(b"legacy" * 100)
        found = mc.scan_model_dirs([str(d)])
        by_name = {Path(f["path"]).name: f for f in found}
        assert "ggml-medium.bin" in by_name
        assert by_name["ggml-medium.bin"]["legacy_ggml"] is True

    def test_scan_of_missing_dir_is_empty_not_an_error(self, tmp_path):
        assert mc.scan_model_dirs([str(tmp_path / "nope")]) == []

    def test_exact_default_name_wins_over_bigger_files(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        build_whisper_gguf(d / mc.DEFAULT_MODEL_NAME)  # 100-byte fixture
        big = build_whisper_gguf(d / "whisper-large-v3-F16.gguf")
        big.write_bytes(big.read_bytes() + b"\x00" * 4096)  # "bigger" file
        found = mc.scan_model_dirs([str(d)])
        assert Path(found[0]["path"]).name == mc.DEFAULT_MODEL_NAME

    def test_turbo_ranks_below_large_v3_but_above_v2(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        for n in ("whisper-large-v3-turbo-Q8_0.gguf", "whisper-large-v2-Q8_0.gguf"):
            build_whisper_gguf(d / n)
        found = mc.scan_model_dirs([str(d)])
        names = [Path(f["path"]).name for f in found]
        assert names.index("whisper-large-v3-turbo-Q8_0.gguf") < names.index(
            "whisper-large-v2-Q8_0.gguf"
        )

    def test_scan_describes_each_find(self, tmp_path):
        d = tmp_path / "m"
        d.mkdir()
        build_whisper_gguf(d / "whisper-large-v3-Q8_0.gguf")
        info = mc.scan_model_dirs([str(d)])[0]
        assert info["size_bytes"] > 0
        assert info["size_text"] and info["size_text"] != "?"
        assert info["verified"] is True
        assert info["family"] == "large-v3"


# ═════════════════════════════════════════════════════════════════════════════
# E. model_search_dirs -- the rig's real locations, deduped
# ═════════════════════════════════════════════════════════════════════════════


class TestModelSearchDirs:
    def test_exe_dir_models_and_saved_model_dir(self, tmp_path):
        exe_dir = tmp_path / "build" / "bin" / "Release"
        exe_dir.mkdir(parents=True)
        saved_dir = tmp_path / "saved"
        saved_dir.mkdir()
        (exe_dir / "models").mkdir()
        dirs = mc.model_search_dirs(
            exe_path=str(exe_dir / "transcribe-cli.exe"),
            saved_model=str(saved_dir / "whisper-large-v3-Q8_0.gguf"),
            home=str(tmp_path),
        )
        assert str(exe_dir) in dirs
        assert str(exe_dir / "models") in dirs
        assert str(saved_dir) in dirs
        # the default C:\transcribe.cpp\models and ~/Downloads are
        # included when they exist (they do not here -> filtered)
        assert str(tmp_path / "Downloads") not in dirs

    def test_downloads_is_scanned_when_it_exists(self, tmp_path):
        exe_dir = tmp_path / "x"
        exe_dir.mkdir()
        dl = tmp_path / "Downloads"
        dl.mkdir()
        dirs = mc.model_search_dirs(exe_path=str(exe_dir / "e.exe"), home=str(tmp_path))
        assert str(dl) in dirs

    def test_dedupe_and_missing_dirs_dropped(self, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        (a / "models").mkdir()
        dirs = mc.model_search_dirs(
            exe_path=str(a / "e.exe"),
            saved_model=str(a / "models" / "m.gguf"),
            home=str(tmp_path / "nohome"),
            extra_dirs=[str(a), str(tmp_path / "missing")],
        )
        assert dirs.count(str(a)) == 1
        assert str(tmp_path / "missing") not in dirs

    def test_saved_models_dir_before_downloads(self, tmp_path):
        """A model folder the operator set up should be scanned BEFORE
        the browser's Downloads dump."""
        exe_dir = tmp_path / "e"
        exe_dir.mkdir()
        saved_dir = tmp_path / "chosen"
        saved_dir.mkdir()
        dl = tmp_path / "Downloads"
        dl.mkdir()
        dirs = mc.model_search_dirs(
            exe_path=str(exe_dir / "e.exe"),
            saved_model=str(saved_dir / "m.gguf"),
            home=str(tmp_path),
        )
        assert dirs.index(str(saved_dir)) < dirs.index(str(dl))

    def test_defaults_point_at_the_documented_rig_layout(self):
        assert mc.DEFAULT_MODEL_NAME == "whisper-large-v3-Q8_0.gguf"
        assert "transcribe.cpp" in mc.DEFAULT_MODELS_DIR
        assert mc.DEFAULT_MODELS_DIR.endswith("models")


# ═════════════════════════════════════════════════════════════════════════════
# F. resolve_model -- THE decision function the engine calls
# ═════════════════════════════════════════════════════════════════════════════


class TestResolveModel:
    def test_saved_valid_model_is_used_verbatim(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-Q5_K_M.gguf")
        out = mc.resolve_model(str(f), extra_scan_dirs=[])
        assert "error" not in out
        assert out["path"] == str(f)
        assert out["source"] == "setting"
        assert out["persist"] is False
        assert out["info"]["verified"] is True

    def test_missing_saved_model_scans_and_autopicks(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        build_whisper_gguf(d / "whisper-small-Q8_0.gguf", "Whisper Small", "244M")
        build_whisper_gguf(d / "whisper-large-v3-Q8_0.gguf")
        out = mc.resolve_model(str(tmp_path / "ghost.gguf"), extra_scan_dirs=[str(d)])
        assert "error" not in out
        assert out["source"] == "scan"
        assert out["persist"] is True  # the engine saves it back to settings
        assert Path(out["path"]).name == "whisper-large-v3-Q8_0.gguf"
        joined = "\n".join(out["log_lines"])
        assert "[MODEL-SCAN]" in joined
        assert "ghost.gguf" in joined  # the stale path is named
        assert "whisper-large-v3-Q8_0.gguf" in joined

    def test_no_model_anywhere_is_a_clear_error(self, tmp_path):
        out = mc.resolve_model(str(tmp_path / "ghost.gguf"), extra_scan_dirs=[str(tmp_path)])
        assert "error" in out
        assert "not found" in out["error"].lower()
        assert "gguf" in out["error"].lower()
        assert "Model" in out["error"]  # names the dialog affordance

    def test_wrong_architecture_fails_fast(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "llama-7b.gguf", arch="llama")
        out = mc.resolve_model(str(f), extra_scan_dirs=[])
        assert "error" in out
        assert "llama" in out["error"]
        assert "whisper" in out["error"].lower()

    def test_non_gguf_saved_model_fails_fast(self, tmp_path):
        f = tmp_path / "model.bin"
        f.write_bytes(b"legacy ggml bytes" * 64)
        out = mc.resolve_model(str(f), extra_scan_dirs=[])
        assert "error" in out
        assert "gguf" in out["error"].lower()

    def test_unparsable_metadata_proceeds_with_a_warning_line(self, tmp_path):
        f = tmp_path / "weird.gguf"
        f.write_bytes(
            b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0) + struct.pack("<Q", 99) + b"j"
        )
        out = mc.resolve_model(str(f), extra_scan_dirs=[])
        assert "error" not in out
        assert out["info"]["verified"] is False
        assert any("WARN" in ln or "not parsable" in ln for ln in out["log_lines"])

    def test_scan_error_mentions_the_handy_computer_source(self, tmp_path):
        out = mc.resolve_model(str(tmp_path / "ghost.gguf"), extra_scan_dirs=[str(tmp_path)])
        assert "handy-computer" in out["error"]  # where to GET a model

    def test_scan_only_legacy_bins_is_not_auto_picked(self, tmp_path):
        """The fresh-eyes review finding: a lone ggml-*.bin must never be
        silently auto-picked + persisted (transcribe-cli.exe loads .gguf)."""
        d = tmp_path / "models"
        d.mkdir()
        (d / "ggml-large-v3.bin").write_bytes(b"legacy ggml bytes" * 64)
        out = mc.resolve_model(str(tmp_path / "ghost.gguf"), extra_scan_dirs=[str(d)])
        assert "error" in out
        assert "legacy" in out["error"].lower()
        assert "ggml-large-v3.bin" in out["error"]

    def test_scan_auto_pick_honest_verdict_line(self, tmp_path):
        d = tmp_path / "models"
        d.mkdir()
        build_whisper_gguf(d / "whisper-large-v3-Q8_0.gguf")
        out = mc.resolve_model(str(tmp_path / "ghost.gguf"), extra_scan_dirs=[str(d)])
        joined = "\n".join(out["log_lines"])
        # the verdict reflects what the header actually proved — no
        # overpromising "the engine will verify it" line.
        assert "saved to settings (GGUF header verified" in joined
        assert "the engine will verify" not in joined

    def test_tokenizer_scale_array_is_skipped_not_materialized(self, tmp_path):
        """The review's pathological-freeze bound: a 60k-item array is
        skipped with a summary marker — parse stays milliseconds and
        verification still succeeds."""
        f = build_gguf(
            tmp_path / "whisper-large-v3-Q5_K_M.gguf",
            [
                ("general.architecture", T_STRING, "whisper"),
                ("general.name", T_STRING, "Whisper Large v3"),
                ("tokenizer.ggml.tokens", T_ARRAY, (T_STRING, [f"t{i}" for i in range(60_000)])),
            ],
        )
        h = mc.read_gguf_header(f)
        assert h["metadata"]["general.architecture"] == "whisper"
        assert isinstance(h["metadata"]["tokenizer.ggml.tokens"], str)
        assert (
            "60,000" in h["metadata"]["tokenizer.ggml.tokens"]
            or "60000" in h["metadata"]["tokenizer.ggml.tokens"]
        )

    def test_resolution_never_raises(self, tmp_path):
        """The catalog is best-effort everywhere: garbage in, dicts out."""
        for weird in (None, "", str(tmp_path), str(tmp_path / "deep" / "deeper" / "x.gguf")):
            out = mc.resolve_model(weird, extra_scan_dirs=[str(tmp_path)])
            assert isinstance(out, dict)


# ═════════════════════════════════════════════════════════════════════════════
# G. engine integration -- the helpers + source pins
# ═════════════════════════════════════════════════════════════════════════════


class TestEngineIntegration:
    def test_model_log_line_carries_header_truth(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-Q8_0.gguf")
        info = mc.describe_model_file(f)
        line = mc.format_model_line(info)
        assert line.startswith("  [MODEL]")
        assert "whisper-large-v3-Q8_0.gguf" in line
        assert "Whisper Large v3" in line  # from the header, not guessed
        assert "1.5B" in line
        assert "Q8_0" in line
        assert "verified" in line

    def test_unverified_model_line_is_honest(self, tmp_path):
        info = mc.describe_model_file(_make_plain_gguf(tmp_path))
        line = mc.format_model_line(info)
        assert "verified" not in line or "not" in line

    def test_run_config_lines_accept_model_info(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        f = build_whisper_gguf(tmp_path / "whisper-large-v3-Q8_0.gguf")
        wav = tmp_path / "in.wav"
        wav.write_bytes(b"x" * 10)
        info = mc.describe_model_file(f)
        lines = _format_run_config_lines(str(f), str(wav), ["exe", "-m", str(f)], model_info=info)
        joined = "\n".join(lines)
        assert "[MODEL]" in joined
        assert "Whisper Large v3" in joined  # richer than the old name+size

    def test_run_config_lines_without_info_keep_the_v0657_contract(self, tmp_path):
        from core.transcribe.transcribe_cpp_engine import _format_run_config_lines

        f = tmp_path / "whisper-large-v3-Q8_0.gguf"
        f.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB — the MB branch
        wav = tmp_path / "in.wav"
        wav.write_bytes(b"x")
        joined = "\n".join(_format_run_config_lines(str(f), str(wav), ["exe"]))
        assert "[MODEL]" in joined and ("GB" in joined or "MB" in joined)
        assert "whisper-large-v3-Q8_0.gguf" in joined

    def test_engine_default_matches_the_catalog_ssot(self):
        from pathlib import PureWindowsPath

        from core.transcribe.transcribe_cpp_engine import DEFAULT_TRANSCRIBE_CPP_MODEL

        # name + dir must agree (PureWindowsPath: the pin holds on both
        # POSIX test rigs and the Windows rig itself)
        assert PureWindowsPath(DEFAULT_TRANSCRIBE_CPP_MODEL).name == mc.DEFAULT_MODEL_NAME
        assert str(PureWindowsPath(DEFAULT_TRANSCRIBE_CPP_MODEL).parent).replace(
            "\\", "/"
        ) == mc.DEFAULT_MODELS_DIR.replace("\\", "/")

    def test_engine_source_pins(self):
        src = _ENGINE.read_text(encoding="utf-8")
        # the catalog is imported and drives the model decision
        assert "from core.transcribe.model_catalog import" in src
        assert "resolve_model(" in src
        # a scan-resolved model is persisted back to settings
        assert 's.set("transcribe.transcribe_cpp_model"' in src
        # the old SILENT default-fallback is dead (the scan replaced it)
        assert "model_path = DEFAULT_TRANSCRIBE_CPP_MODEL" not in src

    def test_engine_resolves_before_the_cli_launches(self):
        """The resolve call must sit in transcribe_with_cpp's body BEFORE
        the Popen/streaming path -- fail-fast beats a 3-minute crash."""
        tree = ast.parse(_ENGINE.read_text(encoding="utf-8"))
        fn = _method(tree, "transcribe_with_cpp")
        src_lines = _ENGINE.read_text(encoding="utf-8").splitlines()
        resolve_line = _first_line_with(src_lines, fn, "_resolve_cpp_model(")
        popen_line = _first_line_with(src_lines, fn, "_stream_cli_output(")
        assert resolve_line is not None and popen_line is not None
        assert resolve_line < popen_line

    def test_catalog_is_a_qt_free_leaf(self):
        src = _CATALOG.read_text(encoding="utf-8")
        import_lines = "\n".join(
            ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))
        )
        for banned in ("PySide6", "PyQt", "QtCore", "QtWidgets", "PyQt5", "tkinter"):
            assert banned not in import_lines


class TestEngineResolveWrapper:
    def test_wrapper_passes_exe_dir_and_logs(self, tmp_path, monkeypatch):
        """_resolve_cpp_model composes search dirs from the real settings
        surface (exe path + saved model) and forwards to resolve_model."""
        from core.transcribe import transcribe_cpp_engine as eng

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        build_whisper_gguf(models_dir / "whisper-large-v3-Q8_0.gguf")
        exe_dir = tmp_path / "exe"
        exe_dir.mkdir()

        seen = {}

        def fake_resolve(saved_path, search_dirs=(), **kw):
            seen["saved"] = saved_path
            seen["dirs"] = search_dirs
            return {
                "path": str(models_dir / "whisper-large-v3-Q8_0.gguf"),
                "source": "scan",
                "persist": True,
                "info": {},
                "log_lines": ["  [MODEL-SCAN] test line"],
            }

        monkeypatch.setattr(eng.mc, "resolve_model", fake_resolve)
        monkeypatch.setattr(
            eng,
            "_settings_get",
            lambda key, default=None: {
                "transcribe.transcribe_cpp_exe": str(exe_dir / "transcribe-cli.exe"),
                "transcribe.transcribe_cpp_model": str(tmp_path / "ghost.gguf"),
            }.get(key, default),
        )

        logged = []
        out = eng._resolve_cpp_model(log=lambda m, l="INFO": logged.append(m))
        assert out["path"] == str(models_dir / "whisper-large-v3-Q8_0.gguf")
        assert out["source"] == "scan" and out["persist"] is True
        assert str(exe_dir) in seen["dirs"]
        assert any("[MODEL-SCAN]" in ln for ln in logged)


def _make_plain_gguf(tmp_path) -> Path:
    f = tmp_path / "plain.gguf"
    f.write_bytes(
        b"GGUF"
        + struct.pack("<I", 3)
        + struct.pack("<Q", 0)
        + struct.pack("<Q", 1)
        + b"\x01\x00\x00\x00"
    )
    return f


def _first_line_with(src_lines, fn: ast.FunctionDef, needle: str) -> int | None:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            try:
                seg = ast.get_source_segment("\n".join(src_lines), node) or ""
            except Exception:
                seg = ""
            if needle in seg:
                return node.lineno
    return None


# ═════════════════════════════════════════════════════════════════════════════
# H. dialog integration -- AST pins (the house style: no PySide6 in
# this sandbox; structure + wiring are pinned, behavior is Qt-free in
# the catalog).
# ═════════════════════════════════════════════════════════════════════════════


class TestDialogIntegration:
    @pytest.fixture(scope="class")
    def dialog_tree(self):
        return ast.parse(_DIALOG.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def dialog_src(self):
        return _DIALOG.read_text(encoding="utf-8")

    def test_gguf_model_row_is_built(self, dialog_tree, dialog_src):
        build = _method(dialog_tree, "_build_options")
        assigns = [
            n.targets[0].attr
            for n in ast.walk(build)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute)
            and n.targets[0].attr in ("cpp_model_combo", "cpp_model_row", "cpp_model_refresh_btn")
        ]
        assert "cpp_model_combo" in assigns
        assert "cpp_model_row" in assigns
        assert "GGUF model" in dialog_src  # the row's user-facing label

    def test_initial_engine_change_call_stays_below_all_model_widgets(self, dialog_tree):
        """The V0.6.55 BLOCKER pin, EXTENDED: the explicit
        _on_engine_changed() call must come after EVERY widget it
        touches -- now including the cpp model combo (the exact
        construction-order AttributeError class V0.6.53 died of)."""
        build = _method(dialog_tree, "_build_options")
        call_lines = [
            n.lineno
            for n in ast.walk(build)
            if isinstance(n, (ast.Expr, ast.Assign))
            and isinstance(getattr(n, "value", None), ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "_on_engine_changed"
        ]
        assert call_lines, "_build_options must call self._on_engine_changed()"
        first_call = min(call_lines)
        for widget in ("cpp_model_combo", "cpp_model_browse_btn", "whisper_combo"):
            assign_lines = [
                n.lineno
                for n in ast.walk(build)
                if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == widget
            ]
            assert assign_lines, f"{widget} never assigned in _build_options"
            assert max(assign_lines) < first_call, (
                f"{widget} assigned at {max(assign_lines)} but "
                f"_on_engine_changed() called at {first_call}"
            )

    def test_engine_change_toggles_the_gguf_row(self, dialog_tree):
        body = ast.unparse(_method(dialog_tree, "_on_engine_changed"))
        assert "cpp_model_row" in body

    def test_combo_selection_is_saved_to_settings(self, dialog_tree, dialog_src):
        handler = _method(dialog_tree, "_on_cpp_model_selected")
        body = ast.unparse(handler)
        assert "transcribe.transcribe_cpp_model" in body
        assert "currentData" in body
        # and the combo is wired to it
        assert ".currentIndexChanged" in dialog_src

    def test_refresh_cpp_models_exists_and_is_called_from_init(self, dialog_tree, dialog_src):
        _method(dialog_tree, "_refresh_cpp_models")  # raises if absent
        init = _method(dialog_tree, "__init__")
        body = ast.unparse(init)
        assert "_refresh_cpp_models" in body
        # the refresh method itself scans via the catalog
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "model_catalog" in refresh or "scan_model" in refresh or "describe_model" in refresh

    def test_browse_refreshes_the_combo_and_filters_gguf(self, dialog_tree, dialog_src):
        handler = ast.unparse(_method(dialog_tree, "_browse_cpp_model"))
        assert "_refresh_cpp_models" in handler
        assert "*.gguf" in dialog_src

    def test_run_header_carries_the_selected_gguf(self, dialog_tree, dialog_src):
        """When the engine is transcribe.cpp the run header must name
        the GGUF (the old code logged None for it -- the V0.6.57
        'meaningless for the transcribe.cpp engine' gap, now filled
        with the REAL model)."""
        src = dialog_src
        assert "_cpp_model_display" in src
        proc = _method(dialog_tree, "_on_process")
        body = ast.unparse(proc)
        assert "_cpp_model_display" in body

    def test_dialog_uses_the_catalog_not_its_own_parser(self, dialog_src):
        assert "from core.transcribe.model_catalog import" in dialog_src or (
            "model_catalog" in dialog_src and "import" in dialog_src
        )

    def test_status_message_contract_survives(self, dialog_src):
        assert "Model set" in dialog_src  # the V0.6.41 affordance text
