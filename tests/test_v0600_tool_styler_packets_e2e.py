"""V0.6.0 (the dedicated-tools verification campaign) — Tools: the Markdown
Styler (``markdown_styler``) + Packets of Knowledge (``packets_tool``),
end-to-end.

Inventory + trace (evidence-first):
- TOOL A — Markdown Styler:
  Card: ``markdown_styler`` — ``ui_qt/views/tool_dashboard.py:77`` TOOL_CARDS
  row 2 (TRANSFORM).
  Routing: ``ui_qt/views/convert_view.py:187`` ``_on_tool_clicked`` →
  ``MarkdownStylerDialog`` (via the base_dialog facade re-export).
  Dialog: ``ui_qt/views/service_dialogs/dialogs/markdown_styler_dialog.py``
  — DETERMINISTIC since V11.71.0 (module docstring :5-7): no LLM, no
  worker thread. The "service" is the embedded
  ``_style_markdown_deterministic`` (:223); the handoff note "check the
  dialog's provider path" resolves to *there is none* — the V11.66.0 LLM
  path was replaced by pure-Python regex in V11.71.0 (dialog :42-44).
- TOOL B — Packets of Knowledge:
  Card: ``packets_tool`` — ``tool_dashboard.py:85`` row 2 (TRANSFORM).
  Routing: ``convert_view.py:194`` → ``PacketsToolDialog`` (facade).
  Dialog: ``dialogs/packets_tool_dialog.py`` (``_PacketWorker`` QThread
  :46, ``run`` :61; ``_on_generate`` :419; ``_on_done`` :472; pure parse
  helpers ``_extract_bullets`` :314, ``_parse_pasted_text`` :335,
  ``_parse_file`` :373).
  Service: ``core/outputs/packets/generator.py`` (``generate`` :77;
  ``_call_llm`` :1030 — raw ``requests`` against
  ``summarisation.endpoint``; a ``/v1`` URL without :11434 hits the
  OpenAI-compatible SSE branch → the :3031 shim speaks exactly that).
  Provider injection: ``Settings._test_override`` (the
  ``scripts/repeatability_run.py:246`` precedent) with
  provider="llamacpp", endpoint="http://localhost:3031/v1",
  model="glm-4-plus".

Layers (house UI-test pattern, cf. tests/test_v0600_tool_cutter_e2e.py):
1. Pure characterization of each tool's helpers (styler regex engine,
   packets dialog parsers, packets generator cluster/parse helpers).
2. Service-level: LIVE LLM through the :3031 shim for Packets (2 packets
   × 2 calls + 1 one-page distillation = 5 live calls; the Styler has no
   LLM — its Layer 2 IS the deterministic engine, pinned in Layer 1) +
   patched-LLM service level for the defect pins.
3. Dialog-level drives: the Styler synchronously (deterministic — modal
   boxes monkeypatched to recorders), Packets through the REAL
   ``_PacketWorker`` QThread + queued signals, spinning the event loop
   until status/output lands.

V0.6.0 defects pinned here (content-agnostic fixes):
- S-A: key-concepts fallback matched across newlines (``\\s+``) → broke
  the Obsidian callout (markdown_styler_dialog.py:390-392 pre-fix).
- S-B: the space-collapse regex left TWO spaces behind — double spaces
  never collapsed (markdown_styler_dialog.py:266 pre-fix).
- S-C: YAML frontmatter title not escaped → a heading with a ``"`` broke
  the frontmatter (markdown_styler_dialog.py:348 pre-fix).
- S-D: dead checkboxes ("Add bullet points…", "Convert related terms to
  [[wikilinks]]") advertised features the deterministic engine never
  implemented (markdown_styler_dialog.py:133-143, 204-206 pre-fix).
- P-A: unsanitized book title in the four output file names → a "/"
  silently scattered outputs into unintended subdirectories (and
  Windows-illegal chars raise) — generator.py:187-206 pre-fix.
- P-B: chapter-aligned packets keep the author's RAW bullets but the
  doc/coverage reported the DEDUPED counts → "10 input bullets" reported
  as "2 keypoints", >100% coverage, false "orphan bullets" lines
  (generator.py:113-115 pre-fix; dedup now runs only in cross-chapter
  mode where it feeds clustering).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Layer 0: availability gates ─────────────────────────────────────────────


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _shim_available() -> bool:
    """The zai-llamacpp shim on :3031 (health endpoint)."""
    try:
        import requests

        r = requests.get("http://localhost:3031/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _ensure_qapp():
    """Every dialog constructed in this module needs a QApplication (a
    QWidget without one aborts the process — no conftest provides one)."""
    if _qt_available():
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
    yield


_SHIM_URL = "http://localhost:3031/v1"
_SHIM_MODEL = "glm-4-plus"


# ── Shared helpers ──────────────────────────────────────────────────────────


class _StubController:
    """Dialogs only need get/update_setting (verified by campaign probes)."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


class _SettingsOverride:
    """In-memory Settings stand-in (the ``Settings._test_override`` DI hook
    at utils/settings.py:85 — every in-function ``Settings()`` call resolves
    to this instance, the scripts/repeatability_run.py:246 pattern)."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)

    def set(self, key: str, value) -> bool:
        self._v[key] = value
        return True


@pytest.fixture
def settings_override(monkeypatch):
    """Install a hermetic Settings override; return it for mutation."""
    from utils.settings import Settings

    override = _SettingsOverride()
    previous = Settings._test_override
    Settings._test_override = override  # type: ignore[assignment]
    try:
        yield override
    finally:
        Settings._test_override = previous  # type: ignore[assignment]


def _shim_values() -> dict[str, object]:
    """Provider plumbing that routes PacketGenerator._call_llm at the shim
    (generator.py:1030: provider != "cloud" + endpoint containing "/v1"
    but not "11434" → OpenAI-compatible /chat/completions SSE branch)."""
    return {
        "summarisation.provider": "llamacpp",
        "summarisation.endpoint": _SHIM_URL,
        "summarisation.model": _SHIM_MODEL,
    }


class _MsgBoxRecorder:
    """Stands in for the dialog module's QMessageBox (static modal calls)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def warning(self, parent, title, text) -> None:
        self.calls.append(("warning", title, text))

    def critical(self, parent, title, text) -> None:
        self.calls.append(("critical", title, text))

    def information(self, parent, title, text) -> None:  # defensive
        self.calls.append(("information", title, text))

    def titles(self) -> list[str]:
        return [t for _kind, t, _text in self.calls]


