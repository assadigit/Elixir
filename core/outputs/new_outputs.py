"""

V4.0.0: New output types — Executive Briefing, Podcast Script, Flashcards.

Each class takes the chapter summaries and uses the Summarizer's LLM
infrastructure to generate a new output format. All outputs are saved
as Markdown files in the output directory.

B3: Executive Briefing — one-page synthesis of all chapter summaries
B1: Podcast Script — conversational 2-host discussion of key ideas
B2: Flashcards — Anki-compatible TSV + Q&A cards from keypoints
"""

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

from core.models import ConversionRequest, SummaryResult
from core.system.timeouts import LLM_REQUEST_TIMEOUT_S

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

logger = logging.getLogger(__name__)


class OutputGeneratorBase:
    """Base class for output generators. Provides LLM call infrastructure."""

    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)

        # Reuse the Summarizer's LLM settings
        from utils.settings import Settings

        settings = Settings()
        self.provider = settings.get("summarisation.provider", "ollama")
        self.primary_model = request.summarisation_model
        self.ollama_base_url = (
            settings.get_ollama_url()
        )  # V18.20.4.3 (W-c9): was hardcoded localhost
        # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
        from core.system.secrets import get_secret

        self.api_key = get_secret("summarisation.api_key", settings, "")
        self.api_base_url = settings.get(
            "summarisation.api_base_url", "https://openrouter.ai/api/v1"
        )
        self.cloud_model = settings.get("summarisation.cloud_model", "")
        self.temperature = 0.4  # Slightly creative for briefing/podcast; 0.2 for flashcards

        # V16.0.4: shared PromptManager for all output generators
        from core.summarisation.prompt_manager import PromptManager

        self.prompt_manager = PromptManager()

    def _call_llm(
        self, prompt: str, temperature: float | None = None, max_tokens: int = 4096
    ) -> str | None:
        """Call the LLM using the same provider as the Summarizer.

        V10.13.0 (A3): Added retry logic — retries 2x on failure (timeout,
        empty response, connection error) before giving up.  Each retry has
        a 3-second backoff.  This prevents a single LLM timeout from killing
        an entire output type.
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            result = self._call_llm_once(prompt, temperature, max_tokens)
            if result and result.strip():
                return result
            if attempt < max_retries:
                self.log(
                    f"    ⚠️ LLM call failed (attempt {attempt + 1}/{max_retries + 1}) "
                    f"— retrying in 3s…",
                    "WARNING",
                )
                time.sleep(3)
            else:
                self.log(
                    f"    ❌ LLM call failed after {max_retries + 1} attempts",
                    "ERROR",
                )
        return None

    def _call_llm_once(
        self, prompt: str, temperature: float | None = None, max_tokens: int = 4096
    ) -> str | None:
        """Single LLM call (no retry). Called by _call_llm."""
        temp = temperature if temperature is not None else self.temperature

        if self.provider == "ollama":
            return self._call_ollama(prompt, temp, max_tokens)
        elif self.provider in ("openrouter", "openai", "openai_compatible"):
            return self._call_openai_compat(prompt, temp, max_tokens)
        elif self.provider == "freellmapi":
            # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext).
            from core.system.secrets import get_secret
            from utils.settings import Settings

            s = Settings()
            return self._call_openai_compat(
                prompt,
                temp,
                max_tokens,
                base_url=s.get("summarisation.freellmapi_url", "http://localhost:3001/v1"),
                api_key=get_secret("summarisation.freellmapi_key", s, ""),
                model=s.get("summarisation.freellmapi_model", "auto"),
            )
        return None

    def _call_ollama(self, prompt: str, temp: float, max_tokens: int) -> str | None:
        """Call local Ollama."""
        try:
            from utils.network import safe_ollama_request

            payload = {
                "model": self.primary_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temp,
                    "num_predict": max_tokens,
                    "num_ctx": max(self.request.summarisation_max_context_tokens, 8000),
                },
            }
            url = f"{self.ollama_base_url}/api/generate"
            resp = safe_ollama_request("POST", url, json=payload, timeout=LLM_REQUEST_TIMEOUT_S)
            return resp.json().get("response", "").strip()
        except Exception as e:
            self.log(f"  ⚠️ Ollama call failed: {e}", "WARNING")
            return None

    def _call_openai_compat(
        self, prompt: str, temp: float, max_tokens: int, base_url=None, api_key=None, model=None
    ) -> str | None:
        """Call OpenAI-compatible API."""
        # V18.20.4.11 (P3 / O-c5): pooled transport + shape-safe parse
        # (replaces bare requests.post + deep-index; a malformed provider
        # payload now returns "" → falsy → callers treat as failure, same
        # as the old KeyError → except → None path but without the noise).
        from utils.network import extract_openai_content, session_for_url

        base_url = base_url or self.api_base_url
        api_key = api_key or self.api_key
        model = model or self.cloud_model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "max_tokens": max_tokens,
        }
        try:
            resp = session_for_url(base_url).post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=LLM_REQUEST_TIMEOUT_S,
            )
            resp.raise_for_status()
            return extract_openai_content(resp.json())
        except Exception as e:
            self.log(f"  ⚠️ API call failed: {e}", "WARNING")
            return None

    def _strip_thinking(self, text: str) -> str:
        """Strip <think>/<thinking> blocks from LLM output."""
        if not text:
            return text
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        text = re.sub(r"<think>(?!.*</think>).*$", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<thinking>(?!.*</thinking>).*$", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()


# ════════════════════════════════════════════════════════════════════════════
# B3: Executive Briefing
# ════════════════════════════════════════════════════════════════════════════


class ExecutiveBriefingGenerator(OutputGeneratorBase):
    """B3: Generate a one-page executive briefing synthesizing all chapters."""

    def generate(
        self, summaries: list[SummaryResult], book_title: str, output_dir: Path
    ) -> Path | None:
        """Generate a single-page executive briefing from all chapter summaries.

        Feeds all executive summaries into one LLM call and asks for a
        synthesized 500-word briefing.
        """
        # Collect all successful chapter summaries
        # V10.0.0 Fix 2: Include ALL successful chapters, not just those with
        # executive_summary.  Also include thorough_summary as fallback when
        # exec_summary is empty (academic-rigor mode often produces only
        # thorough_summary + bullets, no exec_summary).
        chapter_summaries = []
        all_bullets = []
        for s in summaries:
            if s.success:
                # Use exec_summary, or fall back to thorough_summary if empty
                summary_text = s.executive_summary or s.thorough_summary or ""
                if summary_text:
                    chapter_summaries.append(f"## {s.chapter_heading}\n{summary_text}")
                if s.bullet_points:
                    all_bullets.extend(s.bullet_points)

        if not chapter_summaries:
            self.log("  ℹ️ Briefing: No chapter summaries to synthesize.", "INFO")
            return None

        self.log(
            f"  📄 Generating executive briefing from {len(chapter_summaries)} chapters…", "INFO"
        )

        # Build the prompt
        chapters_text = "\n\n".join(chapter_summaries[:20])  # cap at 20 chapters
        bullets_text = "\n".join(f"- {bp}" for bp in all_bullets[:50])  # top 50 bullets

        prompt = self.prompt_manager.render_template(
            "outputs/executive_briefing",
            book_title=book_title,
            chapters_text=chapters_text,
            bullets_text=bullets_text,
        )

        response = self._call_llm(prompt, temperature=0.3, max_tokens=8192)
        if not response:
            self.log("  ⚠️ Briefing: No response from LLM — using fallback", "WARNING")
            response = self._fallback_briefing(chapter_summaries, all_bullets, book_title)

        response = self._strip_thinking(response)
        if not response or not response.strip():
            self.log("  ⚠️ Briefing: Empty response — using fallback", "WARNING")
            response = self._fallback_briefing(chapter_summaries, all_bullets, book_title)

        # V10.12.7: Truncation detection — if the response doesn't end with
        # sentence-ending punctuation (. ! ? : " ' ) ]), it was likely
        # truncated by the max_tokens limit.  Retry once with 16384.
        # V10.12.6's check required len > 200, but the truncation can leave
        # a very short fragment (e.g. "This" = 4 chars).  V10.12.7 removes
        # the length floor — any non-punctuated ending triggers the retry.
        if response:
            _stripped = response.rstrip()
            if _stripped and not _stripped.endswith((".", "!", "?", ":", '"', "'", ")", "]")):
                self.log(
                    f"  ⚠️ Briefing: response appears truncated (ends with "
                    f"'{_stripped[-20:]}' — no terminal punctuation) — retrying with 16384 max_tokens",
                    "WARNING",
                )
                _retry = self._call_llm(prompt, temperature=0.3, max_tokens=16384)
                if _retry:
                    _retry = self._strip_thinking(_retry)
                    if _retry and len(_retry) > len(response):
                        response = _retry
                        self.log(f"  ✅ Briefing: retry produced {len(response)} chars", "INFO")

        # Build the markdown output
        md_content = f"""# Executive Briefing: {book_title}

