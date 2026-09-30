"""V18.5 (Phase 3) — Prompt lowbit-selection + front-matter versioning tests.

Tests two Phase 3 mechanisms:

1. **_select_prompt()** (Task 3.3) — for low-bit quant models, selects the
   ``_lowbit`` prompt variant when it exists; falls back to the base name
   for full-precision models or when no variant exists.

2. **Prompt front-matter** (Task 3.5) — ``_parse_frontmatter`` extracts
   ``version:`` + ``compatible_model_class:`` from the YAML front-matter;
   ``render_template`` strips it before rendering (the LLM never sees it)
   and logs the resolved version on first render.

Uses ``importlib`` to load prompt_manager.py directly (bypasses the heavy
``core.summarisation.__init__`` which imports tiktoken).

Run: ``pytest tests/test_prompt_frontmatter.py -v``
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Load prompt_manager.py directly (bypasses core.summarisation.__init__)
_spec = importlib.util.spec_from_file_location(
    "pm_v18_5_test",
    _project_root / "core" / "summarisation" / "prompt_manager.py",
)
_pm_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _pm_mod
_spec.loader.exec_module(_pm_mod)

PromptManager = _pm_mod.PromptManager


@pytest.fixture
def pm():
    return PromptManager()


# ── 1. _parse_frontmatter ──────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_parses_frontmatter_with_quotes(self, pm):
        """version: "18.5.0" → strips quotes → '18.5.0'."""
        template = (
            '---\nversion: "18.5.0"\ncompatible_model_class: "low_bit_quant"\n---\n\n### BODY ###'
        )
        fm, body = pm._parse_frontmatter(template)
        assert fm["version"] == "18.5.0"
        assert fm["compatible_model_class"] == "low_bit_quant"
        assert body.startswith("### BODY ###")

    def test_parses_frontmatter_without_quotes(self, pm):
        """version: 18.5.0 (no quotes) → '18.5.0'."""
        template = "---\nversion: 18.5.0\n---\n\nBody here."
        fm, body = pm._parse_frontmatter(template)
        assert fm["version"] == "18.5.0"
        assert body.startswith("Body here.")

    def test_no_frontmatter_returns_empty_dict(self, pm):
        """A template without front-matter → ({}, template_unchanged)."""
        template = "### ROLE ###\nNo front-matter here."
        fm, body = pm._parse_frontmatter(template)
        assert fm == {}
        assert body == template

    def test_frontmatter_stripped_from_body(self, pm):
        """The body must NOT contain the --- delimiters."""
        template = '---\nversion: "1.0"\n---\n\nActual content.'
        _, body = pm._parse_frontmatter(template)
        assert "---" not in body
        assert "version" not in body

    def test_comment_lines_ignored(self, pm):
        """Lines starting with # inside front-matter are ignored."""
        template = '---\n# This is a comment\nversion: "2.0"\n---\n\nBody.'
        fm, body = pm._parse_frontmatter(template)
        assert fm == {"version": "2.0"}
        assert body.startswith("Body.")

    def test_real_default_lowbit_has_frontmatter(self, pm):
        """The default_lowbit.md file has front-matter with version + low_bit_quant."""
        tpl = pm.load_prompt("default_lowbit")
        assert tpl is not None, "default_lowbit.md must exist at prompts/default_lowbit.md"
        fm, body = pm._parse_frontmatter(tpl)
        assert fm.get("version") is not None, "must have a version"
        assert fm.get("compatible_model_class") == "low_bit_quant"
        assert body.startswith("### ROLE ###"), "body should start with the ROLE section"


# ── 2. render_template strips front-matter ────────────────────────────────


class TestRenderStripsFrontmatter:
    def test_rendered_prompt_has_no_frontmatter(self, pm):
        """render_template must strip front-matter before returning."""
        rendered = pm.render_template(
            "default_lowbit",
            heading="Test",
            text="content",
            language="",
        )
        assert rendered is not None
        assert not rendered.startswith("---"), "rendered prompt must not start with ---"
        assert "compatible_model_class" not in rendered, "front-matter key must not leak"

    def test_rendered_prompt_has_no_version_key(self, pm):
        """The 'version:' key must not appear in the rendered output."""
        rendered = pm.render_template(
            "summarisation/bullet_consolidation_lowbit",
            bullets="- bullet 1\n- bullet 2",
        )
        assert rendered is not None
        assert (
            "version:" not in rendered.lower() or "version" not in rendered.split("\n")[0].lower()
        )

    def test_render_without_frontmatter_still_works(self, pm):
        """Prompts without front-matter render normally (no regression)."""
        rendered = pm.render_template(
            "summarisation/bullet_consolidation",
            bullets="- test bullet",
        )
        assert rendered is not None
        assert "### ROLE ###" in rendered or "ROLE" in rendered


# ── 3. _select_prompt (lowbit variant selection) ──────────────────────────


