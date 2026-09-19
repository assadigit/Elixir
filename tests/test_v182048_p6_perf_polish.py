"""V18.20.4.8 (P6) — performance-polish pins.

Covers the six P6 items (all hermetic — no network, no disk cache side
effects, every external call site monkeypatched):

  - **O-a3** — ``check_coverage`` / ``extract_authors_from_analysis``
    memoized (``@lru_cache`` on the immutable cores
    ``_check_coverage_cached`` / ``_extract_authors_cached``); public
    wrappers keep fresh-dict / fresh-list semantics and stay replaceable
    via ``setattr`` (the recall-floor / gap-filler monkeypatch contract).
  - **O-a6** — ``find_analysis_for_heading`` whole-tree ``rglob`` scan
    cached per resolved output dir with mtime invalidation
    (``_ANALYSIS_SCAN_CACHE`` / ``_list_analysis_files``).
  - **O-a5 / W-a5** — single canonical structural-stopwords module
    (``core/summarisation/structural_stopwords.py``); the three former
    inline literals (text_preprocessor_impl / summarizer /
    scholar_reflection) are gone, all three sites import the canonical
    module, and the ``"goes", "goes"`` literal duplication is fixed.
  - **W-a4 / O-a7** — ``simplified_keypoints`` migrated to the house LLM
    dispatcher (``llm_dispatcher.call_openai_compat``) and the
    ``@retry_llm_call`` guard pattern; the unguarded deep-indexed
    ``resp.json()["choices"][0]`` parse and both hand-rolled retry loops
    are gone.
  - **O-a8 / W-a9** — ``max_tokens`` is part of the response-cache key;
    same text + different max_tokens can no longer collide.
  - **O-c3** — adaptive-TOC LLM result cache (per-process, FIFO-capped,
    fail-soft, entry copies). REMOVED in V0.08 (P2): the adaptive_toc
    module was dead code — see the tombstone note at the bottom of this
    file.

Run: pytest tests/test_v182048_p6_perf_polish.py -v
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Source paths ────────────────────────────────────────────────────────────

_DA = _project_root / "core" / "preprocessing" / "deterministic_analyzer.py"
_SK = _project_root / "core" / "summarisation" / "simplified_keypoints.py"
_RC = _project_root / "core" / "llm" / "response_cache.py"
_SW = _project_root / "core" / "summarisation" / "structural_stopwords.py"
_TPI = _project_root / "core" / "summarisation" / "text_preprocessor_impl.py"
_SUM = _project_root / "core" / "summarisation" / "summarizer.py"
_SR = _project_root / "core" / "summarisation" / "scholar_reflection.py"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Drop full-line comments and inline '# ...' fragments so pins assert
    CODE, not the fix-documentation comments around it (house pattern from
    tests/test_v182043_p2_settings_integrity.py)."""
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split(" # ")[0].rstrip() if " # " in line else line)
    return "\n".join(out)


# A deterministic analysis with a Citations section shared by the O-a3 tests.
_ANALYSIS = (
    "## Citations\n\n"
    "1. **Erikson** (12 mentions): 1950, 1956, 1958\n"
    "2. **Winnicott** (4 mentions): 1949, 1960\n"
    "3. **Mahler** (2 mentions): 1968\n\n"
    "## Headings\n\n- one\n"
)


# ═══════════════════════════════════════════════════════════════════════════
# O-a3 — memoized check_coverage / extract_authors_from_analysis
# ═══════════════════════════════════════════════════════════════════════════


