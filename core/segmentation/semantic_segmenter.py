"""
Semantic segmenter — uses a local LLM to propose chapter boundaries.

KEY FIXES vs original:
  - self.request.semantic_model_name → self.request.summarisation_model
    (ConversionRequest has no semantic_model_name field; summarisation_model is the
     correct text-model field that already exists)
  - self.model_manager.load_model() → self.model_manager.acquire_model()
    (ModelManager has no load_model method; acquire_model is the correct call)
  - safe_ollama_request json= kwarg was already correct here; kept as-is
"""

import json
import re
from collections.abc import Callable

from core.llm import ModelManager, ModelType
from core.models import ConversionRequest, Segment
from utils.logging import get_main_logger
from utils.network import safe_ollama_request
from utils.settings import Settings
from utils.token_counter import truncate_by_tokens

logger = get_main_logger()


class SemanticSegmenter:
    """
    Uses an LLM (gemma3, llama3, etc.) to identify logical chapter boundaries in
    documents that lack explicit heading markers. Works best for narrative texts.

    Falls back gracefully if the LLM is unavailable or returns bad JSON.
    """

    def __init__(
        self,
        request: ConversionRequest,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.request = request
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.model_manager = ModelManager()
        # V18.20.4.3 (P2 / W-c9): canonical Ollama URL from settings —
        # was hardcoded localhost (broke remote-Ollama rigs).
        try:
            self.ollama_base_url = Settings().get_ollama_url()
        except Exception:
            self.ollama_base_url = "http://localhost:11434"
        self.timeout = 180  # 3 minutes

    def _build_prompt(self, text_sample: str, total_pages: int) -> str:
        return f"""You are an expert document analyst.
Below is the beginning of a document ({total_pages} pages total).
Identify the logical chapter or section boundaries.

Return ONLY a JSON array with objects having "title" (chapter name) and "start_page" (1-based integer).
Example: [{{"title": "Introduction", "start_page": 1}}, {{"title": "Chapter 1", "start_page": 5}}]

Document sample:
{truncate_by_tokens(text_sample, 3500)}

Return only the JSON array, no other text:"""

    def segment(
        self,
        markdown_text: str,
        total_pages: int,
        page_markers: list[tuple[int, int]],
    ) -> list[Segment]:
        """
        Identify segments via LLM.
        Returns empty list if the model is unavailable or returns unusable output.
        """
        # FIX: was self.request.semantic_model_name (doesn't exist in ConversionRequest)
        #      Correct field is summarisation_model (the configured text LLM)
        model_name = self.request.summarisation_model
        if not model_name:
            self.log("[SemanticSegmenter] No text model configured — skipping", "WARNING")
            return []

        if not self.model_manager.model_exists(model_name):
            self.log(
                f"[SemanticSegmenter] Model '{model_name}' not found in Ollama — skipping",
                "WARNING",
            )
            return []

        self.log(f"[SemanticSegmenter] Loading model: {model_name}…", "INFO")

        # FIX: was self.model_manager.load_model() — method does not exist
        #      Correct method is acquire_model()
        if not self.model_manager.acquire_model(model_name, ModelType.SEMANTIC):
            self.log(f"[SemanticSegmenter] Could not load '{model_name}' — skipping", "WARNING")
            return []

        try:
            prompt = self._build_prompt(markdown_text, total_pages)
            payload = {
                "model": model_name,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024},
            }

            self.log("[SemanticSegmenter] Requesting chapter boundaries from LLM…", "INFO")
            response = safe_ollama_request(
                "POST",
                f"{self.ollama_base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            data = response.json()
            raw_response = data.get("response", "[]")

            # Extract JSON array from response (tolerant of surrounding prose)
            json_match = re.search(r"\[[\s\S]*?\]", raw_response)
            if json_match:
                raw_response = json_match.group(0)

            chapters = json.loads(raw_response)
            if not isinstance(chapters, list) or not chapters:
                self.log("[SemanticSegmenter] LLM returned empty chapter list", "WARNING")
                return []

            segments = []
            for i, ch in enumerate(chapters):
                title = ch.get("title", f"Section {i + 1}")
                start_page = int(ch.get("start_page", 1))
                end_page = (
                    int(chapters[i + 1].get("start_page", total_pages)) - 1
                    if i < len(chapters) - 1
                    else total_pages
                )

                # Map page numbers to character positions using the marker list
                start_pos = next(
                    (pos for p, pos in page_markers if p == start_page), 0
                )
                end_pos = next(
                    (pos for p, pos in page_markers if p == end_page + 1), len(markdown_text)
                )

                content = markdown_text[start_pos:end_pos].strip()

                segments.append(
                    Segment(
                        heading=title,
                        content=content,
                        start_page=start_page,
                        end_page=end_page,
                        segment_type="chapter",
                    )
                )

            self.log(
                f"[SemanticSegmenter] Found {len(segments)} semantic sections", "INFO"
            )
            return segments

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.log(f"[SemanticSegmenter] Parse error: {e}", "WARNING")
            return []
        except Exception as e:
            self.log(f"[SemanticSegmenter] Unexpected error: {e}", "ERROR")
            return []
        finally:
            self.model_manager.release_model(model_name)