> A one-page synthesis of the book's core thesis, key frameworks, and actionable takeaways.

---

{response}

---

*Generated from {len(chapter_summaries)} chapter summaries.*
"""

        output_path = output_dir / f"{book_title}.Briefing.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        atomic_write_text(output_path, md_content, encoding="utf-8")
        self.log(f"  ✅ Executive briefing saved to: {output_path}", "SUCCESS")
        return output_path

    @staticmethod
    def _fallback_briefing(chapter_summaries, bullets, book_title):
        """Deterministic fallback when the LLM fails — builds a briefing
        directly from the chapter summaries and keypoints."""
        lines = ["**Executive Briefing (auto-generated fallback)**\n"]

        # Core thesis from first chapter summary
        if chapter_summaries:
            first = chapter_summaries[0]
            # Extract just the text after the heading
            thesis = first.split("\n", 1)[-1].strip() if "\n" in first else first
            lines.append(f"**Core Thesis:** {thesis[:500]}\n")

        # Key points (top 10 bullets)
        lines.append("**Key Points:**\n")
        for i, bp in enumerate(bullets[:10], 1):
            bp_clean = bp.strip().lstrip("-•* ").strip()
            lines.append(f"{i}. {bp_clean}")
        lines.append("")

        # Additional takeaways
        if len(bullets) > 10:
            lines.append("**Additional Takeaways:**\n")
            for i, bp in enumerate(bullets[10:15], 1):
                bp_clean = bp.strip().lstrip("-•* ").strip()
                lines.append(f"{i}. {bp_clean}")

        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# B1: Podcast Script
# ════════════════════════════════════════════════════════════════════════════


class PodcastScriptGenerator(OutputGeneratorBase):
    """B1: Generate a conversational podcast script from keypoints."""

    def generate(
        self, summaries: list[SummaryResult], book_title: str, output_dir: Path
    ) -> Path | None:
        """Generate a 10-minute podcast script with two hosts discussing key ideas."""
        # Collect all bullets
        all_bullets = []
        for s in summaries:
            if s.success and s.bullet_points:
                all_bullets.extend(s.bullet_points)

        if not all_bullets:
            self.log("  ℹ️ Podcast: No keypoints to discuss.", "INFO")
            return None

        self.log(f"  🎙️ Generating podcast script from {len(all_bullets)} keypoints…", "INFO")

        # Cap bullets to keep prompt manageable
        bullets_text = "\n".join(f"- {bp}" for bp in all_bullets[:40])

        prompt = self.prompt_manager.render_template(
            "outputs/podcast_script",
            book_title=book_title,
            bullets_text=bullets_text,
        )

        response = self._call_llm(prompt, temperature=0.5, max_tokens=4096)
        if not response:
            self.log("  ⚠️ Podcast: No response from LLM.", "WARNING")
            return None

        response = self._strip_thinking(response)

        # Build the markdown output
        md_content = f"""# Podcast Script: {book_title}

