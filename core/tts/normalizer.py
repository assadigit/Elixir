"""V4.4.0: LLM-based text normalization for TTS.

Pre-processes text before synthesis to improve pronunciation:

* **English:** expands numbers (2024 → "twenty twenty-four"),
  abbreviations (Dr. → Doctor), dates, times, currencies, units.
* **Persian:** expands Persian/Arabic numerals (۱۲۳ → "صد و بیست و سه"),
  expands abbreviations, AND adds harakat (اعراب‌گذاری) — fatha (َ),
  damma (ُ), kasra (ِ), sukun (ْ), shadda (ّ) — to disambiguate
  pronunciation. This is critical for Persian because the script omits
  short vowels; without harakat the TTS engine must guess, and it
  guesses wrong often.

The normalizer calls an OpenAI-compatible endpoint (Ollama's
``/v1/chat/completions``, OpenRouter, OpenAI, any compatible API). It's
optional and disabled by default — if it fails, the raw text is passed
to the TTS engine unchanged (graceful degradation).

Design:
* **Caching:** same (text, language) → same output. An in-memory dict
  avoids re-normalizing repeated sentences.
* **Context modes:** per-sentence (fast, isolated), per-paragraph
  (balanced), per-segment (most context, slowest).
* **Confidence-first harakat:** the Persian prompt explicitly instructs
  the LLM to add harakat ONLY where confident, leaving ambiguous words
  unmarked rather than guessing wrong.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable

# V18.20.4.12 (T-c7): shared 404 detection + the canonical `ollama pull`
# hint (single source with the LLM providers — see core/llm/model_errors.py).
from core.llm.model_errors import is_model_not_found, model_not_found_hint

# V18.20.4.11 (P2 / W-a7 partial): single source of truth for the legacy
# default-model literal (de-duplication only — value byte-identical).
from core.llm.model_taxonomy import LEGACY_DEFAULT_MODEL
from core.system.timeouts import HTTP_FETCH_TIMEOUT_S, UI_PROBE_TIMEOUT_S

# V18.20.4.11 (P3 / O-c5): pooled LLM transport + shape-safe OpenAI-compat
# response extraction (replaces the bare requests.post + deep-index parse).
from utils.network import extract_openai_content, session_for_url

logger = logging.getLogger(__name__)

LogFn = Callable[[str, str], None]


# ── Default prompts ───────────────────────────────────────────────────────
# V16.0.4: Default prompts are loaded from the Prompt Bank
# (prompts/tts/normalize_en.md and prompts/tts/normalize_fa.md). The
# Prompt Bank files use the Jinja-style ``{{text}}`` placeholder; we
# convert it to the legacy single-brace ``{text}`` placeholder that the
# existing _call_llm path replaces at runtime. If loading fails for any
# reason (frozen import, missing file, etc.), the inline fallback strings
# below are used so TTS normalization degrades gracefully.

_FALLBACK_PROMPT_EN = """You are a text normalization expert for text-to-speech. Given the input text, return it with:

1. Numbers expanded to words:
   - 2024 → "twenty twenty-four" (years)
   - 123 → "one hundred twenty three"
   - $50 → "fifty dollars"
   - 3.14 → "three point one four"