class TestOa3MemoizedCoverage:
    def test_source_pins_cached_cores_exist(self):
        src = _strip_comments(_src(_DA))
        assert "@lru_cache(maxsize=512)" in src
        assert "def _extract_authors_cached(analysis: str) -> tuple:" in src
        assert "def _check_coverage_cached(analysis: str, summary_text: str) -> tuple:" in src
        # the public wrappers stay module-level (replaceable via setattr)
        assert "def extract_authors_from_analysis(analysis: str) -> list[str]:" in src
        assert "def check_coverage(analysis: str, summary_text: str) -> dict:" in src

    def test_repeated_calls_equal_and_independent(self):
        from core.preprocessing.deterministic_analyzer import (
            check_coverage,
            extract_authors_from_analysis,
        )

        r1 = check_coverage(_ANALYSIS, "Erikson and Winnicott and Mahler appear")
        r2 = check_coverage(_ANALYSIS, "Erikson and Winnicott and Mahler appear")
        assert r1 == r2 and r1 is not r2
        # callers may mutate the result without poisoning the cache
        r1["missing"].append("MUT")
        r1["covered"].clear()
        r1["total"] = -1
        r3 = check_coverage(_ANALYSIS, "Erikson and Winnicott and Mahler appear")
        assert r3 == {
            "total": 3,
            "covered": ["Erikson", "Winnicott", "Mahler"],
            "missing": [],
            "coverage_pct": 1.0,
        }, r3
        a1 = extract_authors_from_analysis(_ANALYSIS)
        a1.append("MUT")
        assert extract_authors_from_analysis(_ANALYSIS) == [
            "Erikson",
            "Winnicott",
            "Mahler",
        ]

    def test_empty_contracts_unchanged(self):
        from core.preprocessing.deterministic_analyzer import (
            check_coverage,
            extract_authors_from_analysis,
        )

        assert check_coverage("", "x") == {
            "total": 0,
            "covered": [],
            "missing": [],
            "coverage_pct": 1.0,
        }
        assert check_coverage(None, "x") == {
            "total": 0,
            "covered": [],
            "missing": [],
            "coverage_pct": 1.0,
        }
        assert extract_authors_from_analysis("") == []
        assert extract_authors_from_analysis(None) == []

    def test_memoization_actually_fires(self):
        import core.preprocessing.deterministic_analyzer as da

        da._check_coverage_cached.cache_clear()
        da._extract_authors_cached.cache_clear()
        # per-bullet shape: SAME analysis, 30 DIFFERENT summary texts
        for i in range(30):
            da.check_coverage(_ANALYSIS, f"bullet number {i} text")
        pair = da._check_coverage_cached.cache_info()
        authors = da._extract_authors_cached.cache_info()
        # the Citations regex ran ONCE for the whole loop
        assert authors.misses == 1, authors
        # identical (analysis, summary) pair is a cache HIT
        da.check_coverage(_ANALYSIS, "bullet number 7 text")
        assert da._check_coverage_cached.cache_info().hits == pair.hits + 1

    def test_public_names_still_replaceable(self, monkeypatch):
        """The recall-floor / gap-filler monkeypatch contract: local imports
        pick up whatever is installed on the module attribute."""
        import core.preprocessing.deterministic_analyzer as da
        from core.summarisation import recall_floor

        def _stub(analysis, summary_text):
            return {"total": 1, "covered": [], "missing": ["X"], "coverage_pct": 0.0}

        monkeypatch.setattr(da, "check_coverage", _stub)
        assert da.check_coverage("a", "b")["missing"] == ["X"]
        # recall_floor's function-local import sees the stub (not the cache)
        rf = recall_floor.deterministic_recall_floor(
            _ANALYSIS,
            ["Erikson bullet"],
            "",
            "src",
        )
        assert rf["theorists_total"] == 1, rf


# ═══════════════════════════════════════════════════════════════════════════
# O-a6 — find_analysis_for_heading scan cache
# ═══════════════════════════════════════════════════════════════════════════