> A conversational discussion of the book's key ideas. ~10 minutes.

---

{response}

---

*Generated from {len(all_bullets)} keypoints across {len(summaries)} chapters.*
"""

        output_path = output_dir / f"{book_title}.Podcast.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        atomic_write_text(output_path, md_content, encoding="utf-8")
        self.log(f"  ✅ Podcast script saved to: {output_path}", "SUCCESS")
        return output_path


# ════════════════════════════════════════════════════════════════════════════
# B2: Flashcards (Anki-compatible)
# ════════════════════════════════════════════════════════════════════════════


class FlashcardGenerator(OutputGeneratorBase):
    """B2: Generate Anki-compatible flashcards from keypoints.

    V10.1.0: When ``judge_results`` is supplied (from the Content Judge with
    Layer 8 grounding), each flashcard gains an ``evidence`` field containing
    the verbatim source span that grounds the keypoint.  The TSV gains a 4th
    column (Anki "Extra" field) and the readable MD gains a 🛡️ evidence line.
    """

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
        judge_results: list | None = None,
    ) -> Path | None:
        """Generate flashcards in Anki TSV format (importable directly into Anki).

        Generates both Q&A cards and cloze deletion cards.
        Output: BookName.Flashcards.txt (TSV: front<TAB>back<TAB>tags<TAB>extra)
        """
        # Collect all bullets
        all_bullets = []
        for s in summaries:
            if s.success and s.bullet_points:
                for bp in s.bullet_points:
                    all_bullets.append((s.chapter_heading, bp))

        if not all_bullets:
            self.log("  ℹ️ Flashcards: No keypoints to generate from.", "INFO")
            return None

        self.log(f"  🎴 Generating flashcards from {len(all_bullets)} keypoints…", "INFO")

        # V10.1.0: Build an evidence lookup from judge_results.
        # Each JudgeResult.bullet_evidence maps bullet-text → verbatim source
        # snippet (from langextract char_interval).  When a keypoint has a
        # Layer 8 evidence span, the resulting flashcard carries it as the
        # "Extra" field (4th TSV column) so Anki shows the proof.
        evidence_lookup = {}  # normalized bullet text → snippet
        if judge_results:
            for jr in judge_results:
                if jr is None:
                    continue
                be = getattr(jr, "bullet_evidence", {}) or {}
                for bp_text, snippet in be.items():
                    if snippet:
                        norm = re.sub(r"\s+", " ", bp_text.lower().strip())
                        evidence_lookup[norm] = snippet

        # Build a sanitized book title for tags
        book_tag = re.sub(r"[^a-zA-Z0-9_]", "_", book_title).lower()

        # Batch the bullets for LLM processing (max 20 per call)
        batch_size = 20
        all_flashcards = []  # V10.1.0: List of (front, back, tags, evidence) tuples

        for i in range(0, len(all_bullets), batch_size):
            batch = all_bullets[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(all_bullets) + batch_size - 1) // batch_size
            self.log(f"    🎴 Processing flashcard batch {batch_num}/{total_batches}…", "INFO")

            # Build the prompt
            bullets_list = "\n".join(
                f"{j + 1}. [{chap[:30]}] {bp}" for j, (chap, bp) in enumerate(batch)
            )

            prompt = self.prompt_manager.render_template(
                "outputs/flashcards",
                bullets_list=bullets_list,
            )

            response = self._call_llm(prompt, temperature=0.2, max_tokens=2048)
            if not response:
                self.log(f"    ⚠️ Batch {batch_num}: No response, skipping.", "WARNING")
                continue

            response = self._strip_thinking(response)

            # V4.3.0: Much more tolerant parser. The model returns flashcards
            # in several formats; we try each in priority order:
            #   1. Q<TAB>A              (original spec)
            #   2. Q: ... A: ...        (label format, with optional bold **)
            #   3. Q: ... \n A: ...     (multi-line, handled per-line below)
            #   4. **Q:** ... **A:** ... (markdown bold labels)
            #   5. Question: ... Answer: ...
            #   6. First sentence ending in "?" → Q, rest → A
            # V10.12.8: track the card index within this batch for evidence
            # lookup. The LLM may not produce cards in the same order as the
            # keypoints, so this is a best-effort mapping (capped at batch size).
            _card_idx = 0
            for line in response.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Remove leading numbering like "1. " or "1) "
                line = re.sub(r"^\d+[\.\)]\s*", "", line)
                # Remove leading bullet markers
                line = re.sub(r"^[-\*]\s*", "", line)

                parts = self._parse_flashcard_line(line)
                if parts is None:
                    continue

                q, a = parts
                if q and a and len(q) > 3 and len(a) > 3:
                    chapter_tag = re.sub(r"[^a-zA-Z0-9_]", "", batch[0][0][:20]).lower()
                    tags = f"book::{book_tag} chapter::{chapter_tag}"
                    # V10.1.0: look up evidence for the source keypoint.
                    # V10.12.8: use _card_idx (was bare 'j' which was only
                    # in the list-comprehension scope — NameError at runtime).
                    src_bp = batch[_card_idx][1] if _card_idx < len(batch) else ""
                    src_norm = re.sub(r"\s+", " ", src_bp.lower().strip())
                    evidence = evidence_lookup.get(src_norm, "")
                    all_flashcards.append((q, a, tags, evidence))
                    _card_idx += 1

            time.sleep(0.5)  # brief pause between batches

        # V4.3.0: Deterministic fallback — if the LLM failed to produce any
        # parseable cards, generate simple cloze-style cards directly from
        # the keypoints. This ensures flashcards are NEVER a total failure
        # (unlike V4.0.0 which returned None and produced no file).
        if not all_flashcards:
            self.log(
                "  ℹ️ Flashcards: LLM parsing yielded no cards — "
                "generating deterministic fallback cards from keypoints.",
                "INFO",
            )
            all_flashcards = self._fallback_flashcards(all_bullets, book_tag, evidence_lookup)

        if not all_flashcards:
            self.log("  ⚠️ Flashcards: No valid cards generated.", "WARNING")
            return None

        # Write TSV file (Anki import format)
        output_path = output_dir / f"{book_title}.Flashcards.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        # V10.1.0: count how many cards have evidence for the log
        evidenced = sum(1 for c in all_flashcards if c[3])
        with open(output_path, "w", encoding="utf-8") as f:
            # Anki TSV header comment
            f.write("#separator:tab\n")
            f.write("#html:false\n")
            f.write("#tags column:3\n")
            # V10.1.0: 4 columns when evidence is present (front/back/tags/extra)
            if evidenced > 0:
                f.write("#notes have 4 fields: front, back, tags, extra (evidence)\n")
            f.write("\n")
            for q, a, tags, evidence in all_flashcards:
                # Escape any tabs/newlines in content
                q_clean = q.replace("\t", " ").replace("\n", " ")
                a_clean = a.replace("\t", " ").replace("\n", " ")
                ev_clean = (evidence or "").replace("\t", " ").replace("\n", " ")
                if evidenced > 0:
                    f.write(f"{q_clean}\t{a_clean}\t{tags}\t{ev_clean}\n")
                else:
                    f.write(f"{q_clean}\t{a_clean}\t{tags}\n")

        self.log(
            f"  ✅ Flashcards saved to: {output_path} ({len(all_flashcards)} cards"
            + (f", {evidenced} with 🛡️ evidence" if evidenced else "")
            + ")",
            "SUCCESS",
        )

        # Also write a readable Markdown version
        md_path = output_dir / f"{book_title}.Flashcards.md"
        md_content = f"""# Flashcards: {book_title}

