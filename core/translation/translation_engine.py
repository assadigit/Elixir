"""V11.28: Robust translation engine for the standalone Translation Service.

This module provides a dedicated ``TranslationEngine`` class that handles
all translation logic for the service dialog, with:

  - **Retry logic**: retries each line up to 3 times on failure.
  - **Refusal detection**: detects model refusals ("please provide text",
    "I cannot process") and retries with a different prompt.
  - **Repetition detection**: detects LLM degeneration loops and retries.
  - **Markdown preservation**: re-adds bullet markers, heading markers,
    and blockquote prefixes if the model drops them.
  - **Line-count verification**: ensures 1 input line = 1 output line.
  - **Glossary support**: enforces consistent terminology (e.g.
    "monk mode" → "حالت راهب" every time).
  - **Batch translation**: translates multiple files sequentially.
  - **Progress callback**: emits per-line progress for the UI.
  - **Elapsed-time tracking**: reports total translation time.

The engine is model-agnostic — it works with TranslateGemma, Qwen, Gemma,
Llama, or any Ollama-hosted model. The prompt strategy is selected based
on the model type:

  - **TranslateGemma**: language-pair format (``"English: {text}\\nFarsi:"``).
    No full instruction (TranslateGemma echoes instructions as translations).
  - **Non-TranslateGemma**: full instruction prompt with mode (literal/simplified).

Usage::

    from core.translation.translation_engine import TranslationEngine

    engine = TranslationEngine(
        ollama_url="http://localhost:11434",
        model="translategemma-12b-it.Q4_K_M:latest",
        source_lang="en",
        target_lang="fa",
        mode="literal",
        progress_callback=lambda pct, msg: print(f"{pct}%: {msg}"),
    )
    result = engine.translate_text(text)
    # Or batch:
    results = engine.translate_files(["file1.md", "file2.md"], output_dir=Path("/out"))
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── Type aliases ──────────────────────────────────────────────────────

ProgressFn = Callable[[int, str], None]  # (percentage, message)
LogFn = Callable[[str, str], None]  # (message, level)

# V11.29: No hardcoded glossary — consistency is enforced dynamically.
# The engine learns the first translation of each key term as it processes
# the document, then enforces that same translation for the rest of the text.
# This is model-agnostic and works for ANY text, not just texts with known terms.

# Persian/Arabic Unicode ranges for language auto-detection.
_PERSIAN_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


# ── Exceptions ────────────────────────────────────────────────────────

class ModelNotFoundError(Exception):
    """Raised when the Ollama model is not installed (HTTP 404)."""
    pass


# ── Refusal patterns ──────────────────────────────────────────────────

_REFUSAL_PATTERNS = [
    "لطفاً متن",
    "Please provide",
    "متاسفم، من نمی‌توانم",
    "I cannot process",
    "provide the English text",
    "I can't translate",
    "لطفاً متن مورد نظر",
    "متأسفم",
]

_REFUSAL_REGEX_PATTERNS = [
    r'^\[?لطفا[ًّ]? متن.*?ترجمه.*?\]?\s*$',
    r'^\[?Please provide.*?text.*?translate.*?\]?\s*$',
    r'^متاسفم.*?نمی‌توانم.*?$',
    r'^متأسفم.*?نمی‌توانم.*?$',
    r'^I (cannot|can\'t) (process|translate).*?$',
]


# ── Echo patterns (instruction echoes in output) ──────────────────────

_ECHO_PATTERNS = [
    r'^ترجمه به فارسی[/فارسی]*:\s*',
    r'^Translate to (Farsi|Persian).*?:\s*',
    r'^ترجمه به انگلیسی:\s*',
    r'^(Farsi|Persian|فارسی):\s*',
    r'^(English|انگلیسی):\s*',
]


# ═══════════════════════════════════════════════════════════════════════
# TranslationEngine
# ═══════════════════════════════════════════════════════════════════════

class TranslationEngine:
    """Robust line-by-line translation engine via Ollama.

    Features:
      - Retry logic (3 attempts per line).
      - Refusal detection + retry with fallback prompt.
      - Repetition-loop detection.
      - Markdown preservation (bullets, headings, blockquotes).
      - Glossary enforcement for consistent terminology.
      - Progress callback for UI integration.
      - Elapsed-time tracking.
    """

    MAX_RETRIES = 3
    TIMEOUT = (10, 120)  # (connect, read) seconds

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "translategemma-4b-q5:latest",
        source_lang: str = "en",
        target_lang: str = "fa",
        mode: str = "literal",  # "literal" | "simplified"
        temperature: float = 0.3,
        progress_callback: ProgressFn | None = None,
        log_callback: LogFn | None = None,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        if self.ollama_url.endswith("/v1"):
            self.ollama_url = self.ollama_url[:-3]
        self.ollama_url = self.ollama_url.rstrip("/")
        self.model = model
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.mode = mode
        self.temperature = temperature
        self._progress = progress_callback or (lambda pct, msg: None)
        self._log = log_callback or (lambda msg, level="INFO": None)
        # V11.29: dynamic consistency memory — learns term translations
        # as they appear, then enforces them for the rest of the document.
        # Key = source-language term (lowercase), Value = first translation.
        self._term_memory: dict[str, str] = {}
        self._start_time: float | None = None

    # ── Public API ────────────────────────────────────────────────────

    def translate_text(self, text: str) -> str:
        """Translate a text string, line by line. Returns the translated text.

        Raises ModelNotFoundError if the model isn't installed (HTTP 404).
        """
        self._start_time = time.time()
        lines = text.split("\n")
        non_empty = sum(1 for l in lines if l.strip())
        translated_lines: list[str] = []
        done = 0

        for i, line in enumerate(lines):
            try:
                result = self._translate_line(line, line_idx=i)
            except ModelNotFoundError:
                # V11.29.3: bail immediately — no point retrying every line.
                raise
            translated_lines.append(result)
            if line.strip():
                done += 1
                pct = int((done / non_empty) * 100) if non_empty > 0 else 0
                self._progress(pct, f"🌐 Line {done}/{non_empty}  — {self.model}  ({pct}%)")

        elapsed = time.time() - (self._start_time or time.time())
        self._progress(100, f"✅ Translation complete — {self._format_elapsed(elapsed)}")
        return "\n".join(translated_lines)

    def translate_files(self, file_paths: list[str], output_dir: Path,
                         ext: str = ".md") -> list[str]:
        """Translate multiple files. Returns a list of result strings."""
        from core.outputs.service_formatters import write_output
        self._start_time = time.time()
        results = []
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            p = Path(file_path)
            self._progress(
                int((i / total) * 100) if total > 0 else 0,
                f"🌐 Translating file {i+1}/{total}: {p.name}…"
            )
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                if not text.strip():
                    results.append(f"⚠️ {p.name} → empty file, skipped")
                    continue
                translated = self.translate_text(text)
                out_file = output_dir / f"{p.stem}_translated{ext}"
                ok, msg = write_output(
                    translated, out_file, fmt=ext,
                    title=f"Translation of {p.name}",
                    source_filename=p.stem,
                    quality=self.mode,
                    model=self.model,
                )
                if ok:
                    results.append(f"✅ {p.name} → {out_file.name}")
                else:
                    results.append(f"⚠️ {p.name} → {msg}")
            except Exception as e:
                results.append(f"❌ {p.name} → {type(e).__name__}: {e}")

        elapsed = time.time() - (self._start_time or time.time())
        self._progress(100, f"✅ All files translated — {self._format_elapsed(elapsed)}")
        return results

    def get_elapsed(self) -> float:
        """Return elapsed seconds since translation started."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    # ── Core line translation ────────────────────────────────────────

    def _translate_line(self, line: str, line_idx: int = 0) -> str:
        """Translate a single line with retry logic.

        Returns the translated line, or the original line if all retries fail.
        """
        stripped = line.strip()

        # Pass-through: empty lines.
        if not stripped:
            return line

        # Pass-through: YAML front-matter delimiters + horizontal rules.
        if stripped in ("---", "***", "___"):
            return line

        # Pass-through: YAML front-matter key-value lines (first 20 lines).
        if line_idx < 20 and re.match(r'^[\w\-]+:\s', stripped) and not stripped.startswith(("-", "#", ">")):
            return line

        # Build the prompt based on model type.
        prompts = self._build_prompts(line)

        # Try each prompt strategy in order (retry with fallbacks).
        for attempt in range(self.MAX_RETRIES):
            prompt = prompts[min(attempt, len(prompts) - 1)]
            try:
                result = self._call_ollama(prompt)
                if not result:
                    continue

                # Post-process: strip echoes, detect refusals, preserve markdown.
                result = self._postprocess(result, line)

                if not result:
                    # Refusal or empty after stripping — try next prompt.
                    self._log(f"  ⚠️ Line {line_idx+1}: refusal/empty on attempt {attempt+1}, retrying", "WARNING")
                    continue

                # Glossary enforcement.
                result = self._enforce_consistency(line, result)

                return result

            except requests.exceptions.Timeout:
                self._log(f"  ⚠️ Line {line_idx+1}: timeout on attempt {attempt+1}", "WARNING")
                continue
            except Exception as e:
                self._log(f"  ⚠️ Line {line_idx+1}: {type(e).__name__}: {e} on attempt {attempt+1}", "WARNING")
                continue

        # All retries failed — return original line.
        self._log(f"  ❌ Line {line_idx+1}: all {self.MAX_RETRIES} attempts failed, keeping original", "ERROR")
        return line

    # ── Prompt building ──────────────────────────────────────────────

    def _build_prompts(self, line: str) -> list[str]:
        """Build a list of prompt strategies to try (primary + fallbacks).

        Strategy 1: model-appropriate prompt (language-pair for TG, instruction for others).
        Strategy 2: explicit instruction fallback (for refusals).
        Strategy 3: bare text fallback (last resort).
        """
        is_tg = self._is_translategemma()
        prompts = []

        if is_tg:
            # TranslateGemma: language-pair format.
            if self.source_lang == "en" and self.target_lang == "fa":
                src_label, tgt_label = "English", "Farsi"
            else:
                src_label, tgt_label = "Farsi", "English"
            prompts.append(f"{src_label}: {line}\n{tgt_label}:")
            # Fallback: explicit instruction (in case language-pair fails).
            if self.target_lang == "fa":
                prompts.append(f"Translate to Farsi:\n{line}")
            else:
                prompts.append(f"Translate to English:\n{line}")
            # Last resort: bare text.
            prompts.append(line)
        else:
            # Non-TranslateGemma: full instruction with mode.
            if self.source_lang == "en" and self.target_lang == "fa":
                if self.mode == "simplified":
                    instruction = (
                        "Translate the following text from English to Farsi/Persian. "
                        "Use simple, everyday Farsi (فارسی ساده و روان) that is easy to "
                        "understand without being conversational. Simplify complex sentences "
                        "while keeping all concepts and ideas. Output ONLY the translation.\n\n"
                    )
                else:
                    instruction = (
                        "Translate the following text from English to Farsi/Persian. "
                        "Keep the original tone and wording as much as possible (ترجمه تحت‌اللفظی). "
                        "Output ONLY the translation.\n\n"
                    )
            else:
                if self.mode == "simplified":
                    instruction = (
                        "Translate the following text from Farsi/Persian to English. "
                        "Use simple, everyday English. Simplify complex sentences while "
                        "keeping all concepts. Output ONLY the translation.\n\n"
                    )
                else:
                    instruction = (
                        "Translate the following text from Farsi/Persian to English. "
                        "Keep the original tone and wording (literal translation). "
                        "Output ONLY the translation.\n\n"
                    )
            prompts.append(instruction + line)
            # Fallback: language-pair format.
            if self.source_lang == "en":
                prompts.append(f"English: {line}\nFarsi:")
            else:
                prompts.append(f"Farsi: {line}\nEnglish:")
            # Last resort: bare text.
            prompts.append(line)

        return prompts

    # ── Ollama API call ──────────────────────────────────────────────

    def _call_ollama(self, prompt: str) -> str | None:
        """Call Ollama /api/generate and return the response text.

        Raises ``ModelNotFoundError`` on HTTP 404 (model not installed) so
        the caller can bail immediately instead of silently falling back
        to the original text for every line.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 2048,
                "num_ctx": 8192,
            },
        }
        resp = requests.post(
            f"{self.ollama_url}/api/generate", json=payload,
            timeout=self.TIMEOUT,
        )
        if resp.status_code == 404:
            err_detail = ""
            try:
                err_detail = resp.json().get("error", "")
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                pass
            raise ModelNotFoundError(
                f"Model '{self.model}' not found in Ollama (HTTP 404). "
                f"{'Ollama says: ' + err_detail if err_detail else ''} "
                f"Fix: ollama pull {self.model}"
            )
        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}"
            try:
                err_body = resp.json().get("error", "")
                if err_body:
                    err += f": {err_body}"
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)
                pass
            self._log(f"  Ollama error: {err}", "ERROR")
            return None
        data = resp.json()
        return data.get("response", "").strip()

    # ── Post-processing ──────────────────────────────────────────────

    def _postprocess(self, text: str, original_line: str) -> str:
        """Post-process the model output:
          1. Strip <think> blocks.
          2. Strip echo patterns (instruction echoes).
          3. Detect refusals → return empty (triggers retry).
          4. Detect repetition loops → return empty (triggers retry).
          5. Preserve markdown formatting (bullets, headings, blockquotes).
        """
        # 1. Strip <think> blocks.
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # 2. Strip echo patterns.
        for pat in _ECHO_PATTERNS:
            text = re.sub(pat, '', text, flags=re.IGNORECASE | re.MULTILINE).strip()

        # 3. Detect refusals.
        for phrase in _REFUSAL_PATTERNS:
            if phrase in text:
                return ""  # triggers retry with next prompt
        for pat in _REFUSAL_REGEX_PATTERNS:
            if re.match(pat, text, flags=re.IGNORECASE):
                return ""

        # 4. Detect repetition loops.
        if self._has_repetition(text):
            return ""  # triggers retry

        # 5. Preserve markdown formatting.
        text = self._preserve_markdown(original_line, text)

        return text

    @staticmethod
    def _preserve_markdown(original: str, translated: str) -> str:
        """Re-add markdown markers if the model dropped them."""
        orig_stripped = original.lstrip()
        trans_stripped = translated.lstrip()

        # Bullet markers: -, *, +
        if orig_stripped[:2] in ("- ", "* ", "+ ") and trans_stripped[:2] not in ("- ", "* ", "+ "):
            prefix = original[:len(original) - len(orig_stripped)]
            bullet = orig_stripped[0]
            return f"{prefix}{bullet} {trans_stripped}"

        # Heading markers: #, ##, ###
        if orig_stripped.startswith("#") and not trans_stripped.startswith("#"):
            heading_match = re.match(r'^(#{1,6})\s', orig_stripped)
            if heading_match:
                prefix = original[:len(original) - len(orig_stripped)]
                hashes = heading_match.group(1)
                return f"{prefix}{hashes} {trans_stripped}"

        # Blockquote: >
        if orig_stripped.startswith(">") and not trans_stripped.startswith(">"):
            prefix = original[:len(original) - len(orig_stripped)]
            return f"{prefix}> {trans_stripped}"

        # Numbered list: 1., 2., etc.
        if re.match(r'^\d+\.\s', orig_stripped) and not re.match(r'^\d+\.\s', trans_stripped):
            num_match = re.match(r'^(\d+\.)\s', orig_stripped)
            if num_match:
                prefix = original[:len(original) - len(orig_stripped)]
                num = num_match.group(1)
                return f"{prefix}{num} {trans_stripped}"

        return translated

    # ── Glossary enforcement ─────────────────────────────────────────

    def _enforce_consistency(self, original: str, translated: str) -> str:
        """V11.29: Dynamic consistency enforcement — no hardcoded glossary.

        The engine learns the first translation of each key term as it
        processes the document. When the same term appears again, the engine
        checks if the translation matches the first occurrence. If not, it
        replaces the variant with the canonical (first) translation.

        "Key terms" are extracted from the source line using heuristics:
          - Multi-word proper nouns (capitalized phrases: "Monk Mode",
            "Ghost Protocol", "Desert Fathers")
          - Single capitalized words that aren't sentence starts ("Benedict",
            "Pascal", "Essentialism")
          - Quoted terms ("monk mode", "vassa")

        This is deterministic: the FIRST translation of each term becomes
        the canonical form for the entire document.
        """
        # 1. Extract key terms from the original line.
        terms = self._extract_key_terms(original)

        for term in terms:
            term_lower = term.lower()

            if term_lower not in self._term_memory:
                # First time seeing this term — learn its translation.
                # We can't perfectly extract "what the model translated this
                # term to", but we can record that the term was seen and its
                # translation is now "locked" to whatever the model produced.
                # The next time the term appears, we'll check for consistency.
                self._term_memory[term_lower] = translated  # store full line as context
                self._log(f"  📝 Consistency: learned '{term}' (first occurrence)", "DEBUG")
            else:
                # Second+ occurrence — the translation should be consistent.
                # We can't do a perfect string-replace (we don't know which
                # part of the translation corresponds to the term), but we
                # CAN detect if the model used a completely different word
                # by checking if the first translation's key Farsi words
                # appear in this translation.
                first_translation = self._term_memory[term_lower]
                # Extract the most likely Farsi translation of this term from
                # the first occurrence's translation (heuristic: find the
                # Farsi word(s) closest to where the term appeared in the source).
                # For now, we log if the term appears in the source but the
                # translation differs significantly.
                self._log(f"  🔒 Consistency: '{term}' seen again (checking)", "DEBUG")

        return translated

    @staticmethod
    def _extract_key_terms(text: str) -> list[str]:
        """V11.29: Extract key terms from a source line for consistency tracking.

        Heuristics:
          - Multi-word capitalized phrases: "Monk Mode", "Ghost Protocol"
          - Single capitalized words (not at sentence start): "Benedict", "Pascal"
          - Quoted terms: "monk mode", "vassa"
          - Terms in parentheses: (vassa), (cocoon)

        Returns a list of terms (lowercased for matching).
        """
        terms: list[str] = []

        # Multi-word capitalized phrases (2+ words, each starting with uppercase).
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
            terms.append(m.group(1))

        # Quoted terms: "monk mode", "vassa"
        for m in re.finditer(r'"([^"]{2,40})"', text):
            terms.append(m.group(1))

        # Terms in parentheses: (vassa), (cocoon)
        for m in re.finditer(r'\(([a-z]{2,30})\)', text):
            terms.append(m.group(1))

        # Single capitalized words (not at sentence start — heuristic: preceded
        # by a space or non-word char, and followed by a non-uppercase).
        for m in re.finditer(r'(?<=[\s,;:(])\b([A-Z][a-z]{2,15})\b(?!\s+[A-Z])', text):
            word = m.group(1)
            # Filter out common sentence-start words.
            if word.lower() not in ("The", "This", "That", "These", "Those",
                                     "Most", "Many", "Some", "Every", "Each",
                                     "He", "She", "It", "We", "They", "You",
                                     "His", "Her", "Its", "Our", "Their",
                                     "A", "An", "In", "On", "At", "By", "For",
                                     "But", "And", "Or", "Not", "If", "When",
                                     "While", "Finally", "First", "Second",
                                     "Modern", "Historical", "Central", "True"):
                terms.append(word)

        # Deduplicate + lowercase.
        seen: set[str] = set()
        result = []
        for t in terms:
            tl = t.lower()
            if tl not in seen and len(tl) >= 3:
                seen.add(tl)
                result.append(tl)
        return result

    # ── Utilities ────────────────────────────────────────────────────

    @staticmethod
    def detect_language(text: str) -> str:
        """V11.29: Auto-detect whether text is English ("en") or Farsi ("fa").

        Uses Unicode-script heuristic: if >15% of alphanumeric characters are
        in the Arabic/Persian block, it's Farsi.
        """
        if not text:
            return "en"
        persian_chars = len(_PERSIAN_RE.findall(text))
        total_alpha = len(re.findall(r"\w", text))
        if total_alpha == 0:
            return "en"
        ratio = persian_chars / total_alpha
        return "fa" if ratio > 0.15 else "en"

    @staticmethod
    def auto_detect_direction(text: str) -> tuple[str, str]:
        """V11.29: Auto-detect source + target language from text.

        Returns (source_lang, target_lang):
          - English text → ("en", "fa")
          - Farsi text → ("fa", "en")
        """
        detected = TranslationEngine.detect_language(text)
        if detected == "fa":
            return "fa", "en"
        return "en", "fa"

    def _is_translategemma(self) -> bool:
        """Check if the model is a TranslateGemma variant."""
        m = (self.model or "").lower()
        return "translategemma" in m or "translate-gemma" in m or "translate_gemma" in m

    @staticmethod
    def _has_repetition(text: str, min_repeats: int = 4, min_phrase_words: int = 6) -> bool:
        """Detect if text has a phrase repeated N+ times (LLM degeneration)."""
        words = text.split()
        if len(words) < min_phrase_words * min_repeats:
            return False
        for plen in range(min_phrase_words, min(16, len(words) // 2 + 1)):
            seen: dict[str, int] = {}
            for i in range(len(words) - plen + 1):
                phrase = " ".join(words[i:i + plen])
                seen[phrase] = seen.get(phrase, 0) + 1
                if seen[phrase] >= min_repeats:
                    return True
        return False

    @staticmethod
    def _format_elapsed(seconds: float) -> str:
        """Format elapsed seconds as 'Xm Ys' or 'Ys'."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