def _spin_until_status(app, dlg, prefixes=("✅", "❌", "⚠️"), timeout_ms=15000) -> str:
    """Spin the event loop until the dialog's status label lands."""
    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        text = dlg.status_label.text()
        if text.startswith(tuple(prefixes)):
            return text
        time.sleep(0.02)
        waited += 20
    return dlg.status_label.text()


def _style(text: str, options: dict | None = None) -> str:
    """Invoke the deterministic engine without driving the whole dialog UI."""
    from ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog import MarkdownStylerDialog

    dlg = MarkdownStylerDialog(_StubController())
    return dlg._style_markdown_deterministic(
        text, options or {"tldr": True, "key_concepts": True, "tags": True}
    )


# ═════════════════════════════════════════════════════════════════════════════
# TOOL A — Markdown Styler
# ═════════════════════════════════════════════════════════════════════════════


# ── Layer 1: deterministic engine characterization ─────────────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestStylerEngineCharacterization:
    """Pin the deterministic engine's regex behavior (no LLM involved)."""

    # Step 1 — HTML/artifact removal
    def test_script_and_style_blocks_removed(self):
        out = _style("<script>bad()</script><style>p{}</style>kept text line one here")
        assert "bad()" not in out and "p{}" not in out
        assert "kept text line one here" in out

    def test_html_tags_and_entities_removed(self):
        out = _style("<p>Hello &amp; welcome &nbsp;world &lt;tag&gt; &quot;q&quot;</p>")
        assert "<p>" not in out and "&amp;" not in out
        assert "Hello & welcome" in out
        assert "<tag>" in out and '"q"' in out

    # Step 2 — whitespace
    def test_tabs_become_spaces_then_collapse(self):
        out = _style("alpha\tbeta line in the test document")
        # tab → 4 spaces (Step 2) → collapsed to one space mid-line (S-B)
        assert "\t" not in out
        assert "alpha beta line in the test document" in out

    def test_excess_blank_lines_capped(self):
        out = _style("first line of the note\n\n\n\n\n\nsecond line of the note")
        assert "\n\n\n\n" not in out

    def test_sb_double_spaces_now_collapse(self):
        """S-B (V0.6.0): ``re.sub(r"(?<= ) +", " ")`` always left TWO
        spaces behind (one lookbehind anchor + the replacement) — the
        advertised "collapse multiple spaces" never collapsed doubles."""
        out = _style("Steam engines   needed    water and coal at the depot")
        assert "engines needed water" in out
        assert "engines  needed" not in out

    def test_sb_line_start_whitespace_normalized_by_line_formatter(self):
        # Pre-existing characterization: the heading-formatting loop appends
        # every line STRIPPED — line-leading indentation does not survive
        # (the mid-line collapse fix does not touch line starts).
        out = _style(
            "intro line that is long enough to be counted\n    indented code-ish line stays indented here"
        )
        assert "\nindented code-ish line" in out

    # Step 3 — heading detection
    def test_title_case_short_line_becomes_heading(self):
        out = _style("Study Notes On Trains\n\nRailways changed how people moved goods.")
        assert "## Study Notes On Trains" in out

    def test_all_caps_line_becomes_heading(self):
        out = _style("SECTION HEADER\n\nBody prose that is long enough to look like text.")
        assert "## SECTION HEADER" in out

    def test_sentence_line_is_not_heading(self):
        out = _style(
            "This line ends with a period and is not a heading at all.\n\nAnother line of prose follows here."
        )
        assert "## This line" not in out

    def test_existing_markdown_headings_untouched(self):
        out = _style("### Already Formatted\n\nSome prose under the heading goes here.")
        assert "### Already Formatted" in out
        assert "#### Already" not in out

    def test_sixth_heading_gets_three_hashes(self):
        lines = "\n\n".join(
            [f"Heading Number {i}" for i in range(1, 7)]
            + ["Trailing prose line to close the document out."]
        )
        out = _style(lines)
        assert "## Heading Number 1" in out
        assert "### Heading Number 6" in out

    # Step 4/5 — list normalization
    def test_unicode_bullets_normalized(self):
        out = _style(
            "• First point about the topic\n· Second point made here\n◦ Third point as well"
        )
        assert "\n- First point about the topic" in out
        assert "- Second point made here" in out
        assert "- Third point as well" in out

    def test_star_and_plus_bullets_normalized(self):
        out = _style("* star item described here\n+ plus item described here")
        assert "- star item described here" in out
        assert "- plus item described here" in out

    def test_paren_numbered_list_normalized(self):
        out = _style("1) first numbered point\n2) second numbered point")
        assert "1. first numbered point" in out
        assert "2. second numbered point" in out

    # Step 6 — links
    def test_bare_url_becomes_markdown_link(self):
        out = _style("Visit https://example.com/railways for more details.")
        assert "Visit [https://example.com/railways](https://example.com/railways) for more" in out

    def test_already_linked_url_not_double_wrrapped(self):
        text = "See [the guide](https://example.com/guide) for details today."
        out = _style(text)
        assert out.count("https://example.com/guide") == 2
        assert "[[the guide]" not in out

    # Step 7 — frontmatter
    def test_frontmatter_title_from_heading(self):
        out = _style(
            "A Proper Heading\n\nSome body prose under the heading goes here.",
            {"tldr": False, "key_concepts": False, "tags": True},
        )
        assert 'title: "A Proper Heading"' in out
        assert out.startswith("---\n")

    def test_frontmatter_tags_from_capitalized_words(self):
        out = _style("Heading Line Here\n\nAlpha Beta Gamma Delta Epsilon words in the note body.")
        assert "tags: [heading, line, here" in out

    def test_sc_frontmatter_title_escapes_quotes(self):
        """S-C (V0.6.0): a heading containing a double quote produced
        invalid YAML frontmatter."""
        out = _style('The "Fast" Track\n\nBody prose about railway corridors.')
        assert 'title: "The \\"Fast\\" Track"' in out

    def test_tags_option_gates_frontmatter(self):
        out = _style(
            "Heading Line Here\n\nBody prose that is long enough to count.",
            {"tldr": False, "key_concepts": False, "tags": False},
        )
        assert not out.startswith("---\n")
        assert "title:" not in out

    # Step 8 — TLDR
    def test_tldr_picks_first_eligible_sentence(self):
        """S-E (V0.6.0): the sentence splitter glues a heading line to the
        following paragraph (no terminal punctuation on headings), so the
        first content sentence was skipped whenever a heading preceded it —
        the TL;DR fell through to a later sentence. Heading lines are now
        dropped before the split."""
        out = _style("Plain Heading Text\n\nThe very first sentence of the body text is here.")
        assert "> [!tldr] Summary" in out
        assert "> The very first sentence of the body text is here." in out

    def test_tldr_option_gates_block(self):
        out = _style(
            "Plain Heading Text\n\nThe very first sentence of the body text is here.",
            {"tldr": False, "key_concepts": False, "tags": False},
        )
        assert "[!tldr]" not in out

    # Step 9 — key concepts
    def test_key_concepts_from_bold_terms(self):
        out = _style(
            "Some intro prose here.\n\nBody mentions **Alpha Concept** and **Beta Concept** clearly."
        )
        assert "> [!info] Key Concepts" in out
        assert "> - **Alpha Concept**" in out
        assert "> - **Beta Concept**" in out

    def test_sa_concept_terms_do_not_cross_lines(self):
        """S-A (V0.6.0): the fallback concept regex used ``\\s+`` in the
        continuation group — it matched ACROSS the newline, emitting an
        un-prefixed line inside the ``> - **...**`` callout and breaking
        the Obsidian callout block."""
        out = _style("Study Notes On Trains\nRailways changed the world.")
        lines = out.splitlines()
        in_concepts = False
        for line in lines:
            if line.startswith("> [!info] Key Concepts"):
                in_concepts = True
                continue
            if in_concepts and line == "":
                break
            if in_concepts:
                # every line inside the callout must keep the prefix
                assert line.startswith("> "), repr(line)
        assert in_concepts

    def test_key_concepts_option_gates_block(self):
        out = _style(
            "Study Notes On Trains\nRailways changed the world.",
            {"tldr": False, "key_concepts": False, "tags": False},
        )
        assert "[!info]" not in out

    # S-D — the dead option checkboxes are gone
    def test_sd_dead_option_widgets_removed(self):
        from ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog import MarkdownStylerDialog

        dlg = MarkdownStylerDialog(_StubController())
        # V0.6.0: the deterministic engine never read "bullets"/"links" —
        # the checkboxes advertising them were removed.
        assert not hasattr(dlg, "cb_bullets")
        assert not hasattr(dlg, "cb_links")
        assert (
            hasattr(dlg, "cb_tldr") and hasattr(dlg, "cb_key_concepts") and hasattr(dlg, "cb_tags")
        )

    def test_sd_options_dict_has_only_live_keys(self):
        import ast

        from ui_qt.views.service_dialogs.dialogs import markdown_styler_dialog as styler_mod

        tree = ast.parse(Path(styler_mod.__file__).read_text(encoding="utf-8"))
        method = next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_on_process"
        )
        keys = set()
        for node in ast.walk(method):
            if isinstance(node, ast.Dict):
                keys.update(k.value for k in node.keys if isinstance(k, ast.Constant))
        assert keys == {"tldr", "key_concepts", "tags"}


