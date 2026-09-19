"""V4.6.0: Podcast settings page — a top-level head group in Settings.

Four sections:
  1. **Format** — 1-host vs 2-host, full-book vs per-chapter, host voices
  2. **Depth & Length** — exhaustive (with optional 2hr cap) or
     time-restricted (15/30/45/60 min)
  3. **Style** — tone (serious/conversational/fun), intro hook, outro
     conclusion, human fillers (NotebookLM-style)
  4. **Preview** — estimated word count + runtime based on current settings

All settings persist under the ``podcast.*`` namespace.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QSpinBox,
    QWidget,
)

from controller import Controller
from core.tts.voices import (
    PIPER_FA_VOICES,
    kokoro_voice_groups,
    piper_voice_label,
)
from ui_qt.settings.widgets import make_form

# ── Section 1: Format ─────────────────────────────────────────────────────


class PodcastFormatSection(QGroupBox):
    """Hosts (1/2), scope (full-book/per-chapter), host voice selectors."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Format", parent)
        self.controller = controller
        f = make_form()

        # Hosts
        self.hosts_combo = QComboBox()
        self.hosts_combo.addItem("1-host monologue (single narrator)", 1)
        self.hosts_combo.addItem("2-host dialogue (Host A + Host B)", 2)
        hosts = int(controller.get_setting("podcast.hosts", 2))
        idx = self.hosts_combo.findData(hosts)
        if idx >= 0:
            self.hosts_combo.setCurrentIndex(idx)
        f.addRow("Hosts", self.hosts_combo)

        # Scope
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Full book (one podcast)", "full_book")
        self.scope_combo.addItem("Per chapter (one podcast per chapter)", "per_chapter")
        scope = controller.get_setting("podcast.scope", "per_chapter")  # V7.6.0 R6
        idx = self.scope_combo.findData(scope)
        if idx >= 0:
            self.scope_combo.setCurrentIndex(idx)
        f.addRow("Scope", self.scope_combo)

        # Host A voice (used for 1-host too)
        self.host_a_combo = QComboBox()
        self._populate_voices(self.host_a_combo)
        ha = controller.get_setting("tts.host_a_voice", "")
        self._select(self.host_a_combo, ha or "dave")
        f.addRow("Host A voice", self.host_a_combo)

        # Host B voice (only for 2-host)
        self.host_b_combo = QComboBox()
        self._populate_voices(self.host_b_combo)
        hb = controller.get_setting("tts.host_b_voice", "")
        self._select(self.host_b_combo, hb or "jo")
        f.addRow("Host B voice (2-host only)", self.host_b_combo)

        hint = QLabel(
            "1-host: a single narrator speaks throughout (uses Host A voice). "
            "2-host: two voices alternate in dialogue. Per-chapter produces "
            "separate podcast files for each chapter."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    @staticmethod
    def _populate_voices(combo: QComboBox) -> None:
        """Fill a combo with all available voices (NeuTTS + Kokoro + Piper)."""
        combo.addItem("dave — Male, warm (NeuTTS preset)", "dave")
        combo.addItem("jo — Female, friendly (NeuTTS preset)", "jo")
        combo.addItem("greta — Female, authoritative (NeuTTS preset)", "greta")
        combo.addItem("juliette — Female, gentle (NeuTTS preset)", "juliette")
        combo.addItem("mateo — Male, energetic (NeuTTS preset)", "mateo")
        from core.tts.voice_manager import VoiceManager

        vm = VoiceManager()
        for v in vm.list_voices():
            if v["name"] not in ("dave", "jo", "greta", "juliette", "mateo"):
                combo.addItem(f"{v['name']} — {v['description']}", v["name"])
        for _group_label, voices in kokoro_voice_groups():
            for vid, _lang, _gender, desc in voices:
                combo.addItem(f"Kokoro · {vid} — {desc}", vid)
        for vid, _repo, _sub in PIPER_FA_VOICES:
            combo.addItem(f"Piper · {piper_voice_label(vid)}", vid)

    @staticmethod
    def _select(combo: QComboBox, data: str) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif data:
            combo.insertItem(0, data, data)
            combo.setCurrentIndex(0)

    def save(self) -> None:
        c = self.controller
        c.update_setting("podcast.hosts", self.hosts_combo.currentData())
        c.update_setting("podcast.scope", self.scope_combo.currentData())
        c.update_setting("tts.host_a_voice", self.host_a_combo.currentData() or "")
        c.update_setting("tts.host_b_voice", self.host_b_combo.currentData() or "")

    def reload(self) -> None:
        c = self.controller
        hosts = int(c.get_setting("podcast.hosts", 2))
        idx = self.hosts_combo.findData(hosts)
        if idx >= 0:
            self.hosts_combo.setCurrentIndex(idx)
        scope = c.get_setting("podcast.scope", "per_chapter")  # V7.6.0 R6
        idx = self.scope_combo.findData(scope)
        if idx >= 0:
            self.scope_combo.setCurrentIndex(idx)


# ── Section 2: Depth & Length ─────────────────────────────────────────────


class PodcastDepthSection(QGroupBox):
    """Depth mode (exhaustive/time-restricted) + target length + cap."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Depth & Length", parent)
        self.controller = controller
        f = make_form()

        # Depth mode
        self.depth_combo = QComboBox()
        self.depth_combo.addItem("Exhaustive (cover everything thoroughly)", "exhaustive")
        self.depth_combo.addItem("Time-restricted (fit into a target length)", "time_restricted")
        depth = controller.get_setting("podcast.depth_mode", "exhaustive")
        idx = self.depth_combo.findData(depth)
        if idx >= 0:
            self.depth_combo.setCurrentIndex(idx)
        self.depth_combo.currentIndexChanged.connect(self._on_depth_changed)
        f.addRow("Depth mode", self.depth_combo)

        # Target length (time-restricted)
        self.target_combo = QComboBox()
        for mins in [15, 30, 45, 60]:
            self.target_combo.addItem(f"{mins} minutes (~{mins * 150} words)", mins)
        target = int(controller.get_setting("podcast.target_minutes", 30))
        idx = self.target_combo.findData(target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        f.addRow("Target length", self.target_combo)

        # Exhaustive cap
        self.cap_cb = QCheckBox("Safety cap for exhaustive mode")
        self.cap_cb.setChecked(controller.get_setting("podcast.exhaustive_cap_enabled", True))
        self.cap_cb.setToolTip(
            "When enabled, exhaustive podcasts are capped at the specified "
            "duration as a safety measure. Disable for truly unlimited length."
        )
        f.addRow("", self.cap_cb)

        self.cap_spin = QSpinBox()
        self.cap_spin.setRange(10, 600)
        self.cap_spin.setSuffix(" minutes")
        self.cap_spin.setValue(int(controller.get_setting("podcast.exhaustive_cap_minutes", 120)))
        f.addRow("Exhaustive cap", self.cap_spin)

        hint = QLabel(
            "Exhaustive: covers ALL key points thoroughly (no time limit unless "
            "cap is enabled). Time-restricted: prioritizes the most important "
            "ideas to fit the target length. Disable the cap for truly unlimited "
            "exhaustive podcasts."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)
        self._on_depth_changed()

    def _on_depth_changed(self) -> None:
        """Enable/disable widgets based on depth mode."""
        is_time_restricted = self.depth_combo.currentData() == "time_restricted"
        is_exhaustive = not is_time_restricted
        self.target_combo.setEnabled(is_time_restricted)
        self.cap_cb.setEnabled(is_exhaustive)
        self.cap_spin.setEnabled(is_exhaustive and self.cap_cb.isChecked())

    def save(self) -> None:
        c = self.controller
        c.update_setting("podcast.depth_mode", self.depth_combo.currentData())
        c.update_setting("podcast.target_minutes", self.target_combo.currentData())
        c.update_setting("podcast.exhaustive_cap_enabled", self.cap_cb.isChecked())
        c.update_setting("podcast.exhaustive_cap_minutes", self.cap_spin.value())

    def reload(self) -> None:
        c = self.controller
        depth = c.get_setting("podcast.depth_mode", "exhaustive")
        idx = self.depth_combo.findData(depth)
        if idx >= 0:
            self.depth_combo.setCurrentIndex(idx)
        target = int(c.get_setting("podcast.target_minutes", 30))
        idx = self.target_combo.findData(target)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)
        self.cap_cb.setChecked(c.get_setting("podcast.exhaustive_cap_enabled", True))
        self.cap_spin.setValue(int(c.get_setting("podcast.exhaustive_cap_minutes", 120)))
        self._on_depth_changed()


# ── Section 3: Style ──────────────────────────────────────────────────────


class PodcastStyleSection(QGroupBox):
    """Tone, intro/outro, human fillers."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Style", parent)
        self.controller = controller
        f = make_form()

        # Tone
        self.tone_combo = QComboBox()
        self.tone_combo.addItem("Serious (professional, focused)", "serious")
        self.tone_combo.addItem("Conversational (natural, engaging)", "conversational")
        self.tone_combo.addItem("Fun (sarcasm, laughter, lived experiences)", "fun")
        tone = controller.get_setting("podcast.tone", "conversational")
        idx = self.tone_combo.findData(tone)
        if idx >= 0:
            self.tone_combo.setCurrentIndex(idx)
        f.addRow("Tone", self.tone_combo)

        # Intro
        self.intro_cb = QCheckBox("Include intro hook (compelling opening)")
        self.intro_cb.setChecked(controller.get_setting("podcast.include_intro", True))
        f.addRow("", self.intro_cb)

        # Outro
        self.outro_cb = QCheckBox("Include outro (summary + call-to-action)")
        self.outro_cb.setChecked(controller.get_setting("podcast.include_outro", True))
        f.addRow("", self.outro_cb)

        # Human fillers
        self.fillers_cb = QCheckBox(
            "Human-like fillers (breathing, 'hmm', 'yeah' — NotebookLM style)"
        )
        self.fillers_cb.setChecked(controller.get_setting("podcast.human_fillers", True))
        self.fillers_cb.setToolTip(
            "Adds natural conversational fillers to make the podcast sound like "
            "a real human conversation. Works best with NeuTTS (LLM-based engine). "
            "Kokoro/Piper may pronounce fillers less naturally."
        )
        f.addRow("", self.fillers_cb)

        hint = QLabel(
            "Human fillers add 'hmm', 'yeah', 'exactly', and natural pauses to "
            "mimic real podcast conversations (like NotebookLM). Use sparingly — "
            "the prompt instructs 1-2 per minute. Best results with NeuTTS."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)

    def save(self) -> None:
        c = self.controller
        c.update_setting("podcast.tone", self.tone_combo.currentData())
        c.update_setting("podcast.include_intro", self.intro_cb.isChecked())
        c.update_setting("podcast.include_outro", self.outro_cb.isChecked())
        c.update_setting("podcast.human_fillers", self.fillers_cb.isChecked())

    def reload(self) -> None:
        c = self.controller
        tone = c.get_setting("podcast.tone", "conversational")
        idx = self.tone_combo.findData(tone)
        if idx >= 0:
            self.tone_combo.setCurrentIndex(idx)
        self.intro_cb.setChecked(c.get_setting("podcast.include_intro", True))
        self.outro_cb.setChecked(c.get_setting("podcast.include_outro", True))
        self.fillers_cb.setChecked(c.get_setting("podcast.human_fillers", True))