class TestSelectPrompt:
    """Tests the _select_prompt helper that picks the _lowbit variant.

    Uses a lightweight stub for Summarizer (avoids the heavy __init__ which
    needs tiktoken/torch). The helper only needs: primary_model,
    prompt_manager, and log.
    """

    def _make_stub(self, model_name, pm):
        """Create a minimal Summarizer-like object with _select_prompt."""

        # _select_prompt is a method on Summarizer; we can call it unbound
        # with a simple object that has the needed attributes.
        class _Stub:
            primary_model = model_name
            prompt_manager = pm

            def log(self, msg, level="INFO"):
                pass

        return _Stub()

    def test_non_lowbit_model_returns_base_name(self, pm):
        """Full-precision model → base name unchanged."""
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("gemma2:9b", pm)
        # Use the REAL active_prompt value ("default", root-level) — not
        # "summarisation/default" (which doesn't exist as a file).
        name = Summarizer._select_prompt(stub, "default")
        assert name == "default"

    def test_lowbit_model_returns_lowbit_variant(self, pm):
        """IQ2_S model → _lowbit variant selected (when it exists).

        V18.5.1 regression guard: this test uses the REAL active_prompt value
        ("default", root-level) — NOT "summarisation/default". The
        default_lowbit.md file lives at prompts/default_lowbit.md (root),
        matching prompts/default.md. A previous version of this test used
        "summarisation/default" which tested a non-existent path and masked
        a real bug where the main summary prompt's lowbit variant was never
        selected.
        """
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest", pm)
        name = Summarizer._select_prompt(stub, "default")
        assert name == "default_lowbit", (
            f"expected 'default_lowbit', got '{name}' — the main summary "
            f"prompt's lowbit variant must be found at prompts/default_lowbit.md"
        )

    def test_lowbit_model_falls_back_when_no_variant(self, pm):
        """IQ2_S model + base prompt without _lowbit variant → base name."""
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest", pm)
        # content_judge has no _lowbit variant
        name = Summarizer._select_prompt(stub, "summarisation/content_judge")
        assert name == "summarisation/content_judge"

    def test_additive_sections_lowbit_selected(self, pm):
        """IQ2_S model → additive_sections_lowbit selected."""
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest", pm)
        name = Summarizer._select_prompt(stub, "summarisation/additive_sections")
        assert name == "summarisation/additive_sections_lowbit"

    def test_thematic_synthesis_lowbit_selected(self, pm):
        """IQ2_S model → thematic_synthesis_lowbit selected."""
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest", pm)
        name = Summarizer._select_prompt(stub, "summarisation/thematic_synthesis")
        assert name == "summarisation/thematic_synthesis_lowbit"

    def test_bullet_consolidation_lowbit_selected(self, pm):
        """IQ2_S model → bullet_consolidation_lowbit selected (V18.2.44 prompt)."""
        from core.summarisation.summarizer import Summarizer

        stub = self._make_stub("Qwen3.8-27B-UD-IQ2_S-Instruct-Vision:latest", pm)
        name = Summarizer._select_prompt(stub, "summarisation/bullet_consolidation")
        assert name == "summarisation/bullet_consolidation_lowbit"


# ── 4. All _lowbit prompt variants exist ──────────────────────────────────


class TestLowbitVariantsExist:
    """Verify the Phase 3 _lowbit prompt files exist and are non-empty."""

    @pytest.mark.parametrize(
        "name",
        [
            "default_lowbit",
            "summarisation/additive_sections_lowbit",
            "summarisation/thematic_synthesis_lowbit",
            "summarisation/bullet_consolidation_lowbit",
        ],
    )
    def test_lowbit_variant_exists_and_has_content(self, pm, name):
        """Each _lowbit variant must exist and be > 100 chars."""
        tpl = pm.load_prompt(name)
        assert tpl is not None, f"{name}.md must exist"
        assert len(tpl) > 100, f"{name}.md is suspiciously short ({len(tpl)} chars)"

    @pytest.mark.parametrize(
        "name",
        [
            "default_lowbit",
            "summarisation/additive_sections_lowbit",
            "summarisation/thematic_synthesis_lowbit",
        ],
    )
    def test_lowbit_variant_has_forbidden_section(self, pm, name):
        """Each new _lowbit variant must have a ### FORBIDDEN ### section.

        This is the canonical pattern from bullet_consolidation_lowbit.md —
        the explicit FORBIDDEN section names the leak patterns ("Bullet 1",
        "KEEP BOTH") so the model learns to avoid them by pattern-matching.
        """
        tpl = pm.load_prompt(name)
        assert "FORBIDDEN" in tpl.upper(), f"{name}.md must have a FORBIDDEN section"

    @pytest.mark.parametrize(
        "name",
        [
            "default_lowbit",
            "summarisation/additive_sections_lowbit",
            "summarisation/thematic_synthesis_lowbit",
            "summarisation/bullet_consolidation_lowbit",
        ],
    )
    def test_lowbit_variant_has_frontmatter(self, pm, name):
        """Each _lowbit variant must have YAML front-matter with version + class."""
        tpl = pm.load_prompt(name)
        fm, _ = pm._parse_frontmatter(tpl)
        assert fm.get("version"), f"{name}.md must have a version in front-matter"
        assert fm.get("compatible_model_class") == "low_bit_quant", (
            f"{name}.md must have compatible_model_class=low_bit_quant"
        )
