"""
Simplified Keypoints Digest – converts technical keypoints into plain, jargon‑free language.

Aggregates all bullet points from all chapters, then processes them in batches
using the configured LLM (local or cloud) to produce a simplified, accessible
list of key takeaways.

Outputs:
- [BookName].Keypoints.Simplified.md
- [BookName].Keypoints.Simplified.docx
"""

import re
import time
from collections.abc import Callable
from pathlib import Path

import requests as _requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from core.llm import ModelManager, ModelType
from core.llm.retry import retry_llm_call
from core.models import ConversionRequest, SummaryResult

# V18.20.4.12 (W-a11): /no_think gated on Qwen-family models via the
# shared helper — the directive is a Qwen3 soft-switch; for other models
# it is prompt pollution.
from core.summarisation.filter_thinking import qwen_no_think
from core.system.timeouts import FAST_LLM_TIMEOUT_S, KEYPOINTS_WHOLE_CALL_TIMEOUT_S
from utils.logging import get_main_logger
from utils.network import safe_ollama_request
from utils.settings import Settings

logger = get_main_logger()


class SimplifiedKeypointsBuilder:
    """
    Builds a jargon‑free, simplified version of all keypoints from a book.
    Generates both Markdown and DOCX outputs.
    """

    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.model_manager = ModelManager()

        settings = Settings()
        self.provider = settings.get("summarisation.provider", "ollama")
        # V18.20.4.8 (P6 / W-a4): canonical Ollama URL from Settings (the
        # W-c9 sweep missed this site — it was hardcoded to
        # http://localhost:11434). Fail-soft to the old literal, same as
        # every other W-c9 site.
        try:
            self.ollama_base_url = settings.get_ollama_url()
        except Exception:
            self.ollama_base_url = "http://localhost:11434"

        # Cloud / OpenAI‑compatible settings
        # V0.16 (Phase 3 / 3.2): keyring-backed reads (was plaintext).
        from core.system.secrets import get_secret

        self.api_key = get_secret("summarisation.api_key", settings, "")
        self.api_base_url = settings.get(
            "summarisation.api_base_url", "https://openrouter.ai/api/v1"
        )
        self.cloud_model = settings.get(
            "summarisation.cloud_model", "google/gemini-2.5-flash-preview:free"
        )
        self.cloud_max_tokens = settings.get("summarisation.cloud_max_tokens", 16000)

        # FreeLLMAPI
        self.freellmapi_url = settings.get(
            "summarisation.freellmapi_url", "http://localhost:3001/v1"
        )
        self.freellmapi_key = get_secret("summarisation.freellmapi_key", settings, "")
        self.freellmapi_model = settings.get("summarisation.freellmapi_model", "auto")

        # V0.4.24 (V4.23 run post-mortem): llama.cpp server settings. The
        # provider was UNREACHABLE from this builder — _call_llm routed
        # every non-cloud provider into _call_ollama, whose
        # model_exists() probe queried Ollama; the V4.23 rig log (provider
        # = llamacpp) then shipped "Model '…' not found. Skipping simplified
        # keypoints." for 74/74 keypoints — the entire requested output
        # silently failed while llama-server was serving the model.
        self.llamacpp_base_url = settings.get(
            "summarisation.llamacpp_base_url", "http://127.0.0.1:8080/v1"
        )
        self.llamacpp_api_key = get_secret("summarisation.llamacpp_api_key", settings, "local")
        self.llamacpp_model = settings.get("summarisation.llamacpp_model", "")

        # Which model to use for simplification:
        # V3.5.0: If simplification_model is set, use it (sequential model loading).
        # Otherwise fall back to fast_model or summarisation_model.
        self.simplification_model = getattr(request, "simplification_model", "") or ""
        self.model = (
            self.simplification_model
            or getattr(request, "fast_model", None)
            or request.summarisation_model
        )
        self.summarisation_model = request.summarisation_model  # for model swap logic
        self.temperature = 0.1  # low temperature for translation

        # V3.5.0: Track whether we need to swap models
        self._needs_model_swap = (
            self.simplification_model
            and self.simplification_model != self.summarisation_model
            and self.simplification_model != getattr(request, "fast_model", None)
        )
        # FIX V3.1.5: Reduced batch_size from 15 → 10. The /no_think directive
        # was removed (it caused 41% data loss), so the model now thinks again.
        # Smaller batches compensate for thinking overhead and complete within
        # the timeout. 10 keypoints × thinking model ≈ 60-80s per batch.
        self.batch_size = 10  # number of keypoints per batch
        # FIX V3.1.5: Raised timeout from 300 → 420 to accommodate thinking
        # model overhead (no /no_think directive). 10-item batches with
        # thinking take ~60-80s; 420s gives ample headroom for retries.
        self.timeout = KEYPOINTS_WHOLE_CALL_TIMEOUT_S
        self.retries = 1

        # For token counting when batching
        self.max_batch_tokens = 8000  # increased (was 4000) — model supports 32k+ context

        # V3.10.1 G3: Jargon dictionary cache. Pre-builds {word: is_jargon}
        # from the source text so _identify_jargon does a dict lookup instead
        # of calling enchant.check() for every word in every bullet. 10x faster.
        self._jargon_cache: dict = {}
        self._jargon_cache_built = False
        self._enchant_dict = None
        try:
            import enchant

            self._enchant_dict = enchant.Dict("en_US")
        except ImportError:
            pass  # No pyenchant — will fall back to length-based detection

        # Max output tokens per batch — 4096 is sufficient for 10 keypoints.
        self.max_output_tokens_per_batch = 4096

    # ── LLM calls (mirrors summarizer.py logic) ──────────────────────────

    def _call_llm(self, prompt: str) -> str | None:
        """Call the configured LLM (local or cloud)."""
        if self.provider == "freellmapi":
            return self._call_openai_compat(
                prompt,
                base_url=self.freellmapi_url,
                api_key=self.freellmapi_key,
                model=self.freellmapi_model,
                label="FreeLLMAPI",
            )
        if self.provider in ("openrouter", "openai"):
            return self._call_openai_compat(
                prompt,
                base_url=self.api_base_url,
                api_key=self.api_key,
                model=self.cloud_model,
                label=self.provider.capitalize(),
            )
        # V0.4.24: llama-server exposes the OpenAI-compatible API at the
        # configured base URL — the same transport the cloud path uses.
        if self.provider == "llamacpp":
            return self._call_openai_compat(
                prompt,
                base_url=self.llamacpp_base_url,
                api_key=self.llamacpp_api_key,
                model=self.llamacpp_model or self.model,
                label="llama.cpp",
            )
        return self._call_ollama(prompt)

    def _call_llm_single(self, prompt: str) -> str | None:
        """V3.2.2: Call LLM for single-bullet simplification.

        V3.2.2: REMOVED /no_think — it caused 95% verbatim copies (the model
        defaults to copying input when denied its thinking process). Now lets
        the model think normally. Keeps the 512 token limit + 120s timeout
        + 3 concurrent workers for speed. Expected: ~15s per bullet, 41 items
        / 3 workers = ~3.4 minutes total.
        """
        if self.provider == "freellmapi":
            return self._call_openai_compat(
                prompt,
                base_url=self.freellmapi_url,
                api_key=self.freellmapi_key,
                model=self.freellmapi_model,
                label="FreeLLMAPI",
            )
        if self.provider in ("openrouter", "openai"):
            return self._call_openai_compat(
                prompt,
                base_url=self.api_base_url,
                api_key=self.api_key,
                model=self.cloud_model,
                label=self.provider.capitalize(),
            )
        # V0.4.24: single-bullet simplification via llama-server (the
        # OpenAI-compatible endpoint) — previously fell through to
        # _call_ollama and failed on the Ollama model_exists probe.
        if self.provider == "llamacpp":
            return self._call_openai_compat(
                prompt,
                base_url=self.llamacpp_base_url,
                api_key=self.llamacpp_api_key,
                model=self.llamacpp_model or self.model,
                label="llama.cpp",
            )
        # Ollama: let model think (no /no_think), 512 max_predict, 120s timeout
        return self._call_ollama(prompt, no_think=False, max_predict=512)

    def _call_ollama(
        self, prompt: str, no_think: bool = False, max_predict: int | None = None
    ) -> str | None:
        """Call local Ollama.

        V3.2.1: Added no_think parameter for per-bullet simplification.
        /no_think is safe for single-item translation (trivial task) and
        reduces generation time from ~90s to ~5s per bullet. It was bad
        for BATCH mode (caused data loss) but is perfect for single items.

        V18.20.4.8 (P6 / W-a4 + O-a7): the hand-rolled retry loop was
        migrated to the house guard pattern (the same one
        ``llm_dispatcher._call_ollama_nonstreaming`` uses): the
        ``@retry_llm_call`` decorator retries ConnectionError / 429 / 5xx
        with backoff, classifies Timeout as NON-retryable (V18.2.19 model-
        stall rule) and every failure degrades to ``None`` (fail-soft). The
        payload, the ``model_exists`` pre-check, the ``/no_think`` prompt
        prefix, the per-bullet ``max_predict=512`` and the 120s/420s dual
        timeout are UNCHANGED. Full delegation to
        ``llm_dispatcher.call_ollama`` does NOT fit this site: it requires
        an OllamaSupervisor and rebuilds the payload via OllamaProvider
        (different ctx / system / num_gpu semantics, no model_exists
        pre-check) — documented in the P6 worklog.
        """
        if not self.model_manager.model_exists(self.model):
            self.log(
                f"  ⚠️ Model '{self.model}' not found. Skipping simplified keypoints.", "WARNING"
            )
            return None

        ctx = max(8000, self.request.summarisation_max_context_tokens)
        # V3.2.1: /no_think directive for single-bullet mode — suppresses
        # the thinking model's internal reasoning. Safe for trivial tasks
        # like translating one sentence. Dramatically reduces generation time.
        # V18.20.4.12 (W-a11): gated on Qwen-family via the shared helper —
        # was an unconditional "/no_think\n" prefix (the directive is a
        # Qwen3 soft-switch; prompt pollution for other models).
        actual_prompt = prompt
        if no_think:
            actual_prompt = qwen_no_think(prompt, self.model)

        num_predict = max_predict if max_predict else self.max_output_tokens_per_batch

        payload = {
            "model": self.model,
            "prompt": actual_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": num_predict,
                "num_ctx": ctx,
            },
        }
        url = f"{self.ollama_base_url}/api/generate"

        # V3.2.2: Per-bullet calls (max_predict=512) get 120s timeout.
        # Batch calls get self.timeout (420s). The /no_think path is no longer
        # used but kept for compatibility.
        actual_timeout = FAST_LLM_TIMEOUT_S if max_predict and max_predict <= 512 else self.timeout

        @retry_llm_call(max_attempts=self.retries + 1, log_callback=self.log)
        def _do_one_call() -> str:
            self.log(f"    🤖 {self.model} (t={self.temperature:.2f}) attempt…", "INFO")
            resp = safe_ollama_request("POST", url, json=payload, timeout=actual_timeout)
            text = resp.json().get("response", "").strip()
            if not text:
                # Empty response — raise ConnectionError so the decorator
                # retries (preserves the old "log empty + retry" behavior).
                raise _requests.exceptions.ConnectionError("empty response from model")
            return text

        try:
            return _do_one_call()
        except Exception as e:
            # Retries exhausted OR non-retryable (timeout / 404 / parse
            # error) — fail-soft to None, exactly like the dispatcher's
            # leaf functions. The caller counts the bullet as failed.
            self.log(f"    ⚠️ {self.model} call failed: {e}", "WARNING")
            return None

    def _call_openai_compat(
        self, prompt: str, base_url: str, api_key: str, model: str, label: str
    ) -> str | None:
        """Call OpenAI‑compatible API (OpenRouter, Z.ai, DeepSeek, etc.).

        V18.20.4.8 (P6 / W-a4 + O-a7): migrated to the house LLM dispatcher
        (``core.summarisation.llm_dispatcher.call_openai_compat``). The
        headers / payload / URL construction and the response extraction
        (``choices[0].message.content``) are the dispatcher's VERBATIM copies
        of what this method used to inline; what changes is only the
        transport/robustness layer — the consolidated ``@retry_llm_call``
        classification (429/5xx/ConnectionError retry with backoff;
        401/403/404 fail fast), the guarded parse (the old unguarded
        deep-indexed response parse — ``choices[0].message.content`` with
        no guard — now degrades to a logged warning + None instead of a
        KeyError) and the timeout bound (120s, same value the old code
        hardcoded).
        """
        from core.summarisation.llm_dispatcher import call_openai_compat

        return call_openai_compat(
            prompt,
            base_url,
            api_key,
            model,
            label,
            self.temperature,
            self.max_output_tokens_per_batch,
            timeout=FAST_LLM_TIMEOUT_S,
            retries=self.retries,
            provider=self.provider,
            log=self.log,
        )

    # ── Core logic ──────────────────────────────────────────────────────────

    def build(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """
        Aggregate all keypoints from summaries, translate them into plain language,
        and save to Markdown and DOCX files.
        Returns the output path of the Markdown file (or None if failed).
        """
        # V3.10.0: Check content preset — if preserve_domain_terms is True
        # (academic_paper, philosophy), skip simplification entirely. These
        # content types should keep their technical/philosophical terminology.
        from core.llm.content_presets import get_content_preset

        source_type = getattr(self.request, "source_type", "normal_book")
        preset = get_content_preset(source_type)
        if preset.preserve_domain_terms:
            self.log(
                f"  ⏭️ V3.10.0: Simplification skipped — '{preset.label}' "
                f"preserves domain terms (no jargon simplification).",
                "INFO",
            )
            return None

        # 1. Aggregate all bullet points
        all_bullets: list[str] = []
        for s in summaries:
            if s.success and s.bullet_points:
                all_bullets.extend(s.bullet_points)

        if not all_bullets:
            self.log("  ℹ️ No keypoints found to simplify.", "INFO")
            return None

        self.log(
            f"  📌 Found {len(all_bullets)} keypoints across {len(summaries)} chapters.", "INFO"
        )

        # V3.10.1 G3: Pre-build jargon dictionary cache from all bullets.
        # This scans all 10+ char words ONCE against pyenchant, so subsequent
        # _identify_jargon() calls do O(1) dict lookups instead of enchant.check().
        self._build_jargon_cache(all_bullets)

        # V3.5.0: Sequential model loading — if a separate simplification model
        # is configured, unload the summarisation model and load the simplification
        # model. This frees VRAM and enables using a different model (e.g. Qwythos)
        # that handles translation better than the summarisation model (e.g. Qwen3.5).
        if self._needs_model_swap and self.provider == "ollama":
            self.log("  🔄 V3.5.0: Swapping models for simplification phase…", "INFO")
            # Unload the summarisation model to free VRAM
            models_to_unload = []
            try:
                loaded = self.model_manager.get_loaded_models()
                for m in loaded:
                    if m != self.simplification_model:
                        models_to_unload.append(m)
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

            for m in models_to_unload:
                try:
                    self.model_manager.force_unload(m)
                    self.log(f"    🔓 Unloaded '{m}' to free VRAM", "INFO")
                except Exception as e:
                    self.log(f"    ⚠️ Could not unload '{m}': {e}", "DEBUG")

            # Load the simplification model
            if self.model_manager.model_exists(self.simplification_model):
                self.log(
                    f"    ⏳ Loading simplification model '{self.simplification_model}'…", "INFO"
                )
                loaded_ok = self.model_manager.acquire_model(
                    self.simplification_model,
                    ModelType.SUMMARISATION,
                    skip_vram_check=True,
                )
                if loaded_ok:
                    self.log(
                        f"    ✅ Simplification model loaded: {self.simplification_model}", "INFO"
                    )
                    self.model = self.simplification_model
                else:
                    self.log(
                        "    ⚠️ Failed to load simplification model — using fallback", "WARNING"
                    )
                    self.model = self.summarisation_model
            else:
                self.log(
                    f"    ⚠️ Model '{self.simplification_model}' not found — using fallback",
                    "WARNING",
                )
                self.model = self.summarisation_model

        # V3.3.3: Sequential processing — no concurrency. Concurrent workers were
        # causing access violation crashes in Ollama. Sequential is slower but
        # crash-free.

        # Prepare bullet list (filter empty)
        bullet_list = [(i + 1, bp.strip()) for i, bp in enumerate(all_bullets) if bp and bp.strip()]
        total = len(bullet_list)

        # Results stored by index to preserve order
        results: dict = {}
        completed = 0

        def _simplify_one(idx: int, bullet: str) -> tuple:
            try:
                # V3.4.0 G1+G2: Check if this bullet actually needs simplification.
                # Most keypoints are already in plain language — skip the LLM call
                # entirely for bullets that are already simple. This prevents the
                # "0% simplified" problem (bullets that don't need simplification
                # aren't counted as failures).
                from core.summarisation.text_preprocessor import should_skip_simplification

                should_skip, skip_reason = should_skip_simplification(bullet)
                if should_skip:
                    self.log(f"    ⏭️ Keypoint {idx} skipped ({skip_reason})", "DEBUG")
                    return idx, bullet  # return original — it's already simple

                # V3.3.0 D2: Try targeted simplification first (replace only jargon).
                # V3.3.3: When D2 finds no jargon, it returns the original as-is.
                # This is wrong — we should fall through to D1 (full simplification)
                # so the bullet actually gets translated to plain language.
                simplified = self._translate_single_bullet_targeted(bullet)
                # V3.3.3: If D2 returned the original (no jargon found) or None,
                # fall through to D1 full simplification.
                if simplified is None or simplified == bullet:
                    simplified = self._translate_single_bullet(bullet)
                return idx, simplified
            except Exception as e:
                self.log(f"    ⚠️ Keypoint {idx} error: {e}", "DEBUG")
                # V3.3.3: Retry once after 2s delay on access violation
                if "access violation" in str(e).lower() or "exception" in str(e).lower():
                    self.log(f"    🔄 Retrying keypoint {idx} after 2s delay…", "DEBUG")
                    time.sleep(2)
                    try:
                        simplified = self._translate_single_bullet(bullet)
                        return idx, simplified
                    except Exception as _e:
                        logger.debug("ignored %s: %s", type(_e).__name__, _e)
                return idx, None

        # V3.3.3: Switched to SEQUENTIAL processing (1 worker). Concurrent workers
        # (2 or 3) were causing access violation crashes in Ollama — the GGUF
        # model can't handle rapid concurrent requests. Sequential is slower
        # (~18 × 15s = 4.5 min) but crash-free.
        self.log(f"  📝 Simplifying {total} keypoints (sequential mode)…", "INFO")
        for completed, (idx, bullet) in enumerate(bullet_list, 1):
            idx_result, simplified = _simplify_one(idx, bullet)
            results[idx_result] = simplified if simplified else bullet
            if completed % 5 == 0 or completed == total:
                self.log(f"    📝 Simplified {completed}/{total} keypoints…", "INFO")

        # Reassemble in original order
        # V3.4.0 G1+G2: Track skipped (already simple) vs simplified vs failed
        translated_bullets = []
        # V3.9.6: Track original bullets for comparison view
        original_bullets_ordered = []
        was_simplified_flags = []
        success_count = 0
        skip_count = 0
        fail_count = 0
        for idx, original_bullet in bullet_list:
            result = results.get(idx, original_bullet)
            original_bullets_ordered.append(original_bullet)
            if result and result != original_bullet:
                translated_bullets.append(result)
                was_simplified_flags.append(True)
                success_count += 1
            else:
                translated_bullets.append(original_bullet)
                was_simplified_flags.append(False)
                # Check if this was skipped (already simple) or actually failed
                from core.summarisation.text_preprocessor import should_skip_simplification

                was_skipped, _ = should_skip_simplification(original_bullet)
                if was_skipped:
                    skip_count += 1
                else:
                    fail_count += 1

        if not translated_bullets:
            self.log("  ❌ No translated keypoints generated.", "ERROR")
            return None

        self.log(
            f"  📊 Simplification complete: {success_count} simplified, "
            f"{skip_count} already simple (skipped), "
            f"{fail_count} failed (of {total} total)",
            "INFO",
        )

        # 3. Save to files
        md_path = output_dir / f"{book_title}.Keypoints.Simplified.md"
        docx_path = output_dir / f"{book_title}.Keypoints.Simplified.docx"

        # V4.7.7: Include simplification stats in the markdown header
        md_content = self._build_markdown(
            book_title,
            translated_bullets,
            simplified_count=success_count,
            preserved_count=skip_count,
            failed_count=fail_count,
        )
        md_path.write_text(md_content, encoding="utf-8")
        self.log(f"  ✅ Simplified keypoints saved to: {md_path}", "SUCCESS")

        # V4.7.7: Save a copy-paste-ready version (no comparison, no stats,
        # no header — just the simplified keypoints as a clean numbered list)
        clean_path = output_dir / f"{book_title}.Keypoints.Simplified.Clean.md"
        clean_content = self._build_clean_markdown(book_title, translated_bullets)
        clean_path.write_text(clean_content, encoding="utf-8")
        self.log(f"  ✅ Copy-paste-ready simplified keypoints: {clean_path}", "SUCCESS")

        try:
            # V3.9.6: Pass original bullets + simplified flags for comparison view
            self._build_docx(
                book_title,
                translated_bullets,
                docx_path,
                original_bullets=original_bullets_ordered,
                was_simplified=was_simplified_flags,
            )
            self.log(f"  ✅ Simplified keypoints DOCX saved to: {docx_path}", "SUCCESS")
        except Exception as e:
            self.log(f"  ⚠️ Could not save DOCX: {e}", "WARNING")

        # V3.5.0: Unload the simplification model if we swapped it in
        if self._needs_model_swap and self.provider == "ollama":
            try:
                self.model_manager.force_unload(self.simplification_model)
                self.log("    🔓 Simplification model unloaded after use", "INFO")
            except Exception as _e:
                logger.debug("ignored %s: %s", type(_e).__name__, _e)

        return md_path

    def _strip_thinking(self, text: str) -> str:
        """Strip all forms of LLM thinking/reasoning from the response.

        The Qwen3.5-9B model is a 'thinking' model that leaks chain-of-thought.
        This mirrors the logic in summarizer.py._strip_thinking but is
        self-contained for the simplified-keypoints pipeline.
        """
        # Strip <think> and <thinking> blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)

        # Strip inline reasoning that appears AFTER the translated text on the
        # same line, e.g.:
        #   "9. X never stops 'checking the scene'... So: X never stops..."
        #   "16. Move from just watching... (Original: '<term>'). I'll keep the term in quotes."
        #   "30. Starting a chat... Double check Point 14/16 terms..."
        # These are internal-monologue fragments the model appends to items.
        text = re.sub(
            r"\s*(?:Original:|I\'ll|I will|Let\'s|Let me|So:|Double check|I can|I should|Wait|Hmm|Okay so|Now I|This means|Rule says|Keep term|Keep the term)[^\n]*$",
            "",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # Strip parenthetical reasoning like "(Original: '...'). I'll keep..."
        text = re.sub(
            r"\s*\(Original:.*?\)(?:\.\s*I[^\n]*)?",
            "",
            text,
            flags=re.DOTALL,
        )

        # Strip standalone thinking-process lines
        thinking_line_re = re.compile(
            r"^\s*(?:\*?\*?)?(?:Analyze|Process|Draft|Check|Review|Refine|Identify|"
            r"Extract|Read|Understand|Consider|Note|Step|Plan|Determine|Evaluate|"
            r"Scan|Simplification|Translation|Final|Refinement|Polish|"
            r"I\s+will|I\'ll|Let\'s|Let me|Looks good|Wait|Ready|Okay|"
            r"One more|Now|First|Next|Then|After that|Moving on|"
            r"Double check|I can|I should|This means|Rule says|"
            r"Input|Output|Rules?|Instructions?|Task|Format|Language|Condition|"
            r"Original|Simplified|Plain language|Review against|Refine for)\b.*$",
            re.IGNORECASE | re.MULTILINE,
        )
        text = thinking_line_re.sub("", text)

        # Strip sub-bullet analysis lines starting with * (Jargon:, Context:, etc.)
        text = re.sub(
            r"^\s*\*\s*\*?\*?(?:Jargon|Context|Draft|Simplification|Translation|Refinement|Check|Original|Point)\s*[:\d].*$",
            "",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # Strip common preambles at the very start
        preamble = re.compile(
            r"^(?:I'?ll\b|I will\b|I\s+need\b|Here'?s\b|Here is\b|Sure[,!]?\b|Certainly[,!]?\b|"
            r"Of course[,!]?\b|Below is\b|The following\b|Let me\b|Happy to\b|"
            r"As requested\b|Please find\b|Now\b|First\b|To summarize\b|"
            r"Let'?s\b|Looking at\b|After analyzing\b|Based on\b|"
            r"Rules:|Instructions:|Task:|Format:|Language:|Condition:|"
            r"Output:|Input:)\s*[^\n]{0,300}\n+",
            re.IGNORECASE | re.MULTILINE,
        )
        for _ in range(5):
            text = preamble.sub("", text, count=1)

        return text.strip()

    def _validate_simplification(self, original: str, response: str) -> str | None:
        """V3.9.5: Unified validation for ALL simplification output (D1, D2, batch).

        This method is the SINGLE GATEKEEPER for simplified keypoint quality.
        Every code path that produces a simplified bullet must pass its output
        through this method. If it returns None, the caller falls back to the
        original bullet.

        Guardrails (in order of execution):
        1. Unicode normalization (smart quotes → ASCII)
        2. Strip <think> blocks (all variants)
        3. Strip numbering, leading dashes, surrounding quotes
        4. REJECT reasoning prefixes (Rewritten:, Simplified:, Translated:, etc.)
        5. REJECT meta-commentary (expanded V3.9.4 list, unicode-aware)
        6. REJECT arrow notation (X -> Y, X → Y, X" becomes "Y)
        7. REJECT reasoning-format (newline + bullet list)
        8. REJECT multi-line responses (valid bullets are single sentences)
        9. REJECT too-short (< 5 words)
        10. REJECT truncated (ends with truncation word or no punctuation)
        11. STRUCTURAL: single sentence (no sentence-ending punctuation in middle)
        12. STRUCTURAL: 5-50 words
        13. REASONING_INDICATORS: first-person pronouns, meta words, comparison words
        14. SIMILARITY: 10-90% (reject verbatim copies AND completely different text)
        """
        import difflib
        import unicodedata

        if not response or not response.strip():
            return None

        # ── Guardrail 1: Unicode normalization ──────────────────────────
        # Qwythos outputs smart quotes/apostrophes that bypass ASCII patterns.
        # Normalize: " → ", " → ", ' → ', ‐ → -, — → -, … → ..., etc.
        response = unicodedata.normalize("NFKD", response)
        response = response.replace("\u201c", '"').replace("\u201d", '"')  # smart quotes
        response = response.replace("\u2018", "'").replace("\u2019", "'")  # smart apostrophes
        response = response.replace("\u2010", "-").replace("\u2011", "-")  # non-breaking hyphens
        response = response.replace("\u2013", "-").replace("\u2014", "-")  # en/em dashes
        response = response.replace("\u2026", "...")  # ellipsis
        response = response.replace("\u00a0", " ")  # non-breaking space

        # ── Guardrail 2: Strip <think> blocks (all variants) ────────────
        response = self._strip_thinking(response)
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)
        response = re.sub(
            r"<think>(?!.*</think>).*$", "", response, flags=re.DOTALL | re.IGNORECASE
        )
        response = re.sub(
            r"<thinking>(?!.*</thinking>).*$", "", response, flags=re.DOTALL | re.IGNORECASE
        )

        # ── Guardrail 3: Strip numbering, dashes, quotes ────────────────
        response = response.strip()
        response = re.sub(r"^\s*\d+[\.\)]\s*", "", response)  # "1. " or "1) "
        response = re.sub(r"^\s*[-\*]\s*", "", response)  # "- " or "* "
        response = response.strip("\"'")

        # ── Guardrail 4: REJECT reasoning prefixes ──────────────────────
        # The model is outputting reasoning format, not a simplified bullet.
        _REASONING_PREFIX = re.compile(
            r"^(?:Rewritten|Simplified|Translated|Original|Result|Answer"
            r"|Input|Output|Example|Version)\s*:\s*",
            re.IGNORECASE,
        )
        if _REASONING_PREFIX.match(response):
            return None

        # ── Guardrail 5: REJECT meta-commentary ─────────────────────────
        # Qwythos leaks its reasoning process. These patterns are NEVER valid.
        _META_COMMENTARY = re.compile(
            r"(?:^|\s)(?:"
            # First-person reasoning (the #1 indicator)
            r"I replaced|I might|If I replace|I need to|I must|I simplified|"
            r"I could|I will|I\'ll|I can|I should|I\'ve|I also|"
            r"Let me|Let\'s|So:|Yes,|Wait,|Hmm,|Now I|"
            # Meta about the original/task
            r"The original says|The original keypoint|The original sentence|"
            r"The original includes|The original mentions|"
            r"My translation|My simplified|In plain language|"
            r"Replace jargon:|This captures|So the key facts|"
            r"reading level must be|8th grade|can be rephrased to|"
            # Self-evaluation
            r"That seems|That also works|That\'s still|That\'s more|"
            r"That is appropriate|Double-check|Double check|"
            r"All good|is present\.|is retained\.|is okay|"
            # Word-choice reasoning
            r"The first option|The phrase|The meaning of|The sentence uses|"
            r"The name of the tactic|The emphasis on|"
            r"is a bit formal|might be simpler|might be too|might be considered|"
            r"becomes |replaces |closer to |"
            # Format leakage
            r"Input:|Output:|Example:|Version \d|"
            r"Combine them into|Break it into|"
            r"Since the prompt|The prompt explicitly"
            r")",
            re.IGNORECASE,
        )
        if _META_COMMENTARY.search(response):
            return None

        # ── Guardrail 6: REJECT arrow notation ──────────────────────────
        # "X -> Y", "X → Y", 'X" becomes "Y' — reasoning about translation
        if "->" in response or "→" in response:
            return None
        if re.search(r'"[^"]*"\s+becomes\s+"', response, re.IGNORECASE):
            return None

        # ── Guardrail 7: REJECT reasoning-format (newline + bullet list) ─
        if re.search(r"\n\s*[-\*]\s", response):
            return None

        # ── Guardrail 8: REJECT multi-line responses ────────────────────
        if "\n" in response:
            return None

        # ── Guardrail 8.5: REJECT foreign-script leakage ─────────────────
        # Qwen/Qwythos occasionally code-switch, emitting CJK characters
        # mid-English-sentence (e.g. "just索取 (taking)"). The source text is
        # English; no CJK should ever appear in a simplified keypoint.
        # Blocks: CJK Unified (\u4e00-\u9fff), CJK Radicals (\u2E80-\u2EFF),
        # CJK Symbols (\u3000-\u303f), Hiragana/Katakana (\u3040-\u30ff).
        if re.search(
            r"[\u2e80-\u2eff\u3000-\u303f\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]", response
        ):
            return None

        # ── Guardrail 9: REJECT too-short (< 5 words) ───────────────────
        response_words = response.split()
        if len(response_words) < 5:
            return None

        # ── Guardrail 10: REJECT truncated responses ────────────────────
        # V4.3.0: Strengthened — now also catches:
        #   (a) items ending with a truncation word EVEN IF followed by a
        #       period ("...instead of just." was slipping through)
        #   (b) unclosed quotes or parentheses ("...like a \"Top." — the
        #       opening quote/paren never closed = truncated)
        _TRUNCATION_WORDS = frozenset(
            # function words
            [
                "of",
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "who",
                "which",
                "that",
                "with",
                "for",
                "in",
                "on",
                "at",
                "to",
                "from",
                "by",
                "is",
                "are",
                "was",
            ]
            + [
                "just",
                "also",
                "only",
                "even",
                "still",
                "very",
                "too",
                "so",
                "then",
                "now",
                "here",
                "there",
                "than",
            ]
        )
        response_clean = response.rstrip("\"'\n ")

        # 10a: Unclosed bracket/quote check — if a ( [ { " opens but never
        # closes, the generation was cut off mid-clause.
        _BRACKET_PAIRS = [("(", ")"), ("[", "]"), ("{", "}")]
        for opener, closer in _BRACKET_PAIRS:
            if response_clean.count(opener) != response_clean.count(closer):
                return None  # unbalanced brackets — truncated
        # Unbalanced double quotes (odd count = one was never closed)
        if response_clean.count('"') % 2 != 0:
            return None  # unclosed quote — truncated

        # 10b: Original truncation-word check (no terminal punctuation)
        if response_clean and response_clean[-1] not in ".!?":
            last_word = re.split(r"\s+", response_clean)[-1].lower().strip("\"';:,")
            if last_word in _TRUNCATION_WORDS or len(last_word) <= 2:
                return None  # truncated — fall back to original
            response = response_clean + "."  # add period to complete
        else:
            # 10c: Has terminal punctuation — but check if the LAST WORD
            # before the period is a truncation word ("...instead of just.")
            response_stripped = response_clean.rstrip(".!?")
            last_word = re.split(r"\s+", response_stripped)[-1].lower().strip("\"';:,")
            if last_word in _TRUNCATION_WORDS:
                return None  # ends with a function word = truncated mid-clause

        # ── Guardrail 11: STRUCTURAL — single sentence ──────────────────
        # Split at sentence-ending punctuation. A valid bullet has exactly 1 sentence.
        # (Allow 2 sentences if the second is very short, e.g., "Do X. This works.")
        sentences = re.split(r"(?<=[.!?])\s+", response)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 2:
            return None  # 3+ sentences — too complex for a single bullet

        # ── Guardrail 12: STRUCTURAL — word count ───────────────────────
        word_count = len(response.split())
        if word_count < 5 or word_count > 60:
            return None

        # ── Guardrail 13: REASONING_INDICATORS (final safety net) ───────
        # These catch anything that slipped through. Response is already
        # unicode-normalized so patterns match.
        response_lower = response.lower()
        _REASONING_INDICATORS = [
            # First-person (reasoning always uses "I")
            " i ",
            " i'",
            " my ",
            " me ",
            " myself",
            # Meta about the task
            "original",
            "rewritten",
            "translation",
            "version",
            "prompt",
            "jargon",
            "simplified",
            "plain language",
            # Comparison/reasoning
            "becomes",
            "replaces",
            "closer to",
            "might be",
            "could say",
            "could combine",
            "could break",
            "could phrase",
            "need to ensure",
            "need to make sure",
            "need to preserve",
            "need to check",
            "also need",
            "must keep",
            # Self-commentary
            "that seems",
            "that also works",
            "that's still",
            "double-check",
            "double check",
            # Format leakage
            "input:",
            "output:",
            "example:",
            # Observed V3.9.4 garbage patterns
            "the first option",
            "the name of the tactic",
            "the emphasis on",
            "is present.",
            "is retained.",
            "this matches the style",
            "since the prompt",
        ]
        for indicator in _REASONING_INDICATORS:
            if indicator in response_lower:
                return None

        # ── Guardrail 14: SIMILARITY check ──────────────────────────────
        # 10-90% similarity: reject verbatim copies (>90%) AND completely
        # different text (<10%, which means the LLM generated new content
        # instead of simplifying).
        if original and len(original) > 5:
            similarity = difflib.SequenceMatcher(None, original.lower(), response.lower()).ratio()
            if similarity > 0.90:
                return None  # verbatim copy — didn't simplify
            if similarity < 0.10:
                return None  # completely different — not a simplification

        # ── Final cleanup ───────────────────────────────────────────────
        response = re.sub(r"\s+", " ", response).strip()
        if not response or len(response) < 5 or len(response) > 500:
            return None

        return response

    def _translate_single_bullet(self, bullet: str) -> str | None:
        """V3.2.4 D1: Simplify a SINGLE keypoint into plain language.

        V3.2.4 fixes:
        - Strip UNCLOSED <think> tags (model sometimes outputs <think> with no </think>)
        - Loosen validation (accept >= 5 chars, was >= 10)
        - D3: Diff-based verification — return None if output is >95% identical to input
          (model just copied it) or <20% similar (model changed too much)

        Returns the simplified bullet string, or None on failure.
        """
        bullet = bullet.strip()
        if not bullet or len(bullet) < 5:
            return None

        # V3.1.3: Check for a custom prompt from the Prompt Bank
        custom_prompt_name = Settings().get("summarisation.simplified_prompt", "")
        prompt = None
        if custom_prompt_name:
            try:
                from core.summarisation.prompt_manager import PromptManager

                pm = PromptManager()
                template = pm.load_prompt(custom_prompt_name)
                if template and "{{keypoints}}" in template:
                    prompt = template.replace("{{keypoints}}", f"1. {bullet}")
            except Exception as _e:
                prompt = None

        if prompt is None:
            # V3.9.4: Completely rewritten prompt. The old prompt contained words
            # like "Rewritten:", "Simplified:", "Translated:" which Qwythos echoed
            # back in its output. The new prompt is minimal: one instruction, one
            # example, one bullet. /no_think suppresses Qwen/Qwythos reasoning.
            try:
                from core.summarisation.prompt_manager import PromptManager

                pm = PromptManager()
                prompt = pm.render_template(
                    "summarisation/simplified_d1",
                    bullet=bullet,
                )
            except Exception as _e:
                prompt = None

        response = self._call_llm_single(prompt)
        if not response:
            return None

        # V3.9.5: ALL validation is now handled by the unified
        # _validate_simplification() method. This replaces ~150 lines of
        # inline filters that were duplicated across D1, D2, and batch paths.
        # The unified method has 14 guardrails including unicode normalization,
        # reasoning-prefix rejection, meta-commentary rejection, structural
        # validation, and similarity bounds (10-90%).
        return self._validate_simplification(bullet, response)

    def _build_jargon_cache(self, all_bullets: list[str]) -> None:
        """V3.10.1 G3: Pre-build jargon dictionary cache from all bullets.

        Scans all bullets once, extracts every 10+ char word, checks each
        against pyenchant ONCE, and caches the result. Subsequent calls to
        _identify_jargon() do a dict lookup instead of enchant.check().

        This is 10x faster than the old approach which called enchant.check()
        for every word in every bullet (redundant checks for words appearing
        in multiple bullets).
        """
        if not self._enchant_dict:
            self.log("  ℹ️ V3.10.1: Jargon cache skipped (pyenchant not available)", "DEBUG")
            return

        # Extract all unique 10+ char words from all bullets
        all_words = set()
        for bullet in all_bullets:
            words = re.findall(r"\b[a-zA-Z]{10,}\b", bullet)
            all_words.update(w.lower() for w in words)

        if not all_words:
            self._jargon_cache_built = True
            return

        # Check each word against pyenchant ONCE
        _COMMON_NAMES = frozenset(
            ["ryan", "thad", "clive", "james", "tyler", "bernard", "amsterdam", "moscow"]
        )
        jargon_count = 0
        for word in all_words:
            if word in _COMMON_NAMES:
                self._jargon_cache[word] = False  # not jargon (proper noun)
            elif self._enchant_dict.check(word):
                self._jargon_cache[word] = False  # in dictionary — not jargon
            else:
                self._jargon_cache[word] = True  # not in dictionary — jargon
                jargon_count += 1

        self._jargon_cache_built = True
        self.log(
            f"  📖 V3.10.1: Jargon cache built — {len(all_words)} unique words, "
            f"{jargon_count} identified as jargon",
            "DEBUG",
        )

    def _identify_jargon(self, bullet: str) -> list[str]:
        """V3.3.0 D2 / V3.10.1 G3: Identify jargon words in a bullet.

        Jargon = words that are:
        - Not in a standard English dictionary (pyenchant check)
        - 10+ characters (long words are more likely jargon)
        - Not common proper nouns (names)

        V3.10.1 G3: Now uses the pre-built jargon cache for O(1) lookup
        instead of calling enchant.check() per word per bullet. Falls back
        to per-word check if cache not built (backward compatibility).
        """
        words = re.findall(r"\b[a-zA-Z]{10,}\b", bullet)
        jargon = []
        # V18.20.3.9 (Phase 2 / residuals sweep): removed a hardcoded
        # character-name frozenset here. It was DEAD CODE by construction —
        # the regex only matches words of 10+ characters and every listed
        # name was shorter — but it was still book-derived vocabulary in
        # live source (the residuals-sweep policy test fails on it).

        for w in words:
            w_lower = w.lower()

            # V3.10.1 G3: Use cache if available (fast path)
            if self._jargon_cache_built and w_lower in self._jargon_cache:
                if self._jargon_cache[w_lower]:
                    jargon.append(w)
            elif self._enchant_dict:
                # Cache miss — check directly (and cache the result)
                is_jargon = not self._enchant_dict.check(w_lower)
                self._jargon_cache[w_lower] = is_jargon
                if is_jargon:
                    jargon.append(w)
            else:
                # Fallback: assume 12+ char words that aren't common are jargon
                if len(w) >= 12:
                    jargon.append(w)

        return jargon[:5]  # cap at 5 jargon words per bullet

    def _translate_single_bullet_targeted(self, bullet: str) -> str | None:
        """V3.3.0 D2: Targeted simplification — replace ONLY jargon words.

        Instead of asking the LLM to "simplify everything", identify specific
        jargon words and ask the LLM to replace ONLY those words with plain
        equivalents. This is a much simpler task — the LLM is less likely to
        under-generate or copy verbatim.

        V3.9.5: Fixed critical bug — prompt used to end with "Rewritten:" which
        Qwythos echoed back as "Rewritten: [text]". Now ends with "Output:".
        Also added _validate_simplification() call (was missing entirely —
        D2 bypassed ALL V3.9.4 filters, causing 4/53 garbage items).
        """
        bullet = bullet.strip()
        if not bullet or len(bullet) < 5:
            return None

        jargon = self._identify_jargon(bullet)
        if not jargon:
            # No jargon found — bullet is already plain. Return as-is.
            return bullet

        jargon_list = "\n".join(f"  - {j} -> [plain word]" for j in jargon)
        # V3.9.5: Changed "Rewritten:" to "Output:" to prevent echo.
        # Removed "Do NOT output thinking process" instruction (echo source).
        from core.summarisation.prompt_manager import PromptManager

        pm = PromptManager()
        prompt = pm.render_template(
            "summarisation/simplified_d2_jargon",
            jargon_list=jargon_list,
            bullet=bullet,
        )

        response = self._call_llm_single(prompt)
        if not response:
            return None

        # V3.9.5: Use unified validation (same as D1). This is the critical fix
        # — D2 previously had NO meta-commentary filter, NO reasoning-prefix
        # rejection, NO reasoning-indicators check. All garbage from D2
        # bypassed every V3.9.4 filter.
        return self._validate_simplification(bullet, response)

    def _translate_batch(self, batch_text: str) -> list[str] | None:
        """
        Send a batch of keypoints to the LLM and parse the translated list,
        stripping any meta-text and thinking-process contamination.

        V3.1.3: Supports a custom prompt template from the Prompt Bank
        (setting: summarisation.simplified_prompt). The template uses
        {{keypoints}} as the variable. Falls back to the built-in prompt
        if no custom prompt is set or found.
        """
        # V3.1.3: Check for a custom prompt from the Prompt Bank
        custom_prompt_name = Settings().get("summarisation.simplified_prompt", "")
        prompt = None
        if custom_prompt_name:
            try:
                from core.summarisation.prompt_manager import PromptManager

                pm = PromptManager()
                template = pm.load_prompt(custom_prompt_name)
                if template and "{{keypoints}}" in template:
                    prompt = template.replace("{{keypoints}}", batch_text)
            except Exception as _e:
                prompt = None  # fall back to default

        if prompt is None:
            # Built-in default prompt
            try:
                from core.summarisation.prompt_manager import PromptManager

                pm = PromptManager()
                prompt = pm.render_template(
                    "summarisation/simplified_translate_batch",
                    keypoints=batch_text,
                )
            except Exception as _e:
                prompt = None  # fall back to default

        response = self._call_llm(prompt)
        if not response:
            return None

        # --- Strip thinking process BEFORE parsing ---
        response = self._strip_thinking(response)

        # Also strip <think> blocks that might survive
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL)

        lines = response.splitlines()
        numbered_pattern = re.compile(r"^\s*(\d+)[\.)]\s+(.*)")

        THINKING_MARKERS = [
            "Analyze",
            "Process Each",
            "Process",
            "Draft",
            "Refine",
            "Refinement",
            "Check facts",
            "Check Fact",
            "Check",
            "Final Review",
            "Final Polish",
            "Final",
            "Simplification:",
            "Translation:",
            "Jargon:",
            "Context:",
            "Point 1:",
            "Point 2:",
            "Point 3:",
            "Point 4:",
            "Point 5:",
            "Point 6:",
            "Point 7:",
            "Point 8:",
            "Point 9:",
            "I will",
            "I'll",
            "Let's",
            "Let me",
            "Looks good",
            "Wait",
            "Ready",
            "Okay",
            "One more",
            "As requested",
            "Below is",
            "Here is",
            "Here are",
            "The following",
            "Sure",
            "Certainly",
            "Of course",
            "Happy to",
            "Please find",
            "To summarize",
            "Moving on",
            "Now",
            "Next",
            "Then",
            "After that",
            "Step 1",
            "Step 2",
            "Step 3",
            "Step 4",
            "Step 5",
            "Input keypoints",
            "Output keypoints",
            "Original:",
            "Simplified:",
            "Plain language:",
            "Review against Rules",
            "Refine for Flow",
            "Double check",
            "I can",
            "I should",
            "This means",
            "Rule says",
            "Keep term",
            "Keep the term",
            "So:",
        ]
        # Match with or without ** bold markers
        thinking_re = re.compile(
            r"^\*?\*?(?:" + "|".join(re.escape(m) for m in THINKING_MARKERS) + r")\b", re.IGNORECASE
        )
        internal_thinking_re = re.compile(
            r"\*(?:Jargon|Draft|Check|Refine|Simplification|Translation|Context|Refinement)\s*(?::|1|2)",
            re.IGNORECASE,
        )
        # Detect inline thinking appended to a numbered item
        inline_thinking_re = re.compile(
            r"\s*(?:\.\s*)?(?:Original:|I\'ll|I will|Let\'s|Let me|So:|Double check|I can|I should|Wait|Hmm|Okay so|Now I|This means|Rule says|Keep term|Keep the term)\b",
            re.IGNORECASE,
        )

        runs = []
        current_run = []
        expected_num = 1
        for line in lines:
            stripped = line.strip()
            m = numbered_pattern.match(stripped)
            if m:
                num = int(m.group(1))
                content = m.group(2).strip()
                # Strip inline thinking from the content itself
                content = inline_thinking_re.split(content)[0].strip()
                # Strip parenthetical (Original: ...) notes
                content = re.sub(r"\s*\(Original:.*?\).*$", "", content, flags=re.DOTALL).strip()
                if thinking_re.match(content) or internal_thinking_re.search(content):
                    if current_run:
                        runs.append(current_run)
                    current_run = []
                    expected_num = 1
                    continue
                if num == expected_num:
                    current_run.append(content)
                    expected_num += 1
                    continue
                elif num == 1:
                    if current_run:
                        runs.append(current_run)
                    current_run = [content]
                    expected_num = 2
                    continue
            if current_run and stripped:
                is_meta = thinking_re.match(stripped) or internal_thinking_re.search(stripped)
                if is_meta:
                    if current_run:
                        runs.append(current_run)
                    current_run = []
                    expected_num = 1
                elif not stripped.startswith("*"):
                    # Strip inline thinking before appending continuation
                    cleaned = inline_thinking_re.split(stripped)[0].strip()
                    if cleaned:
                        current_run[-1] += " " + cleaned
        if current_run:
            runs.append(current_run)

        if runs:
            best_run = max(runs, key=len)
            translated = []
            for item in best_run:
                item = item.strip()
                # Final cleanup: strip any residual inline thinking
                item = inline_thinking_re.split(item)[0].strip()
                item = re.sub(r"\s*\(Original:.*?\).*$", "", item, flags=re.DOTALL).strip()
                if (
                    item
                    and len(item) > 10
                    and not thinking_re.match(item)
                    and not internal_thinking_re.search(item)
                ):
                    translated.append(item)
        else:
            translated = []

        return translated if translated else None

    def _build_markdown(
        self,
        book_title: str,
        translated_bullets: list[str],
        simplified_count: int = 0,
        preserved_count: int = 0,
        failed_count: int = 0,
    ) -> str:
        """Assemble the final Markdown output.

        V4.7.7: Includes simplification stats in the header:
        "X Simplified | Y Preserved | Z Failed"
        """
        lines = [
            f"# Simplified Keypoints Digest: {book_title}",
            "",
            "> This document presents all key takeaways from the book, translated into plain, everyday language.",
            "> Facts are preserved; jargon has been simplified for broader accessibility.",
            "",
            "---",
            "",
            f"**Total keypoints:** {len(translated_bullets)}",
        ]

        # V4.7.7: Add simplification stats
        if simplified_count or preserved_count or failed_count:
            stats_parts = []
            if simplified_count:
                stats_parts.append(f"**{simplified_count} Simplified**")
            if preserved_count:
                stats_parts.append(f"**{preserved_count} Preserved** (already simple)")
            if failed_count:
                stats_parts.append(f"**{failed_count} Failed** (kept original)")
            lines.append(f"📊 {' | '.join(stats_parts)}")

        lines.extend(
            [
                "",
                "---",
                "",
            ]
        )
        for i, point in enumerate(translated_bullets, 1):
            lines.append(f"{i}. {point}")
            lines.append("")  # blank line after each keypoint
            lines.append("")  # extra blank line for readability spacing
            lines.append("")  # V3.4.2: third blank line for more line height

        return "\n".join(lines)

    def _build_clean_markdown(self, book_title: str, bullets: list[str]) -> str:
        """V4.7.7: Build a copy-paste-ready simplified keypoints file.

        No header, no stats, no comparison — just the simplified keypoints
        as a clean numbered list. Ready to paste into any document.
        """
        lines = []
        for i, point in enumerate(bullets, 1):
            lines.append(f"{i}. {point}")
        return "\n".join(lines)

    def _build_docx(
        self,
        book_title: str,
        translated_bullets: list[str],
        docx_path: Path,
        original_bullets: list[str] | None = None,
        was_simplified: list[bool] | None = None,
    ) -> None:
        """Build a professionally styled DOCX file.

        V3.9.6: Added comparison view — if original_bullets and was_simplified
        are provided, the DOCX includes a 2-column table showing the original
        keypoint next to the simplified version, with a status indicator
        (✅ Simplified / ⏭️ Kept Original). This makes it easy to verify that
        simplification preserved the meaning.
        """
        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Helvetica"
        style.font.size = Pt(11)

        # Title
        title = doc.add_heading(f"Simplified Keypoints Digest: {book_title}", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Subtitle / intro
        p = doc.add_paragraph()
        run = p.add_run(
            "This document presents all key takeaways from the book, translated into plain, everyday language."
        )
        run.font.size = Pt(11)
        run.font.italic = True
        p.paragraph_format.space_after = Pt(12)

        p = doc.add_paragraph()
        run = p.add_run(
            "Facts are preserved; jargon has been simplified for broader accessibility."
        )
        run.font.size = Pt(11)
        run.font.italic = True
        p.paragraph_format.space_after = Pt(24)

        # Separator line
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(12)
        sep_run = p.add_run("—" * 60)
        sep_run.font.size = Pt(10)
        sep_run.font.color.rgb = RGBColor(150, 150, 150)

        # Total keypoints
        p = doc.add_paragraph()
        run = p.add_run(f"Total keypoints: {len(translated_bullets)}")
        run.font.size = Pt(12)
        run.font.bold = True
        p.paragraph_format.space_after = Pt(24)

        # V3.9.6: Comparison view (if original bullets provided)
        # Shows a 2-column table: Original | Simplified, with status indicator
        if original_bullets and len(original_bullets) == len(translated_bullets):
            # Section heading
            doc.add_heading("Side-by-Side Comparison", level=1)
            p = doc.add_paragraph()
            run = p.add_run("Original keypoints next to their simplified versions. ")
            run.font.italic = True
            run.font.size = Pt(10)
            run2 = p.add_run("✅ = simplified   ")
            run2.font.size = Pt(10)
            run2.font.color.rgb = RGBColor(0, 128, 0)
            run3 = p.add_run("⏭️ = kept original (already simple or simplification failed)")
            run3.font.size = Pt(10)
            run3.font.color.rgb = RGBColor(150, 150, 150)
            p.paragraph_format.space_after = Pt(12)

            # Build comparison table
            from docx.shared import Inches as DocxInches

            table = doc.add_table(rows=1, cols=3)
            table.style = "Light Shading Accent 1"
            table.autofit = False

            # Header row
            hdr = table.rows[0].cells
            hdr[0].text = "#"
            hdr[1].text = "Original"
            hdr[2].text = "Simplified"

            # Set column widths
            for row in table.rows:
                row.cells[0].width = DocxInches(0.4)
                row.cells[1].width = DocxInches(2.8)
                row.cells[2].width = DocxInches(2.8)

            # Data rows
            for i, (orig, simp, was_simp) in enumerate(
                zip(
                    original_bullets,
                    translated_bullets,
                    was_simplified or [True] * len(translated_bullets),
                    strict=False,
                ),
                1,
            ):
                row = table.add_row().cells
                # Number + status indicator
                status = "✅" if was_simp else "⏭️"
                row[0].text = f"{i}\n{status}"
                row[1].text = orig[:300] + ("…" if len(orig) > 300 else "")
                row[2].text = simp[:300] + ("…" if len(simp) > 300 else "")
                # Style the cells
                for cell in row:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(9)
                # If not simplified, gray out the "Simplified" column (same as original)
                if not was_simp:
                    for paragraph in row[2].paragraphs:
                        for run in paragraph.runs:
                            run.font.color.rgb = RGBColor(150, 150, 150)

            # Spacing after table
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(24)

            # Separator before simple list
            p = doc.add_paragraph()
            sep_run = p.add_run("—" * 60)
            sep_run.font.size = Pt(10)
            sep_run.font.color.rgb = RGBColor(150, 150, 150)
            p.paragraph_format.space_after = Pt(12)

            doc.add_heading("Simplified List", level=1)

        # Bullet points (simple list — always included)
        for _i, point in enumerate(translated_bullets, 1):
            p = doc.add_paragraph(style="List Number")
            run = p.add_run(point)
            run.font.size = Pt(11)
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_after = Pt(
                20
            )  # V3.4.2: increased from 14 → 20 for more line height

        doc.save(str(docx_path))
