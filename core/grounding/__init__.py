"""V10.1.0: Source-grounding layer — Google langextract integration.

This package isolates the ``langextract`` library (Google, Apache-2.0) behind
a clean internal interface so the rest of the codebase never imports
``langextract`` directly.  If the library is ever missing, broken, or the
configured model backend is unreachable, every public function degrades
*gracefully* — returning a ``GroundingResult`` with ``available=False`` and a
loud ``alarm`` message, so the pipeline continues on the existing 7-layer
defense (Layers 1-7) without silent weakening.

Two backends are supported (Q1=C — configurable):

* **ollama** (default) — local inference via Ollama.  No API key.  Gets
  precise ``char_interval`` grounding but NO schema-constrained output
  (langextract limitation on Ollama).
* **cloud** — OpenAI-compatible endpoint (9Router / OpenRouter / OpenAI).
  Gets schema-constrained output where supported.  Adds latency + cost.

Design contract
---------------
* ``ClaimExtractor`` is the *only* class the rest of the app touches.
* It is **thread-safe** (one internal lock around langextract calls, which
  are not guaranteed reentrant).
* It is **lazy** — langextract is imported on first use, so the app still
  boots if the library isn't installed (just with grounding disabled).
* It is **cached** — the few-shot example set is built once per content
  type, not per call.
* It **alarms loudly** on failure (Q2=A+alarm): every fallback path emits a
  ``GroundingAlarm`` with a severity the UI/log can surface, so the user
  always knows grounding was degraded for a chapter.
"""

import logging

from core.grounding.claim_extractor import (
    ClaimExtractor,
    GroundedClaim,
    GroundingAlarm,
    GroundingBackend,
    GroundingResult,
    default_backend,
    is_langextract_available,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ClaimExtractor",
    "GroundingBackend",
    "GroundingResult",
    "GroundedClaim",
    "GroundingAlarm",
    "is_langextract_available",
    "default_backend",
]
