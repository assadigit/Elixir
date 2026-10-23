"""V4.2.0 / V7.6.0 R2: Podcast Audio generator (intro podcast from briefing).

V7.6.0 R2 REBUILD: the old flow (read full podcast script → synth every line)
was broken (generated nothing).  The user's proposal: take the book's
executive briefing, turn it into a short engaging 2-host intro podcast via
NeuTTS, one per conversion.  This is faster, more reliable, and matches the
"introduce the book in an engaging way" goal.

New flow:
  1. Locate the executive briefing file (``{book}.Briefing.md``) — if it
     doesn't exist, generate a short brief from the summaries via LLM.
  2. Ask the LLM to rewrite the briefing as a 2-host dialogue (~600-900
     words, ~4-6 minutes spoken).
  3. Strip stage directions / music cues (V7.6.0 R6).
  4. Synthesize each Host A/B line via the TTS router (NeuTTS primary).
  5. Stitch into one ``{book}.IntroPodcast.wav``.

Dependencies (unchanged):
    kokoro, misaki[en], soundfile          → English TTS (fallback)
    TTS (Coqui XTTS v2)                    → Persian TTS (V0.6.64: Piper removed)
    pydub, ffmpeg (optional, for mp3)      → audio stitching
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase
from core.tts.engine import TTSRouter, detect_language

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

# Regex for "Host A:" / "Host B:" / "HostA:" / "A:" prefixes.

logger = logging.getLogger(__name__)

_HOST_LINE_RE = re.compile(
    r"^\s*(?:Host\s*)?([ABa b])\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
_SPEAKER_LINE_RE = re.compile(
    r"^\s*(?:Speaker|Host)\s*([12])\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)


def _parse_speaker_line(line: str) -> tuple[str, str] | None:
    """Return ``(speaker, text)`` if ``line`` is a dialogue line, else None."""
    m = _HOST_LINE_RE.match(line)
    if m:
        speaker = m.group(1).strip().upper().replace(" ", "")
        return (speaker, m.group(2).strip())
    m = _SPEAKER_LINE_RE.match(line)
    if m:
        speaker = "A" if m.group(1) == "1" else "B"
        return (speaker, m.group(2).strip())
    return None


def _split_long_line(text: str, max_chars: int = 280) -> list[str]:
    """Split a line longer than ``max_chars`` on sentence boundaries."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts = re.split(r"(?<=[\.!?۔])\s+", text)
    chunks: list[str] = []
    current = ""
    for p in parts:
        if not p:
            continue
        if len(current) + len(p) + 1 <= max_chars:
            current = (current + " " + p).strip() if current else p
        else:
            if current:
                chunks.append(current)
            while len(p) > max_chars:
                chunks.append(p[:max_chars])
                p = p[max_chars:].lstrip()
            current = p
    if current:
        chunks.append(current)
    return chunks


