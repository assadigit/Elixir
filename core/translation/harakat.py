"""Harakat generator — adds Persian diacritics (اعراب‌گذاری) for TTS.

Reuses the confidence-first prompt pattern from :mod:`core.tts.normalizer`.
The Farsi script omits short vowels; without harakat the TTS engine must
guess, and it guesses wrong often. This module adds:

  * Fatha (َ)  — "a" sound
  * Damma (ُ)  — "u" sound
  * Kasra (ِ)  — "i" sound
  * Sukun (ْ)  — no vowel
  * Shadda (ّ) — doubled consonant

**Confidence-first**: the LLM is instructed to add harakat ONLY where
confident. Wrong harakat is worse than no harakat.

This module produces the ``.harakat.md`` variant that feeds directly into
the Podcast Maker for Farsi audio generation.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable

# V18.20.4.12 (W-a11): /no_think gated on Qwen-family models via the
# shared helper — the directive is a Qwen3 soft-switch; for other models
# (e.g. the default TranslateGemma) it is prompt pollution.
from core.summarisation.filter_thinking import qwen_no_think

# V18.20.4.11 (P3 / O-c5): pooled LLM transport + shape-safe OpenAI-compat
# response extraction (replaces bare requests.post + deep-index parse).
from utils.network import extract_openai_content, session_for_url

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ── Harakat prompt (confidence-first, like the TTS normalizer) ───────────

_HARAKAT_PROMPT = """شما یک متخصص اعراب‌گذاری متن فارسی هستید. متن ورودی را دریافت کرده و \
تمام حرکاتِ اعراب (فتحه ـَ، ضمه ـُ، کسره ـِ، سکون ـْ، تشدید ـّ) را برای تلفظِ صحیح در TTS اضافه کنید.

قوانین:
۱. فقط جایی که مطمئن هستید اعراب بگذارید. اعراب غلط بدتر از هیچ اعرابی است.
۲. اعراب را روی حروف کلمات قرار دهید.
۳. کلماتی که شک دارید را بدون اعراب بگذارید.
۴. ساختار جمله و کلمات را تغییر ندهید — فقط اعراب اضافه کنید.
۵. علائم نگارشی، اعداد، و کلمات انگلیسی را دست نزنید.
۶. فقط متن اعراب‌گذاری شده را خروجی بدهید، بدون توضیح یا مقدمه.

متن ورودی:
{text}