2. Abbreviations expanded:
   - Dr. → Doctor, Mr. → Mister, Mrs. → Misses, etc.
   - USA → "U S A" (spell out acronyms that shouldn't be read as words)
   - NASA → "NASA" (keep acronyms that ARE read as words)
3. Dates, times, units expanded:
   - 3pm → "three P M"
   - Jan 5 → "January fifth"
   - 5kg → "five kilograms"
   - 100mph → "one hundred miles per hour"
4. Symbols expanded:
   - & → "and", % → "percent", # → "hashtag" or "number"

Rules:
- Preserve the EXACT meaning. Only change representation for pronunciation.
- Do NOT change the sentence structure or add/remove words.
- Do NOT add punctuation that wasn't there.
- Output ONLY the normalized text, no explanations, no preamble.

Input text:
{text}

Normalized text:"""


_FALLBACK_PROMPT_FA = """شما یک متخصص نرمال‌سازی متن فارسی برای تبدیل متن به گفتار هستید. متن ورودی را با موارد زیر اصلاح کنید:

۱. اعراب‌گذاری (حرکت‌گذاری):
   - فتحه (ـَ) برای صدای "a"
   - ضمه (ـُ) برای صدای "u"
   - کسره (ـِ) برای صدای "i"
   - سکون (ـْ) جایی که حرف بی‌حرکت است
   - تشدید (ـّ) برای حروف مشدد
   فقط جایی که مطمئن هستید اعراب بگذارید. اگر شک دارید، کلمه را بدون اعراب بگذارید. اعراب غلط بدتر از هیچ اعرابی است.

۲. اعداد را به حروف بنویسید:
   - ۱۲۳ → "صد و بیست و سه"
   - ۱۴۰۳ → "هزار و چهارصد و سه"
   - ۳.۱۴ → "سه ممیز چهارده صدم"
   - اعداد انگلیسی (123) را هم به حروف فارسی بنویسید

۳. مخفف‌ها را باز کنید:
   - ک.ق. → "قدیس"
   - اختصارات رایج را به شکل کامل بنویسید

۴. علائم نگارشی:
   - ٪ → "درصد"
   - & → "و"

قوانین:
- معنی متن را دقیقاً حفظ کنید. فقط شکل نوشتاری را برای تلفظ بهتر تغییر دهید.
- ساختار جمله را تغییر ندهید.
- فقط متن نرمال‌شده را خروجی بدهید، بدون توضیح یا مقدمه.

متن ورودی:
{text}

متن نرمال‌شده:"""


def _load_default_prompt(name: str, fallback: str) -> str:
    """Load a TTS default prompt from the Prompt Bank, falling back to inline.

    Converts the Prompt Bank's ``{{text}}`` placeholder to the legacy
    single-brace ``{text}`` placeholder so the existing call site
    ``template.replace("{text}", text)`` continues to work unchanged.
    """
    try:
        from core.summarisation.prompt_manager import PromptManager

        pm = PromptManager()
        template = pm.load_prompt(name)
        if template and "{{text}}" in template:
            return template.replace("{{text}}", "{text}")
        if template:
            return template
    except Exception as _e:
        logger.debug("TTS default prompt load failed for %s: %s: %s", name, type(_e).__name__, _e)
    return fallback


_DEFAULT_PROMPT_EN = _load_default_prompt("tts/normalize_en", _FALLBACK_PROMPT_EN)
_DEFAULT_PROMPT_FA = _load_default_prompt("tts/normalize_fa", _FALLBACK_PROMPT_FA)


# ── Persian/Arabic numeral maps (for deterministic fallback) ──────────────

_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_EN_DIGITS = "0123456789"
_FA_NUMERAL_WORDS = {
    0: "صفر",
    1: "یک",
    2: "دو",
    3: "سه",
    4: "چهار",
    5: "پنج",
    6: "شش",
    7: "هفت",
    8: "هشت",
    9: "نه",
    10: "ده",
    11: "یازده",
    12: "دوازده",
    13: "سیزده",
    14: "چهارده",
    15: "پانزده",
    16: "شانزده",
    17: "هفده",
    18: "هجده",
    19: "نوزده",
    20: "بیست",
    30: "سی",
    40: "چهل",
    50: "پنجاه",
    60: "شصت",
    70: "هفتاد",
    80: "هشتاد",
    90: "نود",
    100: "صد",
    200: "دویست",
    300: "سیصد",
    400: "چهارصد",
    500: "پانصد",
    600: "ششصد",
    700: "هفتصد",
    800: "هشتصد",
    900: "نهصد",
    1000: "هزار",
}


def _fa_number_to_words(n: int) -> str:
    """Convert an integer to Persian words (deterministic fallback)."""
    if n < 0:
        return "منفی " + _fa_number_to_words(-n)
    if n in _FA_NUMERAL_WORDS:
        return _FA_NUMERAL_WORDS[n]
    if n < 100:
        tens, ones = (n // 10) * 10, n % 10
        if ones == 0:
            return _FA_NUMERAL_WORDS[tens]
        return _FA_NUMERAL_WORDS[tens] + " و " + _FA_NUMERAL_WORDS[ones]
    if n < 1000:
        hundreds, rest = (n // 100) * 100, n % 100
        if rest == 0:
            return _FA_NUMERAL_WORDS[hundreds]
        return _FA_NUMERAL_WORDS[hundreds] + " و " + _fa_number_to_words(rest)
    if n < 1000000:
        thousands, rest = n // 1000, n % 1000
        # "هزار" alone for 1000, "دو هزار" for 2000, etc.
        if thousands == 1:
            thous_str = "هزار"
        else:
            thous_str = _fa_number_to_words(thousands) + " هزار"
        if rest == 0:
            return thous_str
        return thous_str + " و " + _fa_number_to_words(rest)
    # Fallback for very large numbers — just return the digits
    return str(n)


def _expand_fa_numbers(text: str) -> str:
    """Deterministic: expand Persian/Arabic numerals to Persian words.

    Used as a fallback when the LLM is unavailable. Handles standalone
    integers; leaves decimals and mixed alphanumeric strings alone.
    """

    def repl(m):
        raw = m.group(0)
        # Convert Persian digits to ASCII for int()
        ascii_str = raw.translate(str.maketrans(_FA_DIGITS, _EN_DIGITS))
        try:
            n = int(ascii_str)
            return _fa_number_to_words(n)
        except ValueError:
            return raw

    # Match runs of Persian or ASCII digits
    return re.sub(r"[\d" + _FA_DIGITS + "]+", repl, text)


# ── Sentence/paragraph splitting ──────────────────────────────────────────

_SENTENCE_END_RE = re.compile(r"(?<=[\.!?؟。\n])\s+")


def _split_sentences(text: str) -> list:
    """Split text into sentences on EN/FA/Persian sentence enders."""
    parts = _SENTENCE_END_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_paragraphs(text: str) -> list:
    """Split text into paragraphs on double-newlines."""
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


# ── Main normalizer class ─────────────────────────────────────────────────


class TextNormalizer:
    """LLM-based text normalizer for TTS pre-processing.

    Call :meth:`normalize` with raw text + language. Returns normalized
    text (with harakat for FA, expanded numbers/abbrevs for both). Falls
    back to deterministic number expansion if the LLM is unavailable.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        custom_prompt_en: str | None = None,
        custom_prompt_fa: str | None = None,
        context_mode: str = "sentence",  # "sentence" | "paragraph" | "segment"
        log_callback: LogFn | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.prompt_en = custom_prompt_en or _DEFAULT_PROMPT_EN
        self.prompt_fa = custom_prompt_fa or _DEFAULT_PROMPT_FA
        self.context_mode = context_mode
        self.log = log_callback or (lambda msg, level="INFO": None)
        self._cache: dict[str, str] = {}
        self._cache_max = 500  # V13.27.0 (P2.7): bounded cache (was unbounded)
        # V4.7.3: If the LLM fails repeatedly, disable normalization for
        # the rest of the session instead of spamming warnings.
        self._disabled = False
        self._failure_count = 0
        self._max_failures = 3  # after 3 failures, disable

    def normalize(self, text: str, language: str) -> str:
        """Normalize ``text`` for the given language (``"en"`` or ``"fa"``).

        Caches results. If the LLM call fails, falls back to deterministic
        number expansion (Persian only; English passthrough).
        """
        if not text or not text.strip():
            return text

        # V4.7.3: If disabled after repeated failures, skip LLM entirely
        if self._disabled:
            if language == "fa":
                return _expand_fa_numbers(text)
            return text

        cache_key = self._cache_key(text, language)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Split based on context mode
        if self.context_mode == "sentence":
            chunks = _split_sentences(text)
        elif self.context_mode == "paragraph":
            chunks = _split_paragraphs(text)
        else:  # "segment" — normalize the whole text at once
            chunks = [text]

        if not chunks:
            return text

        normalized_chunks = []
        for chunk in chunks:
            result = self._normalize_chunk(chunk, language)
            normalized_chunks.append(result)

        # Rejoin with appropriate separator
        if self.context_mode == "sentence":
            # Preserve sentence boundaries with space
            result = " ".join(normalized_chunks)
        elif self.context_mode == "paragraph":
            result = "\n\n".join(normalized_chunks)
        else:
            result = normalized_chunks[0]

        self._cache[cache_key] = result
        # V13.27.0 (P2.7): Evict oldest if over the cap
        while len(self._cache) > self._cache_max:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        return result

    def _normalize_chunk(self, text: str, language: str) -> str:
        """Normalize a single chunk via the LLM, with fallback."""
        try:
            llm_result = self._call_llm(text, language)
            if llm_result and llm_result.strip():
                # Success — reset failure count
                self._failure_count = 0
                return llm_result.strip()
            # LLM returned empty — fall back
            self.log("  ⚠️ Normalization: empty LLM response, using fallback", "DEBUG")
        except Exception as e:
            self._failure_count += 1
            if self._failure_count >= self._max_failures:
                self._disabled = True
                self.log(
                    f"  ⚠️ Normalization disabled after {self._failure_count} "
                    f"failabilities (last: {e}). Using deterministic fallback "
                    f"for remaining segments.",
                    "WARNING",
                )
            else:
                self.log(
                    f"  ⚠️ Normalization failed ({e}), using fallback "
                    f"(failure {self._failure_count}/{self._max_failures})",
                    "WARNING",
                )

        # Deterministic fallback
        if language == "fa":
            return _expand_fa_numbers(text)
        return text  # English: passthrough if LLM fails

    def _call_llm(self, text: str, language: str) -> str | None:
        """Call the OpenAI-compatible endpoint and return the response."""
        prompt_template = self.prompt_fa if language == "fa" else self.prompt_en
        prompt = prompt_template.replace("{text}", text)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,  # low temp for deterministic normalization
            "stream": False,
        }

        url = f"{self.endpoint}/chat/completions"
        # V18.20.4.11 (P3 / O-c5): pooled transport + shape-safe parse — a
        # malformed provider payload now returns "" (deterministic fallback
        # path) instead of raising KeyError.
        resp = session_for_url(url).post(
            url, json=payload, headers=headers, timeout=HTTP_FETCH_TIMEOUT_S
        )
        # V18.20.4.12 (T-c7): the pre-emptive auto-discovery in
        # create_normalizer_from_settings covers empty/known-bad DEFAULTS,
        # but an explicitly-configured model that isn't pulled still 404s
        # here — surface the canonical actionable hint at WARNING (the
        # generic handler in _normalize_chunk only sees "404 Client Error"
        # with no pull guidance). Control flow unchanged: raise_for_status
        # still raises and the deterministic-fallback + failure-count
        # disable logic in _normalize_chunk still applies unchanged.
        if is_model_not_found(resp.status_code):
            logger.warning(
                "TTS normalization: %s — falling back to deterministic "
                "number expansion for this segment",
                model_not_found_hint(self.model),
            )
        resp.raise_for_status()
        content = extract_openai_content(resp.json())

        # Strip any <think> blocks the model might have included
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    def _cache_key(self, text: str, language: str) -> str:
        """Build a cache key from text hash + language + prompt hash."""
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        prompt = self.prompt_fa if language == "fa" else self.prompt_en
        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8]
        return f"{language}:{text_hash}:{prompt_hash}"

    def clear_cache(self) -> None:
        """Clear the normalization cache."""
        self._cache.clear()


