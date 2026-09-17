"""V18.20.0.0 (Phase 3 / capstone): converter — thin re-export layer.

The last god-module extraction. All code moved to ``converter_impl.py``; this
module re-exports everything for backward compatibility. All existing imports
``from core.pipeline.converter import X`` and ``from core.pipeline import Converter``
continue to work unchanged.

**Why now (V18.20.0.0):** the V18.19.2.0 D4 fix made the three eager
``from core.summarisation import ...`` lines LAZY (inside ``convert()``), breaking
the circular import chain (controller → pipeline.__init__ → converter →
core.summarisation → summarizer → postchecks). The prior V18.19.1.1 attempt at
this split crashed with ``ImportError: cannot import name '_sanitize_filename'
from 'converter_impl'`` because ``from converter_impl import *`` forced full
evaluation of converter_impl's ``from core.summarisation import Summarizer``
before converter.py finished loading. With D4 in place, converter_impl has NO
module-level ``core.summarisation`` imports — the ``import *`` resolves cleanly.

Pattern: identical to the 4 prior splits (postchecks V18.18.0.2, text_preprocessor
V18.19.0.0, content_judge V18.19.1.1, llm_provider V18.19.1.1).
"""
from __future__ import annotations

# Re-export everything from the implementation module
from core.pipeline.converter_impl import *  # noqa: F401, F403

# Explicit re-export of the Converter class (the only public top-level name).
# ``from core.pipeline import Converter`` and ``from core.pipeline.converter
# import Converter`` both resolve through this.
from core.pipeline.converter_impl import Converter  # noqa: F401
