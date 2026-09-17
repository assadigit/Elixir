"""Main translation engine — calls Ollama's OpenAI-compatible API.

Uses **TranslateGemma-12B** by default (purpose-built translator, lowest
hallucination among Ollama-hostable models for EN<->FA). Falls back to
any Ollama model if TranslateGemma is not pulled.

Design mirrors :mod:`core.tts.normalizer`:
  * Calls ``/v1/chat/completions`` (OpenAI-compatible, works with Ollama).
  * Strips ``<think>`` blocks that Qwen-family models emit.
  * Sends ``/no_think`` directive by default to prevent thinking blocks.
  * Caches results by (text, lang, model) hash.
  * Graceful degradation: on failure, returns the original text + logs a warning.

Markdown-aware: the prompt instructs the model to preserve:
  * Headings, bullet lists, numbered lists
  * Inline code (`` `code` ``) and links [text](url)
  * Bold (**text**) and italic (*text*) markers
  * Block quotes (> text)
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable

import requests

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ── Translation prompts ──────────────────────────────────────────────────

_PROMPT_EN_TO_FA = """Translate the following text from English to Farsi/Persian. \
Output ONLY the translation, no explanations, no preamble.

Rules:
- Translate naturally and accurately. Do NOT add or remove information.
- Preserve ALL markdown formatting exactly: headings (#), bullets (-, *), \
numbered lists (1.), bold (**text**), italic (*text*), inline code (`code`), \
links [text](url), block quotes (> text).
- Do NOT translate code blocks, URLs, email addresses, or file paths.
- Do NOT translate text inside backticks (`...`).
- Preserve the exact paragraph structure and line breaks.
- Use formal, standard Persian (فارسی معیار).
- If a glossary is provided, use the specified translations consistently.

{glossary}

Text to translate:
{text}

Persian translation:"""


_PROMPT_FA_TO_EN = """Translate the following text from Farsi/Persian to English. \
Output ONLY the translation, no explanations, no preamble.

Rules:
- Translate naturally and accurately. Do NOT add or remove information.
- Preserve ALL markdown formatting exactly: headings (#), bullets (-, *), \
numbered lists (1.), bold (**text**), italic (*text*), inline code (`code`), \
links [text](url), block quotes (> text).
- Do NOT translate code blocks, URLs, email addresses, or file paths.
- Do NOT translate text inside backticks (`...`).
- Preserve the exact paragraph structure and line breaks.
- Use clear, natural English.
- If a glossary is provided, use the specified translations consistently.

{glossary}

Text to translate:
{text}

English translation:"""


# ── <think> block stripping ──────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks that Qwen-family models emit."""
    return _THINK_RE.sub("", text).strip()


# ── Language detection ───────────────────────────────────────────────────

# Persian/Arabic Unicode ranges
_PERSIAN_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def detect_language(text: str) -> str:
    """Detect whether ``text`` is English ("en") or Farsi ("fa").

    Uses a simple Unicode-script heuristic: if >15% of alphanumeric
    characters are in the Arabic/Persian block, it's Farsi.
    """
    if not text:
        return "en"
    persian_chars = len(_PERSIAN_RE.findall(text))
    total_alpha = len(re.findall(r"\w", text))
    if total_alpha == 0:
        return "en"
    ratio = persian_chars / total_alpha
    return "fa" if ratio > 0.15 else "en"


# ── Translator ───────────────────────────────────────────────────────────

class Translator:
    """LLM-based translator via Ollama's OpenAI-compatible endpoint.

    Usage::

        t = Translator(
            endpoint="http://localhost:11434/v1",
            model="translategemma:4b",
            api_key="",
            no_think=True,
        )
        fa_text = t.translate("Hello world", source_lang="en", target_lang="fa")
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
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.no_think = no_think
        self.timeout = timeout
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._cache: dict[str, str] = {}
        self._cache_max = 2000  # V13.27.0 (P2.7): bounded cache (was unbounded)
        # Failure tracking (like the TTS normalizer)
        self._failure_count = 0
        self._disabled = False
        self._max_failures = 5

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "fa",
        glossary_context: str = "",
        prev_context: str = "",
    ) -> str:
        """Translate ``text`` from ``source_lang`` to ``target_lang``.

        Args:
            text:             the text to translate.
            source_lang:      "en" or "fa" (or "auto" to detect).
            target_lang:      "en" or "fa".
            glossary_context: formatted glossary string from GlossaryManager.
            prev_context:     short text from the previous chunk (for continuity).

        Returns:
            The translated text. On failure, returns the original text.
        """
        if not text or not text.strip():
            return text

        if source_lang == "auto":
            source_lang = detect_language(text)

        # Same-language → no-op
        if source_lang == target_lang:
            return text

        # Disabled after repeated failures
        if self._disabled:
            return text

        # Cache lookup
        cache_key = self._cache_key(text, source_lang, target_lang, glossary_context)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = self._call_llm(text, source_lang, target_lang,
                                     glossary_context, prev_context)
            if result and result.strip():
                self._failure_count = 0  # reset on success
                result = result.strip()
                self._cache[cache_key] = result
                # V13.27.0 (P2.7): Evict oldest if over the cap
                while len(self._cache) > self._cache_max:
                    # Delete the first inserted key (FIFO eviction)
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                return result
            else:
                self.log("  [Translation] Empty LLM response, returning original",
                         "WARNING")
        except Exception as e:
            self._failure_count += 1
            if self._failure_count >= self._max_failures:
                self._disabled = True
                self.log(
                    f"  [Translation] Disabled after {self._failure_count} "
                    f"failures (last: {e}). Returning original text for "
                    f"remaining chunks.",
                    "WARNING"
                )
            else:
                self.log(
                    f"  [Translation] Failed ({e}), returning original "
                    f"(failure {self._failure_count}/{self._max_failures})",
                    "WARNING"
                )

        return text  # graceful degradation: return original

    def translate_back(
        self,
        text: str,
        original_source_lang: str,
        original_target_lang: str,
    ) -> str:
        """Back-translate: translate ``text`` back to the original source language.

        Used by the validator for back-translation quality checking.
        """
        # Swap source and target
        return self.translate(
            text,
            source_lang=original_target_lang,
            target_lang=original_source_lang,
        )

    # ── Internal ──────────────────────────────────────────────────────

    def _call_llm(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        glossary_context: str,
        prev_context: str,
    ) -> str | None:
        """Call the Ollama API and return the translated text."""
        # Build the prompt
        if source_lang == "en" and target_lang == "fa":
            prompt_template = _PROMPT_EN_TO_FA
        elif source_lang == "fa" and target_lang == "en":
            prompt_template = _PROMPT_FA_TO_EN
        else:
            # Unsupported pair — return original
            return text

        glossary_str = glossary_context if glossary_context else "(no glossary provided)"
        prompt = prompt_template.replace("{glossary}", glossary_str)
        prompt = prompt.replace("{text}", text)

        # Add context note if available
        if prev_context:
            prompt += f"\n\n(Context from previous section: \"{prev_context[:200]}...\")"

        # Prepend /no_think directive to suppress thinking blocks
        if self.no_think:
            prompt = "/no_think\n" + prompt

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": False,
        }

        url = f"{self.endpoint}/chat/completions"
        resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip <think> blocks (safety net even with /no_think)
        content = _strip_think_blocks(content)

        # Strip any leading "Persian translation:" or "English translation:"
        # that the model might have echoed
        content = re.sub(
            r"^(Persian|English)\s+translation\s*:\s*",
            "",
            content,
            flags=re.IGNORECASE,
        ).strip()

        return content

    def _cache_key(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        glossary_context: str,
    ) -> str:
        """Build a cache key from text + language pair + model + glossary hash."""
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        glossary_hash = hashlib.md5(
            (glossary_context or "").encode("utf-8")
        ).hexdigest()[:8]
        model_hash = hashlib.md5(self.model.encode("utf-8")).hexdigest()[:6]
        return f"{source_lang}->{target_lang}:{model_hash}:{text_hash}:{glossary_hash}"

    def clear_cache(self) -> None:
        """Clear the translation cache."""
        self._cache.clear()

    def is_disabled(self) -> bool:
        """True if the translator has been disabled due to repeated failures."""
        return self._disabled
