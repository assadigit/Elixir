"""V10.29.0 (Sprint 2.2): Single source of truth for all output types.

Before V10.29.0, the list of output types was duplicated in **4 places**
that silently disagreed:

1. ``ui_qt/views/wizard_view.py`` Step4Outputs — 15 checkboxes (latest)
2. ``ui_qt/views/output_types_dialog.py`` ``_OUTPUTS`` — 13 entries
   (missing qa, glossary, patterns, cheatsheet, skill)
3. ``ui_qt/settings/sections.py`` ``OutputStudioSection._OUTPUTS`` — 9
   entries (missing evidence_map + the 5 V10.20.0 outputs)
4. ``controller.py`` ``_REGENERATE_MAP`` — 10 entries (missing the 5
   V10.20.0 outputs, so they couldn't be regenerated from the scanner)

This module replaces all four with a single ``OUTPUT_REGISTRY`` list.
Every UI surface and the controller now import from here, so adding a
new output type is a one-file change.

Design notes
------------
- **No PySide6 dependency.** The registry is pure data so it can be
  imported from anywhere (including tests and the controller).
- **Icon names** match the keys in ``ui_qt/components/icons.py``.  If an
  icon name is missing, ``icon()`` falls back to a default glyph.
- **Setting key** is the dotted path in ``settings.json`` (e.g.
  ``"outputs.briefing"``).  The wizard's ``outputs_X`` field name and the
  ``ConversionRequest.output_X`` attribute are derived from ``key``
  (the short slug) to keep the three in sync.
- **regenerate_key** is the scanner output key used in
  ``controller._REGENERATE_MAP``.  ``None`` means the output is not
  regenerable from the scanner (e.g. core summaries, DOCX).
- **generator_class_name** is the class name (string, not the class —
  avoids importing the generators here, which would pull in heavy deps).
- **cost_tier** is the label used by ``output_time_estimates`` for the
  badge colour: "instant" / "fast" / "medium" / "slow" / "very_slow".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputSpec:
    """One output type — its metadata across all 4 surfaces.

    Attributes
    ----------
    key:
        Short slug, e.g. ``"briefing"``, ``"evidence_map"``.  Used to
        derive the WizardState field (``outputs_<key>``), the
        ConversionRequest flag (``output_<key>``), and the setting key
        (``outputs.<key>``) — EXCEPT for the 4 "core" outputs
        (summaries, keypoints, simplified_keypoints, docx) which use
        ``summarisation.*`` / ``docx.*`` setting prefixes and have no
        ``output_*`` flag (they're always-available core, not Output
        Studio extras).
    label:
        Human-readable name shown in the UI.
    subtitle:
        One-line description shown under the label.
    icon_name:
        Icon key from ``ui_qt/components/icons.py``.
    default:
        Whether the output is on by default.
    setting_key:
        Dotted settings path.  ``""`` for core outputs that have no
        settings toggle (they're gated by ``generate_summaries`` etc.).
    is_core:
        True for the 4 always-available core outputs (summaries,
        keypoints, simplified_keypoints, docx).  These appear in the
        "Core outputs" section of the dialog/wizard, not the "Output
        Studio" section.
    request_attr:
        The ConversionRequest attribute name (e.g. ``"output_briefing"``).
        ``""`` for core outputs (they use ``generate_summaries`` etc.).
    wizard_attr:
        The WizardState attribute name (e.g. ``"outputs_briefing"``).
        ``""`` for core outputs.
    generator_class_name:
        The generator class name (string).  ``None`` for core outputs
        (they're generated inline by the summariser/docx builder).
    regenerate_key:
        The scanner output key for ``_REGENERATE_MAP``.  ``None`` if not
        regenerable from the scanner.
    cost_tier:
        Badge tier for the time-cost estimate: "instant" / "fast" /
        "medium" / "slow" / "very_slow".
    version_added:
        Version string when this output was introduced (for the docs).
    deprecated:
        V13.30.0 (P3.4): If True, this output is deprecated and hidden from
        the default UI. The user's Q21 audit answer was "10-12 useful, rest
        are noise." Deprecated outputs still work if explicitly enabled via
        settings, but don't appear in the wizard checkboxes by default.
    """

    key: str
    label: str
    subtitle: str
    icon_name: str
    default: bool
    setting_key: str
    is_core: bool = False
    request_attr: str = ""
    wizard_attr: str = ""
    generator_class_name: str | None = None
    regenerate_key: str | None = None
    cost_tier: str = "medium"
    version_added: str = "V4.0.0"
    deprecated: bool = False  # V13.30.0 (P3.4)


# ── The registry ────────────────────────────────────────────────────────────

OUTPUT_REGISTRY: list[OutputSpec] = [
    # ═══ CORE OUTPUTS (always available, gated by generate_summaries etc.) ═══
    OutputSpec(
        key="summaries",
        label="Per-chapter Summaries",
        subtitle="Executive + thorough summary per chapter",
        icon_name="file-text",
        default=True,
        setting_key="summarisation.enabled",
        is_core=True,
        cost_tier="medium",
        version_added="V1.0",
    ),
    OutputSpec(
        key="keypoints",
        label="Keypoints",
        subtitle="All key points extracted from each chapter",
        icon_name="list-checks",
        default=True,
        setting_key="summarisation.include_keypoints",
        is_core=True,
        cost_tier="fast",
        version_added="V1.0",
    ),
    OutputSpec(
        key="simplified_keypoints",
        label="Simplified Keypoints",
        subtitle="Plain-language version of every keypoint",
        icon_name="scissors",
        default=False,
        setting_key="summarisation.simplified_keypoints_enabled",
        is_core=True,
        cost_tier="slow",
        version_added="V3.9.0",
    ),
    OutputSpec(
        key="docx",
        label="DOCX Document",
        subtitle="Formatted Word document with TOC",
        icon_name="file-output",
        default=False,
        setting_key="docx.enabled",
        is_core=True,
        cost_tier="fast",
        version_added="V1.0",
    ),
    # ═══ OUTPUT STUDIO (opt-in extra outputs) ═══
    # ── V4.0.0 originals ──
    OutputSpec(
        key="briefing",
        label="Executive Briefing",
        subtitle="One-page synthesis of the whole book",
        icon_name="file-text",
        default=True,
        setting_key="outputs.briefing",
        request_attr="output_briefing",
        wizard_attr="outputs_briefing",
        generator_class_name="ExecutiveBriefingGenerator",
        regenerate_key="briefing",
        cost_tier="medium",
        version_added="V4.0.0",
    ),
    OutputSpec(
        key="podcast",
        label="Podcast Script (text only)",
        subtitle="2-host conversational script — no audio",
        icon_name="mic",
        default=True,
        setting_key="outputs.podcast",
        request_attr="output_podcast",
        wizard_attr="outputs_podcast",
        generator_class_name="PodcastGenerator",
        regenerate_key="podcast_script",
        cost_tier="slow",
        version_added="V4.0.0",
    ),
    OutputSpec(
        key="flashcards",
        label="Flashcards",
        subtitle="Anki-compatible TSV + readable MD",
        icon_name="book",
        default=True,
        setting_key="outputs.flashcards",
        request_attr="output_flashcards",
        wizard_attr="outputs_flashcards",
        generator_class_name="FlashcardGenerator",
        regenerate_key="flashcards",
        cost_tier="fast",
        version_added="V4.0.0",
    ),
    # ── V4.1.0 ──
    OutputSpec(
        key="packets",
        label="Packets of Knowledge",
        subtitle="Clustered keypoints synthesised into cohesive paragraphs",
        icon_name="layout",
        default=False,
        setting_key="outputs.packets",
        request_attr="output_packets",
        wizard_attr="outputs_packets",
        generator_class_name="PacketGenerator",
        regenerate_key="packets",
        cost_tier="slow",
        version_added="V7.3.0",
    ),
    OutputSpec(
        key="obsidian",
        label="Obsidian Knowledge Base",
        subtitle="Linked notes with YAML + wikilinks",
        icon_name="bookmark",
        default=False,
        setting_key="outputs.obsidian",
        request_attr="output_obsidian",
        wizard_attr="outputs_obsidian",
        generator_class_name="ObsidianKBGenerator",
        regenerate_key="obsidian",
        cost_tier="medium",
        version_added="V4.1.0",
    ),
    OutputSpec(
        key="study_guide",
        label="Study Guide",
        subtitle="Objectives, glossary, Q&A, self-check",
        icon_name="book",
        default=False,
        setting_key="outputs.study_guide",
        request_attr="output_study_guide",
        wizard_attr="outputs_study_guide",
        generator_class_name="StudyGuideGenerator",
        regenerate_key="study_guide",
        cost_tier="medium",
        version_added="V4.1.0",
    ),
    OutputSpec(
        key="social",
        label="Social Media Pack",
        subtitle="X thread + LinkedIn + hashtags",
        icon_name="message-square",
        default=False,
        setting_key="outputs.social",
        request_attr="output_social",
        wizard_attr="outputs_social",
        generator_class_name="SocialMediaPackGenerator",
        regenerate_key="social",
        cost_tier="fast",
        version_added="V4.1.0",
        deprecated=True,  # V13.30.0 (P3.4): low usage, noise
    ),
    OutputSpec(
        key="mindmap",
        label="Mind Map",
        subtitle="Mermaid mindmap + outline (no LLM)",
        icon_name="layout",
        default=False,
        setting_key="outputs.mindmap",
        request_attr="output_mindmap",
        wizard_attr="outputs_mindmap",
        generator_class_name="MindMapGenerator",
        regenerate_key="mindmap",
        cost_tier="instant",
        version_added="V4.1.0",
    ),
    OutputSpec(
        key="tts",
        label="Podcast Audio (TTS — optional, needs script)",
        subtitle="Spoken audio: EN→NeuTTS, FA→Piper. Generate script first.",
        icon_name="mic",
        default=False,
        setting_key="outputs.tts",
        request_attr="output_tts",
        wizard_attr="outputs_tts",
        generator_class_name="PodcastAudioGenerator",
        regenerate_key="podcast_audio",
        cost_tier="very_slow",
        version_added="V4.2.0",
    ),
    # ── V10.1.0 ──
    OutputSpec(
        key="evidence_map",
        label="Scientific Evidence Map (langextract)",
        subtitle="Interactive HTML: every claim highlighted in its source. "
        "Requires langextract + grounding enabled.",
        icon_name="layout",
        default=False,
        setting_key="outputs.evidence_map",
        request_attr="output_evidence_map",
        wizard_attr="outputs_evidence_map",
        generator_class_name="EvidenceMapGenerator",
        regenerate_key="evidence_map",
        cost_tier="slow",
        version_added="V10.1.0",
    ),
    # ── V10.17.0 ──
    OutputSpec(
        key="qa",
        label="Q&A Study Questions",
        subtitle="Self-test questions + answers per chapter",
        icon_name="message-square",
        default=False,
        setting_key="outputs.qa",
        request_attr="output_qa",
        wizard_attr="outputs_qa",
        generator_class_name="QAGenerator",
        regenerate_key="qa",
        cost_tier="medium",
        version_added="V10.17.0",
    ),
    # ── V10.20.0 ──
    OutputSpec(
        key="glossary",
        label="Glossary",
        subtitle="All terms + definitions extracted from the book",
        icon_name="book",
        default=False,
        setting_key="outputs.glossary",
        request_attr="output_glossary",
        wizard_attr="outputs_glossary",
        generator_class_name="GlossaryGenerator",
        regenerate_key="glossary",
        cost_tier="fast",
        version_added="V10.20.0",
    ),
    OutputSpec(
        key="patterns",
        label="Patterns / Techniques",
        subtitle="Recurring methods + frameworks identified across chapters",
        icon_name="layout",
        default=False,
        setting_key="outputs.patterns",
        request_attr="output_patterns",
        wizard_attr="outputs_patterns",
        generator_class_name="PatternsGenerator",
        regenerate_key="patterns",
        cost_tier="medium",
        version_added="V10.20.0",
        deprecated=True,  # V13.30.0 (P3.4): low usage, overlap with study_guide
    ),
    OutputSpec(
        key="cheatsheet",
        label="Cheatsheet",
        subtitle="One-page quick-reference of all key facts",
        icon_name="file-text",
        default=False,
        setting_key="outputs.cheatsheet",
        request_attr="output_cheatsheet",
        wizard_attr="outputs_cheatsheet",
        generator_class_name="CheatsheetGenerator",
        regenerate_key="cheatsheet",
        cost_tier="fast",
        version_added="V10.20.0",
        deprecated=True,  # V13.30.0 (P3.4): low usage, overlap with summary
    ),
    # ── V10.21.0 ──
    OutputSpec(
        key="skill",
        label="Agent Skill (SKILL.md)",
        subtitle="Package the book as a ClawHub-style installable skill",
        icon_name="sparkles",
        default=False,
        setting_key="outputs.skill",
        request_attr="output_skill",
        wizard_attr="outputs_skill",
        generator_class_name="AgentSkillGenerator",
        regenerate_key="skill",
        cost_tier="medium",
        version_added="V10.21.0",
        deprecated=True,  # V13.30.0 (P3.4): never used, plugin system removed
    ),
    # ── V10.35.0 (Sprint 8): EPUB output ──
    OutputSpec(
        key="epub",
        label="EPUB (annotated)",
        subtitle="Re-export with embedded summaries — for e-readers",
        icon_name="book",
        default=False,
        setting_key="outputs.epub",
        request_attr="output_epub",
        wizard_attr="outputs_epub",
        generator_class_name="EPUBGenerator",
        regenerate_key="epub",
        cost_tier="fast",
        version_added="V10.35.0",
    ),
    # ── V10.35.0 (Sprint 9): Quote bank ──
    OutputSpec(
        key="quote_bank",
        label="Quote Bank",
        subtitle="Every direct quote (>40 chars) with page citation",
        icon_name="bookmark",
        default=False,
        setting_key="outputs.quote_bank",
        request_attr="output_quote_bank",
        wizard_attr="outputs_quote_bank",
        generator_class_name="QuoteBankGenerator",
        regenerate_key="quote_bank",
        cost_tier="fast",
        version_added="V10.35.0",
        deprecated=True,  # V13.30.0 (P3.4): low usage, niche
    ),
]


# ── Convenience accessors ───────────────────────────────────────────────────


def get_all_outputs() -> list[OutputSpec]:
    """Return the full registry (core + studio)."""
    return list(OUTPUT_REGISTRY)


def get_core_outputs() -> list[OutputSpec]:
    """Return only the always-available core outputs (4)."""
    return [o for o in OUTPUT_REGISTRY if o.is_core]


def get_studio_outputs() -> list[OutputSpec]:
    """Return only the opt-in Output Studio extras (15)."""
    return [o for o in OUTPUT_REGISTRY if not o.is_core]


def get_active_outputs() -> list[OutputSpec]:
    """V13.30.0 (P3.4): Return all non-deprecated outputs (core + studio).

    Deprecated outputs (social, patterns, cheatsheet, skill, quote_bank)
    are excluded — they still work if explicitly enabled via settings, but
    don't appear in the default UI.
    """
    return [o for o in OUTPUT_REGISTRY if not o.deprecated]


def get_output_by_key(key: str) -> OutputSpec | None:
    """Look up an OutputSpec by its slug key.  Returns None if not found."""
    for o in OUTPUT_REGISTRY:
        if o.key == key:
            return o
    return None


def get_output_by_setting(setting_key: str) -> OutputSpec | None:
    """Look up an OutputSpec by its settings.json dotted path."""
    for o in OUTPUT_REGISTRY:
        if o.setting_key == setting_key:
            return o
    return None


def get_output_by_regenerate_key(regenerate_key: str) -> OutputSpec | None:
    """Look up an OutputSpec by the scanner regenerate key."""
    for o in OUTPUT_REGISTRY:
        if o.regenerate_key == regenerate_key:
            return o
    return None


def get_regenerate_map() -> dict:
    """Build the controller._REGENERATE_MAP dict from the registry.

    Maps ``regenerate_key → (generator_class_name, request_attr)``.
    Skips core outputs (they have regenerate_key=None).
    """
    out = {}
    for o in OUTPUT_REGISTRY:
        if o.regenerate_key and o.generator_class_name and o.request_attr:
            out[o.regenerate_key] = (o.generator_class_name, o.request_attr)
    return out


def get_settings_section_outputs() -> list:
    """Return the (setting_key, label, default) tuples that
    ``settings/sections.py OutputStudioSection._OUTPUTS`` previously
    hardcoded.  Studio outputs only (core outputs are handled elsewhere
    in the settings dialog).
    """
    return [(o.setting_key, o.label, o.default) for o in get_studio_outputs()]


__all__ = [
    "OutputSpec",
    "OUTPUT_REGISTRY",
    "get_all_outputs",
    "get_core_outputs",
    "get_studio_outputs",
    "get_output_by_key",
    "get_output_by_setting",
    "get_output_by_regenerate_key",
    "get_regenerate_map",
    "get_settings_section_outputs",
]
