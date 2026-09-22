"""V18.20.4.3 (P2) — the settings/config-integrity + provenance-visibility
release.

Per the approved V18.20.4.0 SWOT roadmap (P2 cluster) plus the G-series
follow-up to the F8 audit round (the third consecutive stale-artifact
upload — a file stamped by an old app version was mistaken for the fresh
run's output):

- **W-c3:** ``controller.get_settings()`` returned the live ``_data``
  dict — RLock bypassed, racy against the conversion worker, external
  mutations never persisted. Now a locked deep-copy snapshot
  (``Settings.snapshot()``).
- **W-c4 + T-c8:** corrupt ``settings.json`` → silent full reset with
  no backup, and the plain ``utf-8`` open made a Windows-Notepad BOM
  hand-edit trigger that reset. Now: ``utf-8-sig`` load + a timestamped
  ``settings.json.corrupt-<ts>`` backup before the defaults fallback.
- **W-b6:** settings-save failures were swallowed
  (``except: pass`` → ``accept()``) — the dialog closed as-if-saved while
  API keys/model picks never hit disk. ``Settings.save()``/``set()`` now
  return success; the dialog warns and stays open for a retry.
- **W-b7:** ``AiLocalModelSection`` double-wrote
  ``summarisation.fast_model`` — an invisible orphaned ``fast_combo``
  (never added to any layout row) fed a dead write before the real
  ``fast_model_combo`` write, and stole the global model refresh.
  Orphan deleted; one authoritative write.
- **W-c7:** the ``adaptive_toc.py`` LLM call was the only ``requests``
  call in the tree with NO timeout (half-open connection → TOC stage
  hung forever, no cancel path) + a hardcoded model not installed on
  the rig. Now: timeout + model + URL from Settings. (The W-c7 test
  section was removed in V0.08 / P2 together with the dead
  ``adaptive_toc.py`` module.)
- **W-c1:** ``config/models.json`` (V10.15.0 "configurable registry")
  had ZERO readers and disagreed with the live defaults; the request-
  builder fallbacks (``qwen3-vl:8b`` / ``gemma3:12b``) named models the
  rig never had. Registry deleted; defaults unified with
  ``utils/settings.py`` + USER_OLLAMA_MODELS.md.
- **W-c18:** ``regenerate_output`` assigned ``str`` where every other
  path passes ``Path``.
- **W-c9:** the canonical Ollama URL (``Settings.get_ollama_url()``)
  was bypassed by 8 hardcoded ``localhost:11434`` sites — the SWOT's 7
  (new_outputs, toc_extractor, vision_figure_extractor,
  semantic_segmenter, vram_manager ×2, normalizer, ocr/service) + the
  same-class site found during the sweep (summarizer
  ``ollama_base_url``, feeding the dispatcher/supervisor) + adaptive_toc
  (under W-c7).
- **G-1/G-2/G-3 (F8 follow-up):** the final summary-files diagnostic now
  (a) carries each file's FULL path, (b) escalates a stamp from a
  DIFFERENT app version to a STALE ARTIFACT WARNING, and (c) every
  stamped summary gains a human-VISIBLE footer line (the HTML-comment
  stamp is invisible in rendered markdown — the root of the repeated
  wrong-file uploads).

Two layers, per the house pattern: headless-safe source pins + pure-Py
behavioral tests always run; offscreen Qt behavioral tests skip when
PySide6 is unavailable (the headless rig).
"""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub the optional heavy deps exactly like tests/test_v182041_p0_crash_honesty.py
# (markitdown is not installed in this sandbox; the stub keeps the eager
# core.pipeline import chain loadable for the controller behavioral tests).
if "markitdown" not in sys.modules:
    _md = types.ModuleType("markitdown")
    _md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _md

from utils.settings import Settings  # noqa: E402

