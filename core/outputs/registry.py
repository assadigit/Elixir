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
- **cost_tier** is the output's cost badge tier for the UI:
  "instant" / "fast" / "medium" / "slow" / "very_slow".
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
        (``outputs.<key>``) — EXCEPT for the 7 "core" outputs (summaries
        + its children executive/thorough/keypoints/simplified/compact,
        and docx) which use ``summarisation.*`` / ``docx.*`` setting
        prefixes and have no ``output_*`` flag (they're always-available
        core, not Output Studio extras).
    label:
        Human-readable name shown in the UI.
    subtitle:
        One-line description shown under the label.
    icon_name:
        Icon key from ``ui_qt/components/icons.py``.
    default:
        Whether the output is on by default.
    setting_key:
        Dotted settings path.  ``""`` for outputs with no settings toggle
        (gated by another setting instead).
    is_core:
        True for the always-available core outputs — the summaries family
        (summaries, executive/thorough/keypoints/simplified/compact) and
        docx (V0.7.2: 7 in total).  These appear in the wizard's Core /
        category cards, not the deprecated "Output Studio" flat list.
    request_attr:
        The ConversionRequest attribute name (e.g. ``"output_briefing"``).
        ``""`` for core outputs (they use ``generate_summaries`` etc.).
    wizard_attr:
        The WizardState attribute name (e.g. ``"outputs_briefing"``).
        V0.7.2 (wizard rework ④): every output the wizard can select —
        core AND studio — carries one (the summary sub-flags and compact
        joined the registry so ``selected_output_names`` covers them).
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
    short_name:
        V0.7.2 (wizard rework ④, B8): the compact display name the Review
        step and the conversion start-log use when enumerating the selected
        outputs (e.g. ``"exec summary"``).  Empty → fall back to ``label``.
    summary_child:
        V0.7.2 (wizard rework ④): True for outputs that are generated
        inside the summary pipeline and therefore cleanly no-op when
        ``generate_summaries`` is off (exec/thorough/keypoints/simplified/
        compact — audit §W6).  ``selected_output_names`` gates them on the
        master switch; non-children (docx, studio outputs) are listed
        whenever their own flag is set, exactly as before.
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
    short_name: str = ""  # V0.7.2 (wizard rework ④, B8)
    summary_child: bool = False  # V0.7.2 (wizard rework ④)