# ── Section 4: Preview ────────────────────────────────────────────────────


class PodcastPreviewSection(QGroupBox):
    """Estimated word count + runtime based on current settings."""

    def __init__(self, controller: Controller, parent: QWidget | None = None) -> None:
        super().__init__("Preview", parent)
        self.controller = controller
        f = make_form()

        self.estimate_label = QLabel("")
        self.estimate_label.setObjectName("Caption")
        self.estimate_label.setWordWrap(True)
        self.estimate_label.setStyleSheet(
            "font-size: 12px; padding: 10px; background: rgba(0,0,0,0.03);border-radius: 4px;"
        )
        f.addRow("Estimate", self.estimate_label)

        hint = QLabel(
            "Estimates assume ~150 words per minute of spoken audio. Actual "
            "length depends on the LLM's output and the TTS engine's pacing. "
            "For per-chapter scope, the estimate is per chapter."
        )
        hint.setObjectName("Caption")
        hint.setWordWrap(True)
        f.addRow("", hint)

        self.setLayout(f)
        self._update_estimate()

    def _update_estimate(self) -> None:
        """Update the estimate label based on current settings."""
        c = self.controller
        depth = c.get_setting("podcast.depth_mode", "exhaustive")
        if depth == "time_restricted":
            mins = int(c.get_setting("podcast.target_minutes", 30))
            words = mins * 150
            text = (
                f"⏱️  Time-restricted: ~{mins} minutes (~{words:,} words)\n"
                f"The LLM will prioritize the most important ideas to fit."
            )
        else:
            cap_enabled = c.get_setting("podcast.exhaustive_cap_enabled", True)
            if cap_enabled:
                mins = int(c.get_setting("podcast.exhaustive_cap_minutes", 120))
                words = mins * 150
                text = (
                    f"📖  Exhaustive with {mins}-min cap (~{words:,} words max)\n"
                    f"The LLM covers everything but stays under {mins} minutes."
                )
            else:
                text = (
                    "📖  Exhaustive (unlimited)\n"
                    "The LLM covers ALL key points with no length limit.\n"
                    "⚠️  Large books may produce very long scripts (2+ hours)."
                )

        hosts = int(c.get_setting("podcast.hosts", 2))
        scope = c.get_setting("podcast.scope", "per_chapter")  # V7.6.0 R6
        text += f"\n\nFormat: {hosts}-host · {scope.replace('_', ' ')}"

        fillers = c.get_setting("podcast.human_fillers", True)
        if fillers:
            text += " · human fillers ON"

        self.estimate_label.setText(text)

    def save(self) -> None:
        pass

    def reload(self) -> None:
        self._update_estimate()