_CONTROLLER = _project_root / "controller.py"
_SETTINGS = _project_root / "utils" / "settings.py"
_DIALOG = _project_root / "ui_qt" / "settings" / "settings_dialog.py"
# V0.4.19 (de-monolithization) pin evolution: sections.py became the
# sections/ package (17 section classes + helpers moved VERBATIM into
# per-family modules) — the W-b7 pins follow the moved bodies and now
# read every module of the package (same glob precedent as the garble/
# split). Assertions unchanged.
_SECTIONS = _project_root / "ui_qt" / "settings" / "sections"
_SECTIONS_FILES = sorted(_SECTIONS.glob("*.py"))
_TOC_EXTRACTOR = _project_root / "core" / "pdf" / "toc_extractor.py"
_NEW_OUTPUTS = _project_root / "core" / "outputs" / "new_outputs.py"
_VISION_FIG = _project_root / "core" / "pdf" / "vision_figure_extractor.py"
_SEMANTIC_SEG = _project_root / "core" / "segmentation" / "semantic_segmenter.py"
_VRAM_MANAGER = _project_root / "core" / "tts" / "vram_manager.py"
_NORMALIZER = _project_root / "core" / "tts" / "normalizer.py"
_OCR_SERVICE = _project_root / "core" / "ocr" / "service.py"
_SUMMARIZER = _project_root / "core" / "summarisation" / "summarizer.py"
_CONVERTER_IMPL = _project_root / "core" / "pipeline" / "converter_impl.py"
_SUMMARIZATION = _project_root / "core" / "pipeline" / "conversion" / "summarization.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sections_src() -> str:
    """V0.4.19: sections.py became the sections/ package — every module
    concatenated, so the whole-module pins keep their original file-wide
    semantics (the moved bodies are byte-identical)."""
    return "\n".join(_src(p) for p in _SECTIONS_FILES)


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


@contextmanager
def _hermetic_settings(tmp_dir: Path):
    """Point the Settings singleton at a temp dir for the duration (the
    tests/test_integration_pipeline.py pattern), resetting it after."""
    Settings._instance = None
    Settings._test_override = None
    try:
        with (
            patch.object(Settings, "_settings_dir", tmp_dir),
            patch.object(Settings, "_settings_file", tmp_dir / "settings.json"),
        ):
            yield
    finally:
        Settings._instance = None
        Settings._test_override = None


# ═══════════════════════════════════════════════════════════════════════════
# W-c3 — get_settings deep-copy snapshot
# ═══════════════════════════════════════════════════════════════════════════


