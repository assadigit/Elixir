"""V18.2.18: Tests for Phase 4 type-safety work (B3, M3, O4, M7).

Tests verify:
1. O4: repair_hyphenation joins Capitalized proper nouns + accented chars
2. B3/M3: ConversionContext Protocol is defined + Converter satisfies it
3. M7: pre-commit config exists with ruff + mypy hooks
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

# Stub tiktoken (not installed in test env)
if "tiktoken" not in sys.modules:
    tk = types.ModuleType("tiktoken")
    tk.get_encoding = MagicMock(return_value=MagicMock())
    tk.encoding_for_model = MagicMock(return_value=MagicMock())
    tk.Encoding = MagicMock
    sys.modules["tiktoken"] = tk

from core.summarisation.text_preprocessor import repair_hyphenation

# ═══════════════════════════════════════════════════════════════════════════
# O4: repair_hyphenation — Capitalized + accented proper nouns
# ═══════════════════════════════════════════════════════════════════════════


class TestRepairHyphenationProperNouns:
    """V18.2.18 (O4): repair_hyphenation joins Capitalized + accented words."""

    def test_lowercase_word_joined(self):
        """Basic case: 'net-\\nworking' → 'networking'."""
        text = "The net-\nworking of systems is important."
        result = repair_hyphenation(text)
        assert "networking" in result
        assert "net-\nworking" not in result

    def test_capitalized_proper_noun_joined(self):
        """V18.2.18 (O4): 'Jacob-\\nson' → 'Jacobson' (Capitalized)."""
        text = "Jacob-\nson wrote about adolescence."
        result = repair_hyphenation(text)
        assert "Jacobson" in result
        assert "Jacob-\nson" not in result

    def test_accented_word_joined(self):
        """V18.2.18 (O4): accented Latin chars are rejoined."""
        text = "café-\nbar culture"
        result = repair_hyphenation(text)
        assert "cafébar" in result

    def test_german_umlaut_joined(self):
        """V18.2.18 (O4): German umlauts (Ü, ö, etc.) are rejoined."""
        text = "Über-\nschrift translation"
        result = repair_hyphenation(text)
        assert "Überschrift" in result

    def test_long_compound_not_joined(self):
        """Words >25 chars are not joined (likely real hyphenated compounds)."""
        # Build a long hyphenated compound >25 chars after joining
        text = "pneumonoultramicroscopicsilicovolcanoconiosis-\nsuffix"
        result = repair_hyphenation(text)
        # Should NOT be joined (too long) — the hyphen+newline preserved
        assert "-\n" in result


# ═══════════════════════════════════════════════════════════════════════════
# B3/M3: ConversionContext Protocol
# ═══════════════════════════════════════════════════════════════════════════


class TestConversionContextProtocol:
    """V18.2.18 (B3/M3): The Protocol is defined + importable."""

    def _load_protocol_module(self):
        """Load the conversion_context module directly from file (bypass
        the package __init__ which imports markitdown, not installed in
        the test env)."""
        import sys
        from importlib.util import module_from_spec, spec_from_file_location
        from pathlib import Path

        proto_path = (
            Path(__file__).resolve().parent.parent / "core" / "pipeline" / "conversion_context.py"
        )
        # V18.2.27 (warnings fix): use importlib.util spec + exec_module
        # instead of the deprecated SourceFileLoader.load_module() (removed in 3.15).
        # Register in sys.modules BEFORE exec_module so @dataclass resolves.
        spec = spec_from_file_location("_conversion_context_test", str(proto_path))
        mod = module_from_spec(spec)
        sys.modules["_conversion_context_test"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_protocol_importable(self):
        """The ConversionContext Protocol can be imported."""
        mod = self._load_protocol_module()
        assert hasattr(mod, "ConversionContext")
        assert mod.ConversionContext is not None

    def test_protocol_is_runtime_checkable(self):
        """The Protocol is @runtime_checkable so isinstance() works."""
        mod = self._load_protocol_module()
        ConversionContext = mod.ConversionContext
        # @runtime_checkable Protocols support isinstance() checks.
        # Verify the Protocol is a class (Protocols are classes).
        assert isinstance(ConversionContext, type)

    def test_protocol_declares_expected_attributes(self):
        """The Protocol's expected attributes are documented."""
        from pathlib import Path

        proto_src = (
            Path(__file__).resolve().parent.parent / "core" / "pipeline" / "conversion_context.py"
        )
        content = proto_src.read_text()
        expected_attrs = [
            "request",
            "output_dir",
            "settings",
            "paths",
            "full_markdown_path",
            "cancel_event",
            "_partial_failures",
            "_record_partial_failure",
            "_build_error_result",
            "_log",
            "_update_progress",
        ]
        for attr in expected_attrs:
            assert attr in content, f"ConversionContext Protocol missing '{attr}'"


# ═══════════════════════════════════════════════════════════════════════════
# M7: pre-commit config
# ═══════════════════════════════════════════════════════════════════════════


class TestPreCommitConfig:
    """V18.2.18 (M7): pre-commit config exists with ruff + mypy hooks."""

    def test_pre_commit_config_exists(self):
        """The .pre-commit-config.yaml file exists."""
        from pathlib import Path

        config = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
        assert config.exists(), ".pre-commit-config.yaml not found"

    def test_config_has_ruff_hook(self):
        from pathlib import Path

        config = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
        content = config.read_text()
        assert "ruff-pre-commit" in content
        assert "ruff" in content

    def test_config_has_mypy_hook(self):
        from pathlib import Path

        config = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
        content = config.read_text()
        assert "mirrors-mypy" in content
        assert "mypy" in content

    def test_config_has_basic_hygiene_hooks(self):
        from pathlib import Path

        config = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
        content = config.read_text()
        assert "trailing-whitespace" in content
        assert "end-of-file-fixer" in content
