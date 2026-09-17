"""V18.11 (Phase 5 Stage 3, Batch 2.1) — map_reduce characterization tests.

Byte-for-byte stability gate for ``map_reduce_summarize`` extracted from
``Summarizer._map_reduce_summarize``. Uses mocked ``build_prompt`` /
``call_llm`` and a tmp_path cache_dir to capture the map→reduce flow
deterministically.

Run: pytest tests/test_map_reduce.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Stub tiktoken so utils.token_counter imports cleanly.
if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E:
        def encode(self, s, disallowed_special=()):  # pragma: no cover - stub
            return s.split()
        def decode(self, tokens):  # pragma: no cover - stub
            return ' '.join(tokens)
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: _E()
    tk.encoding_for_model = lambda *a, **k: _E()
    sys.modules['tiktoken'] = tk

from core.summarisation.map_reduce import map_reduce_summarize

# ── helpers ──────────────────────────────────────────────────────────────────


class _CapturingLog:
    def __init__(self):
        self.calls = []

    def __call__(self, msg: str, level: str = "INFO"):
        self.calls.append((msg, level))


def _build_multi_para_content(n: int = 12, words_per_para: int = 250) -> str:
    """Build content large enough to produce multiple chunks at 4000 tok/chunk.
    Each paragraph is ~words_per_para words (≈ 325 tokens at 1.3 tok/word)."""
    paras = []
    for i in range(n):
        body = " ".join([f"word{i}_{j}" for j in range(words_per_para)])
        paras.append(f"Paragraph {i}: {body}.")
    return "\n\n".join(paras)


def _make_deps(
    *,
    llm_responses=None,
    build_prompt_result: str = "REDUCE_PROMPT",
):
    """Build mock build_prompt + call_llm. llm_responses is a list cycled
    through (map chunks then the reduce call)."""
    if llm_responses is None:
        llm_responses = ["map response"]
    responses = list(llm_responses)
    call_idx = {"i": 0}
    build_calls = []
    llm_calls = []

    def build_prompt(heading, text, with_cot=True, **kw):
        build_calls.append({"heading": heading, "text": text, "with_cot": with_cot})
        return build_prompt_result

    def call_llm(prompt, model=None, temperature=None, **kw):
        i = call_idx["i"]
        call_idx["i"] += 1
        llm_calls.append({"prompt": prompt, "model": model, "temperature": temperature})
        if i < len(responses):
            return responses[i]
        return None

    return {
        "build_prompt": build_prompt,
        "call_llm": call_llm,
        "_build_calls": build_calls,
        "_llm_calls": llm_calls,
    }


# ── 1. chunking + map phase ───────────────────────────────────────────────


class TestMapReduceChunking:
    def test_multi_paragraph_produces_multiple_chunks(self):
        """Large content (many paragraphs > MAP_CHUNK_TOKENS) is split into
        multiple chunks; each chunk is summarised (map phase)."""
        content = _build_multi_para_content(n=20, words_per_para=300)  # ~20 chunks worth
        deps = _make_deps(llm_responses=[f"mini {i}" for i in range(20)] + ["REDUCED"])
        cap = _CapturingLog()
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="test-model",
            cache_dir=Path("/tmp/nonexistent_cache_dir"),
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.10,
            map_mini_words=300,
            log=cap,
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # Multiple map LLM calls + 1 reduce call
        assert len(deps["_llm_calls"]) >= 2
        # The reduce call is the last one
        assert deps["_llm_calls"][-1]["prompt"] == "REDUCE_PROMPT"
        # Reduce used temperature=0.7 (full), map used 0.7*0.7=0.49
        assert deps["_llm_calls"][-1]["temperature"] == 0.7
        if len(deps["_llm_calls"]) > 1:
            assert abs(deps["_llm_calls"][0]["temperature"] - 0.49) < 0.01

    def test_small_content_single_chunk(self):
        """Content under MAP_CHUNK_TOKENS fits in one chunk → one map call."""
        content = "A short paragraph with a few words."
        deps = _make_deps(llm_responses=["mini 1", "REDUCED"])
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="test-model",
            cache_dir=Path("/tmp/nonexistent_cache_dir"),
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.10,
            map_mini_words=300,
            log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # Exactly 1 map call + 1 reduce call
        assert len(deps["_llm_calls"]) == 2


# ── 2. reduce phase + return contract ────────────────────────────────────


class TestMapReduceReduce:
    def test_returns_reduce_response_and_token_count(self):
        """Returns (reduce_response, combined_tokens) tuple."""
        content = "A paragraph with enough content to summarise meaningfully here."
        deps = _make_deps(llm_responses=["mini summary", "FINAL REDUCED SUMMARY"])
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="test-model",
            cache_dir=Path("/tmp/nonexistent_cache_dir"),
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.10,
            map_mini_words=300,
            log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        assert out == "FINAL REDUCED SUMMARY"
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_all_map_chunks_fail_returns_none_zero(self):
        """If every map chunk's LLM call returns None, returns (None, 0)."""
        content = _build_multi_para_content(n=5, words_per_para=300)
        deps = _make_deps(llm_responses=[None, None, None, None, None])  # all fail
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="test-model",
            cache_dir=Path("/tmp/nonexistent_cache_dir"),
            input_path_stem="book",
            cache_enabled=False,
            temperature=0.7,
            map_chunk_tokens=4000,
            map_chunk_overlap=0.10,
            map_mini_words=300,
            log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        assert out is None
        assert tokens == 0

    def test_returns_tuple_types(self):
        """Returns a (Optional[str], int) tuple."""
        content = "Short content here."
        deps = _make_deps(llm_responses=["mini", "reduced"])
        out, tokens = map_reduce_summarize(
            "Ch", content,
            primary_model="m", cache_dir=Path("/tmp/x"),
            input_path_stem="b", cache_enabled=False,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        assert isinstance(tokens, int)
        assert out is None or isinstance(out, str)


# ── 3. cache behaviour ────────────────────────────────────────────────────


class TestMapReduceCache:
    def test_cache_disabled_does_not_write(self, tmp_path):
        """With cache_enabled=False, no cache file is written even after a
        successful map+reduce."""
        content = "Some content for the map reduce test here."
        deps = _make_deps(llm_responses=["mini", "reduced"])
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        map_reduce_summarize(
            "Chapter 1", content,
            primary_model="m", cache_dir=cache_dir,
            input_path_stem="book", cache_enabled=False,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # No cache files written
        assert list(cache_dir.iterdir()) == []

    def test_cache_enabled_writes_cache_file(self, tmp_path):
        """With cache_enabled=True, a cache file is written after map+reduce."""
        content = "Some content for the map reduce cache test here."
        deps = _make_deps(llm_responses=["mini summary", "reduced final"])
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="m", cache_dir=cache_dir,
            input_path_stem="book", cache_enabled=True,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        cache_files = list(cache_dir.glob("mapreduce_*.mini_summaries.md"))
        assert len(cache_files) == 1
        # Cache file contains the mini-summary
        text = cache_files[0].read_text(encoding="utf-8")
        assert "mini summary" in text
        assert "# Chapter: Chapter 1" in text

    def test_cache_hit_skips_map_phase(self, tmp_path):
        """When a cache file exists and cache_enabled=True, the map phase is
        skipped — only the reduce LLM call runs (1 call, not N+1)."""
        content = "Some content that would normally be chunked."
        # Cache-hit path makes EXACTLY 1 LLM call (the reduce). The map-phase
        # responses are intentionally absent from this list — if the map phase
        # ran, call_llm would return None (out-of-list) and the test would fail
        # differently. The single response here is the reduce result.
        deps = _make_deps(llm_responses=["REDUCED_FROM_CACHE"])
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # Compute the exact cache key the function uses:
        # V18.20.2.0 (SWOT A29 — STALE TEST UPDATED): the cache key hashes the
        # FULL content (sha256[:16]), not the pre-A29 md5(content[:500])[:8].
        # The old test computed the legacy key, pre-created a cache file that
        # could never be hit under the new key, and then asserted the map
        # phase was skipped — a guaranteed failure (the map phase ran: 2 LLM
        # calls instead of 1). The key change is INTENTIONAL: 500-char-prefix
        # keys collided for chapters sharing frontmatter, and edits past char
        # 500 never invalidated the cache. Key-format change invalidates old
        # on-disk entries (cache is opt-in, default OFF).
        #   content_hash = sha256(content)[:16]
        #   model_tag    = (primary_model or "unknown")[:20]  → "m" for "m"
        #   cache_key    = md5(f"{heading}_{input_path_stem}_{content_hash}_{model_tag}")
        import hashlib
        content_hash = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()[:16]
        model_tag = "m"  # (primary_model or "unknown")[:20] with primary_model="m"
        key = hashlib.md5(f"Chapter 1_book_{content_hash}_{model_tag}".encode()).hexdigest()
        cache_file = cache_dir / f"mapreduce_{key}.mini_summaries.md"
        cached_body = "Cached mini summary content covering the chapter."
        cache_file.write_text(
            f"# Map-Reduce Mini-Summaries\n# Chapter: Chapter 1\n# Chunks: 1\n\n{cached_body}",
            encoding="utf-8",
        )
        cap = _CapturingLog()
        out, tokens = map_reduce_summarize(
            "Chapter 1", content,
            primary_model="m", cache_dir=cache_dir,
            input_path_stem="book", cache_enabled=True,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=cap,
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # Exactly 1 LLM call (the reduce) — the map phase was skipped.
        assert len(deps["_llm_calls"]) == 1
        # The single call's prompt is the REDUCE prompt (from build_prompt),
        # NOT a "Summarize the following excerpt..." map prompt.
        assert deps["_llm_calls"][0]["prompt"] == "REDUCE_PROMPT"
        assert out == "REDUCED_FROM_CACHE"
        # An INFO log about the cached mini-summaries
        infos = [m for m, l in cap.calls if l == "INFO"]
        assert any("cached" in i.lower() for i in infos)


# ── 4. build_prompt + map-prompt composition ──────────────────────────────


class TestMapReducePromptComposition:
    def test_map_prompt_contains_heading_and_word_count(self):
        """The map-phase prompt includes the chapter heading and the
        MAP_MINI_WORDS target."""
        content = "A paragraph for the map reduce prompt composition test here."
        deps = _make_deps(llm_responses=["mini", "reduced"])
        map_reduce_summarize(
            "My Chapter", content,
            primary_model="m", cache_dir=Path("/tmp/x"),
            input_path_stem="b", cache_enabled=False,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # The first LLM call is the map call; its prompt contains the heading
        # and "exactly 300 words"
        map_prompt = deps["_llm_calls"][0]["prompt"]
        assert "My Chapter" in map_prompt
        assert "exactly 300 words" in map_prompt

    def test_reduce_prompt_built_with_combined_content(self):
        """build_prompt is called with the heading and the combined
        mini-summaries prefixed by the '[Sequential summaries...]' header."""
        content = "A paragraph for the reduce prompt test here with content."
        deps = _make_deps(llm_responses=["mini summary one", "reduced"])
        map_reduce_summarize(
            "Reduce Chapter", content,
            primary_model="m", cache_dir=Path("/tmp/x"),
            input_path_stem="b", cache_enabled=False,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300, log=_CapturingLog(),
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        # build_prompt was called (at least once, for the reduce step)
        assert len(deps["_build_calls"]) >= 1
        reduce_call = deps["_build_calls"][-1]
        assert reduce_call["heading"] == "Reduce Chapter"
        assert "[Sequential summaries covering the complete chapter]" in reduce_call["text"]
        assert "mini summary one" in reduce_call["text"]


# ── 5. byte-for-byte stability ──────────────────────────────────────────────


class TestMapReduceByteForByte:
    def test_deterministic_for_fixed_inputs(self, tmp_path):
        """Same inputs → same (out, tokens) across calls."""
        content = "Deterministic content for the map reduce test here."
        cache_dir = tmp_path / "c"
        cache_dir.mkdir()
        kwargs = dict(
            primary_model="m", cache_dir=cache_dir, input_path_stem="b",
            cache_enabled=False, temperature=0.7, map_chunk_tokens=4000,
            map_chunk_overlap=0.10, map_mini_words=300, log=_CapturingLog(),
        )
        deps1 = _make_deps(llm_responses=["mini", "reduced"])
        r1 = map_reduce_summarize("Ch", content, **{**kwargs, **{k: v for k, v in deps1.items() if not k.startswith("_")}})
        deps2 = _make_deps(llm_responses=["mini", "reduced"])
        r2 = map_reduce_summarize("Ch", content, **{**kwargs, **{k: v for k, v in deps2.items() if not k.startswith("_")}})
        assert r1 == r2

    def test_no_log_callback_does_not_raise(self):
        """log=None (default) → _noop_log → no raise."""
        content = "Content for the no log test."
        deps = _make_deps(llm_responses=["mini", "reduced"])
        out, tokens = map_reduce_summarize(
            "Ch", content,
            primary_model="m", cache_dir=Path("/tmp/x"),
            input_path_stem="b", cache_enabled=False,
            temperature=0.7, map_chunk_tokens=4000, map_chunk_overlap=0.10,
            map_mini_words=300,
            **{k: v for k, v in deps.items() if not k.startswith("_")},
        )
        assert out == "reduced"