class TestWc3Snapshot:
    def test_snapshot_is_isolated_copy(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            snap = s.snapshot()
            assert isinstance(snap, dict)
            assert snap is not s._data
            snap["summarisation"]["model"] = "MUTATED-XYZ"
            assert s.get("summarisation.model") != "MUTATED-XYZ"
            assert s.snapshot()["summarisation"]["model"] != "MUTATED-XYZ"

    def test_snapshot_nested_isolation(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            snap = s.snapshot()
            snap.setdefault("ocr", {})["primary_model"] = "MUTATED-OCR"
            assert s.get("ocr.primary_model") != "MUTATED-OCR"

    def test_controller_get_settings_returns_snapshot(self, tmp_path):
        import controller as controller_mod

        with _hermetic_settings(tmp_path):
            c = controller_mod.Controller()
            snap = c.get_settings()
            assert isinstance(snap, dict)
            assert snap is not c.settings._data
            snap["summarisation"]["model"] = "MUTATED-CTRL"
            assert c.get_settings()["summarisation"]["model"] != "MUTATED-CTRL"

    def test_controller_no_longer_returns_live_data(self):
        src = _strip_comments(_src(_CONTROLLER))
        assert "return self.settings._data" not in src, (
            "controller.get_settings must not return the live _data dict (W-c3)"
        )
        assert "self.settings.snapshot()" in src


# ═══════════════════════════════════════════════════════════════════════════
# W-c4 + T-c8 — corrupt-file backup + BOM-tolerant load
# ═══════════════════════════════════════════════════════════════════════════


class TestWc4CorruptSettings:
    def test_corrupt_file_backed_up_before_reset(self, tmp_path):
        sdir = tmp_path / "corrupt"
        sdir.mkdir()
        corrupt = "{ this is definitely !! not json"
        (sdir / "settings.json").write_text(corrupt, encoding="utf-8")
        with _hermetic_settings(sdir):
            s = Settings()
            # defaults restored…
            assert s.get("summarisation.model") == "gemma4-12b:latest"
            # …and the corrupt file was backed up, contents intact
            backups = list(sdir.glob("settings.json.corrupt-*"))
            assert len(backups) == 1, (
                "corrupt settings.json must leave exactly one timestamped backup (W-c4)"
            )
            assert backups[0].read_text(encoding="utf-8") == corrupt

    def test_bom_file_loads_without_reset(self, tmp_path):
        sdir = tmp_path / "bom"
        sdir.mkdir()
        # \ufeff = the UTF-8 BOM Notepad writes — used to throw in json.load
        # and silently reset everything to defaults.
        (sdir / "settings.json").write_text(
            '\ufeff{"summarisation": {"model": "bom-model:latest"}}',
            encoding="utf-8",
        )
        with _hermetic_settings(sdir):
            s = Settings()
            assert s.get("summarisation.model") == "bom-model:latest"
            assert not list(sdir.glob("settings.json.corrupt-*")), (
                "a BOM-prefixed but valid settings.json must not trigger the "
                "corrupt-reset path (T-c8)"
            )

    def test_backup_helper_is_best_effort(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            # settings.json may not even exist (fresh dir) — backup of a
            # missing file must return None, never raise.
            with patch("shutil.copy2", side_effect=OSError("disk gone")):
                assert s._backup_corrupt_file() is None

    def test_load_uses_utf8_sig(self):
        src = _strip_comments(_src(_SETTINGS))
        assert 'open(self._settings_file, encoding="utf-8-sig")' in src


# ═══════════════════════════════════════════════════════════════════════════
# W-b6 — save-failure visibility (Settings.save/set return success)
# ═══════════════════════════════════════════════════════════════════════════


class TestWb6SaveFailure:
    def test_save_returns_true_on_success(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            assert s.save() is True

    def test_save_returns_false_when_write_fails(self, tmp_path, monkeypatch):
        import utils.settings as settings_mod

        def _boom(*a, **k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(settings_mod, "atomic_write_json", _boom)
        with _hermetic_settings(tmp_path):
            s = Settings()
            assert s.save() is False

    def test_set_propagates_save_failure(self, tmp_path, monkeypatch):
        import utils.settings as settings_mod

        def _boom(*a, **k):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(settings_mod, "atomic_write_json", _boom)
        with _hermetic_settings(tmp_path):
            s = Settings()
            # the in-memory mutation still happens…
            result = s.set("summarisation.model", "never-persisted:latest")
            assert s.get("summarisation.model") == "never-persisted:latest"
            # …but the failure is now visible to the caller
            assert result is False

    def test_set_returns_true_on_success(self, tmp_path):
        with _hermetic_settings(tmp_path):
            s = Settings()
            assert s.set("summarisation.model", "persisted:latest") is True

    def test_dialog_warns_and_stays_open_on_save_failure(self):
        src = _src(_DIALOG)
        body_start = src.find("def _on_save")
        body = src[body_start : src.find("\n    def ", body_start)]
        assert "QMessageBox.warning" in body
        assert "return  # keep the dialog open for a retry" in body
        # the old swallow-then-accept is gone
        old_swallow = "self.controller.settings.save()\n        except Exception:\n            pass"
        assert old_swallow not in src

    def test_dialog_calls_save_result(self):
        src = _strip_comments(_src(_DIALOG))
        assert "_saved = self.controller.settings.save()" in src


# ═══════════════════════════════════════════════════════════════════════════
# W-b7 — fast_model double-write + orphaned combo
# ═══════════════════════════════════════════════════════════════════════════


class TestWb7FastModelDoubleWrite:
    def test_orphaned_fast_combo_removed(self):
        src = _strip_comments(_sections_src())
        assert "self.fast_combo" not in src, (
            "the orphaned invisible fast_combo widget must be gone (W-b7)"
        )

    def test_exactly_one_fast_model_write(self):
        src = _strip_comments(_sections_src())
        count = src.count('update_setting("summarisation.fast_model"')
        assert count == 1, f"exactly one authoritative fast_model write expected, found {count}"

    def test_single_write_comes_from_visible_combo(self):
        src = _strip_comments(_sections_src())
        assert (
            'update_setting("summarisation.fast_model", self.fast_model_combo.currentData() or "")'
            in src
        )

    def test_refresh_models_targets_visible_combo(self):
        # V18.20.4.5 (W-b11): the populate body moved from _refresh_models
        # into the async finished-handler _on_models_loaded (the fetch now
        # runs on a SimpleWorker). Same W-b7 policy, evolved anchor: the
        # AiLocal populate handler is the one touching simplification_combo.
        src = _strip_comments(_sections_src())
        body_start = src.find("def _on_models_loaded")
        bodies = []
        while body_start != -1:
            bodies.append(src[body_start : src.find("\n    def ", body_start)])
            body_start = src.find("def _on_models_loaded", body_start + 1)
        ai_local = next((b for b in bodies if "self.simplification_combo" in b), "")
        assert "self.fast_model_combo" in ai_local, (
            "the model refresh must populate the VISIBLE fast_model_combo "
            "(W-b7; W-b11 moved the populate into _on_models_loaded)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# W-c7 — adaptive_toc timeout + model from settings
#
# V0.08 (P2 dead-code removal): the TestWc7AdaptiveToc class (4 tests)
# and its helpers were deleted together with core/pdf/adaptive_toc.py
# (production-dead module). _FakeSettings is KEPT below — it is shared
# by the W-c9 URL-unification tests.
# ═══════════════════════════════════════════════════════════════════════════


class _FakeSettings:
    """Duck-typed Settings (originally built for the adaptive_toc
    resolution block; now shared by the W-c9 URL-unification tests)."""

    store: dict = {}

    def __init__(self):
        pass

    def get(self, path, default=None):
        return self.store.get(path, default)

    def get_ollama_url(self):
        return "http://ollama-rig:11500"


# ═══════════════════════════════════════════════════════════════════════════
# W-c1 — dead models.json + unified defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestWc1ModelsRegistry:
    def test_models_json_deleted(self):
        assert not (_project_root / "config" / "models.json").exists(), (
            "config/models.json had zero readers and disagreed with the live "
            "defaults — it must be gone (W-c1)"
        )

    def test_controller_defaults_match_settings_canonical(self):
        ctrl = _strip_comments(_src(_CONTROLLER))
        # OCR: the canonical settings.py string
        setsrc = _strip_comments(_src(_SETTINGS))
        import re

        m = re.search(r'"primary_model":\s*"([^"]+)"', setsrc)
        assert m, "settings.py must still declare ocr.primary_model"
        canonical_ocr = m.group(1)
        assert canonical_ocr in ctrl, (
            "controller request-builder fallback must use the canonical OCR model string (W-c1)"
        )
        assert "qwen3-vl:8b" not in ctrl
        # Summarisation: gemma4-12b:latest (documented default since V13.45.4)
        m2 = re.search(r'"model":\s*"(gemma4-12b:latest)"', setsrc)
        assert m2, "settings.py must still declare gemma4-12b:latest"
        # V0.13: format-wrapped tuple — key and value on adjacent lines
        assert '"summarisation.model",\n            "gemma4-12b:latest",' in ctrl
        assert "gemma3:12b" not in ctrl


# ═══════════════════════════════════════════════════════════════════════════
# W-c18 — str vs Path in regenerate_output
# ═══════════════════════════════════════════════════════════════════════════


class TestWc18OutputDirPath:
    def test_regenerate_assigns_path(self):
        src = _strip_comments(_src(_CONTROLLER))
        assert "request.output_dir = Path(output_dir)" in src
        assert "request.output_dir = str(output_dir)" not in src


# ═══════════════════════════════════════════════════════════════════════════
# W-c9 — canonical Ollama URL at the (8 + 2) previously-hardcoded sites
# ═══════════════════════════════════════════════════════════════════════════


class TestWc9OllamaUrlUnification:
    def test_vram_manager_resolves_url_from_settings(self, monkeypatch):
        from core.tts import vram_manager

        _FakeSettings.store = {}
        monkeypatch.setattr("utils.settings.Settings", _FakeSettings)
        assert vram_manager._ollama_base_url() == "http://ollama-rig:11500"

    def test_vram_manager_falls_back_fail_soft(self, monkeypatch):
        from core.tts import vram_manager

        class _Broken:
            def __init__(self):
                raise RuntimeError("no settings")

        monkeypatch.setattr("utils.settings.Settings", _Broken)
        assert vram_manager._ollama_base_url() == "http://localhost:11434"

    def test_vram_manager_request_lines_use_resolver(self):
        src = _strip_comments(_src(_VRAM_MANAGER))
        # V18.20.4.11 (P3 / O-c5): transport went pooled (session_for_url);
        # the canonical-resolver INTENT of this pin is unchanged — every
        # request line still resolves through _ollama_base_url().
        assert 'f"{_ollama_base_url()}/api/ps"' in src
        assert "session_for_url(_ps_url).get(_ps_url" in src
        assert 'f"{_ollama_base_url()}/api/generate"' in src
        # the two raw hardcodes are gone from the request lines
        assert 'requests.get("http://localhost:11434' not in src
        assert 'requests.post(\n                    "http://localhost:11434' not in src

    def test_toc_extractor_uses_canonical_url(self):
        src = _strip_comments(_src(_TOC_EXTRACTOR))
        assert "self._settings.get_ollama_url()" in src
        assert 'self._ollama_base_url = "http://localhost:11434"' not in src

    def test_new_outputs_uses_canonical_url(self):
        src = _strip_comments(_src(_NEW_OUTPUTS))
        assert "settings.get_ollama_url()" in src
        assert 'self.ollama_base_url = "http://localhost:11434"' not in src

    def test_vision_figure_extractor_uses_canonical_url(self):
        src = _strip_comments(_src(_VISION_FIG))
        assert "self.settings.get_ollama_url()" in src

    def test_semantic_segmenter_uses_canonical_url(self):
        src = _strip_comments(_src(_SEMANTIC_SEG))
        assert "Settings().get_ollama_url()" in src

    def test_normalizer_uses_canonical_url(self):
        src = _strip_comments(_src(_NORMALIZER))
        assert "s.get_ollama_url()" in src
        assert 'requests.get("http://localhost:11434/api/tags"' not in src

    def test_ocr_service_resolves_at_call_time(self):
        src = _strip_comments(_src(_OCR_SERVICE))
        assert "def _ollama_url(self)" in src
        # V0.4.9 refactored the second /api/generate call site to the
        # endpoint-parameterized form ``f"{self._ollama_url()}{endpoint}"``
        # (so /api/chat can share the same resolution path). V0.4.19 routed
        # that helper back through the module-level ``safe_ollama_request``.
        # The pin's INTENT is unchanged: every Ollama call site resolves the
        # URL at call time via ``self._ollama_url()`` — no hardcoded
        # ``http://localhost:11434/api/...`` anywhere in live call sites.
        assert src.count('url = f"{self._ollama_url()}/api/generate"') == 1
        assert src.count('url = f"{self._ollama_url()}{endpoint}"') == 1
        assert "http://localhost:11434/api/" not in src

    def test_ocr_service_resolver_is_fail_soft(self):
        from core.ocr.service import OCRService

        class _Broken:
            def __init__(self):
                raise RuntimeError("no settings")

        with patch("utils.settings.Settings", _Broken):
            assert OCRService._ollama_url(OCRService.__new__(OCRService)) == (
                "http://localhost:11434"
            )

    def test_summarizer_uses_canonical_url(self):
        # V0.18 (Phase 5.1, step 5): _init_runtime_basics moved VERBATIM to
        # summarizer_init.py (SummarizerInitMixin).
        src = _strip_comments(_src(_project_root / "core" / "summarisation" / "summarizer_init.py"))
        body_start = src.find("def _init_runtime_basics")
        assert body_start != -1, "_init_runtime_basics must exist"
        body = src[body_start : src.find("\n    def ", body_start)]
        assert "self.ollama_base_url = Settings().get_ollama_url()" in body
        # the localhost literal survives ONLY as the fail-soft except-branch
        # fallback — exactly once, guarded by "except Exception:"
        assert body.count('self.ollama_base_url = "http://localhost:11434"') == 1
        assert "except Exception:" in body


# ═══════════════════════════════════════════════════════════════════════════
# G-1 — stamp_diagnostic version-mismatch escalation (the F8 follow-up)
# ═══════════════════════════════════════════════════════════════════════════

_STAMPED_38 = (
    "# Summary: T\n\n"
    "<!-- generated-by: Elixir v18.20.3.8 | run_id=20260831-183806-bf1bfab9"
    " | started=2026-08-31T18:38:06 | bullets=44 -->\n\n"
    "## Executive Summary\n\ncontent\n"
)


class TestG1StampVersionMismatch:
    def test_stale_version_escalates_to_warning(self):
        from core.system.provenance import stamp_diagnostic

        level, msg = stamp_diagnostic("001_summary.md", _STAMPED_38, current_version="18.20.4.3")
        assert level == "WARNING"
        assert "STALE ARTIFACT" in msg
        assert "v18.20.3.8" in msg and "18.20.4.3" in msg
        assert "do NOT upload" in msg
        assert "20260831-183806-bf1bfab9" in msg

    def test_same_version_stays_info(self):
        from core.system.provenance import stamp_diagnostic

        level, msg = stamp_diagnostic("001_summary.md", _STAMPED_38, current_version="18.20.3.8")
        assert level == "INFO"
        assert msg.startswith("✓")

    def test_no_current_version_backward_compatible(self):
        from core.system.provenance import stamp_diagnostic

        level, _ = stamp_diagnostic("001_summary.md", _STAMPED_38)
        assert level == "INFO"

    def test_unknown_stamp_version_never_escalates(self):
        from core.system.provenance import stamp_diagnostic

        sentinel_only = "content\n<!-- COMPLETE run_id=abc12345 -->\n"
        level, msg = stamp_diagnostic("old.md", sentinel_only, current_version="18.20.4.3")
        assert level == "INFO"  # legacy sentinel-only: run id present, version unknown

    def test_unstamped_still_warns(self):
        from core.system.provenance import stamp_diagnostic

        level, msg = stamp_diagnostic("old.md", "no stamp here", "18.20.4.3")
        assert level == "WARNING"
        assert "NO generated-by stamp" in msg

    def test_never_raises(self):
        from core.system.provenance import stamp_diagnostic

        assert stamp_diagnostic("a.md", None, "18.20.4.3")[0] == "WARNING"
        assert stamp_diagnostic("b.md", "", "18.20.4.3")[0] == "WARNING"
        assert stamp_diagnostic("c.md", "\x00garbage", "18.20.4.3")[0] == "WARNING"


# ═══════════════════════════════════════════════════════════════════════════
# G-2 — the converter scan passes full paths + current version
# ═══════════════════════════════════════════════════════════════════════════


class TestG2ConverterScan:
    def test_scan_passes_current_version_and_full_path(self):
        src = _strip_comments(_src(_CONVERTER_IMPL))
        assert "current_version=_app_ver" in src
        assert "str(_sf)" in src


# ═══════════════════════════════════════════════════════════════════════════
# G-3 — the visible provenance footer
# ═══════════════════════════════════════════════════════════════════════════


class _Summ:
    """Duck-typed SummaryResult for render_summary_markdown."""

    chapter_heading = "Test Chapter"
    executive_summary = "Exec text (1956)."
    bullet_points = ["B1 (1956)", "B2"]
    thorough_summary = "Thorough text."
    key_distinctions = ""
    theoretical_tensions = ""
    scholar_reflections = None


class TestG3VisibleFooter:
    def test_footer_shape(self):
        from core.system.provenance import visible_footer

        f = visible_footer("18.20.4.3", "20260901-154401-fe4399da", "2026-09-01T15:44:01", 46)
        assert f.startswith("\n---\n\n")
        assert f.endswith("\n\n")
        assert (
            "*Generated by Elixir v18.20.4.3"
            " · run 20260901-154401-fe4399da"
            " · 2026-09-01T15:44:01"
            " · 46 bullets*" in f
        )

    def test_stamped_chapter_renders_footer_before_sentinel(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown
        from core.system.provenance import parse_provenance

        s = _Summ()
        s.run_id = "20260901-154401-fe4399da"
        s.app_version = "18.20.4.3"
        s.run_started = "2026-09-01T15:44:01"
        out = render_summary_markdown(s)
        assert "*Generated by Elixir v18.20.4.3" in out
        # footer sits between the content and the sentinel
        assert out.index("*Generated by") < out.index("<!-- COMPLETE")
        assert out.rstrip().endswith("<!-- COMPLETE run_id=20260901-154401-fe4399da -->")
        # the machine-readable stamp still parses (footer must not confuse it)
        prov = parse_provenance(out)
        assert prov["app_version"] == "18.20.4.3"
        assert prov["run_id"] == "20260901-154401-fe4399da"
        assert prov["bullets"] == "2"

    def test_legacy_chapter_renders_byte_identical_shape(self):
        from core.pipeline.chapter_checkpoint import render_summary_markdown

        s = _Summ()
        s.run_id = ""
        out = render_summary_markdown(s)
        assert "Generated by" not in out
        assert "\n---\n" not in out  # no footer rule for legacy output
        assert out.endswith("<!-- COMPLETE -->\n")

    def test_book_summary_gets_footer(self):
        src = _strip_comments(_src(_SUMMARIZATION))
        assert "visible_footer(_bk_ver" in src