# ── Module-level convenience ──────────────────────────────────────────────


def create_normalizer_from_settings(log_callback: LogFn | None = None) -> TextNormalizer | None:
    """Factory: create a TextNormalizer from saved settings, or None if disabled.

    V4.7.24: If the normalization model is not set or doesn't match any
    Ollama model, auto-discover the first available model from Ollama.
    This prevents the 404 error when the default model name doesn't exist.

    V0.6.13: the llama.cpp-first local fallback (the operator's follow-up
    report: "TTS ... FIND[S] LLM ON OLLAMA ONLY"). When the configured
    ``tts.normalize_endpoint`` is LOCAL and a llama-server is up, the
    normalizer is pointed at it — the OpenAI-compat
    ``{base}/chat/completions`` the TextNormalizer already speaks — with
    the DETECTED served model + bearer key, and the Ollama ``/api/tags``
    discovery is SKIPPED (with Ollama down the discovery failed and
    normalization DISABLED itself — the reported defect). The served
    model is NOT persisted to ``tts.normalize_model`` (that setting
    names the configured backend's model for the no-llama.cpp case). A
    remote endpoint, the ``local.llamacpp_first=false`` kill switch, or
    a dead llama.cpp → the configured path, byte-identical to V0.6.12.
    """
    from utils.settings import Settings

    s = Settings()

    if not s.get("tts.normalize_enabled", False):
        return None

    # V0.6.13: resolve the policy BEFORE the model resolution — a
    # takeover supplies BOTH the endpoint and the model.
    from core.llm.local_fallback import decide_llamacpp_first, is_local_url

    _endpoint = str(s.get("tts.normalize_endpoint", "http://localhost:11434/v1") or "")
    if is_local_url(_endpoint):
        _d = decide_llamacpp_first(s, "ollama")
        if _d.note and log_callback:
            log_callback(f"  🦙 {_d.note}", "INFO")
        if _d.use_llamacpp:
            return TextNormalizer(
                endpoint=_d.base_url,
                api_key=_d.api_key,
                model=_d.model,
                custom_prompt_en=s.get("tts.normalize_prompt_en", ""),
                custom_prompt_fa=s.get("tts.normalize_prompt_fa", ""),
                context_mode=s.get("tts.normalize_context_mode", "sentence"),
                log_callback=log_callback,
            )

    # V4.7.24: Resolve the model — try in order:
    # 1. tts.normalize_model (explicitly set)
    # 2. summarisation.model (the summarizer's model)
    # 3. Auto-discover from Ollama /api/tags
    model = s.get("tts.normalize_model", "")
    if not model:
        model = s.get("summarisation.model", "")

    # V4.7.24: If model is empty or a known-bad default, auto-discover
    # V18.20.4.11 (P2): "gemma3:12b" literal → model_taxonomy constant
    # (value unchanged — the LEGACY sentinel default counts as known-bad).
    if not model or model in ("qwen2.5:3b", LEGACY_DEFAULT_MODEL, ""):
        try:
            _tags_url = f"{s.get_ollama_url()}/api/tags"
            resp = session_for_url(_tags_url).get(
                _tags_url, timeout=UI_PROBE_TIMEOUT_S
            )  # V18.20.4.3 (W-c9): canonical URL; V18.20.4.11: pooled
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    # Prefer the first non-OCR model (skip OlmOCR)
                    for m in models:
                        name = m.get("name", "")
                        if "olmocr" not in name.lower() and "ocr" not in name.lower():
                            model = name
                            break
                    if not model and models:
                        model = models[0].get("name", "")
                    if log_callback:
                        log_callback(f"  ℹ️ Normalization auto-selected model: {model}", "INFO")
                    # Save it so future calls don't re-discover
                    s.set("tts.normalize_model", model)
        except Exception as _e:
            # V18.20.4.12 (T-c7): /api/tags discovery failure is
            # Ollama-down (transient) or a wrong-URL config — it is NOT the
            # model-missing case (a listing endpoint doesn't 404 for an
            # unpulled model), so it stays at DEBUG per the T-c7 brief.
            logger.debug("ignored %s: %s", type(_e).__name__, _e)

    if not model:
        if log_callback:
            log_callback("  ⚠️ No model found for normalization — disabling", "WARNING")
        return None

    # V0.16 (Phase 3 / 3.2): keyring-backed read (was plaintext s.get —
    # defeated the keychain for the TTS normalizer key).
    from core.system.secrets import get_secret

    return TextNormalizer(
        endpoint=s.get("tts.normalize_endpoint", "http://localhost:11434/v1"),
        api_key=get_secret("tts.normalize_api_key", s, ""),
        model=model,
        custom_prompt_en=s.get("tts.normalize_prompt_en", ""),
        custom_prompt_fa=s.get("tts.normalize_prompt_fa", ""),
        context_mode=s.get("tts.normalize_context_mode", "sentence"),
        log_callback=log_callback,
    )
