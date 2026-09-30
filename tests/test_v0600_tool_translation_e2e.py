"""V0.6.0 (the dedicated-tools verification campaign) — Tool: the
Translation Service (EN <-> FA), end-to-end.

Inventory + trace (evidence-first):
- Card: ``translation`` — ``ui_qt/views/tool_dashboard.py:41`` TOOL_CARDS
  row 2 (PROCESS).
- Routing: ``ui_qt/views/convert_view.py:173`` ``_on_tool_clicked`` →
  ``TranslationServiceDialog`` (via the base_dialog facade).
- Dialog: ``ui_qt/views/service_dialogs/dialogs/translation_service_dialog.py``
  — the V18.20.4.6 P5/O-b2 split; backend choice is SINGLE (the Ollama
  ``TranslationEngine``): ``_process`` :822 builds it from the
  ``translation.endpoint`` setting (default ``http://localhost:11434/v1``,
  the engine strips a ``/v1`` suffix at translation_engine.py:147-150) +
  the model resolved on the MAIN thread in ``_collect_options`` :620 from
  the editable model combo (NOT a settings key — V11.29.3; default
  ``translategemma-12b-it.Q4_K_M_mradermacher:latest``). Headless
  injection: ``Settings._test_override`` (utils/settings.py:85) for
  ``translation.endpoint`` + ``dlg.model_combo.setCurrentText(...)``.
- Service layer (the wizard/pipeline path, NOT the dialog): ``core/translation/service.py``
  ``TranslationService.from_settings`` :199 — ollama-only since the NLLB
  retirement; the Translator/validator/harakat trio speaks the
  OpenAI-compatible ``/v1/chat/completions`` shape with an optional Bearer
  ``translation.cloud_api_key`` (canonical, legacy ``translation.api_key``
  migrated once) — that is the cloud-capable side. Settings keys:
  translation.{endpoint, model, temperature, no_think, max_chunk_tokens,
  judge_model (+summarisation.model fallback), validation_enabled,
  back_translation_threshold, judge_threshold, harakat_enabled,
  harakat_model, glossary_enabled, max_retries, default_target_lang,
  outputs} (service.py:220-314, :858-861).
- Engine: ``core/translation/translation_engine.py`` — line-by-line EN<->FA
  via Ollama ``/api/generate`` (:379-427), TranslateGemma vs
  non-TranslateGemma prompt strategies (:313-375), refusal/repetition
  detection + markdown preservation in ``_postprocess`` (:431), dynamic
  consistency memory (:500), language auto-detection (:638-664).
- Existing coverage: source-pin only (test_v182045_p4a /
  test_v182046_p5 AST wiring pins; v13 echo-pattern smoke) — ZERO
  functional end-to-end. This file is the first net.

Layers (house UI-test pattern, cf. test_v0600_tool_cutter_e2e):
1. Pure characterization (no Qt, no network) of the engine postprocess /
   refusal / repetition / line-count / Persian-regex / prompt strategies /
   dynamic glossary, chunker, cache, glossary, harakat, translator,
   validator, service wiring.
2. Service-level LIVE translation through the zai-llamacpp shim :3031
   (Ollama-shape ``/api/generate``) — shim-gated, ~7 short LLM calls total.
3. Dialog-level drive: the real SimpleWorker QThread + queued signals,
   modal monkeypatched to a recorder (``msg.exec()`` must never block a
   headless test), plus one LIVE full drive through the shim.

V0.6.0 defects pinned here (all in core/translation + the dialog, all
fixed in the same session — see the worklog Task 5-b entry):
- T1: ModelNotFoundError swallowed by the retry loop → silent original-text
  "translation" (translation_engine.py).
- T2: dialog ``_process`` error strings bypassed the shared "Error:"
  contract → failures written to the output file + reported ✅.
- T3: no line-count verification despite the module contract (1 input
  line = 1 output line).
- T4: heading marker level drift not normalized (live-observed H1→H2).
- T5: front-matter pass-through keyed on ``line_idx < 20`` → prose
  "Note: ..." lines skipped translation.
- T6: corrupted cache JSON crashed the chunk translator (cache.py).
- T7: all-failed queue batch still announced "✅ Translation Complete".
- T8: dead stopword filter (Title-case tuple vs lowercased word).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Layer 0: availability gates ─────────────────────────────────────────────

SHIM_URL = "http://localhost:3031"
SHIM_MODEL = "glm-4-plus"


def _qt_available() -> bool:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication  # noqa: F401

        return True
    except Exception:
        return False


def _shim_available() -> bool:
    try:
        import requests

        r = requests.get(f"{SHIM_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


_SHIM_OK = _shim_available()
_shim_gate = pytest.mark.skipif(not _SHIM_OK, reason="zai-llamacpp shim :3031 unavailable")


# Think-tag markers built by concatenation so no literal tag sequence ever
# appears in this file's source.
_T_OPEN = "<" + "think" + ">"
_T_CLOSE = "</" + "think" + ">"

_FA_HI = "سلام دنیا"  # generic Persian greeting — no book content (Rule 1)
_FA_Q = "این یک متن آزمایشی است"


# ── Shared fakes ────────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}")


class _FakeSession:
    """Requests-session stand-in recording every post.

    ``openai=True`` shapes the payload as an OpenAI chat-completions
    response (what ``extract_openai_content`` reads); the default is the
    Ollama ``/api/generate`` shape.
    """

    def __init__(self, content=None, status_code=200, payload=None, raise_exc=None, openai=False):
        self.calls: list[dict] = []
        self._content = content
        self._status = status_code
        self._payload = payload
        self._raise = raise_exc
        self._openai = openai

    def post(self, url, json=None, timeout=None, headers=None, **kw):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        if self._raise is not None:
            raise self._raise
        if self._payload is None:
            if self._openai:
                self._payload = {"choices": [{"message": {"content": self._content or ""}}]}
            else:
                self._payload = {"response": self._content or ""}
        return _FakeResp(self._status, self._payload)


class _DictSettings:
    """Offline Settings (real Settings._test_override DI hook — the OCR
    suite's precedent)."""

    def __init__(self, values: dict | None = None):
        self.data = dict(values or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update_setting(self, key, value):
        self.data[key] = value


class _StubController:
    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


@pytest.fixture()
def mock_settings():
    from utils.settings import Settings

    prev = Settings._test_override
    m = _DictSettings()
    Settings._test_override = m
    yield m
    Settings._test_override = prev


def _make_engine(**kw):
    from core.translation.translation_engine import TranslationEngine

    defaults = dict(
        ollama_url="http://localhost:1",
        model="some-model",
        source_lang="en",
        target_lang="fa",
        mode="literal",
    )
    defaults.update(kw)
    return TranslationEngine(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — engine characterization (pure, hermetic)
# ═══════════════════════════════════════════════════════════════════════════


class TestEngineConstruction:
    def test_url_normalization_strips_trailing_slash_and_v1(self):
        assert _make_engine(ollama_url="http://localhost:3031").ollama_url == SHIM_URL
        assert _make_engine(ollama_url="http://localhost:3031/").ollama_url == SHIM_URL
        assert _make_engine(ollama_url="http://localhost:3031/v1").ollama_url == SHIM_URL
        assert _make_engine(ollama_url="http://localhost:3031/v1/").ollama_url == SHIM_URL
        assert _make_engine(ollama_url="http://host:7").ollama_url == "http://host:7"

    def test_retry_and_timeout_constants(self):
        from core.translation.translation_engine import TranslationEngine

        assert TranslationEngine.MAX_RETRIES == 3
        assert TranslationEngine.TIMEOUT == (10, 120)

    def test_no_hardcoded_glossary_rule1_pin(self):
        """Rule 1: the engine ships NO prefilled glossary — consistency is
        purely dynamic (translation_engine.py:64-67)."""
        e = _make_engine()
        assert e._term_memory == {}
        import core.translation.translation_engine as te_mod

        glossary_globals = [n for n in vars(te_mod) if "glossary" in n.lower()]
        assert glossary_globals == []


class TestPostprocess:
    """_postprocess: think-strip → echo-strip → line collapse (T3) →
    refusal → repetition → markdown preservation."""

    def _pp(self, text, original="hello there"):
        return _make_engine()._postprocess(text, original)

    def test_think_block_stripped(self):
        assert self._pp(f"{_T_OPEN}internal reasoning{_T_CLOSE}{_FA_HI}") == _FA_HI

    def test_only_think_block_becomes_empty(self):
        assert self._pp(f"{_T_OPEN}reasoning only{_T_CLOSE}") == ""

    def test_echo_farsi_label_stripped(self):
        assert self._pp("Farsi: سلام") == "سلام"

    def test_echo_persian_instruction_stripped(self):
        out = self._pp("ترجمه به فارسی: سلام")
        assert out == "سلام"

    def test_echo_english_instruction_stripped(self):
        assert self._pp("Translate to Farsi: hello") == "hello"

    def test_real_text_untouched(self):
        assert self._pp("This is a real translation.") == "This is a real translation."

    def test_t3_embedded_newlines_collapsed_to_one_line(self):
        """V0.6.0 (T3): the engine translates line by line, so one input
        line must yield ONE output line (the module contract at
        translation_engine.py:12). Pre-fix a 2-line model reply produced a
        2-line output for a 1-line input."""
        assert self._pp("سلام\nدنیا") == _FA_HI
        assert "\n" not in self._pp("سلام\n\nدنیا\nسلام")

    def test_refusal_substring_shapes_return_empty(self):
        assert self._pp("Please provide the English text to translate.") == ""
        assert self._pp("متاسفم، من نمی‌توانم این کار را انجام دهم") == ""
        assert self._pp("I cannot process this request.") == ""

    def test_refusal_regex_shape_without_diacritic_returns_empty(self):
        # "لطفا متن ... ترجمه" (no fathatan) misses the substring list but
        # the regex ^\[\u0644\u0637\u0641\u0627[\u064b\u0651]? \u0645\u062a\u0646… matches.
        assert self._pp("لطفا متن انگلیسی را ترجمه کنید") == ""

    def test_repetition_loop_returns_empty(self):
        phrase = "this exact phrase keeps repeating over and over"
        assert self._pp(f"{phrase} {phrase} {phrase} {phrase} {phrase}") == ""

    def test_normal_text_is_not_flagged_as_repetition(self):
        assert self._pp("A short normal sentence with unique words.") != ""


def _pm(original: str, translated: str) -> str:
    from core.translation.translation_engine import TranslationEngine

    return TranslationEngine._preserve_markdown(original, translated)


class TestPreserveMarkdown:
    """_preserve_markdown pins (static helper)."""

    def test_bullet_marker_re_added(self):
        assert _pm("- an item", "موردی") == "- موردی"

    def test_bullet_marker_preserved_with_indent(self):
        assert _pm("  - nested item", "مورد تودرتو") == "  - مورد تودرتو"

    def test_star_bullet_kept_when_already_bullet(self):
        assert _pm("* an item", "* موردی") == "* موردی"

    def test_heading_marker_re_added(self):
        assert _pm("## A Title", "یک عنوان") == "## یک عنوان"

    def test_t4_heading_level_normalized(self):
        """V0.6.0 (T4): live-observed '# Small Heading' → '## سرتیتر کوچک'
        — the model kept a marker but drifted the level, corrupting the
        heading hierarchy. The original level is now always restored."""
        assert _pm("# A Title", "## یک عنوان") == "# یک عنوان"
        assert _pm("#### Deep", "## عمیق") == "#### عمیق"
        assert _pm("# Title", "### عنوان") == "# عنوان"

    def test_t4_heading_model_marker_whitespace_shapes(self):
        assert _pm("# Title", "#عنوان") == "# عنوان"
        assert _pm("# Title", "##  عنوان") == "# عنوان"

    def test_blockquote_re_added(self):
        assert _pm("> a quote", "نقل قول") == "> نقل قول"

    def test_numbered_list_re_added(self):
        assert _pm("1. an item", "موردی") == "1. موردی"

    def test_numbered_list_persian_digits_untouched(self):
        # ۱. (U+06F1) is a Unicode decimal digit — \d matches, so no
        # double numbering is re-added.
        assert _pm("1. an item", "۱. موردی") == "۱. موردی"

    def test_plain_text_unchanged(self):
        assert _pm("just text", "فقط متن") == "فقط متن"


class TestHasRepetition:
    def test_short_text_never_repeats(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE._has_repetition("short text here") is False

    def test_word_loop_detected(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE._has_repetition("word " * 30) is True

    def test_distinct_words_not_flagged(self):
        from core.translation.translation_engine import TranslationEngine as TE

        text = " ".join(f"unique{i}" for i in range(40))
        assert TE._has_repetition(text) is False


class TestPromptStrategies:
    def test_translategemma_language_pair_first(self):
        e = _make_engine(model="translategemma-12b-it:latest")
        p = e._build_prompts("hello there")
        assert p[0] == "English: hello there\nFarsi:"
        assert p[1] == "Translate to Farsi:\nhello there"
        assert p[2] == "hello there"

    def test_translategemma_fa_to_en_pair(self):
        e = _make_engine(model="TranslateGemma-4b", source_lang="fa", target_lang="en")
        assert e._build_prompts("سلام")[0] == "Farsi: سلام\nEnglish:"

    def test_non_tg_literal_instruction_first(self):
        e = _make_engine(model="qwen3:8b", mode="literal")
        p = e._build_prompts("hello there")
        assert "Keep the original tone" in p[0]
        assert p[0].endswith("hello there")
        # Fallbacks: language-pair, then bare text.
        assert p[1] == "English: hello there\nFarsi:"
        assert p[2] == "hello there"

    def test_non_tg_simplified_instruction(self):
        e = _make_engine(model="qwen3:8b", mode="simplified")
        assert "simple, everyday Farsi" in e._build_prompts("hello")[0]

    def test_non_tg_fa_to_en_instruction(self):
        e = _make_engine(model="glm-4-plus", source_lang="fa", target_lang="en")
        assert "from Farsi/Persian to English" in e._build_prompts("سلام")[0]
        assert e._build_prompts("سلام")[1] == "Farsi: سلام\nEnglish:"

    def test_is_translategemma_variants(self):
        assert _make_engine(model="translategemma:4b")._is_translategemma() is True
        assert _make_engine(model="Translate-Gemma-12B")._is_translategemma() is True
        assert _make_engine(model="translate_gemma")._is_translategemma() is True
        assert _make_engine(model="qwen3:8b")._is_translategemma() is False
        assert _make_engine(model="glm-4-plus")._is_translategemma() is False


class TestLanguageDetection:
    def test_persian_regex_shape(self):
        from core.translation.translation_engine import _PERSIAN_RE

        assert _PERSIAN_RE.search(_FA_HI)
        assert not _PERSIAN_RE.search("plain english text 123")

    def test_detect_language(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE.detect_language("Hello world, how are you?") == "en"
        assert TE.detect_language("سلام این یک جمله فارسی است") == "fa"
        assert TE.detect_language("") == "en"
        assert TE.detect_language("1234 !!! ???") == "en"

    def test_detect_language_ratio_threshold(self):
        from core.translation.translation_engine import TranslationEngine as TE

        # A mostly-Latin line with one Persian word stays "en" (>15% rule).
        mixed = "Mostly latin words here and here plus one word سلام ok"
        assert TE.detect_language(mixed) == "en"

    def test_auto_detect_direction_both_ways(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE.auto_detect_direction("Hello there friend") == ("en", "fa")
        assert TE.auto_detect_direction("سلام دوست من") == ("fa", "en")


class TestFrontmatterEnd:
    def test_empty_and_no_block(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE._frontmatter_end([]) == 0
        assert TE._frontmatter_end(["text", "more"]) == 0

    def test_leading_block_bounds(self):
        from core.translation.translation_engine import TranslationEngine as TE

        lines = ["---", "title: X", "---", "", "body"]
        assert TE._frontmatter_end(lines) == 3

    def test_unterminated_block_is_not_frontmatter(self):
        from core.translation.translation_engine import TranslationEngine as TE

        assert TE._frontmatter_end(["---", "title: X", "body"]) == 0


class TestTranslateTextHermetic:
    def _fake_engine(self, reply):
        e = _make_engine()
        e._call_ollama = lambda prompt: reply
        return e

    def test_empty_and_rule_lines_pass_through(self):
        e = self._fake_engine("سلام")
        out = e.translate_text("first\n\n---\n***\n___\nsecond")
        lines = out.split("\n")
        assert lines[1] == "" and lines[2] == "---" and lines[3] == "***"
        assert lines[4] == "___"
        assert lines[5] == "سلام"

    def test_line_count_preserved(self):
        e = self._fake_engine("سلام\nدو خطی")  # multi-line model reply
        out = e.translate_text("one\ntwo\nthree")
        assert len(out.split("\n")) == 3  # T3: 1 input line = 1 output line

    def test_yaml_keys_inside_leading_block_pass_through(self):
        e = self._fake_engine("سلام")
        text = "---\ntitle: Sample\nauthor: someone\n---\n\nBody line."
        out = e.translate_text(text)
        lines = out.split("\n")
        assert lines[1] == "title: Sample"
        assert lines[2] == "author: someone"
        assert lines[3] == "---"
        assert lines[5] == "سلام"

    def test_t5_prose_keyvalue_line_outside_block_is_translated(self):
        """V0.6.0 (T5): the old ``line_idx < 20`` heuristic silently
        skipped ANY "Word: ..." prose line near the top of a document."""
        e = self._fake_engine("سلام")
        out = e.translate_text("Note: verify the results")
        assert out == "سلام"

    def test_t5_keyvalue_line_inside_unterminated_block_translated(self):
        e = self._fake_engine("سلام")
        out = e.translate_text("---\nkey: value\nbody text")
        assert out.split("\n")[1] == "سلام"

    def test_progress_callback_sequence(self):
        e = self._fake_engine("سلام")
        seen = []
        e._progress = lambda pct, msg: seen.append((pct, msg))
        e.translate_text("one\ntwo")
        assert seen[0][0] == 50 and "1/2" in seen[0][1]
        assert seen[1][0] == 100 and "2/2" in seen[1][1]
        assert seen[-1][0] == 100 and "complete" in seen[-1][1]

    def test_retry_falls_back_to_next_prompt_on_refusal(self):
        e = _make_engine()
        prompts_seen: list[str] = []

        def fake_call(prompt):
            prompts_seen.append(prompt)
            if len(prompts_seen) == 1:
                return "Please provide the English text to translate."  # refusal
            return "سلام"

        e._call_ollama = fake_call
        assert e._translate_line("hello line", 0) == "سلام"
        assert len(prompts_seen) == 2 and prompts_seen[0] != prompts_seen[1]

    def test_all_retries_fail_returns_original_line(self):
        e = _make_engine()
        e._call_ollama = lambda prompt: ""  # always empty → always retry
        assert e._translate_line("keep me", 0) == "keep me"

    def test_t1_model_not_found_bails_whole_document(self, monkeypatch):
        """V0.6.0 (T1): a 404 must raise ModelNotFoundError after ONE HTTP
        call (was: 3 retries per line + the original text silently returned
        as the translation)."""
        import core.translation.translation_engine as te

        sess = _FakeSession(status_code=404, payload={"error": "model not found"})
        monkeypatch.setattr(te, "session_for_url", lambda url: sess)
        e = _make_engine(ollama_url="http://localhost:1", model="nope")
        with pytest.raises(te.ModelNotFoundError) as exc:
            e.translate_text("hello")
        assert "nope" in str(exc.value)
        assert "not found" in str(exc.value)
        assert len(sess.calls) == 1  # bails immediately — no 3x retry storm

    def test_call_ollama_non404_error_returns_none(self, monkeypatch):
        import core.translation.translation_engine as te

        sess = _FakeSession(status_code=500, payload={"error": "boom"})
        monkeypatch.setattr(te, "session_for_url", lambda url: sess)
        e = _make_engine()
        assert e._call_ollama("prompt") is None

    def test_call_ollama_ok_returns_response_text(self, monkeypatch):
        import core.translation.translation_engine as te

        sess = _FakeSession(content="سلام", payload={"response": " سلام "})
        monkeypatch.setattr(te, "session_for_url", lambda url: sess)
        e = _make_engine()
        assert e._call_ollama("prompt") == "سلام"
        sent = sess.calls[0]["json"]
        assert sent["model"] == "some-model" and sent["stream"] is False
        assert sent["options"]["temperature"] == 0.3

    def test_translate_files_hermetic_writes_output(self, tmp_path):
        e = self._fake_engine("سلام")
        src = tmp_path / "doc.md"
        src.write_text("line one\nline two", encoding="utf-8")
        results = e.translate_files([str(src)], tmp_path / "outdir")
        out = tmp_path / "outdir" / "doc_translated.md"
        assert out.exists()
        # V0.6.5 contract: RTL-dominant output (.md) gains the Obsidian
        # ``dir: rtl`` front-matter property (write_output auto-detect).
        content = out.read_text(encoding="utf-8")
        assert content.startswith("---\ndir: rtl\n---")
        assert content.endswith("سلام\nسلام")
        assert results == ["✅ doc.md → doc_translated.md"]

    def test_translate_files_empty_file_skipped(self, tmp_path):
        e = self._fake_engine("سلام")
        src = tmp_path / "empty.md"
        src.write_text("   ", encoding="utf-8")
        results = e.translate_files([str(src)], tmp_path / "outdir")
        assert results == ["⚠️ empty.md → empty file, skipped"]
        assert not (tmp_path / "outdir" / "empty_translated.md").exists()


class TestKeyTermsAndConsistency:
    def test_t8_stopword_filter_now_filters(self):
        """V0.6.0 (T8): the stopword tuple was Title-case while the
        comparison lowercased the word — "The"/"This"/... leaked into the
        term memory as fake key terms."""
        from core.translation.translation_engine import TranslationEngine as TE

        terms = TE._extract_key_terms("In the garden The flowers bloom")
        assert "the" not in terms

    def test_multi_word_capitalized_phrases(self):
        from core.translation.translation_engine import TranslationEngine as TE

        terms = TE._extract_key_terms("Monk Mode was practiced by Benedict")
        assert "monk mode" in terms
        assert "benedict" in terms

    def test_quoted_and_parenthesized_terms(self):
        from core.translation.translation_engine import TranslationEngine as TE

        terms = TE._extract_key_terms('the term "quiet discipline" is quoted (vassa) here')
        assert "quiet discipline" in terms
        assert "vassa" in terms

    def test_dedup_and_min_length(self):
        from core.translation.translation_engine import TranslationEngine as TE

        terms = TE._extract_key_terms("Alpha Beta and Alpha Beta again")
        assert terms.count("alpha beta") == 1
        assert all(len(t) >= 3 for t in terms)

    def test_consistency_memory_learns_first_translation(self):
        e = _make_engine()
        out = e._enforce_consistency("Monk Mode helps", "حالت راهب کمک می‌کند")
        assert out == "حالت راهب کمک می‌کند"
        assert "monk mode" in e._term_memory
        # Second occurrence: translation returned unchanged (dynamic
        # consistency contract — no hardcoded replacement).
        out2 = e._enforce_consistency("Monk Mode again", "حالت راهب دوباره")
        assert out2 == "حالت راهب دوباره"


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — chunker / cache / glossary / harakat / translator / validator
# ═══════════════════════════════════════════════════════════════════════════


class TestChunker:
    def _chunker(self, max_tokens=2000):
        from core.translation.chunker import TranslationChunker

        return TranslationChunker(max_tokens=max_tokens)

    def test_empty_text_no_chunks(self):
        assert self._chunker().chunk("") == []
        assert self._chunker().chunk("   \n  ") == []

    def test_frontmatter_code_and_text_flags(self):
        text = "---\ntitle: T\n---\n\npara one\n\n```python\nx = 1\n```\n\npara two"
        chunks = self._chunker().chunk(text)
        kinds = [(c.is_frontmatter, c.is_code) for c in chunks]
        assert (True, False) in kinds and (False, True) in kinds and (False, False) in kinds
        fm = [c for c in chunks if c.is_frontmatter][0]
        assert fm.text.startswith("---") and "title: T" in fm.text
        code = [c for c in chunks if c.is_code][0]
        assert code.text.startswith("```python") and code.text.endswith("```")

    def test_small_doc_merges_into_one_text_chunk(self):
        text = "# Head One\nbody a\n\n# Head Two\nbody b"
        chunks = self._chunker().chunk(text)
        texts = [c for c in chunks if not (c.is_frontmatter or c.is_code)]
        assert len(texts) == 1
        assert "# Head One" in texts[0].text and "# Head Two" in texts[0].text

    def test_tiny_max_tokens_splits_sections(self):
        text = "# Head One\n\nbody a\n\n# Head Two\n\nbody b"
        chunks = self._chunker(max_tokens=4).chunk(text)
        texts = [c.text for c in chunks]
        assert "# Head One" in texts and "# Head Two" in texts
        assert len(texts) >= 2

    def test_context_window_carries_previous_tail(self):
        text = "para one words\n\n```py\ncode\n```\n\npara two words"
        chunks = self._chunker().chunk(text)
        code = [c for c in chunks if c.is_code][0]
        assert code.context.endswith("para one words")
        idx_code = chunks.index(code)
        after = chunks[idx_code + 1]
        assert after.context  # non-empty context from the code chunk

    def test_single_long_paragraph_sentence_split(self):
        text = "First sentence ends here. Second sentence follows. Third one too."
        parts = self._chunker(max_tokens=2)._split_by_sentences(text)
        assert len(parts) >= 2

    def test_persian_question_mark_sentence_split(self):
        text = "اول؟ دوم! سوم."
        parts = self._chunker(max_tokens=1)._split_by_sentences(text)
        assert len(parts) == 3


class TestTranslationCache:
    def test_cache_key_covers_all_dimensions(self):
        import core.translation.cache as tcache

        keys = {
            tcache._cache_key("a", "en", "fa", "m"),
            tcache._cache_key("b", "en", "fa", "m"),
            tcache._cache_key("a", "fa", "en", "m"),
            tcache._cache_key("a", "en", "en", "m"),
            tcache._cache_key("a", "en", "fa", "other"),
            tcache._cache_key("a", "en", "fa", "m", "gloss"),
        }
        assert len(keys) == 6

    def test_save_get_roundtrip(self, tmp_path, monkeypatch):
        import core.translation.cache as tcache

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path)
        tcache.save_cached_translation(
            "hello", "en", "fa", "m", "سلام", similarity_score=0.9, judge_score=0.8
        )
        got = tcache.get_cached_translation("hello", "en", "fa", "m")
        assert got is not None
        assert got["translated_text"] == "سلام"
        assert got["similarity_score"] == 0.9 and got["passed"] is True
        assert got["source_lang"] == "en" and got["target_lang"] == "fa"

    def test_missing_key_returns_none(self, tmp_path, monkeypatch):
        import core.translation.cache as tcache

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path)
        assert tcache.get_cached_translation("absent", "en", "fa", "m") is None

    def test_preview_mismatch_returns_none(self, tmp_path, monkeypatch):
        import core.translation.cache as tcache

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path)
        key = tcache._cache_key("X", "en", "fa", "m")
        (tmp_path / f"{key}.json").write_text(
            json.dumps({"text_preview": "different", "translated_text": "t"}),
            encoding="utf-8",
        )
        assert tcache.get_cached_translation("X", "en", "fa", "m") is None

    def test_t6_corrupted_cache_json_degrades_to_miss(self, tmp_path, monkeypatch):
        """V0.6.0 (T6): a truncated cache file raised JSONDecodeError
        (ValueError) through the OSError-only handler and crashed the chunk
        translation — now a cache miss."""
        import core.translation.cache as tcache

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path)
        key = tcache._cache_key("X", "en", "fa", "m")
        (tmp_path / f"{key}.json").write_text("{not valid json", encoding="utf-8")
        assert tcache.get_cached_translation("X", "en", "fa", "m") is None

    def test_fifo_eviction_removes_oldest(self, tmp_path, monkeypatch):
        import core.translation.cache as tcache

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path)
        for i, year in enumerate((2020, 2021, 2022)):
            key = tcache._cache_key(f"text{i}", "en", "fa", "m")
            (tmp_path / f"{key}.json").write_text(
                json.dumps({"created_at": f"{year}-01-01T00:00:00"}),
                encoding="utf-8",
            )
        evicted = tcache._evict_if_needed(max_entries=2)
        assert evicted == 1
        remaining = sorted(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.json"))
        assert "2020" not in "".join(remaining)
        assert "2021" in "".join(remaining) and "2022" in "".join(remaining)


class TestGlossary:
    def test_add_and_frequency_increment(self):
        from core.translation.glossary import Glossary

        g = Glossary()
        g.add("Term One")
        g.add("term one")
        assert g.entries["term one"].frequency == 2

    def test_prompt_format_with_and_without_translation(self):
        from core.translation.glossary import Glossary, GlossaryEntry

        g = Glossary()
        g.entries["alpha beta"] = GlossaryEntry(source="Alpha Beta")
        g.entries["gamma"] = GlossaryEntry(source="Gamma", translation="گاما")
        out = g.get_terms_for_prompt()
        assert out.startswith("Glossary (keep these translations consistent):")
        assert "- Alpha Beta -> (translate consistently)" in out
        assert "- Gamma -> گاما" in out

    def test_empty_glossary_prompt_is_blank(self):
        from core.translation.glossary import Glossary

        assert Glossary().get_terms_for_prompt() == ""

    def test_save_load_roundtrip(self, tmp_path):
        from core.translation.glossary import Glossary, GlossaryEntry, GlossaryManager

        gm = GlossaryManager(source_lang="en", target_lang="fa")
        gm.glossary.entries["alpha beta"] = GlossaryEntry(
            source="Alpha Beta", entity_type="TERM", frequency=3
        )
        p = tmp_path / "g.json"
        gm.glossary.save(p)
        loaded = Glossary.load(p)
        assert loaded is not None
        assert loaded.entries["alpha beta"].frequency == 3
        assert loaded.source_lang == "en" and loaded.target_lang == "fa"

    def test_regex_fallback_extraction(self, monkeypatch):
        import core.translation.glossary as gmod

        monkeypatch.setattr(gmod, "_get_nlp", lambda: None)
        gm = gmod.GlossaryManager(source_lang="en", target_lang="fa")
        gm.extract_from_text("Monk Mode and Quiet Practice were discussed.")
        assert "monk mode" in gm.glossary.entries
        assert "quiet practice" in gm.glossary.entries

    def test_quoted_title_extracted(self, monkeypatch):
        import core.translation.glossary as gmod

        monkeypatch.setattr(gmod, "_get_nlp", lambda: None)
        gm = gmod.GlossaryManager(source_lang="en", target_lang="fa")
        gm.extract_from_text('He wrote "Atomic Ideas" last year.')
        assert "atomic ideas" in gm.glossary.entries
        # The multi-word capitalized-phrase regex runs first, so the entry
        # lands as TERM (frequency increments on the quoted-title re-add).
        assert gm.glossary.entries["atomic ideas"].frequency == 2

    def test_farsi_source_skips_ner(self):
        from core.translation.glossary import GlossaryManager

        gm = GlossaryManager(source_lang="fa", target_lang="en")
        gm.extract_from_text("یک متن فارسی با کلمات")
        assert gm.glossary.entries == {}

    def test_update_translations_fills_only_empty(self):
        from core.translation.glossary import GlossaryEntry, GlossaryManager

        gm = GlossaryManager()
        gm.glossary.entries["alpha"] = GlossaryEntry(source="Alpha", translation="اول")
        gm.update_translations("Alpha", "دوم")
        assert gm.glossary.entries["alpha"].translation == "اول"
        gm.glossary.entries["beta"] = GlossaryEntry(source="Beta")
        gm.update_translations("Beta", "بتا")
        assert gm.glossary.entries["beta"].translation == "بتا"


class TestHarakat:
    def _gen(self, **kw):
        from core.translation.harakat import HarakatGenerator

        defaults = dict(endpoint="http://localhost:1", model="some-model")
        defaults.update(kw)
        return HarakatGenerator(**defaults)

    def test_has_farsi(self):
        from core.translation.harakat import _has_farsi

        assert _has_farsi("سلام") is True
        assert _has_farsi("hello") is False
        assert _has_farsi("") is False

    def test_strip_think_blocks(self):
        from core.translation.harakat import _strip_think_blocks

        assert _strip_think_blocks(f"{_T_OPEN}reasoning{_T_CLOSE}سلام") == "سلام"
        assert _strip_think_blocks("سلام") == "سلام"

    def test_non_farsi_text_returned_without_llm_call(self):
        hg = self._gen()
        hg._call_llm = lambda text, model_override="": pytest.fail("must not call")
        assert hg.add_harakat("english only") == "english only"

    def test_valid_harakat_returned_and_cached(self):
        hg = self._gen()
        calls: list[str] = []
        hg._call_llm = lambda text, model_override="": (calls.append(text), "سَلام")[1]
        assert hg.add_harakat("سلام") == "سَلام"
        assert hg.add_harakat("سلام") == "سَلام"  # cache hit
        assert len(calls) == 1

    def test_validate_harakat_shapes(self):
        hg = self._gen()
        assert hg._validate_harakat("سلام دنیا", "سَلام دُنیا") is True
        assert hg._validate_harakat("سلام", "") is False
        assert hg._validate_harakat("short", "a " + "much " * 20 + "longer text") is False
        # Diacritic garbage (>40% of Persian chars are diacritics).
        assert hg._validate_harakat("سلام سلام سلام", "سََََََ سََََََ سََََََ") is False
        # Word set must survive (>= 70%).
        assert hg._validate_harakat("یک دو سه چهار", "شش هفت هشت نه") is False

    def test_fallback_model_used_on_garbage(self):
        hg = self._gen(fallback_model="fb-model")
        seen: list[str] = []

        def fake_llm(text, model_override=""):
            seen.append(model_override)
            if not model_override:
                return "سَََََََََ"  # garbage from the primary
            return "سَلام"  # clean from the fallback

        hg._call_llm = fake_llm
        assert hg.add_harakat("سلام") == "سَلام"
        assert seen == ["", "fb-model"]

    def test_disabled_after_three_failures(self):
        hg = self._gen()
        calls: list[str] = []

        def raising(text, model_override=""):
            calls.append(text)
            raise RuntimeError("down")

        hg._call_llm = raising
        assert hg.add_harakat("سلام") == "سلام"
        assert hg.add_harakat("سلام") == "سلام"
        assert hg.add_harakat("سلام") == "سلام"
        assert hg.is_disabled() is True
        assert len(calls) == 3  # disabled: no 4th call

    def test_split_markdown_segments(self):
        hg = self._gen()
        text = "---\ntitle: T\n---\ntext before\n```py\nx=1\n```\ntext after"
        segs = hg._split_markdown(text)
        kinds = [k for _, k in segs]
        assert kinds.count("frontmatter") == 1
        assert kinds.count("code") == 1
        assert kinds.count("text") == 2

    def test_inline_code_and_urls_protected(self):
        hg = self._gen()
        hg.add_harakat = lambda t: t  # identity: the placeholder machinery only
        text = "متن با کد `x=1` و لینک http://example.com در آن"
        out = hg._add_harakat_preserving_inline(text)
        assert "`x=1`" in out and "http://example.com" in out
        assert "__PLACEHOLDER" not in out


class TestTranslator:
    def _tr(self, **kw):
        from core.translation.translator import Translator

        defaults = dict(endpoint="http://localhost:1/v1", model="some-model")
        defaults.update(kw)
        return Translator(**defaults)

    def test_strip_think_blocks(self):
        from core.translation.translator import _strip_think_blocks

        assert _strip_think_blocks(f"{_T_OPEN}reasoning{_T_CLOSE}سلام") == "سلام"

    def test_detect_language(self):
        from core.translation.translator import detect_language

        assert detect_language("hello world") == "en"
        assert detect_language("سلام این متن فارسی است") == "fa"

    def test_cache_key_dimensions(self):
        tr = self._tr(model="m1")
        k1 = tr._cache_key("a", "en", "fa", "")
        assert k1 != tr._cache_key("b", "en", "fa", "")
        assert k1 != tr._cache_key("a", "fa", "en", "")
        assert k1 != tr._cache_key("a", "en", "fa", "gloss")
        assert k1 != self._tr(model="m2")._cache_key("a", "en", "fa", "")

    def test_same_language_noop_makes_no_call(self):
        tr = self._tr()
        tr._call_llm = lambda *a: pytest.fail("must not call")
        assert tr.translate("hello", source_lang="en", target_lang="en") == "hello"
        assert tr.translate("", source_lang="en", target_lang="fa") == ""

    def test_translate_caches_and_reuses(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(content="سلام", openai=True)
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        tr = self._tr()
        assert tr.translate("hello", "en", "fa") == "سلام"
        assert tr.translate("hello", "en", "fa") == "سلام"
        assert len(sess.calls) == 1

    def test_call_llm_prompt_and_payload_shape(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(content="سلام", openai=True)
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        tr = self._tr()
        out = tr._call_llm("hello", "en", "fa", "GLOSS-CTX", "")
        assert out == "سلام"
        sent = sess.calls[0]
        assert sent["url"].endswith("/chat/completions")
        prompt = sent["json"]["messages"][0]["content"]
        assert "Output ONLY the translation" in prompt
        assert "hello" in prompt and "GLOSS-CTX" in prompt
        assert sent["json"]["model"] == "some-model"
        assert sent["json"]["stream"] is False

    def test_call_llm_strips_echo_and_think(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(content=f"{_T_OPEN}hmm{_T_CLOSE}Persian translation: سلام", openai=True)
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        assert self._tr()._call_llm("hello", "en", "fa", "", "") == "سلام"

    def test_api_key_sent_as_bearer(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(content="سلام", openai=True)
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        self._tr(api_key="sk-x")._call_llm("hello", "en", "fa", "", "")
        assert sess.calls[0]["headers"]["Authorization"] == "Bearer sk-x"

    def test_translate_back_swaps_direction(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(content="hello", openai=True)
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        tr = self._tr()
        assert tr.translate_back("سلام", "en", "fa") == "hello"
        prompt = sess.calls[0]["json"]["messages"][0]["content"]
        assert "Farsi/Persian to English" in prompt

    def test_disabled_after_five_failures(self, monkeypatch):
        import core.translation.translator as trmod

        sess = _FakeSession(raise_exc=RuntimeError("down"))
        monkeypatch.setattr(trmod, "session_for_url", lambda url: sess)
        tr = self._tr()
        for _ in range(6):
            assert tr.translate("hello", "en", "fa") == "hello"  # graceful
        assert tr.is_disabled() is True
        assert len(sess.calls) == 5  # no call after disabling


class TestValidator:
    def _val(self, **kw):
        from core.translation.validator import TranslationValidator

        defaults = dict(endpoint="http://localhost:1/v1", judge_model="")
        defaults.update(kw)
        return TranslationValidator(**defaults)

    def test_jaccard_similarity(self):
        from core.translation.validator import _jaccard_similarity

        assert _jaccard_similarity("a b c", "a b c") == 1.0
        assert _jaccard_similarity("a b", "c d") == 0.0
        assert _jaccard_similarity("", "x") == 0.0

    def test_no_translator_no_judge_passes(self):
        cv = self._val().validate_chunk("src", "trans", 0, "en", "fa")
        assert cv.passed is True
        assert cv.similarity_score == 1.0 and cv.judge_score == 1.0

    def test_similarity_threshold_flags(self, monkeypatch):
        import core.translation.validator as vmod

        monkeypatch.setattr(vmod, "_semantic_similarity", lambda a, b: 0.1)

        class _BackTranslator:
            def translate_back(self, text, a, b):
                return text

        cv = self._val(translator=_BackTranslator()).validate_chunk("src", "trans", 0, "en", "fa")
        assert cv.passed is False
        assert "similarity 0.10 < 0.6" in cv.flagged_reason

    def test_judge_threshold_flags(self, monkeypatch):
        v = self._val(judge_model="judge-m")
        monkeypatch.setattr(v, "_call_judge", lambda *a: (0.5, "weak"))
        cv = v.validate_chunk("src", "trans", 0, "en", "fa")
        assert cv.passed is False
        assert "judge 0.50 < 0.7" in cv.flagged_reason

    def test_judge_parse_and_clamp(self, monkeypatch):
        import core.translation.validator as vmod

        sess = _FakeSession(content="SCORE: 0.85\nREASON: faithful", openai=True)
        monkeypatch.setattr(vmod, "session_for_url", lambda url: sess)
        v = self._val(judge_model="judge-m")
        score, reason = v._call_judge("s", "t", "en", "fa")
        assert score == 0.85 and reason == "faithful"
        assert sess.calls[0]["json"]["temperature"] == 0.0

        sess2 = _FakeSession(content="SCORE: 1.7\nREASON: over", openai=True)
        monkeypatch.setattr(vmod, "session_for_url", lambda url: sess2)
        assert v._call_judge("s", "t", "en", "fa")[0] == 1.0

        sess3 = _FakeSession(content="no score anywhere", openai=True)
        monkeypatch.setattr(vmod, "session_for_url", lambda url: sess3)
        assert v._call_judge("s", "t", "en", "fa")[0] == 0.5

    def test_judge_failure_disables_after_five(self, monkeypatch):
        import core.translation.validator as vmod

        sess = _FakeSession(raise_exc=RuntimeError("judge down"))
        monkeypatch.setattr(vmod, "session_for_url", lambda url: sess)
        v = self._val(judge_model="judge-m")
        for _ in range(5):
            cv = v.validate_chunk("s", "t", 0, "en", "fa")
            assert cv.judge_score == 0.5
        assert v._judge_disabled is True
        cv = v.validate_chunk("s", "t", 0, "en", "fa")
        assert cv.judge_score == 1.0  # unavailable, not failing

    def test_report_save_and_summary(self, tmp_path):
        from core.translation.validator import ChunkValidation, ValidationReport

        r = ValidationReport(file_name="f.md", source_lang="en", target_lang="fa")
        r.chunk_results = [
            ChunkValidation(chunk_index=0, passed=True, similarity_score=0.9, judge_score=0.8),
            ChunkValidation(
                chunk_index=1,
                passed=False,
                similarity_score=0.2,
                judge_score=0.3,
                flagged_reason="low",
            ),
        ]
        r.total_chunks, r.passed_chunks, r.flagged_chunks = 2, 1, 1
        r.avg_similarity, r.avg_judge_score = 0.55, 0.55
        jp = tmp_path / "r.json"
        mp = tmp_path / "r.md"
        r.save(jp)
        r.save_markdown(mp)
        data = json.loads(jp.read_text(encoding="utf-8"))
        assert data["file_name"] == "f.md" and len(data["chunk_results"]) == 2
        md = mp.read_text(encoding="utf-8")
        assert "# Translation Report: f.md" in md
        assert "## Flagged Chunks (Require Manual Review)" in md
        assert "1/2 chunks passed" in r.summary()

    def test_to_dict_truncates_long_texts(self):
        from core.translation.validator import ChunkValidation, ValidationReport

        r = ValidationReport()
        long = "x" * 600
        r.chunk_results = [ChunkValidation(chunk_index=0, source_text=long, translated_text=long)]
        d = r.to_dict()
        assert d["chunk_results"][0]["source_text"].endswith("...")
        assert len(d["chunk_results"][0]["source_text"]) == 503


class TestServiceFromSettings:
    """The pipeline-path factory: settings keys + the cloud-capable
    OpenAI-compat wiring + the secrets path handling."""

    def _patch_secrets(self, monkeypatch, canonical="", legacy=""):
        import core.system.secrets as secrets_mod

        set_calls: list[tuple] = []

        def fake_get(path, settings, default=""):
            if path == "translation.cloud_api_key":
                return canonical
            if path == "translation.api_key":
                return legacy
            return default

        def fake_set(path, value, settings):
            set_calls.append((path, value))

        monkeypatch.setattr(secrets_mod, "get_secret", fake_get)
        monkeypatch.setattr(secrets_mod, "set_secret", fake_set)
        return set_calls

    def test_wiring_from_settings(self, mock_settings, monkeypatch):
        self._patch_secrets(monkeypatch, canonical="sk-canonical")
        mock_settings.data = {
            "translation.endpoint": "http://localhost:3031/v1",
            "translation.model": "engine-m",
            "translation.temperature": 0.25,
            "translation.no_think": True,
            "translation.validation_enabled": True,
            "translation.judge_model": "judge-m",
            "translation.harakat_enabled": True,
            "translation.harakat_model": "hara-m",
            "summarisation.model": "summ-m",
            "translation.glossary_enabled": False,
            "translation.max_retries": 2,
        }
        from core.translation.service import TranslationService

        svc = TranslationService.from_settings()
        assert svc is not None
        assert svc.translator.endpoint == "http://localhost:3031/v1"
        assert svc.translator.model == "engine-m"
        assert svc.translator.temperature == 0.25
        assert svc.translator.api_key == "sk-canonical"
        assert svc.validator is not None and svc.validator.judge_model == "judge-m"
        assert svc.harakat_gen is not None
        assert svc.harakat_gen.model == "hara-m"
        assert svc.harakat_gen.fallback_model == "summ-m"
        assert svc.glossary_enabled is False
        assert svc.max_retries == 2

    def test_judge_model_falls_back_to_summarisation_model(self, mock_settings, monkeypatch):
        self._patch_secrets(monkeypatch)
        mock_settings.data = {
            "translation.validation_enabled": True,
            "summarisation.model": "summ-m",
            "translation.harakat_enabled": False,
        }
        from core.translation.service import TranslationService

        svc = TranslationService.from_settings()
        assert svc.validator is not None and svc.validator.judge_model == "summ-m"

    def test_no_judge_available_validator_none(self, mock_settings, monkeypatch):
        self._patch_secrets(monkeypatch)
        mock_settings.data = {
            "translation.validation_enabled": True,
            "translation.judge_model": "",
            "summarisation.model": "",
            "translation.harakat_enabled": False,
        }
        from core.translation.service import TranslationService

        assert TranslationService.from_settings().validator is None

    def test_legacy_api_key_migrated_to_canonical(self, mock_settings, monkeypatch):
        set_calls = self._patch_secrets(monkeypatch, legacy="sk-legacy")
        mock_settings.data = {"translation.harakat_enabled": False}
        from core.translation.service import TranslationService

        svc = TranslationService.from_settings()
        assert svc.translator.api_key == "sk-legacy"
        assert ("translation.cloud_api_key", "sk-legacy") in set_calls


class TestServiceTranslateFile:
    def _svc(self, monkeypatch, tmp_path, **kw):
        import core.translation.cache as tcache
        from core.translation.chunker import TranslationChunker
        from core.translation.service import TranslationService

        monkeypatch.setattr(tcache, "_CACHE_DIR", tmp_path / "cache")
        monkeypatch.setattr(
            "core.translation.glossary._get_nlp", lambda: None
        )  # deterministic regex fallback

        class _StubTranslator:
            def __init__(self):
                self.model = "stub-model"
                self.temperature = 0.1
                self.calls: list[str] = []

            def translate(
                self, text, source_lang="en", target_lang="fa", glossary_context="", prev_context=""
            ):
                self.calls.append(text)
                return f"[fa]{text[:8]}"

            def translate_back(self, text, a, b):
                return text

        stub = _StubTranslator()
        defaults = dict(
            translator=stub,
            validator=None,
            harakat_generator=None,
            chunker=TranslationChunker(max_tokens=2000),
            glossary_enabled=True,
            harakat_enabled=False,
            validation_enabled=False,
            max_retries=0,
            log_callback=lambda msg, level="INFO": None,
        )
        defaults.update(kw)
        return TranslationService(**defaults), stub

    def test_translate_file_writes_lang_subfolder_output(self, monkeypatch, tmp_path):
        svc, stub = self._svc(monkeypatch, tmp_path)
        src = tmp_path / "notes.md"
        src.write_text("# Head\n\nSome body text here.", encoding="utf-8")
        out_path, report = svc.translate_file(src, target_lang="fa")
        assert out_path == tmp_path / "fa" / "notes.fa.md"
        content = out_path.read_text(encoding="utf-8")
        assert content.startswith("[fa]") and "# Head" in content
        assert report is None  # validation disabled
        assert stub.calls  # the text chunk really went through the stub

    def test_frontmatter_and_code_chunks_not_translated(self, monkeypatch, tmp_path):
        svc, stub = self._svc(monkeypatch, tmp_path)
        src = tmp_path / "doc.md"
        src.write_text("---\ntitle: T\n---\n\nBody text.\n\n```py\nx = 1\n```", encoding="utf-8")
        out_path, _ = svc.translate_file(src, target_lang="fa")
        content = out_path.read_text(encoding="utf-8")
        assert "title: T" in content  # front-matter chunk verbatim
        assert "```py\nx = 1\n```" in content  # code chunk verbatim
        joined = "\n".join(stub.calls)
        assert "title: T" not in joined and "x = 1" not in joined

    def test_glossary_saved_next_to_source(self, monkeypatch, tmp_path):
        svc, _ = self._svc(monkeypatch, tmp_path)
        src = tmp_path / "doc.md"
        src.write_text("Monk Mode ideas appear here.", encoding="utf-8")
        svc.translate_file(src, target_lang="fa")
        glossary_path = tmp_path / "translation_logs" / "doc.glossary.json"
        assert glossary_path.exists()
        data = json.loads(glossary_path.read_text(encoding="utf-8"))
        assert "monk mode" in data["entries"]

    def test_cache_hit_avoids_second_translate(self, monkeypatch, tmp_path):
        svc, stub = self._svc(monkeypatch, tmp_path)
        src = tmp_path / "doc.md"
        src.write_text("Stable body text.", encoding="utf-8")
        svc.translate_file(src, target_lang="fa")
        first = len(stub.calls)
        svc.translate_file(src, target_lang="fa")
        assert len(stub.calls) == first  # V7.2.0 S5 persistent cache hit
        assert list((tmp_path / "cache").glob("*.json"))

    def test_missing_and_empty_and_same_lang_files(self, monkeypatch, tmp_path):
        svc, _ = self._svc(monkeypatch, tmp_path)
        assert svc.translate_file(tmp_path / "nope.md") == (None, None)
        empty = tmp_path / "empty.md"
        empty.write_text("   ", encoding="utf-8")
        assert svc.translate_file(empty) == (None, None)
        fa_src = tmp_path / "fa.md"
        fa_src.write_text("این متن فارسی است", encoding="utf-8")
        assert svc.translate_file(fa_src, target_lang="fa") == (None, None)  # same lang skip

    def test_translate_book_outputs_skips_stale_files(self, mock_settings, monkeypatch, tmp_path):
        svc, _ = self._svc(monkeypatch, tmp_path)
        mock_settings.data = {
            "translation.outputs": {"full_markdown": True},
            "translation.default_target_lang": "fa",
        }
        book_dir = tmp_path / "book"
        book_dir.mkdir()
        fresh = book_dir / "MyBook.md"
        fresh.write_text("Fresh content here.", encoding="utf-8")
        stale = book_dir / "OldBook.md"
        stale.write_text("Stale content here.", encoding="utf-8")
        old = time.time() - 3600  # > 30 minutes old
        os.utime(stale, (old, old))
        results = svc.translate_book_outputs(book_dir, "MyBook")
        assert [p.name for p, _ in results] == ["MyBook.fa.md"]
        assert (book_dir / "fa" / "MyBook.fa.md").exists()

    def test_translate_book_outputs_no_config_returns_empty(
        self, mock_settings, monkeypatch, tmp_path
    ):
        svc, _ = self._svc(monkeypatch, tmp_path)
        mock_settings.data = {"translation.outputs": {}}
        assert svc.translate_book_outputs(tmp_path, "x") == []

    def test_translate_standalone_text_harakat_wrapper(self, monkeypatch, tmp_path):
        svc, _ = self._svc(monkeypatch, tmp_path, harakat_enabled=True)

        class _StubHarakat:
            def add_harakat_to_markdown(self, text):
                return text + "|HARAKAT"

        svc.harakat_gen = _StubHarakat()
        out = svc.translate_standalone_text("hello there", source_lang="en", target_lang="fa")
        assert out.endswith("|HARAKAT")
        out_en = svc.translate_standalone_text("سلام", source_lang="fa", target_lang="en")
        assert not out_en.endswith("|HARAKAT")  # harakat only for Farsi target

    def test_translate_text_quick_path(self, monkeypatch, tmp_path):
        svc, stub = self._svc(monkeypatch, tmp_path)
        assert svc.translate_text("hello", source_lang="auto", target_lang="fa") == "[fa]hello"
        assert stub.calls == ["hello"]


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2 — service-level LIVE translation through the shim (:3031)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.live_llm
@_shim_gate
class TestLiveEngineShim:
    def test_single_line_en_to_fa(self):
        from core.translation.translation_engine import _PERSIAN_RE

        e = _make_engine(ollama_url=SHIM_URL, model=SHIM_MODEL, source_lang="en", target_lang="fa")
        out = e.translate_text("Hello, how are you today?")
        assert _PERSIAN_RE.search(out)
        assert "Hello" not in out  # not the silent original-text fallback

    def test_multiline_markdown_structure_preserved(self):
        from core.translation.translation_engine import _PERSIAN_RE

        e = _make_engine(ollama_url=SHIM_URL, model=SHIM_MODEL, source_lang="en", target_lang="fa")
        text = "# Weekend Notes\n\n- first task today\n- second task today"
        out = e.translate_text(text)
        lines = out.split("\n")
        assert len(lines) == 4  # line-count contract
        assert lines[1] == ""
        assert lines[0].startswith("# ") and not lines[0].startswith("## ")  # T4 level
        assert lines[2].startswith("- ") and lines[3].startswith("- ")
        persian_lines = sum(1 for ln in lines if _PERSIAN_RE.search(ln))
        assert persian_lines >= 2  # majority actually translated

    def test_translate_files_writes_real_output(self, tmp_path):
        from core.translation.translation_engine import _PERSIAN_RE

        e = _make_engine(ollama_url=SHIM_URL, model=SHIM_MODEL, source_lang="en", target_lang="fa")
        src = tmp_path / "notes.md"
        src.write_text("First short line.\nSecond short line.", encoding="utf-8")
        results = e.translate_files([str(src)], tmp_path / "out")
        out = tmp_path / "out" / "notes_translated.md"
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert _PERSIAN_RE.search(content)
        assert results[0].startswith("✅") and "notes_translated.md" in results[0]

    def test_direction_detection_roundtrip_on_live_output(self):
        from core.translation.translation_engine import TranslationEngine

        fa = "سلام، حال شما امروز چطور است؟"
        assert TranslationEngine.auto_detect_direction(fa) == ("fa", "en")
        assert TranslationEngine.auto_detect_direction("Hello, how are you?") == ("en", "fa")


# ═══════════════════════════════════════════════════════════════════════════
# Layer 3 — dialog-level drive
# ═══════════════════════════════════════════════════════════════════════════


def _qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _spin(app, dlg, timeout_ms=30000):
    import time as _t

    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        if dlg.status_label.text().startswith(("✅", "❌", "⚠️")):
            break
        _t.sleep(0.02)
        waited += 20
    return dlg.status_label.text()


def _flush(app, ms=1500):
    """Drain deferred zero-timers (the dialog's success/warning modals are
    scheduled via QTimer.singleShot(0) AFTER the status lands — without a
    flush they fire during the NEXT test's spin and leak across tests)."""
    import time as _t

    waited = 0
    while waited < ms:
        app.processEvents()
        _t.sleep(0.02)
        waited += 20


def _make_dialog():
    from ui_qt.views.service_dialogs.dialogs.translation_service_dialog import (
        TranslationServiceDialog,
    )

    _qt_app()  # a QWidget before QApplication is a hard Qt abort
    return TranslationServiceDialog(_StubController())


class _ModalRecorder:
    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, parent, title, message, file_path=None, on_try_another=None):
        self.calls.append((title, message, file_path))


class _FakeQMessageBox:
    def __init__(self):
        self.warnings: list[tuple] = []

    def warning(self, *args, **kwargs):
        self.warnings.append(args)
        return None


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDialogHermeticHelpers:
    def test_sanitize_stem(self):
        cls = type(_make_dialog())
        assert cls._sanitize_stem("My Notes: v2!") == "My_Notes__v2"
        assert cls._sanitize_stem("") == "output"
        assert len(cls._sanitize_stem("x" * 200)) == 80

    def test_default_output_filename(self):
        dlg = _make_dialog()
        assert dlg._default_output_filename("tiger", "fa", ".md") == "tiger-fa-translation.md"
        assert dlg._default_output_filename("pasted", "en", "md") == "pasted-en-translation.md"

    def test_default_output_dir_priority(self, tmp_path):
        dlg = _make_dialog()
        # Queue dir wins when no save_to folder is set.
        dlg._save_to_folder = ""
        dlg._file_queue = [str(tmp_path / "a.md")]
        assert dlg._default_output_dir() == str(tmp_path)
        # Gear save-to folder wins over the queue dir.
        dlg._save_to_folder = str(tmp_path / "chosen")
        assert dlg._default_output_dir() == str(tmp_path / "chosen")
        assert (tmp_path / "chosen").exists()  # created on demand

    def test_collect_options_model_resolution(self):
        dlg = _make_dialog()
        dlg.text_input.setPlainText("English input line")
        # (a) typed model text (editable combo, no items yet) — a typed
        # model stays authoritative even under the V0.6.5 active-LLM
        # fallback (it rides the provider transport with THAT model).
        dlg.model_combo.setCurrentText("glm-4-plus")
        opts = dlg._collect_options()
        assert opts["model"] == "glm-4-plus"
        assert opts["source_lang"] == "en" and opts["target_lang"] == "fa"
        assert opts["mode"] == "literal" and opts["format"] == ".md"
        # (b) no text at all → V0.6.5 contract: no dedicated translation
        # model exists, so the resolution falls back to the ACTIVE LLM
        # (the user requirement — was the hardcoded 12B default that
        # 404'd when translategemma isn't installed).
        from utils.settings import Settings

        prev = getattr(Settings, "_test_override", None)
        Settings._test_override = {
            "summarisation.provider": "llamacpp",
            "summarisation.model": "active-model-x",
            "quick_services.defaults.summarize_model": "",
        }
        try:
            dlg2 = _make_dialog()
            dlg2.model_combo.setCurrentText("")
            dlg2.text_input.setPlainText("Another English line")
            assert dlg2._collect_options()["model"] == "active-model-x"
            assert dlg2._active_llm_fallback is True
        finally:
            # V0.6.6 (review-loop): restore the PREVIOUS value verbatim —
            # `prev or {}` turned the neutral None into {}, and {} passes
            # Settings.__new__'s `is not None` check, so the empty dict
            # became the global Settings() for the rest of the session.
            Settings._test_override = prev

    def test_collect_options_persian_input_flips_direction(self):
        dlg = _make_dialog()
        dlg.text_input.setPlainText("سلام این یک متن فارسی است")
        opts = dlg._collect_options()
        assert opts["source_lang"] == "fa" and opts["target_lang"] == "en"

    def test_update_direction_reacts_to_text(self):
        dlg = _make_dialog()
        dlg.text_input.setPlainText("Plain English words")
        assert dlg._detected_direction == ("en", "fa")
        dlg.text_input.setPlainText("متن فارسی اینجا")
        assert dlg._detected_direction == ("fa", "en")

    def test_refresh_default_output_keeps_custom_name(self):
        dlg = _make_dialog()
        dlg.text_input.setPlainText("English words")
        custom = str(Path.home() / "my-custom-name.md")
        dlg.out_path_edit.setText(custom)
        dlg._refresh_default_output()
        assert dlg.out_path_edit.text() == custom

    def test_format_elapsed(self):
        cls = type(_make_dialog())
        assert cls._format_elapsed(5.2) == "5.2s"
        assert cls._format_elapsed(125.0) == "2m 5s"

    def test_refresh_models_from_api_tags(self, mock_settings, monkeypatch):
        import requests

        mock_settings.data = {"translation.endpoint": f"{SHIM_URL}/v1"}

        class _R:
            status_code = 200

            def json(self):
                return {
                    "models": [
                        {"name": "qwen3:8b"},
                        {"name": "translategemma-12b-it.Q4_K_M_mradermacher:latest"},
                    ]
                }

        seen: list[str] = []

        def fake_get(url, timeout=None):
            seen.append(url)
            return _R()

        monkeypatch.setattr(requests, "get", fake_get)
        dlg = _make_dialog()
        dlg._refresh_models()
        assert seen == [f"{SHIM_URL}/api/tags"]  # /v1 stripped for /api/tags
        assert dlg.model_combo.count() == 2
        assert dlg.model_combo.currentData() == "translategemma-12b-it.Q4_K_M_mradermacher:latest"

    def test_refresh_models_unreachable_seeds_default(self, mock_settings, monkeypatch):
        import requests

        mock_settings.data = {"translation.endpoint": f"{SHIM_URL}/v1"}

        def fake_get(url, timeout=None):
            raise requests.ConnectionError("down")

        monkeypatch.setattr(requests, "get", fake_get)
        dlg = _make_dialog()
        dlg._refresh_models()
        assert dlg.model_combo.count() == 1
        assert "Ollama unreachable" in dlg.model_combo.currentText()
        assert dlg.model_combo.currentData() == ("translategemma-12b-it.Q4_K_M_mradermacher:latest")

    def test_peek_input_text_priority(self, tmp_path):
        dlg = _make_dialog()
        dlg.text_input.setPlainText("typed text wins")
        assert dlg._peek_input_text() == "typed text wins"
        dlg.text_input.setPlainText("")
        q = tmp_path / "queued.md"
        q.write_text("queued file content", encoding="utf-8")
        dlg._file_queue = [str(q)]
        assert dlg._peek_input_text() == "queued file content"


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDialogProcessErrorContract:
    """T2: dialog failures must land in the shared 'Error:' contract."""

    def _patch_modals(self, monkeypatch):
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod

        recorder = _ModalRecorder()
        monkeypatch.setattr(shared_mod, "_show_success_modal", recorder)
        monkeypatch.setattr(trans_mod, "_show_success_modal", recorder)
        return recorder

    def test_process_model_not_found_returns_error_prefix(self, monkeypatch):
        from core.translation.translation_engine import ModelNotFoundError, TranslationEngine

        def raise_mnf(self, text):
            raise ModelNotFoundError("Model 'x' not found in Ollama (HTTP 404)")

        monkeypatch.setattr(TranslationEngine, "translate_text", raise_mnf)
        dlg = _make_dialog()
        out = dlg._process("some text", {"source_lang": "en", "target_lang": "fa"})
        assert out.startswith("Error:")
        assert "not found" in out

    def test_process_generic_failure_returns_error_prefix(self, monkeypatch):
        from core.translation.translation_engine import TranslationEngine

        def boom(self, text):
            raise RuntimeError("engine exploded")

        monkeypatch.setattr(TranslationEngine, "translate_text", boom)
        dlg = _make_dialog()
        out = dlg._process("some text", {"source_lang": "en", "target_lang": "fa"})
        assert out.startswith("Error:")
        assert "RuntimeError" in out

    def test_t2_full_worker_drive_failure_is_not_success(self, tmp_path, monkeypatch):
        """Pre-fix: '❌ {e}' fell through _on_finished's Error: check → the
        error text was WRITTEN to the output file with a ✅ status + modal."""
        from core.translation.translation_engine import ModelNotFoundError, TranslationEngine

        def raise_mnf(self, text):
            raise ModelNotFoundError("Model 'x' not found in Ollama (HTTP 404)")

        monkeypatch.setattr(TranslationEngine, "translate_text", raise_mnf)
        recorder = self._patch_modals(monkeypatch)

        app = _qt_app()
        dlg = _make_dialog()
        dlg.text_input.setPlainText("translate me please")
        out = tmp_path / "out.md"
        dlg.out_path_edit.setText(str(out))
        dlg._on_process()

        status = _spin(app, dlg)
        assert status.startswith("❌ Error:"), status
        assert not out.exists()  # nothing written for a failure
        assert recorder.calls == []  # no success modal
        assert not dlg.again_btn.isHidden()  # failure branch re-arms "Try Another"


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDialogQueueFlow:
    """The multi-file queue path (hermetic — _process stubbed on the
    instance; write_output + SimpleWorker are real)."""

    def _run_queue(self, tmp_path, monkeypatch, process_result):
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod

        recorder = _ModalRecorder()
        monkeypatch.setattr(shared_mod, "_show_success_modal", recorder)
        monkeypatch.setattr(trans_mod, "_show_success_modal", recorder)

        dlg = _make_dialog()
        files = []
        for name in ("one.md", "two.md"):
            f = tmp_path / name
            f.write_text(f"content of {name}\nsecond line", encoding="utf-8")
            files.append(f)
            dlg._file_queue.append(str(f))
            dlg.file_queue_list.addItem(str(f))
        dlg.out_path_edit.setText(str(tmp_path))
        if callable(process_result):
            dlg._process = process_result
        else:
            dlg._process = lambda text, options: process_result
        dlg._on_process()
        return dlg, recorder

    def test_queue_success_writes_each_file_and_modal(self, tmp_path, monkeypatch):
        dlg, recorder = self._run_queue(tmp_path, monkeypatch, "ترجمه‌ی این فایل")
        app = _qt_app()
        status = _spin(app, dlg)
        assert status.startswith("✅"), status
        for name in ("one-fa-translation.md", "two-fa-translation.md"):
            f = tmp_path / name
            assert f.exists(), name
            # V0.6.5 contract: Persian output (.md) carries the Obsidian
            # ``dir: rtl`` front-matter property — byte-exact equality
            # with the bare translation no longer holds.
            content = f.read_text(encoding="utf-8")
            assert content.startswith("---\ndir: rtl\n---")
            assert content.endswith("ترجمه‌ی این فایل")
        assert "✅ one.md → one-fa-translation.md" in dlg.result_preview.toPlainText()
        # The modal is DEFERRED (QTimer.singleShot(0)) — flush so it fires
        # inside THIS test instead of leaking into the next one's spin.
        _flush(app)
        assert recorder.calls and recorder.calls[0][0] == "✅ Translation Complete"

    def test_t7_all_failed_queue_never_success_modal(self, tmp_path, monkeypatch):
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod

        def failing(text, options):
            raise RuntimeError("no engine")

        recorder = _ModalRecorder()
        monkeypatch.setattr(trans_mod, "_show_success_modal", recorder)
        fake_mb = _FakeQMessageBox()
        monkeypatch.setattr(trans_mod, "QMessageBox", fake_mb)

        app = _qt_app()
        dlg = _make_dialog()
        f = tmp_path / "bad.md"
        f.write_text("content", encoding="utf-8")
        dlg._file_queue = [str(f)]
        dlg.out_path_edit.setText(str(tmp_path))
        dlg._process = failing
        dlg._on_process()

        status = _spin(app, dlg)
        # Flush BEFORE asserting recorder emptiness: a prior test's deferred
        # modal timer may still be pending — it must fire (and be absorbed by
        # THIS test's monkeypatched recorder) inside this test, not the next.
        _flush(app)
        assert status.startswith("❌"), status
        assert not (tmp_path / "bad-fa-translation.md").exists()
        assert recorder.calls == []  # no success modal on failure (T7)
        # The deferred warning modal fired instead.
        extra = 0
        while extra < 2000 and not fake_mb.warnings:
            app.processEvents()
            time.sleep(0.02)
            extra += 20
        assert fake_mb.warnings and fake_mb.warnings[0][1] == "⚠️ Translation Failed"

    def test_empty_file_in_queue_reported_and_skipped(self, tmp_path, monkeypatch):
        empty = tmp_path / "empty.md"
        empty.write_text("   ", encoding="utf-8")

        def fake_process(text, options):
            return "ترجمه"

        # The empty-file-only queue takes the all-failed path → the dialog
        # defers a REAL QMessageBox.warning — which BLOCKS forever offscreen
        # (no user to dismiss it). Stub it like the t7 test does.
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod

        fake_mb = _FakeQMessageBox()
        monkeypatch.setattr(trans_mod, "QMessageBox", fake_mb)

        dlg, recorder = self._run_queue(tmp_path, monkeypatch, fake_process)
        # Now drive an empty-file-only queue on a fresh dialog.
        app = _qt_app()
        d = _make_dialog()
        d._file_queue = [str(empty)]
        d.out_path_edit.setText(str(tmp_path))
        d._process = lambda text, options: "ترجمه"
        d._on_process()
        status = _spin(app, d)
        assert "⚠️ empty.md → empty file, skipped" in status
        assert not (tmp_path / "empty-fa-translation.md").exists()
        # BOTH dialogs' workers must fully finish (queued signals delivered,
        # deferred timers flushed) before teardown — a still-running
        # SimpleWorker at interpreter exit is the QThread-destroyed abort.
        _spin(app, dlg)
        _flush(app)
        # The deferred warning modal fired (stubbed — non-blocking).
        assert fake_mb.warnings and fake_mb.warnings[0][1] == "⚠️ Translation Failed"


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestDialogGuards:
    def test_no_input_warns_and_spawns_no_worker(self, monkeypatch):
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod

        fake_mb = _FakeQMessageBox()
        monkeypatch.setattr(shared_mod, "QMessageBox", fake_mb)
        monkeypatch.setattr(trans_mod, "QMessageBox", fake_mb)
        _qt_app()
        dlg = _make_dialog()
        dlg._on_process()
        assert fake_mb.warnings and fake_mb.warnings[0][1] == "No input"
        assert dlg._worker is None

    def test_no_output_autofills_and_spawns_worker(self, monkeypatch, tmp_path):
        """V11.29 contract: with text input and an EMPTY output path, the
        dialog AUTO-FILLS the default ``*-translation`` path (the base class's
        'No output' warning is unreachable by design — _refresh_default_output
        runs first) and spawns the worker. The previous expectation ('No
        output' warning) was wrong: it pinned a base-class branch this dialog
        can never reach."""
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod
        from ui_qt.views.service_dialogs.dialogs.translation_service_dialog import (
            TranslationServiceDialog,
        )

        fake_mb = _FakeQMessageBox()
        monkeypatch.setattr(trans_mod, "QMessageBox", fake_mb)
        recorder = _ModalRecorder()
        # BOTH bindings: the base-class deferred modal (shared.py:572) calls
        # the SHARED module's _show_success_modal — patching only the
        # translation module's name leaves the real modal.exec() blocking.
        monkeypatch.setattr(shared_mod, "_show_success_modal", recorder)
        monkeypatch.setattr(trans_mod, "_show_success_modal", recorder)
        # Keep the auto-filled default INSIDE tmp_path (otherwise the dialog
        # derives pasted-*-translation.md in the user's home).
        monkeypatch.setattr(
            TranslationServiceDialog, "_default_output_dir", lambda self: str(tmp_path)
        )
        app = _qt_app()
        dlg = _make_dialog()
        dlg.text_input.setPlainText("some input text")
        dlg.out_path_edit.setText("")
        dlg._process = lambda text, options: "متن ترجمه"
        dlg._on_process()

        assert not any(w[1] == "No output" for w in fake_mb.warnings)
        assert dlg.out_path_edit.text().strip()
        assert Path(dlg.out_path_edit.text().strip()).name.endswith("-translation.md")
        assert dlg._worker is not None
        # Complete + flush HERE: this dialog's deferred modal must fire inside
        # THIS test — otherwise it leaks into a later test's recorder (the
        # exact failure the live-drive test hit in sequence: its recorder
        # captured THIS dialog's stale success modal).
        status = _spin(app, dlg)
        assert status.startswith("✅"), status
        _flush(app)
        assert recorder.calls


@pytest.mark.live_llm
@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
@pytest.mark.skipif(not _SHIM_OK, reason="zai-llamacpp shim :3031 unavailable")
class TestDialogLiveDrive:
    """The full LIVE flow: paste text → real SimpleWorker → real
    TranslationEngine → shim :3031 → write_output → status + modal."""

    def test_full_worker_drive_lands_success_and_persian_file(
        self, tmp_path, monkeypatch, mock_settings
    ):
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.translation_service_dialog as trans_mod
        from core.translation.translation_engine import _PERSIAN_RE

        mock_settings.data = {"translation.endpoint": f"{SHIM_URL}/v1"}
        recorder = _ModalRecorder()
        monkeypatch.setattr(shared_mod, "_show_success_modal", recorder)
        monkeypatch.setattr(trans_mod, "_show_success_modal", recorder)

        app = _qt_app()
        dlg = _make_dialog()
        dlg.text_input.setPlainText("Hello, how are you today?")
        dlg.model_combo.setCurrentText(SHIM_MODEL)
        out = tmp_path / "live-translation.md"
        dlg.out_path_edit.setText(str(out))

        dlg._on_process()

        status = _spin(app, dlg)
        assert status.startswith("✅"), status
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert _PERSIAN_RE.search(content)
        assert "Error" not in content

        # The deferred success modal fired with the real output path.
        extra = 0
        while extra < 2000 and not recorder.calls:
            app.processEvents()
            time.sleep(0.02)
            extra += 20
        assert recorder.calls
        title, _message, file_path = recorder.calls[0]
        assert title == "✅ 🌐 Translation Service Complete"
        assert file_path == str(out)
