"""V0.7.4 (wizard rework ⑥, Step 6) — the pin file.

6a — two selection modes (D15): the master "Translate outputs" switch
carries the "optional — runs after conversion" caption (skipability is
visible, audit §W10); "What to translate" is a radio — "The outputs I
selected in step 4" (the default) vs "Let me choose" (the manual
checkbox list).  Mode A derives ``translation.outputs`` from the Step-4
selection AT START through the registry-driven mapping layer
(``core.outputs.registry.selected_translation_outputs``); the backend
needs no change (translation is a settings-driven post-conversion
phase, controller.py:432-492).  The harakat/judge combos open on the
last-used picks (the V0.7.3 ``_seed_model_combo`` pattern, D14's
"manual picking, auto-remembered") and list live off the UI thread.

6b — honesty: the ``.harakat.md`` output is documented as a
manual-review file (D16 deferred the TTS wiring to the backlog); the
dead settings keys (``translation.outputs.packets``,
``translation.harakat_confident_only``) are purged.

6c — VRAM truth (B7): the conversion-start VRAM check passes the REAL
translator model (the ``translation.model`` setting), not
``summarisation_model`` standing in for the translator.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_STEP6 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step6_translation.py"
_STEP8 = _project_root / "ui_qt" / "views" / "wizard_steps" / "step8_review.py"
_WIZARD = _project_root / "ui_qt" / "views" / "wizard_view.py"
_SHARED = _project_root / "ui_qt" / "views" / "wizard_steps" / "shared.py"
_REGISTRY = _project_root / "core" / "outputs" / "registry.py"
_SETTINGS = _project_root / "utils" / "settings.py"
_TR_PAGE = _project_root / "ui_qt" / "settings" / "translation_page.py"
_HARAKAT = _project_root / "core" / "translation" / "harakat.py"
_SERVICE = _project_root / "core" / "translation" / "service.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# 6a — the mapping layer (registry-driven, pure, Qt-less)
# ═══════════════════════════════════════════════════════════════════════════


def _selection(**overrides) -> SimpleNamespace:
    """A Step-4-shaped selection source (the wizard_attr flags)."""
    base = dict(
        generate_summaries=True,
        include_executive_summary=True,
        include_thorough_summary=True,
        include_keypoints=True,
        simplified_keypoints_enabled=False,
        compact_summaries=False,
        generate_docx=False,
        outputs_briefing=False,
        outputs_podcast=False,
        outputs_flashcards=False,
        outputs_packets=False,
        outputs_obsidian=False,
        outputs_study_guide=False,
        outputs_social=False,
        outputs_mindmap=False,
        outputs_tts=False,
        outputs_evidence_map=False,
        outputs_qa=False,
        outputs_glossary=False,
        outputs_epub=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestSelectedTranslationOutputs:
    def test_default_selection_derives_summaries_and_keypoints(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert out["chapter_summaries"] is True, "exec+thorough → chapter summaries"
        assert out["keypoints"] is True
        assert out["simplified_keypoints"] is False
        for k in (
            "full_markdown",
            "briefing",
            "podcast",
            "flashcards",
            "obsidian",
            "study_guide",
            "social",
            "mindmap",
        ):
            assert out[k] is False, f"{k} must stay off for the default selection"

    def test_studio_selections_map_one_to_one(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(
                outputs_briefing=True,
                outputs_podcast=True,
                outputs_flashcards=True,
                outputs_obsidian=True,
                outputs_study_guide=True,
                outputs_mindmap=True,
                simplified_keypoints_enabled=True,
            )
        )
        for k in (
            "briefing",
            "podcast",
            "flashcards",
            "obsidian",
            "study_guide",
            "mindmap",
            "simplified_keypoints",
        ):
            assert out[k] is True, f"{k} must follow its Step-4 selection"

    def test_master_switch_gates_the_summary_family(self):
        """generate_summaries off → the summary-family translations no-op
        (audit §W6) — studio outputs are unaffected."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(generate_summaries=False, outputs_briefing=True)
        )
        assert out["chapter_summaries"] is False
        assert out["keypoints"] is False
        assert out["simplified_keypoints"] is False
        assert out["briefing"] is True

    def test_summaries_off_with_both_essentials_on(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(generate_summaries=False))
        assert out["chapter_summaries"] is False

    def test_essentials_off_kills_chapter_summaries(self):
        """Both include flags off (a settings-forced state) → no summary
        files exist → nothing to translate."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(
            _selection(include_executive_summary=False, include_thorough_summary=False)
        )
        assert out["chapter_summaries"] is False
        assert out["keypoints"] is True, "keypoints is a separate flag"

    def test_either_essential_suffices(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(include_thorough_summary=False))
        assert out["chapter_summaries"] is True

    def test_deprecated_social_never_maps(self):
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection(outputs_social=True))
        assert out["social"] is False, "deprecated outputs are unselectable on Step 4 (D6)"

    def test_full_markdown_never_derived(self):
        """The whole-book translation is a manual-only choice — it is not a
        Step-4 selection and must never be implicit (the most expensive
        translation job)."""
        from core.outputs.registry import selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert out["full_markdown"] is False

    def test_result_covers_every_map_key(self):
        """A mode-A Start rewrites the WHOLE selection — every
        translation.outputs key is present (no stale carryover)."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP, selected_translation_outputs

        out = selected_translation_outputs(_selection())
        assert set(out) == set(_TRANSLATION_OUTPUT_MAP)
        assert all(isinstance(v, bool) for v in out.values())

    def test_untranslatable_outputs_are_not_keys(self):
        """qa/glossary/packets/tts/epub/docx/compact have no translation
        counterpart (no backend glob) — they must not appear in the map."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP

        for k in (
            "qa",
            "glossary",
            "packets",
            "tts",
            "evidence_map",
            "epub",
            "docx",
            "compact_summaries",
        ):
            assert k not in _TRANSLATION_OUTPUT_MAP


class TestTranslationMapIntegrity:
    """The mapping can never drift from the two lists it mirrors."""

    def test_map_keys_match_the_backend_file_map(self):
        """Every derivation key is a real translation.outputs key the
        backend globs for (core.translation.service._OUTPUT_FILE_MAP)."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP
        from core.translation.service import _OUTPUT_FILE_MAP

        assert set(_TRANSLATION_OUTPUT_MAP) == set(_OUTPUT_FILE_MAP), (
            "the registry mapping and the service file map must list the same keys"
        )

    def test_every_source_key_exists_in_the_registry(self):
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP, OUTPUT_REGISTRY

        reg_keys = {spec.key for spec in OUTPUT_REGISTRY}
        for _label, sources in _TRANSLATION_OUTPUT_MAP.values():
            for src in sources:
                assert src in reg_keys, f"mapping source {src!r} is not a registry key (typo?)"

    def test_labels_match_the_settings_page_list(self):
        """The labels shown in the mode-A review copy are the same labels
        the Settings translation page shows for the manual list."""
        from core.outputs.registry import _TRANSLATION_OUTPUT_MAP

        page_labels = {}
        exec_ns = {}
        src = _src(_TR_PAGE)
        start = src.index("_TRANSLATABLE_OUTPUTS = [")
        end = src.index("]", start) + 1
        exec(src[start:end], exec_ns)  # noqa: S102 — test-local literal parse
        for key, label, _sub in exec_ns["_TRANSLATABLE_OUTPUTS"]:
            page_labels[key] = label
        assert {k: v[0] for k, v in _TRANSLATION_OUTPUT_MAP.items()} == page_labels


class TestTranslationOutputLabel:
    def test_known_keys(self):
        from core.outputs.registry import translation_output_label

        assert translation_output_label("chapter_summaries") == "Chapter summaries"
        assert translation_output_label("full_markdown") == "Full book Markdown"

    def test_unknown_key_passthrough(self):
        from core.outputs.registry import translation_output_label

        assert translation_output_label("anything-else") == "anything-else"