> {len(all_flashcards)} question-answer pairs. Import the .txt file into Anki (File → Import).

"""
        if evidenced > 0:
            md_content += (
                f"> 🛡️ {evidenced} card(s) include verbatim source evidence (Layer 8 grounding).\n"
            )
        md_content += "\n---\n\n"
        for i, (q, a, tags, evidence) in enumerate(all_flashcards, 1):
            md_content += f"**Card {i}**\n\n"
            md_content += f"- **Q:** {q}\n"
            md_content += f"- **A:** {a}\n"
            md_content += f"- *Tags: {tags}*\n"
            if evidence:
                md_content += f'- 🛡️ **Evidence:** "{evidence[:300]}"\n'
            md_content += "\n---\n\n"

        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        atomic_write_text(md_path, md_content, encoding="utf-8")
        self.log(f"  ✅ Flashcards (readable) saved to: {md_path}", "SUCCESS")

        # V10.22.1: Also export as .apkg if genanki is available
        try:
            from core.outputs.anki_export import export_anki_deck

            export_anki_deck(all_flashcards, book_title, output_dir, log_callback=self.log)
        except Exception as e:
            self.log(f"  ℹ️ Anki .apkg export skipped: {e}", "DEBUG")

        return output_path

    # ── V4.3.0 helper methods ──────────────────────────────────────────────

    @staticmethod
    def _parse_flashcard_line(line: str):
        """Try every known flashcard format; return (question, answer) or None.

        V4.3.0: Replaces the old tab-only parser. The LLM returns cards in
        wildly different formats across batches; this tries each in priority
        order until one matches.
        """
        # Strip markdown bold markers for easier matching (**Q:** → Q:)
        stripped = re.sub(r"\*\*", "", line)

        # 1. Tab-separated: "Q<TAB>A"
        if "\t" in stripped:
            parts = stripped.split("\t", 1)
            q = parts[0].lstrip("Qq:").strip()
            a = parts[1].lstrip("Aa:").strip()
            return (q, a) if q and a else None

        # 2. "Q: ... A: ..." (label format, any case)
        m = re.match(r"^Q\s*[:\-]\s*(.+?)\s+A\s*[:\-]\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), m.group(2).strip())

        # 3. "Question: ... Answer: ..."
        m = re.match(r"^Question\s*[:\-]\s*(.+?)\s+Answer\s*[:\-]\s*(.+)$", stripped, re.IGNORECASE)
        if m:
            return (m.group(1).strip(), m.group(2).strip())

        # 4. First sentence ending in "?" → Q, rest → A
        m = re.match(r"^(.+?\?)\s+(.+)$", stripped)
        if m:
            q = m.group(1).strip()
            a = m.group(2).strip()
            # Sanity: the answer shouldn't be another question
            if not a.endswith("?"):
                return (q, a)

        return None

    @staticmethod
    def _fallback_flashcards(all_bullets, book_tag, evidence_lookup=None):
        """Deterministic fallback: generate cloze-style cards from keypoints.

        If the LLM failed to produce any parseable cards, we turn each
        keypoint into a simple "What does the book say about X?" card where
        X is the first noun phrase (first few words). This guarantees
        flashcards are never a total failure.

        V10.1.0: accepts an optional evidence_lookup so fallback cards also
        carry the 🛡️ evidence field.
        """
        cards = []
        evidence_lookup = evidence_lookup or {}
        for chap, bp in all_bullets:
            bp_clean = bp.strip().lstrip("-•* ").strip()
            if len(bp_clean) < 15:
                continue
            # Take the first 5-8 words as the "topic"
            words = bp_clean.split()
            topic_len = min(8, max(5, len(words) // 3))
            topic = " ".join(words[:topic_len]).rstrip(",.;:")
            # Build a simple Q/A
            q = f"What does the book say about: {topic}?"
            a = bp_clean
            chapter_tag = re.sub(r"[^a-zA-Z0-9_]", "", chap[:20]).lower()
            tags = f"book::{book_tag} chapter::{chapter_tag}"
            # V10.1.0: evidence lookup
            norm = re.sub(r"\s+", " ", bp.lower().strip())
            evidence = evidence_lookup.get(norm, "")
            cards.append((q, a, tags, evidence))
        return cards


# ════════════════════════════════════════════════════════════════════════════
# V10.17.0 (F1): Q&A Generator — open-ended question-answer pairs per chapter
# ════════════════════════════════════════════════════════════════════════════


class QAGenerator(OutputGeneratorBase):
    """V10.17.0 (F1): Generate open-ended Q&A pairs from chapter summaries.

    Unlike flashcards (which test recall with cloze-style cards), the Q&A
    generator produces open-ended study questions that test understanding:
    "Explain the mechanism of...", "Compare and contrast...", "Why does..."

    Output format: Markdown file with Q&A pairs grouped by chapter.
    """

    def generate(
        self, summaries: list[SummaryResult], book_title: str, output_dir: Path
    ) -> Path | None:
        """Generate Q&A pairs from chapter summaries.

        For each chapter, the LLM is asked to generate 5-10 open-ended
        questions with model answers based on the chapter's summary.
        """
        chapter_qa = []
        for s in summaries:
            if not s.success:
                continue
            summary_text = s.executive_summary or s.thorough_summary or ""
            if not summary_text or len(summary_text) < 50:
                continue

            # Build the prompt
            prompt = self.prompt_manager.render_template(
                "outputs/qa_pairs",
                chapter_heading=s.chapter_heading,
                summary_text=summary_text[:4000],
            )

            response = self._call_llm(prompt, temperature=0.3, max_tokens=4096)
            if not response:
                self.log(f"  ⚠️ Q&A: No response for '{s.chapter_heading[:40]}'", "WARNING")
                continue

            response = self._strip_thinking(response)
            # Parse Q&A pairs
            qa_pairs = self._parse_qa_pairs(response)
            if qa_pairs:
                chapter_qa.append((s.chapter_heading, qa_pairs))
                self.log(
                    f"  ❓ Q&A: {len(qa_pairs)} pairs for '{s.chapter_heading[:40]}'",
                    "INFO",
                )

        if not chapter_qa:
            self.log("  ℹ️ Q&A: No questions generated.", "INFO")
            return None

        # Build the markdown output
        total_q = sum(len(qa) for _, qa in chapter_qa)
        md_lines = [
            f"# Study Questions: {book_title}",
            "",
            f"**{total_q} questions across {len(chapter_qa)} chapter(s)**",
            "",
            "---",
            "",
        ]

        for chapter_heading, qa_pairs in chapter_qa:
            md_lines.append(f"## {chapter_heading}")
            md_lines.append("")
            for i, (q, a) in enumerate(qa_pairs, 1):
                md_lines.append(f"**Q{i}: {q}**")
                md_lines.append("")
                md_lines.append(f"A: {a}")
                md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

        md_content = "\n".join(md_lines)
        output_path = output_dir / f"{book_title}.StudyQuestions.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # V18.20.4.12 (T-c3): atomic — disk-full can't leave a partial output file.
        atomic_write_text(output_path, md_content, encoding="utf-8")
        self.log(f"  ✅ Q&A saved to: {output_path}", "SUCCESS")
        return output_path

    def _parse_qa_pairs(self, text: str) -> list[tuple]:
        """Parse LLM response into [(question, answer), ...] pairs.

        Handles formats:
        - Q: ... A: ... (label format)
        - **Q:** ... **A:** ... (markdown bold)
        - Question: ... Answer: ... (long form)
        - Numbered: 1. Q ... A ...
        """
        pairs = []
        # Split on Q: or Question: markers
        blocks = re.split(
            r"(?:^|\n)(?:\d+[\.\)]\s*)?(?:\*\*)?(?:Q|Question)(?:\*\*)?\s*[:\.]\s*", text
        )

        for block in blocks[1:]:  # skip the first (before the first Q:)
            block = block.strip()
            if not block:
                continue
            # Split on A: or Answer: marker
            a_match = re.search(
                r"(?:\n\s*)(?:\*\*)?(?:A|Answer)(?:\*\*)?\s*[:\.]\s*",
                block,
                re.IGNORECASE,
            )
            if a_match:
                question = block[: a_match.start()].strip()
                answer = block[a_match.end() :].strip()
                # Clean up
                question = re.sub(r"^\d+[\.\)]\s*", "", question)
                question = re.sub(r"\*+", "", question).strip()
                answer = re.sub(r"\*+", "", answer).strip()
                if question and answer and len(question) > 5 and len(answer) > 5:
                    # Take only the first paragraph of the answer
                    answer = answer.split("\n\n")[0].strip()
                    pairs.append((question, answer))

        return pairs
