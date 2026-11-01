"""M2 (UI/UX redesign) — dashboard structure pins (hermetic source pins).

THE SCOPE: the M2 dashboard build per docs/M0_NEXT_SESSION_PROMPT.md —
the fixed sidebar shell + QStackedWidget, the hero home view, the Quick
Tools grid, the experimental four behind the About & System fallback
(decision Q2), the header reduction (decisions Q3/Q7 + the documented
Merge choice), and the ``_switch_to_tab`` → ``switch_to_page``
navigation facade.

THE PINS (all hermetic — AST/source parsing, no Qt import: the house
no-Qt-on-CI pattern from tests/test_m1_theme_tokens.py; the headless
sandbox lacks libEGL.so.1 so widget-instantiating tests cannot run
there. The behavioural net for the new shell already exists — the
internal-tabs / tool e2e / controller-mapping suites exercise the views
themselves on a real Qt):

  1. Sidebar IA (decision Q1): exact groups + labels, the Audio group
     IN, every label cross-checked against the TOOL_CARDS titles.
  2. Experimental four (decision Q2): absent from the sidebar nav data;
     view modules + convert_view keys + the About&System fallback rows
     all intact (hidden ≠ removed).
  3. The hero (decision Q7): present, ONE "Start Conversion" CTA that
     reuses the window's ``_open_wizard`` (no forked opening logic),
     and NO Full Conversion tile in the Quick Tools data.
  4. The header: wizard button gone, the LLM lights mini-locked
     (decision Q3), Merge kept (the documented choice).
  5. The navigation facade: ``_switch_to_tab`` preserved and backed by
     the window's ``switch_to_page``; queue-badge + quarantine-reload
     hooks preserved on the stack signal; DnD still lands in the queue
     AND opens its page.

Run: pytest tests/test_m2_dashboard.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_SIDEBAR = _project_root / "ui_qt" / "components" / "sidebar.py"
_HOME = _project_root / "ui_qt" / "views" / "home_view.py"
_APP = _project_root / "ui_qt" / "app.py"
_CONVERT = _project_root / "ui_qt" / "views" / "convert_view.py"
_ABOUT = _project_root / "ui_qt" / "views" / "about_system_dialog.py"
_TOOLDASH = _project_root / "ui_qt" / "views" / "tool_dashboard.py"
_VIEWS = _project_root / "ui_qt" / "views"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments (house pattern)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


def _module_const(module: Path, name: str):
    """AST-extract a module-level constant (plain OR annotated assignment)."""
    tree = ast.parse(_src(module))
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if getattr(target, "id", "") == name:
                return ast.literal_eval(node.value)  # type: ignore[union-attr]
    raise AssertionError(f"module constant {name!r} not found in {module.name}")


# The nav data of the fixed rail (single source of truth for the IA).
_NAV_GROUPS = _module_const(_SIDEBAR, "NAV_GROUPS")
_NAV_FOOTER = _module_const(_SIDEBAR, "NAV_FOOTER")
_NAV_KEYS = [k for _g, items in _NAV_GROUPS for k, _i, _l in items] + [
    k for k, _i, _l in _NAV_FOOTER
]
_NAV_LABELS = {k: lbl for _g, items in _NAV_GROUPS for k, _i, lbl in items}

# The tool-card data (single source of truth for exact user-facing titles).
_TOOL_TITLES = {entry[0]: entry[1] for entry in _module_const(_TOOLDASH, "TOOL_CARDS")}


# ════════════════════════════════════════════════════════════════════════════
# 1. Sidebar IA (decision Q1)
# ════════════════════════════════════════════════════════════════════════════


class TestSidebarIAPin:
    def test_exact_groups_and_labels(self):
        assert [g for g, _items in _NAV_GROUPS] == [None, "Processing", "Utilities", "Audio"]
        assert [lbl for _k, _i, lbl in _NAV_GROUPS[0][1]] == ["Home"]
        assert [lbl for _k, _i, lbl in _NAV_GROUPS[1][1]] == [
            "Summarization",
            "Document → Markdown",
            "Translation",
        ]
        assert [lbl for _k, _i, lbl in _NAV_GROUPS[2][1]] == [
            "Markdown Styler",
            "Packets of Knowledge",
            "OCR Service",
            "PDF/DOCX Cutter",
            "Image Extractor",
        ]
        # decision Q1: the Audio group is IN (TTS, Podcast, Transcribe).
        assert [lbl for _k, _i, lbl in _NAV_GROUPS[3][1]] == [
            "TTS Service",
            "Podcast Maker",
            "Transcribe Service",
        ]
        assert [lbl for _k, _i, lbl in _NAV_FOOTER] == ["Settings", "About"]

    def test_every_tool_label_is_the_exact_toolcards_title(self):
        """No renames: every sidebar tool label equals its TOOL_CARDS title
        (the M2 prompt: 'exact user-facing names only')."""
        for key, label in _NAV_LABELS.items():
            if key in _TOOL_TITLES:  # Home/Settings/About are not tool cards
                assert _TOOL_TITLES[key] == label, f"{key}: {label!r} != TOOL_CARDS title"

    def test_sidebar_glyphs_exist_in_the_icon_set(self):
        """Every nav glyph is a real icons.py entry (no emoji, spec §7)."""
        icons = _module_const(_project_root / "ui_qt" / "components" / "icons.py", "ICONS")
        for _g, items in _NAV_GROUPS:
            for _k, glyph, _l in items:
                assert glyph in icons, f"unknown sidebar glyph: {glyph!r}"
        for _k, glyph, _l in _NAV_FOOTER:
            assert glyph in icons, f"unknown footer glyph: {glyph!r}"


# ════════════════════════════════════════════════════════════════════════════
# 2. The experimental four stay functional, just unlisted (decision Q2)
# ════════════════════════════════════════════════════════════════════════════


class TestExperimentalFour:
    _EXPERIMENTAL = ("batch_queue", "output_scanner", "quarantine", "hallucination_audit")

    def test_absent_from_sidebar_nav_data(self):
        for key in self._EXPERIMENTAL:
            assert key not in _NAV_KEYS, f"{key} must not be in primary navigation"
        # the pin anchor: sidebar.py documents the deliberate absence
        assert '"batch_queue", "output_scanner", "quarantine", "hallucination_audit"' in _src(
            _SIDEBAR
        )

    def test_view_modules_and_routing_keys_intact(self):
        """Hidden ≠ removed: the three view modules exist and every legacy
        convert_view routing key still resolves."""
        for fname in ("queue_view.py", "output_scanner_view.py", "quarantine_view.py"):
            assert (_VIEWS / fname).exists(), f"{fname} removed (must stay)"
        convert = _strip_comments(_src(_CONVERT))
        for key in ("output_scanner", "batch_queue", "hallucination_audit", "quarantine"):
            assert f'"{key}"' in convert, f"convert_view key {key!r} lost"
        # the hallucination audit dialog class stays reachable
        assert "HallucinationAuditDialog" in convert

    def test_about_system_fallback_rows(self):
        about = _strip_comments(_src(_ABOUT))
        assert '"Experimental tools"' in about
        assert "open_page = Signal(str)" in about
        for key, label in (
            ("queue", "Queue"),
            ("output_scanner", "Output Scanner"),
            ("quarantine", "Bullet Audit"),
            ("hallucination_audit", "Hallucination Audit"),
        ):
            assert f'("{key}"' in about, f"fallback row for {key} missing"
            assert f'"{label}"' in about, f"fallback label {label!r} missing"

    def test_window_connects_the_fallback_to_the_facade(self):
        app = _strip_comments(_src(_APP))
        assert "dlg.open_page.connect(self.switch_to_page)" in app


# ════════════════════════════════════════════════════════════════════════════
# 3. The hero (decision Q7)
# ════════════════════════════════════════════════════════════════════════════


class TestHero:
    def test_single_start_conversion_cta_reusing_the_wizard_entry(self):
        code = _strip_comments(_src(_HOME))
        assert code.count('QPushButton("Start Conversion")') == 1, "exactly one hero CTA"
        assert 'setObjectName("HeroPrimary")' in code
        # the view only EMITS — the opening logic is never forked into it
        assert "start_requested = Signal()" in code
        assert "from ui_qt.views.wizard_view import WizardView" not in code, (
            "home_view must not construct the wizard itself (route via the window)"
        )

    def test_window_routes_the_cta_to_the_existing_open_wizard(self):
        app = _strip_comments(_src(_APP))
        assert "self.home_view.start_requested.connect(self._open_wizard)" in app

    def test_no_full_conversion_tile_in_quick_tools(self):
        groups = _module_const(_HOME, "_QUICK_GROUPS")
        quick_keys = [k for _g, keys in groups for k in keys]
        assert "full_conversion" not in quick_keys, "the hero must not be duplicated as a tile"
        # …while the TOOL_CARDS data itself is untouched (the legacy convert
        # page still renders its full dashboard from it)
        assert "full_conversion" in _TOOL_TITLES

    def test_quick_tools_labels_match_toolcards(self):
        groups = _module_const(_HOME, "_QUICK_GROUPS")
        for _group, keys in groups:
            for key in keys:
                assert key in _TOOL_TITLES, f"{key} is not a TOOL_CARDS tool"
        assert sorted(k for _g, ks in groups for k in ks) == sorted(
            set(_TOOL_TITLES) - {"full_conversion"}
        ), "Quick Tools must be exactly TOOL_CARDS minus full_conversion"


# ════════════════════════════════════════════════════════════════════════════
# 4. The header (decisions Q3 + Q7 + the Merge choice)
# ════════════════════════════════════════════════════════════════════════════


class TestHeaderReduction:
    def test_wizard_button_gone(self):
        code = _strip_comments(_src(_APP))
        assert "wizard_btn" not in code, "decision Q7: the header wizard button is removed"

    def test_llm_lights_locked_to_mini(self):
        code = _strip_comments(_src(_APP))
        assert "set_budget(0)" in code, "the header lights must be mini-locked (decision Q3)"
        # the full lights live in About & System, fed by the same poll loop
        about = _strip_comments(_src(_ABOUT))
        assert "build_status_lights" in about
        assert "apply_llm_statuses" in code, "the poll loop must feed both sinks"

    def test_merge_kept_in_header(self):
        """The documented Merge decision: the compact header link stays (a
        real cross-output action; keeps the W-b12 threading pins green)."""
        code = _strip_comments(_src(_APP))
        assert 'QPushButton("📚  Merge")' in code
        assert "_open_merge_dialog" in code


# ════════════════════════════════════════════════════════════════════════════
# 5. The navigation facade + preserved page hooks
# ════════════════════════════════════════════════════════════════════════════


class TestNavigationFacade:
    def test_convert_view_facade(self):
        code = _strip_comments(_src(_CONVERT))
        assert "def _switch_to_tab(self, tab_name: str) -> None:" in code
        assert "switch_to_page" in code, "the facade must route through the window"
        assert "tab_widget" not in code, "the old QTabWidget walk must be gone"

    def test_window_facade_and_stack_pages(self):
        code = _strip_comments(_src(_APP))
        assert "def switch_to_page(self, key: str) -> bool:" in code
        for key in ("home", "convert", "queue", "output_scanner", "quarantine", "hallucination_audit"):
            assert f'_add_page("{key}"' in code, f"stack page {key!r} not registered"

    def test_page_open_hooks_preserved(self):
        """The _on_tab_changed equivalents must keep firing on page switches."""
        code = _strip_comments(_src(_APP))
        assert "currentChanged.connect(self._on_page_changed)" in code
        assert "self.queue_view.refresh()" in code  # V4.3.0 queue badge
        assert "self.quarantine_view._reload()" in code  # V10.28.0 auto-reload
        assert "self.quarantine_view._auto_detect()" in code

    def test_dnd_lands_in_queue_and_opens_its_page(self):
        code = _strip_comments(_src(_APP))
        assert "handle_dropped_files" in code
        assert 'self.switch_to_page("queue")' in code

    def test_theme_toggle_covers_the_m2_surfaces(self):
        code = _strip_comments(_src(_APP))
        assert "self.home_view.refresh_theme()" in code
        assert "self.sidebar.refresh_theme()" in code


# ════════════════════════════════════════════════════════════════════════════
# 6. Token cleanliness of the new surfaces (the M1 census extended to M2)
# ════════════════════════════════════════════════════════════════════════════


class TestM2TokenCleanliness:
    def test_new_surfaces_carry_zero_colour_literals(self):
        hex_re = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
        rgba_re = re.compile(r"rgba?\(\s*\d")
        for path in (_SIDEBAR, _HOME):
            code = _strip_comments(_src(path))
            for i, line in enumerate(code.splitlines(), 1):
                assert not (hex_re.search(line) or rgba_re.search(line)), (
                    f"{path.name}:{i} carries a colour literal (use theme tokens)"
                )

    def test_sidebar_rail_qss_rule_exists(self):
        code = _strip_comments(_src(_project_root / "ui_qt" / "theme.py"))
        assert "QFrame#SidebarRail" in code