class TestOa6ScanCache:
    def test_source_pins(self):
        src = _strip_comments(_src(_DA))
        assert "_ANALYSIS_SCAN_CACHE" in src
        assert "def _list_analysis_files(output_dir: Path) -> list:" in src
        assert "analysis_files = _list_analysis_files(output_dir)" in src

    @pytest.fixture()
    def analysis_tree(self, tmp_path):
        seg = tmp_path / "segments"
        seg.mkdir()
        (seg / "001_Chapter One.md").write_text("# Chapter One\nbody", encoding="utf-8")
        (seg / "001_Chapter One_analysis.md").write_text(_ANALYSIS, encoding="utf-8")
        import core.preprocessing.deterministic_analyzer as da

        da._ANALYSIS_SCAN_CACHE.clear()
        yield tmp_path
        da._ANALYSIS_SCAN_CACHE.clear()

    def test_second_call_uses_cached_scan(self, analysis_tree, monkeypatch):
        from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

        p1, t1 = find_analysis_for_heading(analysis_tree, "Chapter One")
        assert p1.endswith("001_Chapter One.md") and "Erikson" in t1

        calls = {"n": 0}
        real_rglob = Path.rglob

        def counting_rglob(self, pattern):
            calls["n"] += 1
            return real_rglob(self, pattern)

        monkeypatch.setattr(Path, "rglob", counting_rglob)
        p2, t2 = find_analysis_for_heading(analysis_tree, "Chapter One")
        p3, t3 = find_analysis_for_heading(analysis_tree, "any other heading")
        monkeypatch.undo()
        assert (p2, t2) == (p1, t1)
        assert (p3, t3) == (p1, t1)
        assert calls["n"] == 0, "repeat calls must not re-walk the tree (O-a6)"

    def test_mtime_invalidation_rescans(self, analysis_tree):
        from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

        p1, t1 = find_analysis_for_heading(analysis_tree, "Chapter One")
        assert "Erikson" in t1
        # a direct-entry change bumps the dir mtime -> rescan -> new result
        (analysis_tree / "000_zero_analysis.md").write_text(
            "## Citations\n\n1. **Freud** (1 mentions): 1900\n",
            encoding="utf-8",
        )
        p2, t2 = find_analysis_for_heading(analysis_tree, "Chapter One")
        assert "Freud" in t2 or "Erikson" in t2  # rescan saw the new file
        # removing everything (again a direct-entry change) -> not found
        for f in (analysis_tree / "segments").glob("*"):
            f.unlink()
        (analysis_tree / "000_zero_analysis.md").unlink()
        assert find_analysis_for_heading(analysis_tree, "x") == ("", "")

    def test_per_directory_isolation(self, analysis_tree, tmp_path_factory):
        from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

        other = tmp_path_factory.mktemp("other_out")
        (other / "zzz_analysis.md").write_text("other-analysis", encoding="utf-8")
        po, to = find_analysis_for_heading(other, "x")
        assert to == "other-analysis"
        p, t = find_analysis_for_heading(analysis_tree, "Chapter One")
        assert "Erikson" in t  # the first dir's cache is untouched

    def test_missing_dir_fail_soft_then_finds_late_population(self, tmp_path):
        from core.preprocessing.deterministic_analyzer import find_analysis_for_heading

        missing = tmp_path / "not_yet"
        assert find_analysis_for_heading(missing, "x") == ("", "")
        missing.mkdir()
        (missing / "a_analysis.md").write_text("content", encoding="utf-8")
        assert find_analysis_for_heading(missing, "x")[1] == "content"


# ═══════════════════════════════════════════════════════════════════════════
# O-a5 / W-a5 — single canonical structural-stopwords module
# ═══════════════════════════════════════════════════════════════════════════

_CANONICAL_NAMES = (
    "CONCEPT_STOPWORDS",
    "STRUCTURAL_FUNCTION_WORDS",
    "THEORIST_NAME_STOPWORDS",
)
_FORMER_SITES = {
    "text_preprocessor_impl.py": (_TPI, "_CONCEPT_STOPWORDS"),
    "summarizer.py": (_SUM, "_STRUCTURAL_FUNCTION_WORDS"),
    "scholar_reflection.py": (_SR, "_stopwords"),
}