# ── The registry ────────────────────────────────────────────────────────────
#
# V0.7.2 (wizard rework ④, B8): every output the WIZARD can select now
# carries a ``wizard_attr`` — including the summary sub-flags and compact
# summaries, which previously lived outside the registry.  The Review step
# and the conversion start-log enumerate the selection through
# ``selected_output_names()`` below, driven from this list, so they can
# never drift from it again (the audit found 9-10 newer outputs silently
# omitted from both surfaces, §3 B8).

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
        wizard_attr="generate_summaries",  # the master switch, not an output itself
        cost_tier="medium",
        version_added="V1.0",
    ),
    # V0.7.2 (wizard rework ④, D7): the two essentials.  The wizard locks
    # them on (audit §W6 — the include_* flags merely gate prompt sections;
    # generate_summaries stays the single off-switch).  They live here so
    # the registry-driven enumeration covers them like every other output.
    OutputSpec(
        key="executive_summary",
        label="Executive Summary",
        subtitle="Short overview of each chapter, scaled to its length",
        icon_name="zap",
        default=True,
        setting_key="summarisation.include_executive_summary",
        is_core=True,
        wizard_attr="include_executive_summary",
        cost_tier="fast",
        version_added="V1.0",
        short_name="exec summary",
        summary_child=True,
    ),
    OutputSpec(
        key="thorough_summary",
        label="Thorough Summary",
        subtitle="Detailed prose summary of each chapter, scaled to its length",
        icon_name="book",
        default=True,
        setting_key="summarisation.include_thorough_summary",
        is_core=True,
        wizard_attr="include_thorough_summary",
        cost_tier="medium",
        version_added="V1.0",
        short_name="thorough summary",
        summary_child=True,
    ),
    OutputSpec(
        key="keypoints",
        label="Keypoints",
        subtitle="All key points extracted from each chapter",
        icon_name="list-checks",
        default=True,
        setting_key="summarisation.include_keypoints",
        is_core=True,
        wizard_attr="include_keypoints",
        cost_tier="fast",
        version_added="V1.0",
        short_name="keypoints",
        summary_child=True,
    ),
    OutputSpec(
        key="simplified_keypoints",
        label="Simplified Keypoints",
        subtitle="Plain-language version of every keypoint",
        icon_name="scissors",
        default=False,
        setting_key="summarisation.simplified_keypoints_enabled",
        is_core=True,
        wizard_attr="simplified_keypoints_enabled",
        cost_tier="slow",
        version_added="V3.9.0",
        short_name="simplified keypoints",
        summary_child=True,
    ),
    # V0.7.2 (wizard rework ④, §W8): compact summaries joins the registry —
    # a pure output-token cap (audit §W8), relocated to the wizard's
    # Reference card and enumerated like every other selected output.
    OutputSpec(
        key="compact_summaries",
        label="Compact Summaries",
        subtitle="Density mode — caps each chapter's summary (~1,000 tokens)",
        icon_name="minimize-2",
        default=False,
        setting_key="summarisation.compact_summaries",
        is_core=True,
        wizard_attr="compact_summaries",
        cost_tier="instant",
        version_added="V10.20.0",
        short_name="compact summaries",
        summary_child=True,
    ),
    OutputSpec(
        key="docx",
        label="DOCX Document",
        subtitle="Formatted Word document with TOC",
        icon_name="file-output",
        default=False,
        setting_key="docx.enabled",
        is_core=True,
        wizard_attr="generate_docx",
        cost_tier="fast",
        version_added="V1.0",
        short_name="DOCX",
    ),
    # ═══ OUTPUT STUDIO (opt-in extra outputs) ═══
    # ── V4.0.0 originals ──
    OutputSpec(
        key="briefing",
        label="Executive Briefing",
        subtitle="One-page synthesis of the whole book",
        icon_name="newspaper",
        default=True,
        setting_key="outputs.briefing",
        request_attr="output_briefing",
        wizard_attr="outputs_briefing",
        generator_class_name="ExecutiveBriefingGenerator",
        regenerate_key="briefing",
        cost_tier="medium",
        version_added="V4.0.0",
        short_name="briefing",
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
        short_name="podcast script",
    ),
    OutputSpec(
        key="flashcards",
        label="Flashcards",
        subtitle="Anki-compatible TSV + readable MD",
        icon_name="layers",
        default=True,
        setting_key="outputs.flashcards",
        request_attr="output_flashcards",
        wizard_attr="outputs_flashcards",
        generator_class_name="FlashcardGenerator",
        regenerate_key="flashcards",
        cost_tier="fast",
        version_added="V4.0.0",
        short_name="flashcards",
    ),
    # ── V4.1.0 ──
    OutputSpec(
        key="packets",
        label="Packets of Knowledge",
        subtitle="Clustered keypoints synthesised into cohesive paragraphs",
        icon_name="package",
        default=False,
        setting_key="outputs.packets",
        request_attr="output_packets",
        wizard_attr="outputs_packets",
        generator_class_name="PacketGenerator",
        regenerate_key="packets",
        cost_tier="slow",
        version_added="V7.3.0",
        short_name="packets",
    ),
    OutputSpec(
        key="obsidian",
        label="Obsidian Knowledge Base",
        subtitle="Linked notes with YAML + wikilinks",
        icon_name="link",
        default=False,
        setting_key="outputs.obsidian",
        request_attr="output_obsidian",
        wizard_attr="outputs_obsidian",
        generator_class_name="ObsidianKBGenerator",
        regenerate_key="obsidian",
        cost_tier="medium",
        version_added="V4.1.0",
        short_name="obsidian KB",
    ),
    OutputSpec(
        key="study_guide",
        label="Study Guide",
        subtitle="Objectives, glossary, Q&A, self-check",
        icon_name="graduation-cap",
        default=False,
        setting_key="outputs.study_guide",
        request_attr="output_study_guide",
        wizard_attr="outputs_study_guide",
        generator_class_name="StudyGuideGenerator",
        regenerate_key="study_guide",
        cost_tier="medium",
        version_added="V4.1.0",
        short_name="study guide",
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
        icon_name="network",
        default=False,
        setting_key="outputs.mindmap",
        request_attr="output_mindmap",
        wizard_attr="outputs_mindmap",
        generator_class_name="MindMapGenerator",
        regenerate_key="mindmap",
        cost_tier="instant",
        version_added="V4.1.0",
        short_name="mind map",
    ),
    # V0.7.2 (wizard rework ④, B9): the label no longer claims the podcast
    # script — the generator reads the EXECUTIVE BRIEFING file
    # (core/outputs/podcast_audio.py:108-131, audit §3 B9).  Honest on
    # every surface that renders this spec.
    OutputSpec(
        key="tts",
        label="Podcast Audio (TTS)",
        subtitle=(
            "Spoken audio built from the executive briefing — EN→NeuTTS/Kokoro, FA→Coqui XTTS v2."
        ),
        icon_name="audio-lines",
        default=False,
        setting_key="outputs.tts",
        request_attr="output_tts",
        wizard_attr="outputs_tts",
        generator_class_name="PodcastAudioGenerator",
        regenerate_key="podcast_audio",
        cost_tier="very_slow",
        version_added="V4.2.0",
        short_name="TTS audio (from briefing)",
    ),
    # ── V10.1.0 ──
    # V0.7.2 (wizard rework ④): the subtitle carries the honest
    # degradation copy (audit §W7 — evidence_map.py degrades to a guidance
    # page when the langextract extra is absent).
    OutputSpec(
        key="evidence_map",
        label="Scientific Evidence Map (langextract)",
        subtitle=(
            "Interactive HTML: every claim highlighted in its source. "
            "Needs the langextract extra — falls back to a guidance page "
            "without it."
        ),
        icon_name="map",
        default=False,
        setting_key="outputs.evidence_map",
        request_attr="output_evidence_map",
        wizard_attr="outputs_evidence_map",
        generator_class_name="EvidenceMapGenerator",
        regenerate_key="evidence_map",
        cost_tier="slow",
        version_added="V10.1.0",
        short_name="evidence map",
    ),
    # ── V10.17.0 ──
    OutputSpec(
        key="qa",
        label="Q&A Study Questions",
        subtitle="Self-test questions + answers per chapter",
        icon_name="help-circle",
        default=False,
        setting_key="outputs.qa",
        request_attr="output_qa",
        wizard_attr="outputs_qa",
        generator_class_name="QAGenerator",
        regenerate_key="qa",
        cost_tier="medium",
        version_added="V10.17.0",
        short_name="Q&A",
    ),
    # ── V10.20.0 ──
    OutputSpec(
        key="glossary",
        label="Glossary",
        subtitle="All terms + definitions extracted from the book",
        icon_name="book-open",
        default=False,
        setting_key="outputs.glossary",
        request_attr="output_glossary",
        wizard_attr="outputs_glossary",
        generator_class_name="GlossaryGenerator",
        regenerate_key="glossary",
        cost_tier="fast",
        version_added="V10.20.0",
        short_name="glossary",
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
        short_name="EPUB",
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
    """Return the always-available core outputs (7 — the summaries family
    + docx; V0.7.2 added executive/thorough/compact to the registry)."""
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


def selected_output_names(source: object) -> list[str]:
    """V0.7.2 (wizard rework ④, B8): every non-deprecated SELECTED output.

    The Review step's outputs line and the conversion start-log both
    enumerate through this function — driven from ``OUTPUT_REGISTRY``, so
    the two surfaces can never drift from the registry again (the audit
    found 9-10 newer outputs silently omitted from both: packets, qa,
    glossary, evidence map, epub, compact, …; §3 B8).

    Args:
        source: any object carrying the wizard's output flags (WizardState,
            or a stub in tests).  Attributes are read via ``getattr`` with
            the spec's ``wizard_attr``.

    Rules:
    - deprecated outputs are never listed (D6 — gone from the wizard;
      they still run if explicitly enabled via settings);
    - ``summaries`` (the master switch) is not itself an output;
    - ``summary_child`` outputs no-op when ``generate_summaries`` is off
      (audit §W6), so they are listed only when the master switch is on;
    - every other output is listed whenever its own flag is set.
    """
    summaries_on = bool(getattr(source, "generate_summaries", True))
    names: list[str] = []
    for spec in OUTPUT_REGISTRY:
        if spec.deprecated or not spec.wizard_attr or spec.key == "summaries":
            continue
        if spec.summary_child and not summaries_on:
            continue
        if bool(getattr(source, spec.wizard_attr, False)):
            names.append(spec.short_name or spec.label)
    return names


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
    "get_active_outputs",
    "selected_output_names",
]