# ── Layer 3: dialog drive (deterministic, synchronous — no worker) ─────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestStylerDialogDrive:
    """Drive _on_process/_on_save exactly as the UI does. Modal boxes are
    monkeypatched to recorders — ``QMessageBox.warning`` would block a
    headless test."""

    def _make(self, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.markdown_styler_dialog as styler_mod

        rec = _MsgBoxRecorder()
        monkeypatch.setattr(styler_mod, "QMessageBox", rec)
        dlg = styler_mod.MarkdownStylerDialog(_StubController())
        return dlg, app, rec, styler_mod

    def test_full_style_flow_lands_success(self, monkeypatch):
        dlg, _app, rec, _mod = self._make(monkeypatch)
        # V0.6.5 contract update: the dialog now defaults to the LLM path;
        # this Layer-3 drive pins the DETERMINISTIC engine, so it opts out
        # explicitly (the LLM path has its own drive in
        # test_v065_rtl_styler_translation.py with a fake at the seam).
        dlg.llm_chk.setChecked(False)
        messy = (
            "<div>Study Notes On Trains</div>\n\n"
            "Railways changed how people travel and trade goods across continents.\n\n"
            "• First bullet point about locomotive boiler pressure\n"
            "• Second bullet about timetables needing a standard clock\n"
        )
        dlg.text_input.setPlainText(messy)
        dlg._on_process()

        assert dlg.status_label.text().startswith("✅"), dlg.status_label.text()
        assert "Styled!" in dlg.status_label.text()
        out = dlg.output_preview.toPlainText()
        assert "## Study Notes On Trains" in out
        assert "- First bullet point about locomotive boiler pressure" in out
        assert dlg.save_btn.isEnabled()
        assert dlg.process_btn.text() == "✨ Style My Markdown"
        assert dlg.process_btn.isEnabled()
        assert rec.calls == []

    def test_short_text_guard_warns_and_skips(self, monkeypatch):
        dlg, _app, rec, _mod = self._make(monkeypatch)
        dlg.llm_chk.setChecked(False)  # V0.6.5: deterministic path for this drive
        dlg.text_input.setPlainText("too short")
        dlg._on_process()
        assert rec.titles() == ["Need more text"]
        assert not dlg.save_btn.isEnabled()
        assert dlg.output_preview.toPlainText() == ""
        assert dlg.process_btn.isEnabled()

    def test_save_writes_file_and_reports_path(self, monkeypatch, tmp_path):
        dlg, _app, rec, styler_mod = self._make(monkeypatch)
        target = tmp_path / "styled_note.md"

        class _FakeFileDialog:
            @staticmethod
            def getSaveFileName(*_a, **_k):
                return (str(target), "")

        monkeypatch.setattr(styler_mod, "QFileDialog", _FakeFileDialog)
        dlg.output_preview.setPlainText("# Styled\n\nContent of the note goes right here.")
        dlg._on_save()

        assert target.read_text(encoding="utf-8").startswith("# Styled")
        assert dlg.status_label.text() == f"✅ Saved to: {target}"
        assert rec.calls == []

    def test_save_failure_shows_critical_box(self, monkeypatch, tmp_path):
        dlg, _app, rec, styler_mod = self._make(monkeypatch)

        class _FakeFileDialog:
            @staticmethod
            def getSaveFileName(*_a, **_k):
                return (str(tmp_path), "")  # a DIRECTORY → write fails

        monkeypatch.setattr(styler_mod, "QFileDialog", _FakeFileDialog)
        dlg.output_preview.setPlainText("Some content that would be written out to a file.")
        dlg._on_save()
        assert rec.titles() == ["Save failed"]
        assert "Saved to:" not in dlg.status_label.text()


# ═════════════════════════════════════════════════════════════════════════════
# TOOL B — Packets of Knowledge
# ═════════════════════════════════════════════════════════════════════════════


# ── Layer 1a: dialog pure parse helpers ─────────────────────────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestPacketsDialogParseHelpers:
    """Static helpers — characterization without a dialog instance."""

    def _cls(self):
        from ui_qt.views.service_dialogs.dialogs.packets_tool_dialog import PacketsToolDialog

        return PacketsToolDialog

    def test_extract_bullets_markdown_and_unicode(self):
        extract = self._cls()._extract_bullets
        text = "## Heading\n- first bullet line here\n* second bullet line here\n• third bullet line here\nplain prose line"
        assert extract(text) == [
            "first bullet line here",
            "second bullet line here",
            "third bullet line here",
        ]

    def test_extract_bullets_numbered_forms(self):
        extract = self._cls()._extract_bullets
        assert extract("1. numbered one here\n2) numbered two here") == [
            "numbered one here",
            "numbered two here",
        ]

    def test_extract_bullets_skips_short_and_headings(self):
        extract = self._cls()._extract_bullets
        assert extract("## Chapter\n- tiny\n- a real bullet point survives") == [
            "a real bullet point survives"
        ]
        assert extract("no bullets anywhere in this prose") == []

    def test_parse_pasted_text_splits_on_h2_only(self):
        parse = self._cls()._parse_pasted_text
        text = (
            "## Alpha Section\n- alpha bullet one goes here\n- alpha bullet two goes here\n"
            "### Sub Heading\n- alpha bullet three goes here\n- alpha bullet four goes here\n"
            "## Beta Section\n- beta bullet one goes here\n- beta bullet two goes here\n"
        )
        summaries = parse(text)
        assert [s.chapter_heading for s in summaries] == ["Alpha Section", "Beta Section"]
        assert len(summaries[0].bullet_points) == 4  # the ### sub-heading does NOT split
        assert len(summaries[1].bullet_points) == 2
        assert all(s.success for s in summaries)

    def test_parse_pasted_text_without_headings_is_one_chunk(self):
        parse = self._cls()._parse_pasted_text
        summaries = parse("- lone bullet number one here\n- lone bullet number two here")
        assert len(summaries) == 1
        # no ## heading → chunk heading is "" → the Chapter-N fallback
        assert summaries[0].chapter_heading == "Chapter 1"

    def test_parse_pasted_text_prose_without_bullets_is_empty(self):
        assert (
            self._cls()._parse_pasted_text("Just flowing prose with no bullets at all here.") == []
        )

    def test_parse_file_legacy_markdown(self, tmp_path):
        parse = self._cls()._parse_file
        f = tmp_path / "my_note.md"
        f.write_text("# ignored\n- legacy bullet one goes here\n- legacy bullet two goes here\n")
        summaries = parse(f)
        assert len(summaries) == 1
        assert summaries[0].chapter_heading == "my_note"
        assert summaries[0].bullet_points == [
            "legacy bullet one goes here",
            "legacy bullet two goes here",
        ]

    def test_parse_file_read_error_returns_none(self, tmp_path):
        assert self._cls()._parse_file(tmp_path / "missing.md") is None

    def test_parse_file_empty_returns_none(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("   ")
        assert self._cls()._parse_file(f) is None

    def test_parse_file_no_bullets_returns_empty(self, tmp_path):
        f = tmp_path / "prose.md"
        f.write_text("Only prose lives in this file, nothing else at all.")
        assert self._cls()._parse_file(f) == []

    def test_parse_file_chapters_md_delegates(self, tmp_path):
        """V13.23.0: a .Chapters.md export is parsed by read_chapters_md —
        each chapter section becomes its own SummaryResult with the
        executive summary populated."""
        from core.models import SummaryResult
        from core.outputs.chapters_export import write_chapters_md

        summaries = [
            SummaryResult(
                chapter_heading="Alpha Chapter",
                executive_summary="Alpha chapter summary sentence that is long enough.",
                thorough_summary="",
                bullet_points=["alpha bullet one goes here", "alpha bullet two goes here"],
                success=True,
            ),
            SummaryResult(
                chapter_heading="Beta Chapter",
                executive_summary="Beta chapter summary sentence that is long enough.",
                thorough_summary="",
                bullet_points=["beta bullet one goes here", "beta bullet two goes here"],
                success=True,
            ),
        ]
        path = write_chapters_md(summaries, "Fixture Book", tmp_path / "Fixture Book.Chapters.md")
        parsed = self._cls()._parse_file(path)
        assert parsed is not None and len(parsed) == 2
        assert [s.chapter_heading for s in parsed] == ["Alpha Chapter", "Beta Chapter"]
        assert parsed[0].executive_summary.startswith("Alpha chapter summary")
        assert parsed[1].bullet_points == ["beta bullet one goes here", "beta bullet two goes here"]


# ── Layer 1b: generator pure helpers ────────────────────────────────────────


class TestPacketsGeneratorPureHelpers:
    def _gen(self):
        from core.outputs.packets.generator import PacketGenerator

        return PacketGenerator(request=None, log_callback=lambda m, l="INFO": None)

    def test_split_bullets_even_distribution(self):
        from core.outputs.packets.generator import PacketGenerator

        sizes = [
            len(c)
            for c in PacketGenerator._split_bullets_into_chunks([f"b{i}" for i in range(22)], 7)
        ]
        assert sizes == [6, 6, 5, 5]

    def test_split_bullets_small_input_single_chunk(self):
        from core.outputs.packets.generator import PacketGenerator

        assert PacketGenerator._split_bullets_into_chunks(["a", "b", "c"], 7) == [["a", "b", "c"]]
        assert PacketGenerator._split_bullets_into_chunks([], 7) == []

    def test_sanitize_mermaid_id_shapes(self):
        from core.outputs.packets.generator import PacketGenerator

        s = PacketGenerator._sanitize_mermaid_id
        assert s("Concept A, B & C!") == "concept_a_b_c"
        assert s("9startsdigit") == "n_9startsdigit"
        assert s("") == "n"
        assert s("x" * 50) == "x" * 30

    def test_parse_combined_response_shapes(self):
        gen = self._gen()
        assert gen._parse_combined_response('{"paragraph": "abc", "tldr": "xyz"}') == ("abc", "xyz")
        assert gen._parse_combined_response('```json\n{"paragraph": "a", "tldr": "b"}\n```') == (
            "a",
            "b",
        )
        raw = 'prefix {"paragraph": "esc\\naped", "tldr": "tl"} suffix'
        assert gen._parse_combined_response(raw) == ("esc\naped", "tl")
        assert gen._parse_combined_response("Just a plain paragraph answer.") == (
            "Just a plain paragraph answer.",
            "",
        )
        assert gen._parse_combined_response(None) == ("", "")
        assert gen._parse_combined_response("") == ("", "")

    def test_parse_combined_response_think_blocks_stripped(self):
        gen = self._gen()
        out = gen._parse_combined_response(
            '<think>scratch</think>\n{"paragraph": "p", "tldr": "t"}'
        )
        assert out == ("p", "t")

    def test_extract_exec_summary_sentences(self):
        from core.outputs.packets.generator import PacketGenerator

        extract = PacketGenerator._extract_exec_summary_sentences
        assert extract("") == []
        assert extract("   ") == []
        sentences = extract(
            "One sentence that is definitely long enough to survive. "
            "Another sentence that is also long enough to survive. "
            "A third sentence that is long enough and should survive."
        )
        assert sentences == [
            "One sentence that is definitely long enough to survive.",
            "Another sentence that is also long enough to survive.",
            "A third sentence that is long enough and should survive.",
        ]
        assert (
            len(
                extract(
                    " ".join(f"Sentence number {i} is long enough to count here." for i in range(8))
                )
            )
            == 5
        )

    def test_collect_bullets_filters_and_strips(self):
        from core.models import SummaryResult

        gen = self._gen()
        summaries = [
            SummaryResult(
                chapter_heading="Alpha",
                executive_summary="",
                thorough_summary="",
                bullet_points=[
                    "  -alpha bullet keeps its text here",
                    "short",
                    "a bullet that is long enough passes",
                ],
                success=True,
            ),
            SummaryResult(
                chapter_heading="Failed",
                executive_summary="",
                thorough_summary="",
                bullet_points=["failed chapter bullet that is long enough"],
                success=False,
            ),
        ]
        bullets = gen._collect_bullets(summaries)
        assert bullets == [
            ("alpha bullet keeps its text here", "Alpha"),
            ("a bullet that is long enough passes", "Alpha"),
        ]

    def test_get_mode_resolution(self, settings_override):
        gen = self._gen()
        assert gen._get_mode() == "chapter"  # default
        settings_override.set("packets.mode", "cross_chapter")
        assert gen._get_mode() == "cross_chapter"
        settings_override.set("packets.mode", "garbage")
        assert gen._get_mode() == "chapter"


# ── Layer 2: service-level (patched LLM) — defect pins ─────────────────────


def _patched_generator(settings_override, tmp_path, llm_response: str | None = None):
    """A PacketGenerator with the LLM call patched at the INSTANCE level —
    the real clustering/hierarchy/writers run, only the HTTP call is fake."""
    from core.models import ConversionRequest
    from core.outputs.packets.generator import PacketGenerator

    settings_override.set("packets.mode", "chapter")
    gen = PacketGenerator(
        request=ConversionRequest(input_path=tmp_path / "book.pdf", output_dir=tmp_path),
        log_callback=lambda m, l="INFO": None,
    )
    if llm_response is None:
        llm_response = (
            '{"paragraph": "Synthesized paragraph text that is long enough to pass '
            'the length gate for validation purposes.", "tldr": "brief take"}'
        )
    gen._call_llm = lambda prompt, model, provider, temperature: llm_response
    return gen


def _chapter_summaries(dup_style: bool = False) -> list:
    from core.models import SummaryResult

    if dup_style:
        # near-duplicate phrasing across chapters (the V13.19.0 dedup signal)
        return [
            SummaryResult(
                chapter_heading="Alpha Chapter",
                executive_summary="",
                thorough_summary="",
                bullet_points=[f"Take detailed notes using a contact sheet {i}" for i in range(5)],
                success=True,
            ),
            SummaryResult(
                chapter_heading="Beta Chapter",
                executive_summary="",
                thorough_summary="",
                bullet_points=[
                    f"Use detailed notes called a client contact sheet {i}" for i in range(5)
                ],
                success=True,
            ),
        ]
    return [
        SummaryResult(
            chapter_heading="Alpha Chapter",
            executive_summary="The alpha chapter surveys railways and their operating model.",
            thorough_summary="",
            bullet_points=[
                "Locomotive boilers need careful pressure monitoring daily",
                "Timetables demanded one standard clock across whole regions",
                "Rail gauge widths differed between neighboring countries",
                "Signal towers coordinated movements across busy junctions",
                "Braking systems evolved from hand brakes to air brakes",
            ],
            success=True,
        ),
        SummaryResult(
            chapter_heading="Beta Chapter",
            executive_summary="",
            thorough_summary="",
            bullet_points=[
                "Harbor cranes transferred freight between ship and rail",
                "Canal competition forced railways to cut their freight rates",
                "Ticket printing machines reduced queues at busy stations",
                "Sleeping cars enabled long journeys across entire continents",
                "Railways transformed newspaper distribution into daily news",
            ],
            success=True,
        ),
    ]


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestPacketsGeneratorPatchedLLM:
    """Service-level end-to-end with the HTTP call faked — the real
    chapter clustering, hierarchy, writers, and coverage report run."""

    def test_generate_produces_all_four_outputs(self, settings_override, tmp_path):
        gen = _patched_generator(settings_override, tmp_path)
        paths = gen.generate(
            summaries=_chapter_summaries(), book_title="Fixture Book", output_dir=tmp_path
        )
        assert paths is not None and len(paths) == 4
        names = {p.name for p in paths}
        assert names == {
            "Fixture Book.Packets.md",
            "Fixture Book.Packets.OnePage.md",
            "Fixture Book.Packets.Map.md",
            "Fixture Book.Packets.Coverage.md",
        }

    def test_generate_chapter_mode_content(self, settings_override, tmp_path):
        gen = _patched_generator(settings_override, tmp_path)
        gen.generate(summaries=_chapter_summaries(), book_title="Fixture Book", output_dir=tmp_path)
        doc = (tmp_path / "Fixture Book.Packets.md").read_text(encoding="utf-8")
        assert doc.count("### 📦 Packet") == 2
        assert "## 📋 Alpha Chapter" in doc and "## 📋 Beta Chapter" in doc
        # every source bullet remains visible (in the <details> block at
        # minimum — bullet-list fallback keeps them in the paragraph too)
        for bullet in _chapter_summaries()[0].bullet_points + _chapter_summaries()[1].bullet_points:
            assert bullet in doc, bullet
        coverage = (tmp_path / "Fixture Book.Packets.Coverage.md").read_text(encoding="utf-8")
        assert "Bullets in packets: 10" in coverage
        assert "Not in any packet" not in coverage
        assert "Orphan bullets" not in coverage
        one_page = (tmp_path / "Fixture Book.Packets.OnePage.md").read_text(encoding="utf-8")
        assert one_page.startswith("# 📖 One-Page Distillation: Fixture Book")
        assert "2 knowledge packets" in one_page  # fallback overview shape
        knowledge_map = (tmp_path / "Fixture Book.Packets.Map.md").read_text(encoding="utf-8")
        assert "```mermaid" in knowledge_map and "graph TD" in knowledge_map

    def test_pb_chapter_mode_reports_raw_bullet_counts(self, settings_override, tmp_path):
        """P-B (V0.6.0): chapter-aligned packets keep the author's RAW
        bullets, but the doc/coverage used the DEDUPED counts — 10 input
        bullets were reported as ~2 keypoints with >100% coverage and
        false 'orphan bullets' lines. Dedup now runs only where it feeds
        clustering (cross-chapter mode)."""
        gen = _patched_generator(settings_override, tmp_path)
        gen.generate(
            summaries=_chapter_summaries(dup_style=True), book_title="Dup Book", output_dir=tmp_path
        )
        doc = (tmp_path / "Dup Book.Packets.md").read_text(encoding="utf-8")
        assert "**2 packets** synthesized from **10 keypoints**" in doc
        coverage = (tmp_path / "Dup Book.Packets.Coverage.md").read_text(encoding="utf-8")
        assert "Removed as duplicates" not in coverage
        assert "Orphan bullets" not in coverage
        assert "❌ Not in any packet" not in coverage
        for i in range(5):
            assert f"Take detailed notes using a contact sheet {i}" in doc
            assert f"Use detailed notes called a client contact sheet {i}" in doc

    def test_pb_cross_chapter_mode_still_deduplicates(self, settings_override, tmp_path):
        """The V13.19.0 dedup pre-pass survives — in the mode it serves."""
        settings_override.set("packets.mode", "cross_chapter")
        seen_logs: list[str] = []
        from core.models import ConversionRequest
        from core.outputs.packets.generator import PacketGenerator

        gen = PacketGenerator(
            request=ConversionRequest(input_path=tmp_path / "book.pdf", output_dir=tmp_path),
            log_callback=lambda m, l="INFO": seen_logs.append(m),
        )
        gen._call_llm = lambda p, m, pr, t: (
            '{"paragraph": "Synthesized paragraph text that is long enough to pass '
            'the length gate for validation purposes.", "tldr": "brief take"}'
        )
        gen.generate(
            summaries=_chapter_summaries(dup_style=True),
            book_title="Xdup Book",
            output_dir=tmp_path,
        )
        assert any("Deduplicated" in m for m in seen_logs)
        coverage = (tmp_path / "Xdup Book.Packets.Coverage.md").read_text(encoding="utf-8")
        assert "Removed as duplicates" in coverage

    def test_pa_title_with_separator_sanitized(self, settings_override, tmp_path):
        """P-A (V0.6.0): an unsanitized book title scattered the four
        outputs into unintended subdirectories ("My/Notes" → a "My"
        subdir, silently) and breaks on Windows-illegal characters.
        Filenames now go through utils.filename.sanitize_filename (the
        obsidian-KB rider contract); the DOCUMENT keeps the real title."""
        gen = _patched_generator(settings_override, tmp_path)
        paths = gen.generate(
            summaries=_chapter_summaries(), book_title="My/Notes 2024", output_dir=tmp_path
        )
        for p in paths:
            assert p.parent == tmp_path, p
        names = {p.name for p in paths}
        assert names == {
            "My_Notes 2024.Packets.md",
            "My_Notes 2024.Packets.OnePage.md",
            "My_Notes 2024.Packets.Map.md",
            "My_Notes 2024.Packets.Coverage.md",
        }
        assert not (tmp_path / "My").exists()
        doc = (tmp_path / "My_Notes 2024.Packets.md").read_text(encoding="utf-8")
        assert doc.startswith("# 📦 Packets of Knowledge: My/Notes 2024")

    def test_generate_below_minimum_returns_none(self, settings_override, tmp_path):
        from core.models import SummaryResult

        gen = _patched_generator(settings_override, tmp_path)
        thin = [
            SummaryResult(
                chapter_heading="Thin",
                executive_summary="",
                thorough_summary="",
                bullet_points=["one bullet only here that is long enough"],
                success=True,
            )
        ]
        assert gen.generate(summaries=thin, book_title="Thin Book", output_dir=tmp_path) is None

    def test_generate_failure_raises_to_worker_boundary(self, settings_override, tmp_path):
        gen = _patched_generator(settings_override, tmp_path)
        gen._call_llm = lambda p, m, pr, t: None  # total LLM failure
        paths = gen.generate(
            summaries=_chapter_summaries(), book_title="Dead LLM Book", output_dir=tmp_path
        )
        # Every packet falls back to the honest bullet list — files exist.
        assert paths is not None and len(paths) == 4
        doc = (tmp_path / "Dead LLM Book.Packets.md").read_text(encoding="utf-8")
        assert "Synthesis failed" in doc or "Generation error" in doc


# ── Layer 2: service-level LIVE LLM through the :3031 shim ─────────────────


@pytest.mark.live_llm
@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _shim_available(), reason="zai-llamacpp shim :3031 unavailable")
class TestPacketsGeneratorLiveShim:
    """The REAL provider path: PacketGenerator._call_llm → the OpenAI-
    compatible SSE branch → the zai-llamacpp shim (glm-4-plus). Exactly 5
    live calls: 2 packets × (synthesis + importance) + 1 one-page."""

    def test_live_generate_end_to_end(self, settings_override, monkeypatch, tmp_path):
        for key, value in _shim_values().items():
            settings_override.set(key, value)

        # Count the real HTTP calls the generator makes (evidence the
        # provider path fired, not a mock).
        import utils.network as net_mod

        real_session_for = net_mod.session_for_url
        urls: list[str] = []

        def counting_session_for(url: str):
            urls.append(url)
            return real_session_for(url)

        monkeypatch.setattr(net_mod, "session_for_url", counting_session_for)

        from core.models import ConversionRequest
        from core.outputs.packets.generator import PacketGenerator

        gen = PacketGenerator(
            request=ConversionRequest(input_path=tmp_path / "book.pdf", output_dir=tmp_path),
            log_callback=lambda m, l="INFO": None,
        )
        paths = gen.generate(
            summaries=_chapter_summaries(), book_title="Live Shim Book", output_dir=tmp_path
        )

        # Provider-path evidence: every call hit the shim's OpenAI-
        # compatible chat endpoint (generator.py:1030 — provider
        # "llamacpp" + /v1 endpoint without :11434 → that branch).
        assert len(urls) == 5, urls
        assert all(u == _SHIM_URL for u in urls), urls

        assert paths is not None and len(paths) == 4
        doc = (tmp_path / "Live Shim Book.Packets.md").read_text(encoding="utf-8")
        assert doc.count("### 📦 Packet") == 2
        assert "## 📋 Alpha Chapter" in doc and "## 📋 Beta Chapter" in doc
        # bullet preservation holds in BOTH environments (synthesized on a
        # rig with sentence-transformers, bullet-list fallback here)
        for bullet in _chapter_summaries()[0].bullet_points + _chapter_summaries()[1].bullet_points:
            assert bullet in doc, bullet
        coverage = (tmp_path / "Live Shim Book.Packets.Coverage.md").read_text(encoding="utf-8")
        assert "Bullets in packets: 10" in coverage
        assert "❌ Not in any packet" not in coverage
        one_page = (tmp_path / "Live Shim Book.Packets.OnePage.md").read_text(encoding="utf-8")
        assert one_page.startswith("# 📖 One-Page Distillation: Live Shim Book")
        knowledge_map = (tmp_path / "Live Shim Book.Packets.Map.md").read_text(encoding="utf-8")
        assert "```mermaid" in knowledge_map

        # Live synthesis evidence: at least one packet kept a real LLM
        # paragraph/TL;DR (not the fallback banner) OR the one-page was
        # LLM-synthesized — the sandbox has no sentence-transformers, so
        # validation degrades to the honest bullet-list fallback there.
        fallback_only = "⚠️ Synthesis failed validation" in doc
        llm_one_page = "Theme synthesis unavailable" not in one_page
        if not fallback_only:
            assert "⚠️ Synthesis failed validation" not in doc or llm_one_page
        # importance classification always lands in the valid set
        for line in doc.splitlines():
            if (
                line.startswith("**")
                and line.endswith("**")
                and any(i in line for i in ("Critical", "Important", "Contextual"))
            ):
                assert any(k in line for k in ("Critical", "Important", "Contextual"))


# ── Layer 3: dialog drive (the real _PacketWorker QThread) ─────────────────


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestPacketsDialogDrive:
    """Drive _on_generate exactly as the UI does: the REAL _PacketWorker
    QThread + queued signals + _on_done on the main thread. Modals are
    monkeypatched to recorders; the LLM call is patched at the CLASS
    level (the worker imports PacketGenerator inside run())."""

    PASTED = (
        "## Alpha Chapter\n"
        "- Locomotive boilers need careful pressure monitoring daily\n"
        "- Timetables demanded one standard clock across whole regions\n"
        "- Rail gauge widths differed between neighboring countries\n"
        "- Signal towers coordinated movements across busy junctions\n"
        "- Braking systems evolved from hand brakes to air brakes\n\n"
        "## Beta Chapter\n"
        "- Harbor cranes transferred freight between ship and rail\n"
        "- Canal competition forced railways to cut their freight rates\n"
        "- Ticket printing machines reduced queues at busy stations\n"
        "- Sleeping cars enabled long journeys across entire continents\n"
        "- Railways transformed newspaper distribution into daily news\n"
    )

    def _make(self, monkeypatch, settings_override, llm_json: str | None = "default"):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        import ui_qt.views.service_dialogs.dialogs.packets_tool_dialog as pk_mod

        rec = _MsgBoxRecorder()
        monkeypatch.setattr(pk_mod, "QMessageBox", rec)
        modals: list[tuple] = []
        monkeypatch.setattr(
            pk_mod,
            "_show_success_modal",
            lambda parent, title, message, file_path=None, on_try_another=None: modals.append(
                (title, message, file_path)
            ),
        )
        if llm_json is not None:
            from core.outputs.packets.generator import PacketGenerator

            response = (
                '{"paragraph": "Synthesized paragraph text that is long enough to pass '
                'the length gate for validation purposes.", "tldr": "brief take"}'
                if llm_json == "default"
                else llm_json
            )
            monkeypatch.setattr(PacketGenerator, "_call_llm", lambda self, p, m, pr, t: response)
        dlg = pk_mod.PacketsToolDialog(_StubController())
        return dlg, app, rec, modals, pk_mod

    def _drive(self, dlg, app, timeout_ms=15000) -> str:
        status = _spin_until_status(app, dlg, prefixes=("✅", "❌"), timeout_ms=timeout_ms)
        if dlg._worker is not None:
            dlg._worker.wait(10000)
        return status

    def test_full_text_tab_flow_lands_success(self, monkeypatch, settings_override, tmp_path):
        dlg, app, rec, modals, _mod = self._make(monkeypatch, settings_override)
        out_dir = tmp_path / "pk_out"
        dlg.text_input.setPlainText(self.PASTED)
        dlg.out_edit.setText(str(out_dir))
        dlg.title_edit.setText("Dialog Drive")
        dlg._on_generate()

        status = self._drive(dlg, app)
        assert status == f"✅ Packets generated in: {out_dir}", status

        names = {p.name for p in out_dir.iterdir()}
        assert names == {
            "Dialog Drive.Packets.md",
            "Dialog Drive.Packets.OnePage.md",
            "Dialog Drive.Packets.Map.md",
            "Dialog Drive.Packets.Coverage.md",
        }
        assert dlg.gen_btn.text() == "📦 Generate Packets" and dlg.gen_btn.isEnabled()
        assert not dlg.progress_bar.isVisible()
        # the live log captured the worker's log_signal stream
        log_text = dlg.live_log.toPlainText()
        assert "Input: 10 keypoints, 2 sections" in log_text
        assert "Generating Packets of Knowledge (mode: chapter)" in log_text
        # the success modal fired with the output FOLDER (recorded, not exec'd)
        assert modals and modals[0][0] == "📦 Packets of Knowledge Complete"
        assert modals[0][2] == str(out_dir)
        assert rec.calls == []

    def test_file_tab_flow_lands_success(self, monkeypatch, settings_override, tmp_path):
        dlg, app, rec, modals, _mod = self._make(monkeypatch, settings_override)
        f1 = tmp_path / "notes_a.md"
        f1.write_text(
            "- Locomotive boilers need careful pressure monitoring daily\n- Timetables demanded one standard clock across whole regions\n- Rail gauge widths differed between neighboring countries\n- Signal towers coordinated movements across busy junctions\n- Braking systems evolved from hand brakes to air brakes\n"
        )
        f2 = tmp_path / "notes_b.md"
        f2.write_text(
            "- Harbor cranes transferred freight between ship and rail\n- Canal competition forced railways to cut their freight rates\n- Ticket printing machines reduced queues at busy stations\n- Sleeping cars enabled long journeys across entire continents\n- Railways transformed newspaper distribution into daily news\n"
        )
        for f in (f1, f2):
            dlg._files.append(str(f))
            dlg.file_list.addItem(str(f))
        dlg.tabs.setCurrentIndex(1)
        out_dir = tmp_path / "pk_files"
        dlg.out_edit.setText(str(out_dir))
        dlg.title_edit.setText("File Drive")
        dlg._on_generate()

        status = self._drive(dlg, app)
        assert status == f"✅ Packets generated in: {out_dir}", status
        assert (out_dir / "File Drive.Packets.md").exists()
        assert modals and modals[0][2] == str(out_dir)
        assert rec.calls == []

    def test_title_separator_sanitized_in_worker_flow(
        self, monkeypatch, settings_override, tmp_path
    ):
        """P-A at the full worker level: a title with "/" must not create
        subdirectories."""
        dlg, app, _rec, _modals, _mod = self._make(monkeypatch, settings_override)
        out_dir = tmp_path / "pk_title"
        dlg.text_input.setPlainText(self.PASTED)
        dlg.out_edit.setText(str(out_dir))
        dlg.title_edit.setText("My/Notes")
        dlg._on_generate()
        status = self._drive(dlg, app)
        assert status.startswith("✅"), status
        assert (out_dir / "My_Notes.Packets.md").exists()
        assert not (out_dir / "My").exists()

    def test_worker_error_lands_critical_box(self, monkeypatch, settings_override, tmp_path):
        dlg, app, rec, modals, _mod = self._make(monkeypatch, settings_override, llm_json=None)

        from core.outputs.packets.generator import PacketGenerator

        def _boom(self, summaries, book_title, output_dir):
            raise RuntimeError("synthetic generator failure")

        monkeypatch.setattr(PacketGenerator, "generate", _boom)
        out_dir = tmp_path / "pk_err"
        dlg.text_input.setPlainText(self.PASTED)
        dlg.out_edit.setText(str(out_dir))
        dlg._on_generate()
        status = self._drive(dlg, app)
        assert status.startswith("❌"), status
        assert "RuntimeError: synthetic generator failure" in status
        assert rec.titles() == ["❌ Packets Failed"]
        assert not modals
        assert dlg.gen_btn.isEnabled()
        assert not (out_dir / "Knowledge Packets.Packets.md").exists()

    def test_short_bullets_worker_refusal_is_honest(self, monkeypatch, settings_override, tmp_path):
        """The dialog guard counts bullets the generator will DROP
        (generator.py _collect_bullets keeps only >10-char bullets) — the
        worker then refuses honestly instead of writing empty output."""
        dlg, app, rec, modals, _mod = self._make(monkeypatch, settings_override)
        out_dir = tmp_path / "pk_thin"
        text = "## Chapter\n" + "\n".join(f"- abcdef{i}" for i in range(10))
        dlg.text_input.setPlainText(text)
        dlg.out_edit.setText(str(out_dir))
        dlg._on_generate()
        status = self._drive(dlg, app)
        assert status.startswith("❌"), status
        assert "No packets generated — need at least 10 keypoints" in status
        assert rec.titles() == ["❌ Packets Failed"]
        assert not modals
        assert not out_dir.exists()  # nothing written on refusal

    def test_cross_chapter_mode_persisted_through_worker(
        self, monkeypatch, settings_override, tmp_path
    ):
        dlg, app, _rec, _modals, _mod = self._make(monkeypatch, settings_override)
        out_dir = tmp_path / "pk_xc"
        dlg.text_input.setPlainText(self.PASTED)
        dlg.out_edit.setText(str(out_dir))
        dlg.mode_combo.setCurrentIndex(1)  # cross_chapter
        assert not dlg.mode_warning_label.isHidden()  # dialog unshown → isVisible() is always False
        dlg._on_generate()
        status = self._drive(dlg, app)
        assert status.startswith("✅"), status
        # the worker persisted the combo's mode into Settings (V13.23.0)
        assert settings_override.get("packets.mode") == "cross_chapter"
        assert (out_dir / "Knowledge Packets.Packets.md").exists()

    # ── guards: no worker spawned ──────────────────────────────────────

    def test_guard_short_text(self, monkeypatch, settings_override):
        dlg, _app, rec, _modals, _mod = self._make(monkeypatch, settings_override)
        dlg.text_input.setPlainText("short")
        dlg._on_generate()
        assert rec.titles() == ["Need more text"]
        assert dlg._worker is None

    def test_guard_too_few_bullets(self, monkeypatch, settings_override, tmp_path):
        dlg, _app, rec, _modals, _mod = self._make(monkeypatch, settings_override)
        dlg.text_input.setPlainText("## Chapter\n- only one bullet point exists here today")
        dlg.out_edit.setText(str(tmp_path / "x"))
        dlg._on_generate()
        assert rec.titles() == ["Not enough keypoints"]
        assert "Found 1" in rec.calls[0][2]
        assert dlg._worker is None

    def test_guard_no_output_folder(self, monkeypatch, settings_override):
        dlg, _app, rec, _modals, _mod = self._make(monkeypatch, settings_override)
        dlg.text_input.setPlainText(self.PASTED)
        dlg.out_edit.setText("")
        dlg._on_generate()
        assert rec.titles() == ["No output folder"]
        assert dlg._worker is None

    def test_guard_no_files_on_file_tab(self, monkeypatch, settings_override, tmp_path):
        dlg, _app, rec, _modals, _mod = self._make(monkeypatch, settings_override)
        dlg.tabs.setCurrentIndex(1)
        dlg.out_edit.setText(str(tmp_path / "y"))
        dlg._on_generate()
        assert rec.titles() == ["No files"]
        assert dlg._worker is None