متن اعراب‌گذاری شده:"""


# ── <think> block stripping (shared with translator) ────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_blocks(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


# ── Harakat generator ────────────────────────────────────────────────────


class HarakatGenerator:
    """Adds Persian harakat (diacritics) to Farsi text via LLM.

    Uses the same Ollama endpoint as the translator. Can use the same model
    (TranslateGemma-4B) or a different one if configured.

    Usage::

        hg = HarakatGenerator(
            endpoint="http://localhost:11434/v1",
            model="translategemma:4b",
        )
        harakat_text = hg.add_harakat(farsi_text)
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/v1",
        model: str = "translategemma:4b",
        api_key: str = "",
        temperature: float = 0.1,
        no_think: bool = True,
        timeout: int = 120,
        log_callback: LogFn | None = None,
        fallback_model: str = "",
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.no_think = no_think
        self.timeout = timeout
        self.log = log_callback or (lambda msg, level="INFO": None)
        # V8.0.0: fallback model for harakat — if the primary model produces
        # garbage (too many diacritics = corruption), retry with this model.
        # Defaults to empty (no fallback). The service sets it to the
        # summarisation model as a last resort.
        self.fallback_model = fallback_model
        self._cache: dict[str, str] = {}
        self._max_cache_size = 2000  # V8.0.0 #11: prevent unbounded memory growth
        # Failure tracking
        self._failure_count = 0
        self._disabled = False
        self._max_failures = 3

    def add_harakat(self, text: str) -> str:
        """Add harakat to Farsi ``text``. Returns original on failure.

        If the text contains no Farsi characters, returns it unchanged.
        """
        if not text or not text.strip():
            return text

        # Skip if no Farsi characters
        if not _has_farsi(text):
            return text

        if self._disabled:
            return text

        # Cache
        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # V8.0.0 #11: evict oldest entries if cache is full
        if len(self._cache) >= self._max_cache_size:
            self._cache.pop(next(iter(self._cache)), None)

        try:
            result = self._call_llm(text)
            if result and result.strip():
                result = result.strip()
                # V8.0.0: validate the harakat output — reject garbage
                # (corrupted models produce text that's >50% diacritics)
                if self._validate_harakat(text, result):
                    self._failure_count = 0
                    self._cache[cache_key] = result
                    return result
                else:
                    self.log(
                        f"  [Harakat] Output from '{self.model}' looks corrupted "
                        f"(diacritic ratio too high), trying fallback…",
                        "WARNING",
                    )
                    # Try fallback model if configured
                    if self.fallback_model and self.fallback_model != self.model:
                        fb_result = self._call_llm(text, model_override=self.fallback_model)
                        if fb_result and fb_result.strip():
                            fb_result = fb_result.strip()
                            if self._validate_harakat(text, fb_result):
                                self.log(
                                    f"  [Harakat] Fallback '{self.fallback_model}' "
                                    f"produced valid output",
                                    "INFO",
                                )
                                self._failure_count = 0
                                self._cache[cache_key] = fb_result
                                return fb_result
                            else:
                                self.log(
                                    "  [Harakat] Fallback also produced garbage — "
                                    "returning original text",
                                    "WARNING",
                                )
            else:
                self.log("  [Harakat] Empty LLM response, returning original", "WARNING")
        except Exception as e:
            self._failure_count += 1
            if self._failure_count >= self._max_failures:
                self._disabled = True
                self.log(
                    f"  [Harakat] Disabled after {self._failure_count} "
                    f"failures (last: {e}). Using original text.",
                    "WARNING",
                )
            else:
                self.log(
                    f"  [Harakat] Failed ({e}), returning original "
                    f"({self._failure_count}/{self._max_failures})",
                    "WARNING",
                )

        return text  # graceful degradation

    def add_harakat_to_markdown(self, markdown_text: str) -> str:
        """Add harakat to a markdown file's text content.

        Preserves:
          * YAML front-matter (untouched)
          * Code blocks (untouched)
          * URLs and inline code (untouched)
          * Markdown formatting (untouched)

        Only Farsi text in paragraphs, headings, and list items gets harakat.
        """
        if not markdown_text or not markdown_text.strip():
            return markdown_text

        # Split into segments: front-matter, code blocks, and text
        segments = self._split_markdown(markdown_text)
        result_parts = []

        for seg_text, seg_type in segments:
            if seg_type in ("frontmatter", "code"):
                # Keep as-is
                result_parts.append(seg_text)
            else:
                # Add harakat to text segments
                # But preserve inline code and URLs
                harakat_text = self._add_harakat_preserving_inline(seg_text)
                result_parts.append(harakat_text)

        return "".join(result_parts)

    # ── Internal ──────────────────────────────────────────────────────

    def _split_markdown(self, text: str) -> list:
        """Split markdown into segments: (text, type) tuples.

        Types: "frontmatter", "code", "text"
        """
        segments = []
        remaining = text

        # Extract front-matter
        fm_re = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
        fm_match = fm_re.match(remaining)
        if fm_match:
            segments.append((fm_match.group(0), "frontmatter"))
            remaining = remaining[fm_match.end() :]

        # Extract code blocks
        code_re = re.compile(r"```[\s\S]*?```")
        last_end = 0
        for m in code_re.finditer(remaining):
            if m.start() > last_end:
                segments.append((remaining[last_end : m.start()], "text"))
            segments.append((m.group(0), "code"))
            last_end = m.end()
        if last_end < len(remaining):
            segments.append((remaining[last_end:], "text"))

        return segments

    def _add_harakat_preserving_inline(self, text: str) -> str:
        """Add harakat to text while preserving inline code and URLs.

        Strategy: replace inline code and URLs with placeholders, add harakat,
        then restore.
        """
        placeholders = []

        # Protect inline code: `code`
        def _protect_inline_code(m):
            placeholders.append(m.group(0))
            return f"__PLACEHOLDER_{len(placeholders) - 1}__"

        text_protected = re.sub(r"`[^`]+`", _protect_inline_code, text)

        # Protect URLs: http://... or https://...
        def _protect_url(m):
            placeholders.append(m.group(0))
            return f"__PLACEHOLDER_{len(placeholders) - 1}__"

        text_protected = re.sub(r"https?://\S+", _protect_url, text_protected)

        # Protect markdown links: [text](url) — protect the URL part
        def _protect_link(m):
            url = m.group(2)
            idx = len(placeholders)
            placeholders.append(url)
            return f"{m.group(1)}(__PLACEHOLDER_{idx}__)"

        text_protected = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            _protect_link,
            text_protected,
        )

        # Now add harakat to the protected text
        harakat_text = self.add_harakat(text_protected)

        # Restore placeholders
        for i, original in enumerate(placeholders):
            harakat_text = harakat_text.replace(f"__PLACEHOLDER_{i}__", original)

        return harakat_text

    # V8.0.0: validate harakat output — reject garbage from poor models.
    # Corrupted models (TranslateGemma, sometimes Qwen) produce text where
    # nearly every character has a diacritic, which is unnatural and breaks
    # TTS. A healthy harakat text has <30% diacritic-bearing characters.
    _DIACRITICS = set("َُِّْٰ")  # fatha, damma, kasra, shadda, sukun, alef wasla

    def _validate_harakat(self, original: str, harakat: str) -> bool:
        """Return True if the harakat output looks valid (not garbage).

        Checks:
        1. Length similar to original (±50%) — garbage often truncates or expands.
        2. Diacritic ratio < 40% — corrupted output has >50% diacritics.
        3. V9.0.0 P2-5: Original words preserved — strip diacritics from the
           harakat output and verify the word set matches the original.
        """
        if not harakat or not harakat.strip():
            return False
        # 1. Length check
        orig_len = len(original.strip())
        hara_len = len(harakat.strip())
        if orig_len > 0:
            ratio = hara_len / orig_len
            if ratio < 0.5 or ratio > 2.0:
                return False
        # 2. Diacritic ratio check
        farsi_chars = [c for c in harakat if _PERSIAN_RE.match(c)]
        if farsi_chars:
            diacritic_count = sum(1 for c in harakat if c in self._DIACRITICS)
            diacritic_ratio = diacritic_count / len(farsi_chars)
            if diacritic_ratio > 0.40:
                return False  # too many diacritics = garbage
        # 3. V9.0.0 P2-5: Word-preservation check — strip diacritics from
        # the harakat output and compare the word set to the original.
        # If the model invented or dropped words, it's corrupt.
        orig_words = set(original.strip().split())
        # Strip diacritics from the harakat text to get the base words
        harakat_stripped = harakat
        for d in self._DIACRITICS:
            harakat_stripped = harakat_stripped.replace(d, "")
        hara_words = set(harakat_stripped.strip().split())
        if orig_words and hara_words:
            # At least 70% of original words should appear in the harakat output
            preserved = orig_words & hara_words
            preservation_ratio = len(preserved) / len(orig_words)
            if preservation_ratio < 0.70:
                return False  # too many words changed/dropped = corrupt
        return True

    def _call_llm(self, text: str, model_override: str = "") -> str | None:
        """Call the LLM with the harakat prompt.

        V8.0.0: ``model_override`` lets the fallback retry use a different
        model without reconstructing the generator.
        """
        prompt = _HARAKAT_PROMPT.replace("{text}", text)

        # V18.20.4.12 (W-a11): /no_think gated on Qwen-family via the shared
        # helper — was an unconditional "/no_think\n" prefix whenever
        # ``no_think`` was enabled, regardless of model (the directive is a
        # Qwen3 soft-switch; the ``<think/>``-block strip below stays as the
        # safety net for every model). Gated on the model THIS call uses
        # (``model_override`` when present — the fallback retry model).
        if self.no_think:
            prompt = qwen_no_think(prompt, model_override or self.model)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model_override or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": False,
        }

        url = f"{self.endpoint}/chat/completions"
        # V18.20.4.11 (P3 / O-c5): pooled transport + shape-safe parse.
        resp = session_for_url(url).post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        content = extract_openai_content(resp.json())
        content = _strip_think_blocks(content)

        # Strip leading "متن اعراب‌گذاری شده:" if echoed
        content = re.sub(
            r"^متن\s+اعراب[‌ ]گذاری\s+شده\s*:\s*",
            "",
            content,
        ).strip()

        return content

    def _cache_key(self, text: str) -> str:
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        model_hash = hashlib.md5(self.model.encode("utf-8")).hexdigest()[:6]
        return f"harakat:{model_hash}:{text_hash}"

    def is_disabled(self) -> bool:
        return self._disabled


# ── Helpers ──────────────────────────────────────────────────────────────

_PERSIAN_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _has_farsi(text: str) -> bool:
    """True if ``text`` contains any Persian/Arabic characters."""
    return bool(_PERSIAN_RE.search(text))
