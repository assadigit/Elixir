"""V4.6.0: Parameterized podcast script generator.

Replaces the hardcoded V4.0.0 ``PodcastScriptGenerator`` with a fully
configurable generator that supports:

* **Format**: 1-host monologue or 2-host dialogue
* **Scope**: full-book (one podcast) or per-chapter (N podcasts)
* **Depth**: exhaustive (cover everything, optional 2hr cap) or
  time-restricted (15/30/45/60 min)
* **Style**: tone (serious/conversational/fun), intro hook, outro conclusion
* **Human fillers**: optional breathing, "hmm", "yeah" etc. for a
  NotebookLM-like natural feel (works best with NeuTTS)

The prompt is built dynamically by :class:`PodcastPromptBuilder` based on
the settings. The generator produces one or more ``.Podcast.md`` files
depending on the scope setting.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

# ── Word-count estimation ─────────────────────────────────────────────────
# Spoken English averages ~150 words/minute. Used for target-length prompts
# and the runtime preview in settings.

logger = logging.getLogger(__name__)

_WPM = 150


def minutes_to_words(minutes: int) -> int:
    """Estimate word count for a given podcast duration in minutes."""
    return minutes * _WPM


def words_to_minutes(words: int) -> int:
    """Estimate podcast duration in minutes from word count."""
    return max(1, words // _WPM)


# ── Prompt builder ────────────────────────────────────────────────────────


class PodcastPromptBuilder:
    """Builds a dynamic LLM prompt from podcast configuration settings.

    All methods return strings (prompt fragments) that are composed into
    the final prompt by :meth:`build`.
    """

    def __init__(
        self,
        hosts: int = 2,  # 1 or 2
        depth_mode: str = "exhaustive",  # "exhaustive" or "time_restricted"
        target_minutes: int = 30,  # for time_restricted
        exhaustive_cap_minutes: int = 120,  # 2hr safety cap
        exhaustive_cap_enabled: bool = True,
        tone: str = "conversational",  # "serious" / "conversational" / "fun"
        include_intro: bool = True,
        include_outro: bool = True,
        human_fillers: bool = False,
    ) -> None:
        self.hosts = hosts
        self.depth_mode = depth_mode
        self.target_minutes = target_minutes
        self.exhaustive_cap_minutes = exhaustive_cap_minutes
        self.exhaustive_cap_enabled = exhaustive_cap_enabled
        self.tone = tone
        self.include_intro = include_intro
        self.include_outro = include_outro
        self.human_fillers = human_fillers

    def build(self, keypoints_text: str, book_title: str, chapter_label: str | None = None) -> str:
        """Build the complete prompt.

        Args:
            keypoints_text: the key points to cover (one per line, "- ...")
            book_title: the book's title
            chapter_label: if per-chapter, the chapter heading (else None)
        """
        scope_label = chapter_label or "the book"

        parts = []
        parts.append(self._format_instructions(scope_label))
        parts.append(self._depth_instructions())
        parts.append(self._style_instructions())
        parts.append(self._structure_instructions())
        parts.append(self._filler_instructions())

        parts.append(f"\nKey Points from {scope_label}:\n{keypoints_text}")
        parts.append(f"\nPodcast Script (for '{book_title}'):")
        return "\n".join(parts)

    def _format_instructions(self, scope_label: str) -> str:
        """Instructions for 1-host vs 2-host format.

        V10.1.11: Strengthened the Host A/B requirement.  The TTS engine
        (Kokoro/NeuTTS) ONLY recognizes 'Host A:' and 'Host B:' prefixes.
        Random names (John, Julia, Sarah) cause the TTS to either skip
        the line or read the name aloud.  The prompt now explicitly
        forbids any speaker label other than 'Host A:' / 'Host B:'.
        """
        if self.hosts == 1:
            return (
                f"Write a podcast script where a SINGLE narrator discusses the "
                f"key ideas from {scope_label}. The narrator speaks in a flowing, "
                f"engaging monologue. Do NOT use 'Host A:' or 'Host B:' labels — "
                f"write it as continuous narration with natural paragraph breaks. "
                f"Occasionally ask rhetorical questions to engage the listener."
            )
        else:
            return (
                f"Write a podcast script where TWO hosts discuss the key ideas "
                f"from {scope_label}. Alternate between 'Host A:' and 'Host B:'. "
                f"Host A is a curious learner who asks questions and reacts. "
                f"Host B is an expert who explains concepts with examples. "
                f"Keep the conversation natural and engaging.\n\n"
                f"CRITICAL — SPEAKER LABELS (the TTS engine requires this exact format):\n"
                f"- EVERY dialogue line MUST start with 'Host A:' or 'Host B:'\n"
                f"- Do NOT use any other speaker label — no 'John:', no 'Julia:', "
                f"no 'Sarah:', no 'Speaker 1:', no 'Narrator:', no 'Interviewer:', "
                f"no 'Expert:', no 'Learner:', no person names of any kind.\n"
                f"- The ONLY valid labels are 'Host A:' and 'Host B:' (with the "
                f"colon, capitalized exactly as shown).\n"
                f"- Do NOT include music cues (e.g. [Intro music], [Upbeat music], "
                f"[Outro music]) — the TTS engine cannot speak music.\n"
                f"- Do NOT include sound effects (e.g. [Applause], [Laughter], "
                f"[Bell rings]) — the TTS engine would read them aloud.\n"
                f"- Do NOT include stage directions in brackets (e.g. [pause], "
                f"[whispering], [excited]) — use punctuation instead.\n"
                f"- Output ONLY dialogue lines starting with 'Host A:' or 'Host B:'."
            )

    def _depth_instructions(self) -> str:
        """Instructions for exhaustive vs time-restricted depth."""
        if self.depth_mode == "time_restricted":
            target_words = minutes_to_words(self.target_minutes)
            return (
                f"\nLENGTH CONSTRAINT: Fit the most important ideas into "
                f"approximately {self.target_minutes} minutes (~{target_words} "
                f"words). Prioritize the highest-impact concepts. Be concise — "
                f"skip minor details. Do not exceed {target_words} words."
            )
        else:
            # Exhaustive
            if self.exhaustive_cap_enabled and self.exhaustive_cap_minutes > 0:
                cap_words = minutes_to_words(self.exhaustive_cap_minutes)
                return (
                    f"\nDEPTH: Cover ALL the key ideas thoroughly. Do not omit "
                    f"important concepts. Be comprehensive and detailed. "
                    f"However, keep the total under {self.exhaustive_cap_minutes} "
                    f"minutes (~{cap_words} words) as a safety cap."
                )
            else:
                return (
                    "\nDEPTH: Cover ALL the key ideas thoroughly. Do not omit "
                    "important concepts. Be comprehensive and detailed. There "
                    "is no length limit — be as thorough as needed to cover "
                    "everything."
                )

    def _style_instructions(self) -> str:
        """Instructions for tone."""
        tone_map = {
            "serious": (
                "TONE: Maintain a serious, professional tone throughout. Focus "
                "on clarity, accuracy, and depth. No jokes or casual language."
            ),
            "conversational": (
                "TONE: Use a conversational, engaging tone. Make it feel like "
                "a natural discussion between interested people. Accessible but "
                "informative. Include occasional relatable examples and analogies."
            ),
            "fun": (
                "TONE: Use a fun, engaging, and authentic tone. Make it feel "
                "like two friends having a real conversation:\n"
                "- Use SARCASM and wit sparingly but naturally\n"
                "- Include RELATABLE EXAMPLES that are grounded in the source "
                "material (do NOT invent personal anecdotes or lived experiences)\n"
                "- Add natural LAUGHTER cues like 'Haha, exactly!' or "
                "'That's hilarious but also true'\n"
                "- Use playful disagreement ('No way, I completely disagree "
                "— but let me hear you out')\n"
                "- Make the listener feel like they're eavesdropping on a "
                "genuine, entertaining conversation\n"
                "Keep it educational but entertaining. Don't force humor — "
                "let it arise naturally from the material.\n"
                "ANTI-HALLUCINATION: Do NOT invent personal anecdotes, lived "
                "experiences, or hypothetical scenarios. All examples must be "
                "grounded in the source keypoints. The hosts can be playful, "
                "but their claims must be factual."
            ),
        }
        return "\n" + tone_map.get(self.tone, tone_map["conversational"])

    def _structure_instructions(self) -> str:
        """Instructions for intro hook + outro conclusion."""
        parts = []
        if self.include_intro:
            parts.append(
                "STRUCTURE: Start with a compelling hook — a surprising fact, a "
                "thought-provoking question, or a brief scenario that draws the "
                "listener in. Then introduce the topic naturally."
            )
        if self.include_outro:
            parts.append(
                "End with a brief conclusion: summarize the single most important "
                "takeaway, and end with a call-to-action or reflective question "
                "for the listener."
            )
        if parts:
            return "\n" + "\n".join(parts)
        return ""

    def _filler_instructions(self) -> str:
        """Instructions for human-like fillers (NotebookLM-style)."""
        if not self.human_fillers:
            return (
                "\nOUTPUT: Output ONLY the script. Do not output thinking "
                "process, explanations, or stage directions in brackets."
            )

        # Human fillers enabled — make it sound natural like NotebookLM
        if self.hosts == 2:
            return (
                "\nNATURAL DELIVERY (human-like fillers): Make the conversation "
                "sound like a real podcast. Include occasional natural fillers:\n"
                "- Reactions: 'Yeah', 'Exactly', 'Oh, that's interesting', 'Right'\n"
                "- Hesitations: 'Hmm', 'Well...', 'You know'\n"
                "- Backchanneling: 'Mm-hmm', 'Right, right' (from the listening host)\n"
                "- Natural pauses: use '...' for a thoughtful pause\n"
                "- Agreement: 'That's a great point', 'I never thought of it that way'\n"
                "Use these SPARINGLY (1-2 per minute) to sound natural, not "
                "distracting. Do NOT use bracketed stage directions like [pause] "
                "or [breathes] — use actual words and punctuation.\n"
                "OUTPUT: Output ONLY the script with natural fillers. No "
                "thinking process or meta-commentary."
            )
        else:
            return (
                "\nNATURAL DELIVERY (human-like fillers): Make the narration "
                "sound like a real person talking, not reading. Include "
                "occasional natural fillers:\n"
                "- Hesitations: 'Hmm', 'Well...', 'You know'\n"
                "- Self-correction: 'Actually...', 'Or rather...'\n"
                "- Emphasis: 'Now, here's the thing', 'And this is key'\n"
                "- Natural pauses: use '...' for a thoughtful pause\n"
                "Use these SPARINGLY (1-2 per minute) to sound natural, not "
                "distracting. Do NOT use bracketed stage directions.\n"
                "OUTPUT: Output ONLY the script with natural fillers. No "
                "thinking process or meta-commentary."
            )


# ── Generator ─────────────────────────────────────────────────────────────


class PodcastGenerator(OutputGeneratorBase):
    """V4.6.0: Configurable podcast script generator.

    Produces one or more ``.Podcast.md`` files based on the podcast
    settings (format, scope, depth, length, style). Reads all configuration
    from ``podcast.*`` settings keys via the Settings singleton.
    """

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> list[Path] | None:
        """Generate podcast script(s) and return list of output paths.

        Returns a list (may be empty on failure, or contain 1 path for
        full-book scope, or N paths for per-chapter scope).
        """
        from utils.settings import Settings

        s = Settings()

        # Read all podcast settings
        hosts = int(s.get("podcast.hosts", 2))
        # V7.6.0 R6: default scope changed to per_chapter — the user wants
        # one podcast script file per chapter, not one big chapterized file.
        scope = s.get("podcast.scope", "per_chapter")
        depth_mode = s.get("podcast.depth_mode", "exhaustive")
        target_minutes = int(s.get("podcast.target_minutes", 30))
        exhaustive_cap_minutes = int(s.get("podcast.exhaustive_cap_minutes", 120))
        exhaustive_cap_enabled = s.get("podcast.exhaustive_cap_enabled", True)
        tone = s.get("podcast.tone", "conversational")
        include_intro = s.get("podcast.include_intro", True)
        include_outro = s.get("podcast.include_outro", True)
        human_fillers = s.get("podcast.human_fillers", False)

        builder = PodcastPromptBuilder(
            hosts=hosts,
            depth_mode=depth_mode,
            target_minutes=target_minutes,
            exhaustive_cap_minutes=exhaustive_cap_minutes,
            exhaustive_cap_enabled=exhaustive_cap_enabled,
            tone=tone,
            include_intro=include_intro,
            include_outro=include_outro,
            human_fillers=human_fillers,
        )

        # Gather successful chapters
        chapters = [s for s in summaries if s.success]
        if not chapters:
            self.log("  ℹ️ Podcast: No chapter summaries available.", "INFO")
            return []

        output_paths: list[Path] = []

        if scope == "per_chapter":
            # Generate one podcast per chapter
            self.log(
                f"  🎙️ Generating per-chapter podcasts ({len(chapters)} "
                f"chapters, {hosts}-host, {depth_mode})…",
                "INFO",
            )
            for idx, chapter in enumerate(chapters, 1):
                chapter_label = chapter.chapter_heading or f"Chapter {idx}"
                # Sanitize chapter number for filename
                ch_tag = f"Ch{idx:02d}"
                output_path = output_dir / f"{book_title}.{ch_tag}.Podcast.md"

                keypoints = self._chapter_keypoints(chapter)
                if not keypoints:
                    self.log(f"    ⏭️  {ch_tag}: no keypoints, skipping", "DEBUG")
                    continue

                self.log(f"    🎙️ {ch_tag}: {chapter_label[:50]}…", "INFO")
                # V4.7.21: Pass keypoints list for coverage verification
                kp_list = [
                    bp.strip().lstrip("-•* ").strip() for bp in chapter.bullet_points if bp.strip()
                ]
                script = self._generate_one(
                    builder,
                    keypoints,
                    book_title,
                    chapter_label,
                    keypoints_list=kp_list,
                )
                if script:
                    self._write_script(
                        output_path, script, book_title, chapter_label, len(chapters), hosts
                    )
                    output_paths.append(output_path)
        else:
            # Full-book: one podcast from all chapters
            self.log(f"  🎙️ Generating full-book podcast ({hosts}-host, {depth_mode})…", "INFO")
            all_keypoints = self._all_keypoints(chapters)
            if not all_keypoints:
                self.log("  ℹ️ Podcast: No keypoints to discuss.", "INFO")
                return []

            # V4.7.21: Build keypoints list for coverage verification
            all_kp_list = []
            for s in chapters:
                if s.bullet_points:
                    for bp in s.bullet_points:
                        bp_clean = bp.strip().lstrip("-•* ").strip()
                        if bp_clean:
                            all_kp_list.append(bp_clean)

            # V7.1.0 S11: Batched podcast generation for full-book scope.
            # If there are more than 25 keypoints, split into batches of ~20,
            # generate a script segment per batch, add transition lines,
            # then stitch into one cohesive script. This ensures full coverage
            # instead of the LLM only processing the first ~10% of keypoints.
            BATCH_SIZE = 20
            if len(all_kp_list) > 25:
                self.log(
                    f"  📦 V7.1.0 S11: Batched generation — {len(all_kp_list)} keypoints "
                    f"in batches of {BATCH_SIZE}",
                    "INFO",
                )
                batches = []
                for i in range(0, len(all_kp_list), BATCH_SIZE):
                    batch_kps = all_kp_list[i : i + BATCH_SIZE]
                    batches.append(batch_kps)

                all_segments = []
                for batch_idx, batch_kps in enumerate(batches):
                    self.log(
                        f"    📦 Batch {batch_idx + 1}/{len(batches)}: {len(batch_kps)} keypoints",
                        "INFO",
                    )
                    # Build keypoints text for this batch
                    batch_keypoints_text = "\n".join(f"- {kp}" for kp in batch_kps)
                    # V7.6.0 R6: removed the [Intro]/[Transition]/[Outro] bracket
                    # markers — they're stage directions the TTS can't speak, and
                    # the user asked to keep only Host A/B dialogue.  The LLM
                    # prompt already handles intro hook + outro conclusion via
                    # _structure_instructions (spoken content, not brackets).

                    batch_kp_list = batch_kps
                    script_segment = self._generate_one(
                        builder,
                        batch_keypoints_text,
                        book_title,
                        None,
                        keypoints_list=batch_kp_list if batch_kp_list else None,
                    )
                    if script_segment:
                        all_segments.append(script_segment)
                        self.log(
                            f"    ✅ Batch {batch_idx + 1}: "
                            f"{len(batch_kps)}/{len(batch_kps)} keypoints covered",
                            "INFO",
                        )
                    else:
                        self.log(f"    ⚠️ Batch {batch_idx + 1}: generation failed", "WARNING")

                # V7.6.0 R6: no [Outro] bracket — the LLM's outro conclusion
                # (from _structure_instructions) is spoken by the hosts.
                # Stitch all segments
                script = "\n\n".join(all_segments) if all_segments else None
            else:
                # Small enough for single pass
                script = self._generate_one(
                    builder,
                    all_keypoints,
                    book_title,
                    None,
                    keypoints_list=all_kp_list if all_kp_list else None,
                )
            if script:
                output_path = output_dir / f"{book_title}.Podcast.md"
                self._write_script(output_path, script, book_title, None, len(chapters), hosts)
                output_paths.append(output_path)

        if output_paths:
            self.log(f"  ✅ Podcast: {len(output_paths)} script(s) generated", "SUCCESS")
        return output_paths

    def _chapter_keypoints(self, chapter: SummaryResult) -> str:
        """Format one chapter's keypoints as a bullet list."""
        lines = []
        if chapter.executive_summary:
            lines.append(f"Chapter: {chapter.chapter_heading}")
            lines.append(f"Summary: {chapter.executive_summary.strip()}")
        if chapter.bullet_points:
            lines.append("Key Points:")
            for bp in chapter.bullet_points:
                bp_clean = bp.strip().lstrip("-•* ").strip()
                if bp_clean:
                    lines.append(f"- {bp_clean}")
        return "\n".join(lines)

    def _all_keypoints(self, chapters: list[SummaryResult]) -> str:
        """Format all chapters' keypoints (capped for prompt size)."""
        lines = []
        for s in chapters:
            if s.bullet_points:
                lines.append(f"## {s.chapter_heading}")
                for bp in s.bullet_points:
                    bp_clean = bp.strip().lstrip("-•* ").strip()
                    if bp_clean:
                        lines.append(f"- {bp_clean}")
                lines.append("")
        return "\n".join(lines)

    def _generate_one(
        self,
        builder: PodcastPromptBuilder,
        keypoints_text: str,
        book_title: str,
        chapter_label: str | None,
        keypoints_list: list[str] | None = None,
    ) -> str | None:
        """Generate one podcast script via the LLM.

        V4.7.21: If keypoints_list is provided, runs coverage verification
        after generation. If coverage < 90%, sends the script back for
        revision (up to 2 passes).
        """
        prompt = builder.build(keypoints_text, book_title, chapter_label)
        response = self._call_llm(prompt, temperature=0.5, max_tokens=8192)
        if not response:
            self.log("  ⚠️ Podcast: No response from LLM.", "WARNING")
            return None
        script = self._strip_thinking(response)

        # V4.7.21: Coverage verification + gap-fill retry
        if keypoints_list and len(keypoints_list) > 0:
            from core.outputs.podcast_coverage import PodcastCoverageChecker

            checker = PodcastCoverageChecker(self.request, log_callback=self.log)

            for attempt in range(3):  # initial + 2 revisions
                report = checker.verify(script, keypoints_list)

                if report.is_complete:
                    self.log("  ✅ All keypoints covered!", "SUCCESS")
                    break

                if not report.needs_revision or attempt >= 2:
                    self.log(
                        f"  ⚠️ Coverage at {report.percentage:.0f}% — "
                        f"{len(report.missing)} keypoints still missing after "
                        f"{attempt} revision(s). Proceeding with best effort.",
                        "WARNING",
                    )
                    break

                # Revise
                revised = checker.revise(script, report.missing, book_title)
                if revised and len(revised) > len(script) * 0.5:
                    script = revised
                    self.log(f"  🔄 Revision {attempt + 1} applied — re-checking coverage…", "INFO")
                else:
                    self.log(
                        "  ⚠️ Revision produced no improvement — keeping original script", "WARNING"
                    )
                    break

            # Append coverage report to the script
            script = script + checker.build_report_markdown(report)

        return script

    def _write_script(
        self,
        path: Path,
        script: str,
        book_title: str,
        chapter_label: str | None,
        chapter_count: int,
        hosts: int,
    ) -> None:
        """Write the script to a .md file with a header."""
        scope_desc = f"Chapter: {chapter_label}" if chapter_label else "Full book"
        format_desc = f"{hosts}-host" if hosts == 2 else "1-host monologue"

        header = (
            f"# Podcast Script: {book_title}"
            + (f" — {chapter_label}" if chapter_label else "")
            + f"\n\n"
            f"> {format_desc} · {scope_desc} · {chapter_count} chapter(s)\n\n"
            f"---\n\n"
        )
        # V7.6.0 R6: strip residual bracketed stage directions the LLM may
        # have emitted despite instructions (e.g. [Intro music], [pause]).
        # Keep only Host A/B dialogue lines + plain narration.
        cleaned = self._strip_stage_directions(script)
        path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        atomic_write_text(path, header + cleaned.strip() + "\n", encoding="utf-8")
        self.log(f"  ✅ Podcast script saved: {path.name}", "SUCCESS")

    # V7.6.0 R6: strip bracketed stage directions + music cues from the script.
    # V10.1.11: also normalize speaker labels to Host A/B + strip ALL non-dialogue.
    def _strip_stage_directions(self, script: str) -> str:
        """Remove ``[...]`` stage directions, music cues, and sound-effect lines.

        V10.1.11: Now also normalizes speaker labels.  If the LLM emitted
        'John:', 'Julia:', 'Speaker 1:', 'Narrator:', or any other label,
        this converts them to 'Host A:' / 'Host B:' so the TTS engine
        (Kokoro/NeuTTS) can parse them correctly.

        Also strips:
        - Music cues: [Intro music], [Upbeat music], [Outro], etc.
        - Sound effects: [Applause], [Laughter], [Bell rings], etc.
        - Stage directions: [pause], [whispering], [excited], etc.
        - Markdown headers (#, ##, ###)
        - Horizontal rules (---)
        - Scene dividers (* * *)
        - Any line that isn't a Host A/B dialogue line or plain narration
        """
        lines = script.splitlines()
        cleaned = []
        _last_speaker = "A"  # track alternation for normalizing unknown labels
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # ── Skip non-dialogue lines ────────────────────────────────
            # Skip markdown headers
            if stripped.startswith("#"):
                continue
            # Skip horizontal rules / scene dividers
            if re.match(r"^[\-\*_]{3,}$", stripped) or stripped == "* * *":
                continue
            # Skip lines that are entirely a bracketed stage direction
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            # Skip markdown bold-only divider lines
            no_bold = re.sub(r"\*+", "", stripped).strip()
            if no_bold.startswith("[") and no_bold.endswith("]"):
                continue
            # Skip music/SFX cue lines
            if re.match(
                r"^(music|sfx|sound|soundtrack|intro|outro|transition|fade)\s*:",
                no_bold,
                re.IGNORECASE,
            ):
                continue
            # Skip lines with music note symbols
            if "♪" in stripped or "♫" in stripped or "🎵" in stripped:
                continue

            # ── Normalize speaker labels ───────────────────────────────
            # V10.1.11: convert any "Name:" prefix to "Host A:" / "Host B:"
            # Check if this line has a speaker label (word(s) followed by colon)
            speaker_match = re.match(r"^([A-Z][\w\-\s]{0,30}):\s*(.+)$", stripped)
            if speaker_match:
                label = speaker_match.group(1).strip().lower()
                text = speaker_match.group(2).strip()

                # Normalize known labels
                if label in ("host a", "hosta", "a", "host 1", "speaker 1", "speaker1", "1"):
                    line = f"Host A: {text}"
                    _last_speaker = "A"
                elif label in ("host b", "hostb", "b", "host 2", "speaker 2", "speaker2", "2"):
                    line = f"Host B: {text}"
                    _last_speaker = "B"
                elif label in ("narrator", "narration", "voice", "announcer"):
                    # Narrator lines — assign to alternating host
                    if _last_speaker == "A":
                        line = f"Host B: {text}"
                        _last_speaker = "B"
                    else:
                        line = f"Host A: {text}"
                        _last_speaker = "A"
                else:
                    # Unknown speaker label (John, Julia, Sarah, Expert, etc.)
                    # Assign to alternating host
                    if _last_speaker == "A":
                        line = f"Host B: {text}"
                        _last_speaker = "B"
                    else:
                        line = f"Host A: {text}"
                        _last_speaker = "A"
            else:
                # No speaker label — this is plain narration
                # Inline-bracket removal: "Host A: [laughs] That's great" → "Host A: That's great"
                line = re.sub(r"\s*\[[^\]]*\]\s*", " ", line)
                # Remove music notes inline
                line = re.sub(r"[♪♫🎵]", "", line)

            # Collapse double spaces
            line = re.sub(r"  +", " ", line).strip()
            if line:
                cleaned.append(line)
        return "\n".join(cleaned)