class PodcastAudioGenerator(OutputGeneratorBase):
    """V7.6.0 R2: Generate a short intro podcast from the book's executive briefing.

    Replaces the old full-script audio flow (which was broken).  Produces one
    ``{book}.IntroPodcast.wav`` per conversion — a 4-6 minute 2-host
    introduction to the book, synthesised via NeuTTS (or Kokoro fallback).
    """

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> list[Path] | None:
        """Generate one intro podcast audio file from the book briefing.

        Returns a list with one path (the .wav), or empty on failure.
        """
        # ── 1. Locate or generate the briefing ───────────────────────────
        # V7.6.0 R2: the briefing lives in briefing/{book}.Briefing.md
        # (V7.5.0 subfolder layout).  Fall back to the legacy flat location.
        briefing_path = output_dir / f"{book_title}.Briefing.md"
        if not briefing_path.exists():
            # Try the briefing/ subfolder (V7.5.0 layout)
            briefing_path = output_dir / "briefing" / f"{book_title}.Briefing.md"
        if not briefing_path.exists():
            # Generate a brief on-the-fly from the summaries
            self.log(
                "  ℹ️ No briefing file found — generating a short brief "
                "from summaries for the intro podcast…",
                "INFO",
            )
            briefing_text = self._build_briefing_from_summaries(summaries, book_title)
            if not briefing_text:
                self.log("  ⚠️ Cannot build intro podcast: no briefing content", "WARNING")
                return []
        else:
            briefing_text = briefing_path.read_text(encoding="utf-8")
            # Strip markdown headers/quotes for the LLM prompt
            briefing_text = re.sub(r"^#.*$", "", briefing_text, flags=re.MULTILINE)
            briefing_text = re.sub(r"^>.*$", "", briefing_text, flags=re.MULTILINE)
            briefing_text = briefing_text.strip()

        # ── 2. Generate the 2-host intro dialogue via LLM ────────────────
        self.log("  🎙️ Generating 2-host intro podcast script from briefing…", "INFO")
        script = self._generate_intro_dialogue(briefing_text, book_title)
        if not script:
            self.log("  ⚠️ Intro podcast script generation failed", "WARNING")
            return []

        # V7.6.0 R6: strip stage directions + music cues
        script = self._strip_stage_directions(script)

        # Save the intro script for reference (so the user can see what was spoken)
        script_path = output_dir / f"{book_title}.IntroPodcast.md"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            script_path,
            f"# Intro Podcast Script: {book_title}\n\n"
            f"> 2-host introduction (~4-6 min) · generated from executive briefing\n\n---\n\n"
            f"{script}\n",
            encoding="utf-8",
        )
        self.log(f"  📝 Intro script saved: {script_path.name}", "DEBUG")

        # ── 3. Parse + synthesize ─────────────────────────────────────────
        segments = self._parse_dialogue(script)
        if not segments:
            self.log("  ⚠️ No dialogue lines parsed from intro script", "WARNING")
            return []
        self.log(f"  🎙️ Synthesizing {len(segments)} segments via TTS…", "INFO")

        # Load TTS settings
        # V0.6.8 (audit B18): the Windows-path defaults are single-sourced
        # in the Settings defaults registry (utils/settings.py:791-793) —
        # Settings._load() deep-merges the defaults under the user data, so
        # these keys ALWAYS resolve without inline fallbacks. The re-declared
        # literals here could silently drift from the registry (the audit's
        # W5 duplication); they are gone. The "" fallbacks keep the type
        # contract if the registry ever drops a key — the TTS layer's
        # missing-binary handling takes over from there.
        from utils.settings import Settings

        s = Settings()
        host_a_voice = s.get("tts.host_a_voice", "")
        host_b_voice = s.get("tts.host_b_voice", "")
        en_voice = s.get("tts.en_voice", "af_heart")
        # V0.6.64: the Piper default voice id is gone with the engine — the
        # empty default means "use the Coqui speaker" (CoquiTTSEngine falls
        # back to its configured speaker when the voice string is empty).
        fa_voice = s.get("tts.fa_voice", "")
        speed = float(s.get("tts.speed", 1.0))
        en_engine = s.get("tts.en_engine", "neutts")
        neutts_gguf = s.get("tts.neutts_gguf_path", "")
        neutts_project = s.get("tts.neutts_project_path", "")

        # Resolve voices (same logic as before — ensures A ≠ B)
        host_a_voice, host_b_voice = self._resolve_host_voices(
            en_engine, host_a_voice, host_b_voice, en_voice
        )

        self.log(
            f"     EN engine: {en_engine} | Host A: {host_a_voice} | "
            f"Host B: {host_b_voice} | speed: {speed}×",
            "DEBUG",
        )

        router = TTSRouter(
            en_engine=en_engine,
            neutts_gguf_path=Path(neutts_gguf) if neutts_gguf else None,
            neutts_project_path=Path(neutts_project) if neutts_project else None,
            coqui_model=s.get("tts.coqui_model", "tts_models/multilingual/multi-dataset/xtts_v2"),
            coqui_speaker=s.get("tts.coqui_speaker", "Ana"),
            coqui_voice_sample=s.get("tts.coqui_voice_sample", ""),
            log_callback=self.log,
        )

        normalizer = None
        try:
            from core.tts.normalizer import create_normalizer_from_settings

            normalizer = create_normalizer_from_settings(log_callback=self.log)
            if normalizer:
                self.log("  ✨ Text normalization enabled", "INFO")
        except Exception as e:
            self.log(f"  ⚠️ Normalizer init failed ({e}), using raw text", "DEBUG")

        # ── 4. Synthesize each segment → stitch into one WAV ─────────────
        output_path = output_dir / f"{book_title}.IntroPodcast.wav"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_segments: list[Path] = []
        with _TempDir() as tmp:
            for idx, (speaker, text) in enumerate(segments, 1):
                chunks = _split_long_line(text, max_chars=280)
                if not chunks:
                    continue
                lang = detect_language(chunks[0])
                voice = self._resolve_voice(
                    speaker,
                    lang,
                    host_a_voice,
                    host_b_voice,
                    en_voice,
                    fa_voice,
                    en_engine,
                )
                if normalizer:
                    chunks = [normalizer.normalize(c, lang) for c in chunks]
                seg_path = Path(tmp) / f"seg_{idx:04d}.wav"
                self.log(
                    f"  [{idx}/{len(segments)}] {speaker} ({lang}) → {voice}: {text[:60]}…",
                    "INFO",
                )
                if len(chunks) == 1:
                    result = router.synthesize(chunks[0], seg_path, lang, voice, speed)
                    if result:
                        audio_segments.append(result)
                else:
                    chunk_paths: list[Path] = []
                    for ci, chunk in enumerate(chunks):
                        cp = Path(tmp) / f"seg_{idx:04d}_{ci:02d}.wav"
                        r = router.synthesize(chunk, cp, lang, voice, speed)
                        if r:
                            chunk_paths.append(r)
                    if chunk_paths:
                        self._concat_wavs(chunk_paths, seg_path)
                        audio_segments.append(seg_path)

            if not audio_segments:
                self.log("  ⚠️ No audio segments generated", "WARNING")
                return []

            self.log(f"  🔀 Stitching {len(audio_segments)} segments → {output_path.name}…", "INFO")
            try:
                self._concat_wavs(audio_segments, output_path)
            except Exception as e:
                self.log(f"  ⚠️ Stitch failed ({e})", "WARNING")
                return []

        self.log(f"  ✅ {output_path.name} ({output_path.stat().st_size // 1024} KB)", "SUCCESS")
        return [output_path]

    # ── V7.6.0 R2: intro dialogue generation ─────────────────────────────

    def _build_briefing_from_summaries(
        self, summaries: list[SummaryResult], book_title: str
    ) -> str:
        """Build a short briefing from summaries when no briefing file exists."""
        parts = [f"Book: {book_title}"]
        for s in summaries[:10]:  # cap at 10 chapters
            if s.executive_summary:
                parts.append(f"\n{s.chapter_heading}:\n{s.executive_summary[:300]}")
        return "\n".join(parts)

    def _generate_intro_dialogue(self, briefing_text: str, book_title: str) -> str | None:
        """Ask the LLM to rewrite the briefing as a 2-host intro podcast.

        Targets ~600-900 words (~4-6 minutes spoken).  Strict format: only
        Host A / Host B lines, no stage directions, no music cues.
        """
        # Cap the briefing input to avoid huge prompts
        briefing = briefing_text[:3000]
        prompt = self.prompt_manager.render_template(
            "outputs/podcast_audio_intro",
            book_title=book_title,
            briefing=briefing,
        )
        response = self._call_llm(prompt, temperature=0.6, max_tokens=4096)
        if not response:
            return None
        return self._strip_thinking(response)

    def _parse_dialogue(self, script: str) -> list[tuple[str, str]]:
        """Parse a 2-host dialogue script into ``[(speaker, text), …]``."""
        segments: list[tuple[str, str]] = []
        for raw in script.splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ">", "---")):
                continue
            # Strip markdown bold
            line_clean = re.sub(r"\*+", "", line).strip()
            parsed = _parse_speaker_line(line_clean)
            if parsed:
                speaker, text = parsed
                if text:
                    segments.append((speaker, text))
        return segments

    def _strip_stage_directions(self, script: str) -> str:
        """Remove ``[...]`` stage directions + music cues (V7.6.0 R6)."""
        lines = script.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            no_bold = re.sub(r"\*+", "", stripped).strip()
            if no_bold.startswith("[") and no_bold.endswith("]"):
                continue
            if re.match(r"^(music|sfx|sound|soundtrack)\s*:", no_bold, re.IGNORECASE):
                continue
            line = re.sub(r"\s*\[[^\]]*\]\s*", " ", line)
            line = re.sub(r"  +", " ", line).strip()
            if line:
                cleaned.append(line)
        return "\n".join(cleaned)

    def _resolve_host_voices(
        self, en_engine: str, host_a: str, host_b: str, en_voice: str
    ) -> tuple[str, str]:
        """Resolve + deduplicate host voices (ensures A ≠ B)."""
        from core.tts.voices import KOKORO_VOICES

        kokoro_ids = {v[0] for v in KOKORO_VOICES}

        if en_engine == "kokoro":
            if not host_a or host_a not in kokoro_ids:
                host_a = "am_michael"
            if not host_b or host_b not in kokoro_ids:
                host_b = "af_heart"
        else:  # neutts
            if not host_a:
                host_a = "dave"
            if not host_b:
                host_b = "jo"

        # Ensure distinct
        if host_a == host_b:
            if en_engine == "kokoro":
                host_b = "af_heart" if host_a != "af_heart" else "am_michael"
            else:
                from core.tts.voice_manager import VoiceManager

                vm = VoiceManager(log_callback=self.log)
                all_voices = [v["name"] for v in vm.list_voices() if v["has_wav"]]
                for alt in all_voices:
                    if alt != host_a:
                        host_b = alt
                        break
                if host_a == host_b:
                    host_b = "af_heart"  # Kokoro fallback for Host B
            self.log(
                f"  🔀 Host A and Host B had the same voice — switched Host B to {host_b}",
                "WARNING",
            )
        return host_a, host_b

    def _resolve_voice(
        self,
        speaker: str,
        lang: str,
        host_a: str,
        host_b: str,
        en_voice: str,
        fa_voice: str,
        en_engine: str,
    ) -> str:
        """Pick the right voice for a speaker given the detected language."""
        from core.tts.voices import KOKORO_VOICES

        kokoro_ids = {v[0] for v in KOKORO_VOICES}
        host_voice = host_a if speaker == "A" else host_b

        if lang == "fa":
            # V0.6.64: Persian routes to Coqui XTTS v2 — the voice string is
            # the Coqui speaker name (empty = the configured coqui_speaker).
            return fa_voice
        # English
        if en_engine == "kokoro":
            if host_voice in kokoro_ids:
                return host_voice
            return en_voice or "af_heart"
        # NeuTTS
        if host_voice and host_voice not in kokoro_ids:
            return host_voice
        return "dave"

    def _concat_wavs(self, wav_paths: list[Path], out_path: Path) -> None:
        """Concatenate WAV files into one using pydub (falls back to wave)."""
        try:
            from pydub import AudioSegment

            combined = AudioSegment.empty()
            for wp in wav_paths:
                seg = AudioSegment.from_wav(str(wp))
                combined += seg
            combined.export(str(out_path), format="wav")
            return
        except ImportError:
            pass
        import wave as _wave

        if not wav_paths:
            return
        with _wave.open(str(wav_paths[0]), "rb") as first:
            params = first.getparams()
        with _wave.open(str(out_path), "wb") as out:
            out.setparams(params)
            for wp in wav_paths:
                with _wave.open(str(wp), "rb") as w:
                    out.writeframes(w.readframes(w.getnframes()))


class _TempDir:
    """Context manager wrapper around tempfile.TemporaryDirectory (Path-y)."""

    def __enter__(self) -> str:
        import tempfile

        self._d = tempfile.mkdtemp(prefix="tts_")
        return self._d

    def __exit__(self, *exc) -> None:
        import shutil

        shutil.rmtree(self._d, ignore_errors=True)
