"""V0.7.2 (wizard rework ④, item 4c — D9) — the emoji→icons sweep.

The audit §W6 inventory (labels/buttons only; log lines keep their emoji
by D9's explicit carve-out): the 10 Step-4 checkbox prefixes (gone with
the category-card rework), `🏠/☁️/🔄/🔌/📝` through Step 5, `📝` in Step
6, the `🦙` embed item (step7b), the Review section headers + `🚀` Start
(step8). V0.7.0/V0.7.1 already cleaned the Step-2 TOC button and the
nav/Start chrome — this file pins that nothing regressed and that the
new professional glyphs landed.

Scope note (the session contract): Step 9's live status prefixes and
Step 1's detector banner are display/status text outside this phase's
Steps 4-8 + Review/Start scope; status-feedback labels (✅/❌/⚠️/🔒
warnings inside Step 5/7b tooltips and validation hints) are the same
class and stay.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEPS = _project_root / "ui_qt" / "views" / "wizard_steps"
_STEP5 = _STEPS / "step5_models.py"
_STEP6 = _STEPS / "step6_translation.py"
_STEP7B = _STEPS / "step7b_fine_tune.py"
_STEP8 = _STEPS / "step8_review.py"
_ICONS = _project_root / "ui_qt" / "components" / "icons.py"

# The §W6 inventory emoji for Steps 2-8 controls.
_INVENTORY_EMOJI = [
    "🏠",
    "☁",
    "🔄",
    "🔌",
    "📝",
    "🦙",
    "🚀",
    "📄",
    "📐",
    "🔍",
    "📤",
    "🤖",
    "🌐",
    "⚙",
    "🔧",
    "📦",
    "📡",
    "❓",
    "📖",
    "📋",
    "🗺",
    "📚",
    "💬",
]

# Control-label surface: constructor calls + setText + addItem lines.
_CONTROL_LINE = re.compile(
    r"QPushButton\(|QGroupBox\(|QCheckBox\(|\.addItem\(|\.setText\(|QRadioButton\("
)


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _control_lines(path: Path) -> list[str]:
    return [ln for ln in _src(path).splitlines() if _CONTROL_LINE.search(ln)]


# ═══════════════════════════════════════════════════════════════════════════
# The emoji purge pins (per file, per §W6 inventory item)
# ═══════════════════════════════════════════════════════════════════════════


class TestStep5Purge:
    def test_arch_combo_items_plain(self):
        src = _src(_STEP5)
        assert 'addItem("Local model (on your GPU)", "local")' in src
        assert 'addItem("Cloud API model", "cloud")' in src
        assert "🏠" not in src.split("def _build", 1)[0] + "".join(_control_lines(_STEP5))

    def test_group_box_titles_plain(self):
        src = _src(_STEP5)
        assert 'QGroupBox("Local configuration")' in src
        assert 'QGroupBox("Cloud API configuration (the model)")' in src

    def test_refresh_button_gets_the_icon(self):
        src = _src(_STEP5)
        assert 'QPushButton("Refresh models")' in src
        assert 'setIcon(icon("refresh"' in src, "the professional glyph (D9)"
        assert "🔄 Refresh" not in src

    def test_test_connection_button_gets_the_plug(self):
        src = _src(_STEP5)
        assert 'QPushButton("Test connection")' in src
        assert 'setIcon(icon("plug"' in src
        assert "🔌" not in "".join(_control_lines(_STEP5))

    def test_model_combo_items_plain(self):
        src = _src(_STEP5)
        assert "combo.addItem(m, m)" in src
        assert '"📝 "' not in src

    def test_no_inventory_emoji_on_control_lines(self):
        for ln in _control_lines(_STEP5):
            for emo in _INVENTORY_EMOJI:
                assert emo not in ln, f"control label still carries {emo}: {ln.strip()}"


class TestStep6Purge:
    def test_backend_combo_plain(self):
        src = _src(_STEP6)
        assert 'addItem("Ollama LLM (TranslateGemma)", "ollama")' in src
        assert "addItem(m, m)" in src
        assert '"📝 "' not in src

    def test_no_inventory_emoji_on_control_lines(self):
        for ln in _control_lines(_STEP6):
            for emo in _INVENTORY_EMOJI:
                assert emo not in ln, f"control label still carries {emo}: {ln.strip()}"


class TestStep7bPurge:
    def test_embed_item_plain(self):
        src = _src(_STEP7B)
        assert '"nomic-embed-text (274 MB — via Ollama' in src
        assert "🦙" not in "".join(_control_lines(_STEP7B))

    def test_no_inventory_emoji_on_control_lines(self):
        for ln in _control_lines(_STEP7B):
            for emo in _INVENTORY_EMOJI:
                assert emo not in ln, f"control label still carries {emo}: {ln.strip()}"


class TestStep8Purge:
    def test_start_button_rocket_icon(self):
        src = _src(_STEP8)
        assert 'QPushButton("Start Conversion")' in src
        assert 'setIcon(icon("rocket"' in src, "the professional glyph (D9)"
        # The tint rides the palette's on-accent token (the V0.7.1 lesson).
        assert "text_on_accent" in src.split('setIcon(icon("rocket"', 1)[1].split(")", 1)[0]
        assert "🚀" not in src

    def test_review_section_headers_plain(self):
        src = _src(_STEP8)
        for header in (
            "<b>PDF & Document</b>",
            "<b>Page Range</b>",
            "<b>OCR</b>",
            "<b>Outputs</b>",
            "<b>Models</b>",
            "<b>Translation</b>",
            "<b>Advanced</b>",
            "<b>Fine-tuning</b>",
        ):
            assert header in src, f"the plain section header {header!r} is missing"
        for emo in ("📄", "📐", "🔍", "📤", "🤖", "🌐", "⚙", "🔧"):
            assert emo not in src, f"emoji {emo} back in the review summary"

    def test_warning_label_plain(self):
        src = _src(_STEP8)
        assert '"Conversion is resource and time intensive.' in src
        assert "⚠️ Conversion" not in src


# ═══════════════════════════════════════════════════════════════════════════
# No-regression pins: the earlier phases' cleanups stay clean
# ═══════════════════════════════════════════════════════════════════════════


class TestEarlierCleanupsHold:
    def test_step2_toc_button_stays_clean(self):
        src = (_STEPS / "step2_range.py").read_text(encoding="utf-8")
        assert "🔍 Detect" not in src, "V0.7.1's TOC-button cleanup regressed"
        assert 'pixmap("list-checks"' in src

    def test_wizard_view_settext_lines_stay_clean(self):
        src = (_project_root / "ui_qt" / "views" / "wizard_view.py").read_text("utf-8")
        settext_lines = [ln for ln in src.splitlines() if ".setText(" in ln]
        for ln in settext_lines:
            assert "🚀" not in ln, f"control label still carries an emoji: {ln.strip()}"


# ═══════════════════════════════════════════════════════════════════════════
# The icon-set render check (needs PySide6)
# ═══════════════════════════════════════════════════════════════════════════


def _qt_or_skip():
    return pytest.importorskip("PySide6.QtWidgets")


class TestIconSetRenderCheck:
    @pytest.fixture(scope="class")
    def app(self):
        QtWidgets = _qt_or_skip()
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_every_glyph_renders_non_trivially(self, app, tmp_path):
        """Every key in ICONS renders to a non-null, non-blank pixmap at
        the sizes the wizard uses (the new V0.7.2 glyphs included — a
        malformed path would render empty)."""
        from ui_qt.components.icons import ICONS, pixmap

        assert len(ICONS) >= 60, "the set should carry the V0.7.2 additions"
        for name in ICONS:
            for size in (16, 20):
                pm = pixmap(name, color="#333333", size=size)
                assert not pm.isNull(), f"{name}: null pixmap at {size}px"
                assert pm.width() == size and pm.height() == size
                # A blank render (all-transparent) means broken path data.
                img = pm.toImage()
                assert img.pixelColor(size // 2, size // 2).alpha() > 0 or any(
                    img.pixelColor(x, y).alpha() > 0
                    for x in range(0, size, max(1, size // 8))
                    for y in range(0, size, max(1, size // 8))
                ), f"{name}: renders fully transparent (broken glyph)"

    def test_new_glyphs_render_distinctly(self, app):
        """The nine new glyphs produce non-identical pixmaps (each path
        data is real, not a copy-paste stub)."""
        from ui_qt.components.icons import pixmap

        names = [
            "package",
            "link",
            "graduation-cap",
            "network",
            "map",
            "help-circle",
            "book-open",
            "minimize-2",
            "plug",
        ]
        sigs = {}
        for n in names:
            pm = pixmap(n, color="#333333", size=24)
            sigs[n] = pm.toImage().cacheKey()
        assert len(set(sigs.values())) == len(names), "two glyphs render identically"

    def test_registry_icons_all_render(self, app):
        """Every OutputSpec.icon_name in the registry is a renderable key
        (the Step-4 cards consume them directly)."""
        from core.outputs.registry import OUTPUT_REGISTRY
        from ui_qt.components.icons import ICONS, pixmap

        for spec in OUTPUT_REGISTRY:
            assert spec.icon_name in ICONS, (
                f"{spec.key}: icon_name {spec.icon_name!r} missing from icons.py"
            )
            pm = pixmap(spec.icon_name, color="#333333", size=16)
            assert not pm.isNull(), f"{spec.key}: glyph fails to render"