def _assign_targets(path: Path) -> set:
    """Names assigned at module/class/function level in a file (any value)."""
    tree = ast.parse(_src(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def _literal_stopword_assigns(path: Path, varname: str) -> list:
    """Assignments of ``varname`` whose value is a literal word-list
    (frozenset/set/list of string constants). An alias such as
    ``_X = IMPORTED_NAME`` (ast.Name value) is NOT a literal."""
    hits = []
    tree = ast.parse(_src(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == varname for t in node.targets):
            continue
        value = node.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in ("frozenset", "set")
            and value.args
        ):
            value = value.args[0]
        if isinstance(value, (ast.List, ast.Set, ast.Tuple)) and all(
            isinstance(e, ast.Constant) and isinstance(e.value, str) for e in value.elts
        ):
            hits.append(node.lineno)
    return hits


class TestOa5CanonicalStopwordsModule:
    def test_exactly_one_module_defines_the_lists(self):
        definers = set()
        for py in (_project_root / "core").rglob("*.py"):
            try:
                targets = _assign_targets(py)
            except SyntaxError:  # pragma: no cover — tree compiles
                continue
            if any(n in targets for n in _CANONICAL_NAMES):
                definers.add(str(py.relative_to(_project_root)))
        assert definers == {"core/summarisation/structural_stopwords.py"}, definers

    def test_no_stopword_literals_left_at_former_sites(self):
        for site, (path, varname) in _FORMER_SITES.items():
            hits = _literal_stopword_assigns(path, varname)
            assert not hits, (
                f"{site} must not define the {varname} stopword LITERAL anymore "
                f"(found at lines {hits}); import the canonical module instead"
            )
            # stripped source: code only, not the fix-documentation comments
            code = _strip_comments(_src(path))
            assert '"goes"' not in code, (
                f"{site} must not contain a 'goes' stopword literal anymore"
            )

    def test_summarizer_keeps_the_compat_alias(self):
        """The class attribute stays as a bare alias of the canonical import
        (self._STRUCTURAL_FUNCTION_WORDS + setattr-on-class monkeypatching
        keep working)."""
        src = _strip_comments(_src(_SUM))
        assert "_STRUCTURAL_FUNCTION_WORDS = STRUCTURAL_FUNCTION_WORDS" in src

    def test_all_three_former_sites_import_the_canonical_module(self):
        for site, (path, _var) in _FORMER_SITES.items():
            src = _src(path)
            assert "from core.summarisation.structural_stopwords import" in src, (
                f"{site} must import the canonical stopword module"
            )

    def test_goes_duplication_gone_in_canonical_module(self):
        code = _strip_comments(_src(_SW))
        assert code.count('"goes"') == 1, "the literal 'goes' must appear exactly once"
        assert '"goes", "goes"' not in _src(_SW)

    def test_canonical_content_pinned(self):
        from core.summarisation.structural_stopwords import (
            CONCEPT_STOPWORDS,
            STRUCTURAL_FUNCTION_WORDS,
            THEORIST_NAME_STOPWORDS,
        )

        # membership byte-parity with the pre-P6 sets (drift documented in
        # the module docstring: union REJECTED, three sets kept as-is)
        assert len(THEORIST_NAME_STOPWORDS) == 66
        assert len(STRUCTURAL_FUNCTION_WORDS) == 93
        assert len(CONCEPT_STOPWORDS) == 111
        # case conventions preserved per site
        assert all(w[0].isupper() for w in THEORIST_NAME_STOPWORDS)
        assert all(w == w.lower() for w in STRUCTURAL_FUNCTION_WORDS)
        assert all(w == w.lower() for w in CONCEPT_STOPWORDS)
        assert "The" in THEORIST_NAME_STOPWORDS and "the" not in THEORIST_NAME_STOPWORDS
        assert "Later" in THEORIST_NAME_STOPWORDS and "Subsequently" in THEORIST_NAME_STOPWORDS
        assert "being" in STRUCTURAL_FUNCTION_WORDS and "least" in STRUCTURAL_FUNCTION_WORDS
        assert "goes" in CONCEPT_STOPWORDS and "opportunity" in CONCEPT_STOPWORDS

    def test_former_sites_alias_the_canonical_objects(self):
        import core.summarisation.text_preprocessor as tp
        import core.summarisation.text_preprocessor_impl as tpi
        from core.summarisation.simplified_keypoints import (
            SimplifiedKeypointsBuilder,  # noqa: F401 — import order guard
        )
        from core.summarisation.structural_stopwords import (
            CONCEPT_STOPWORDS,
            STRUCTURAL_FUNCTION_WORDS,
        )
        from core.summarisation.summarizer import Summarizer

        assert tpi._CONCEPT_STOPWORDS is CONCEPT_STOPWORDS
        # the W-a6 facade re-export still resolves the same object
        assert tp._CONCEPT_STOPWORDS is CONCEPT_STOPWORDS
        assert Summarizer._STRUCTURAL_FUNCTION_WORDS is STRUCTURAL_FUNCTION_WORDS

    def test_scholar_filter_behavior_unchanged(self):
        """V13.45.0 parity: 'Later Erikson' → 'Erikson'; capitalized common
        words are filtered; lowercase words can never match the name regex
        output (case-sensitive set)."""
        from core.summarisation.structural_stopwords import THEORIST_NAME_STOPWORDS as sw

        parts = ["Later", "Erikson"]
        assert len(parts) > 1 and parts[0] in sw  # 'Later' stripped
        assert "Erikson" not in sw
        assert "Say" not in sw and "Tell" not in sw and "Key" not in sw  # real surnames survive


# ═══════════════════════════════════════════════════════════════════════════
# W-a4 / O-a7 — simplified_keypoints on the house LLM dispatcher
# ═══════════════════════════════════════════════════════════════════════════


class TestWa4DispatcherMigration:
    def test_unguarded_choices_parse_gone(self):
        src = _strip_comments(_src(_SK))
        assert 'resp.json()["choices"]' not in src, (
            "W-a4: the unguarded deep-indexed response parse must be gone"
        )

    def test_dispatcher_import_present(self):
        src = _strip_comments(_src(_SK))
        assert "from core.summarisation.llm_dispatcher import call_openai_compat" in src, (
            "the OpenAI-compat call must go through llm_dispatcher"
        )

    def test_hand_rolled_retry_loops_gone(self):
        src = _strip_comments(_src(_SK))
        assert "for attempt in range(self.retries" not in src, (
            "both hand-rolled retry loops must be gone (house @retry_llm_call)"
        )
        assert "@retry_llm_call(max_attempts=self.retries + 1" in src
        assert "safe_ollama_request" in src  # ollama transport unchanged

    def test_ollama_url_resolved_from_settings(self):
        src = _strip_comments(_src(_SK))
        assert "settings.get_ollama_url()" in src, (
            "W-c9 class: the Ollama URL must resolve from Settings (fail-soft)"
        )

    def _builder(self, **overrides):
        from core.summarisation.simplified_keypoints import SimplifiedKeypointsBuilder

        b = object.__new__(SimplifiedKeypointsBuilder)  # skip ModelManager/Settings
        b.provider = "openrouter"
        b.temperature = 0.1
        b.max_output_tokens_per_batch = 4096
        b.retries = 1
        b.log = lambda msg, level="INFO": None
        b.api_base_url = "https://openrouter.ai/api/v1"
        b.api_key = "sk-x"
        b.cloud_model = "m1"
        b.freellmapi_url = "http://localhost:3001/v1"
        b.freellmapi_key = "fl-key"
        b.freellmapi_model = "auto"
        b.ollama_base_url = "http://localhost:11434"
        for k, v in overrides.items():
            setattr(b, k, v)
        return b

    def test_call_openai_compat_delegates_to_dispatcher(self, monkeypatch):
        import core.summarisation.llm_dispatcher as disp

        spy = []

        def _fake(
            prompt,
            base_url,
            api_key,
            model,
            label,
            temp,
            max_tokens,
            *,
            timeout,
            retries,
            provider,
            log=None,
        ):
            spy.append(
                dict(
                    prompt=prompt,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    label=label,
                    temp=temp,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    retries=retries,
                    provider=provider,
                )
            )
            return "SIMPLIFIED-TEXT"

        monkeypatch.setattr(disp, "call_openai_compat", _fake)
        b = self._builder()
        out = b._call_openai_compat(
            "PROMPT",
            base_url=b.api_base_url,
            api_key=b.api_key,
            model=b.cloud_model,
            label="Openrouter",
        )
        assert out == "SIMPLIFIED-TEXT"
        s = spy[0]
        assert s["prompt"] == "PROMPT"
        assert s["base_url"] == "https://openrouter.ai/api/v1"
        assert s["api_key"] == "sk-x"
        assert s["model"] == "m1"
        assert s["label"] == "Openrouter"
        # temp + max_tokens flow through; timeout=120 and retries preserved
        assert s["temp"] == 0.1 and s["max_tokens"] == 4096
        assert s["timeout"] == 120 and s["retries"] == 1
        assert s["provider"] == "openrouter"

    def test_call_llm_routes_providers_to_dispatcher(self, monkeypatch):
        import core.summarisation.llm_dispatcher as disp

        spy = []

        def _fake(
            prompt,
            base_url,
            api_key,
            model,
            label,
            temp,
            max_tokens,
            *,
            timeout,
            retries,
            provider,
            log=None,
        ):
            spy.append((label, base_url, model, provider))
            return "OK"

        monkeypatch.setattr(disp, "call_openai_compat", _fake)
        b = self._builder()
        assert b._call_llm("p1") == "OK"
        assert b._call_llm_single("p2") == "OK"
        assert spy[0] == ("Openrouter", "https://openrouter.ai/api/v1", "m1", "openrouter")
        assert spy[1] == ("Openrouter", "https://openrouter.ai/api/v1", "m1", "openrouter")
        b2 = self._builder(provider="freellmapi")
        assert b2._call_llm("p3") == "OK"
        assert spy[2] == ("FreeLLMAPI", "http://localhost:3001/v1", "auto", "freellmapi")

    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def json(self):
            return self._p

    class _MM:
        def model_exists(self, m):
            return True

    class _Req:
        summarisation_max_context_tokens = 8192

    def _ollama_builder(self):
        b = self._builder(provider="ollama")
        b.model_manager = self._MM()
        b.request = self._Req()
        b.model = "mymodel"
        b.timeout = 420
        return b

    def test_call_ollama_payload_semantics_preserved(self, monkeypatch):
        import core.summarisation.simplified_keypoints as sk

        captured = {}

        def _capture(method, url, json=None, timeout=None):
            captured.update(method=method, url=url, payload=json, timeout=timeout)
            return self._Resp({"response": "  ok  "})

        monkeypatch.setattr(sk, "safe_ollama_request", _capture)
        b = self._ollama_builder()
        assert b._call_ollama("hello", no_think=True, max_predict=512) == "ok"
        assert captured["method"] == "POST"
        assert captured["url"] == "http://localhost:11434/api/generate"
        # V18.20.4.12 (W-a11): gated on Qwen — was unconditional
        # ("/no_think\nhello"); "mymodel" is not Qwen-family, so the prompt
        # ships clean (the Qwen counterpart is pinned in
        # tests/test_v1820412_b_semantics.py).
        assert captured["payload"]["prompt"] == "hello"
        assert captured["payload"]["options"]["num_predict"] == 512
        assert captured["payload"]["options"]["num_ctx"] == 8192
        assert captured["payload"]["options"]["temperature"] == 0.1
        assert captured["timeout"] == 120  # per-bullet (max_predict <= 512)
        # batch call: full max_output_tokens and the batch timeout
        assert b._call_ollama("hello") == "ok"
        assert captured["payload"]["options"]["num_predict"] == 4096
        assert captured["timeout"] == 420

    def test_call_ollama_empty_response_retries_then_fails_soft(self, monkeypatch):
        import core.summarisation.simplified_keypoints as sk

        reqs = {"n": 0}

        def _empty(method, url, json=None, timeout=None):
            reqs["n"] += 1
            return self._Resp({"response": ""})

        monkeypatch.setattr(sk, "safe_ollama_request", _empty)
        b = self._ollama_builder()
        assert b._call_ollama("hello") is None  # fail-soft, never raises
        assert reqs["n"] == 2  # 1 initial + 1 retry (retries=1, house fallback)

    def test_call_ollama_timeout_is_non_retryable(self, monkeypatch):
        import requests as _rq

        import core.summarisation.simplified_keypoints as sk

        reqs = {"n": 0}

        def _timeout(method, url, json=None, timeout=None):
            reqs["n"] += 1
            raise _rq.exceptions.Timeout("model stall")

        monkeypatch.setattr(sk, "safe_ollama_request", _timeout)
        b = self._ollama_builder()
        assert b._call_ollama("hello") is None
        assert reqs["n"] == 1, "V18.2.19 house rule: timeout = model stall — no pointless retry"

    def test_call_ollama_model_missing_skips(self, monkeypatch):
        import core.summarisation.simplified_keypoints as sk

        class _NoMM:
            def model_exists(self, m):
                return False

        b = self._ollama_builder()
        b.model_manager = _NoMM()
        called = {"n": 0}

        def _boom(method, url, json=None, timeout=None):
            called["n"] += 1
            raise AssertionError("must not be reached")

        monkeypatch.setattr(sk, "safe_ollama_request", _boom)
        assert b._call_ollama("hello") is None
        assert called["n"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# O-a8 / W-a9 — max_tokens in the response-cache key
# ═══════════════════════════════════════════════════════════════════════════


class TestOa8CacheKey:
    def test_source_pins(self):
        rc = _strip_comments(_src(_RC))
        assert "max_tokens: int | None = None" in rc
        assert "f\"_{max_tokens if max_tokens is not None else 'default'}_\"" in rc
        summ = _strip_comments(_src(_SUM))
        assert 'response_cache.get(prompt, model or "", temp, max_tok)' in summ
        assert 'response_cache.put(prompt, model or "", temp, _result, max_tok)' in summ

    def test_key_sensitive_to_max_tokens(self):
        from core.llm.response_cache import ResponseCache

        c = ResponseCache(max_entries=8, persist_to_disk=False)
        c.put("same prompt", "model-x", 0.0, "short-response", max_tokens=2048)
        c.put("same prompt", "model-x", 0.0, "long-response", max_tokens=6144)
        # same text, different max_tokens -> different keys -> no collision
        assert c.get("same prompt", "model-x", 0.0, max_tokens=2048) == "short-response"
        assert c.get("same prompt", "model-x", 0.0, max_tokens=6144) == "long-response"
        assert c.get("same prompt", "model-x", 0.0, max_tokens=4096) is None
        assert c._key("p", "m", 0.1, 2048) != c._key("p", "m", 0.1, 4096)
        # temperature sensitivity retained (pre-existing)
        assert c._key("p", "m", 0.1, 2048) != c._key("p", "m", 0.2, 2048)
        # model sensitivity retained (pre-existing)
        assert c._key("p", "m1", 0.1, 2048) != c._key("p", "m2", 0.1, 2048)

    def test_none_max_tokens_is_a_distinct_key(self):
        from core.llm.response_cache import ResponseCache

        c = ResponseCache(max_entries=8, persist_to_disk=False)
        c.put("p", "m", 0.1, "explicit", max_tokens=2048)
        assert c.get("p", "m", 0.1) is None  # legacy 3-arg call ≠ explicit cap
        c.put("p", "m", 0.1, "legacy")
        assert c.get("p", "m", 0.1) == "legacy"
        assert c.get("p", "m", 0.1, max_tokens=2048) == "explicit"

    def test_stats_and_eviction_unchanged(self):
        from core.llm.response_cache import ResponseCache

        c = ResponseCache(max_entries=2, persist_to_disk=False)
        c.put("p1", "m", 0.0, "r1", max_tokens=1)
        c.put("p2", "m", 0.0, "r2", max_tokens=2)
        c.put("p3", "m", 0.0, "r3", max_tokens=3)  # evicts p1
        assert c.get("p1", "m", 0.0, max_tokens=1) is None
        assert c.get("p2", "m", 0.0, max_tokens=2) == "r2"
        st = c.stats()
        assert st["size"] == 2 and st["max"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# O-c3 — adaptive-TOC LLM result cache
#
# V0.08 (P2 dead-code removal): the TestOc3TocLlmCache class (8 tests) was
# deleted together with core/pdf/adaptive_toc.py — the module was
# production-dead (AdaptiveTOCExtractor had zero production callers; the
# live TOC pipeline uses toc_extractor.py + core.models TOCEntry/TOCResult).
# ═══════════════════════════════════════════════════════════════════════════
