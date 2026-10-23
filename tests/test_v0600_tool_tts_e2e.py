"""V0.6.0 (the dedicated-tools verification campaign) — Tool: the TTS
Service (``tts_service``) + the podcast AUDIO chain, end-to-end.

Inventory + trace (evidence-first):
- Card: ``tts_service`` — ``ui_qt/views/tool_dashboard.py:119`` TOOL_CARDS
  row 4 (AUDIO).
- Routing: ``ui_qt/views/convert_view.py:180-184`` ``_on_tool_clicked`` →
  ``TtsServiceDialog`` (via the base_dialog facade re-export :61).
- Dialog: ``ui_qt/views/service_dialogs/dialogs/tts_service_dialog.py``
  (1088 lines; GPU guardrails :46-220, ``_populate_voices`` :502, CPU
  guard ``_guard_gpu_required`` :609, worker entry ``_on_process`` :644,
  preview worker :655, engine dispatch ``_process`` :951-1088 — the seam
  the dialog calls core is ``from core.tts.engine_cache import
  get_kokoro_engine / get_vibevoice_engine`` INSIDE ``_process``).
- Service: ``core/tts/`` — engine.py (TTSEngine base + Kokoro/Coqui +
  TTSRouter + detect_language; V0.6.64: the Piper engine removed),
  engine_cache.py (persistent
  singletons), voices.py + voice_manager.py (catalogs), normalizer.py
  (LLM text normalization + deterministic Persian number fallback),
  neutts/qwen/vibevoice/sherpa/persian_vits engines (GPU/external).
- Podcast AUDIO: ``core/podcast/audio_generator.py`` (396 —
  ``_synthesize_line`` :81 engine dispatch, ``generate_podcast_audio``
  :169 assembly + crossfade stitching) and ``core/outputs/
  podcast_audio.py`` (``_parse_speaker_line`` :52, ``_split_long_line``
  :65, ``_concat_wavs`` :414, ``_resolve_host_voices`` :343).

Sandbox capability map (live-probed):
- torch/kokoro/qwen_tts/sherpa_onnx/TTS — ABSENT → all
  neural engines are CONTRACT-level here (rig-checklist items)
  (V0.6.64: the Piper binary engine was removed entirely).
- soundfile + numpy + pydub + ffmpeg + huggingface_hub — PRESENT → the
  WAV assembly, concat and WAV→MP3 conversion run LIVE.
- The LLM shim on :3031 — PRESENT → the TextNormalizer's OpenAI-
  compatible /chat/completions path runs LIVE (audio-side LLM).

Layers (house UI-test pattern, cf. test_v0600_tool_cutter_e2e.py):
1. Pure characterization: detect_language, normalizer (numbers, sentence
   split, cache/fallback/disable), voices catalogs, VoiceManager, the
   engine_cache keying, TTSRouter's engine-selection matrix.
2. Service-level: LIVE Kokoro synthesize with faked
   torch/kokoro modules (real soundfile write), LIVE normalizer round-
   trip through the :3031 shim, contracts for the GPU engines (qwen/
   vibevoice/sherpa), and the podcast audio assembly with the TTS
   engine faked at its engine_cache seam (real crossfade + real WAV).
3. Dialog-level drive: the real SimpleWorker QThread through
   ``_on_process`` → ``_process`` → ``_on_finished`` with the engine
   faked at the ``core.tts.engine_cache`` seam, modals stubbed on BOTH
   modules (batch-B lesson), workers completed in-test, real .wav AND
   .mp3 outputs (pydub+ffmpeg), the reactive CUDA-error modal, and the
   preview worker drive.

V0.6.0 defects pinned here (content-agnostic fixes):
- T1: the VibeVoice→Kokoro fallback passed the ``"vibevoice:…"``
  prefixed voice string straight to Kokoro (tts_service_dialog.py:1025
  and the preview path :721 pre-fix) — the advertised fallback engine
  then fails on the unknown voice instead of falling back.
- A1: ``audio_generator._detect_language`` (:70 pre-fix) is a drifting
  copy of ``core.tts.engine.detect_language`` that misses the Arabic
  presentation-form blocks (U+FB50–U+FDFF / U+FE70–U+FEFF) — Persian
  text in presentation forms (common after PDF extraction) routed to
  the English branch. Fix: delegate to the canonical detector.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Layer 0: availability gates ─────────────────────────────────────────────


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

        r = requests.get("http://localhost:3031/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


_SHIM_URL = "http://localhost:3031/v1"
_SHIM_MODEL = "glm-4-plus"


@pytest.fixture(autouse=True)
def _ensure_qapp():
    if _qt_available():
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
    yield


# ── Shared stubs + helpers ─────────────────────────────────────────────────


class _StubController:
    """Dialogs only need get/update_setting (campaign-probed contract)."""

    def __init__(self) -> None:
        self._settings: dict[str, object] = {}

    def get_setting(self, key: str, default=None):
        return self._settings.get(key, default)

    def update_setting(self, key: str, value) -> None:
        self._settings[key] = value


class _SettingsOverride:
    """In-memory Settings stand-in (the Settings._test_override DI hook at
    utils/settings.py:85 — every in-function ``Settings()`` call resolves to
    this instance, the scripts/repeatability_run.py:246 pattern)."""

    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v: dict[str, object] = dict(values or {})

    def get(self, key: str, default=None):
        return self._v.get(key, default)

    def set(self, key: str, value) -> bool:
        self._v[key] = value
        return True


@pytest.fixture
def settings_override(monkeypatch):
    from utils.settings import Settings

    override = _SettingsOverride()
    previous = Settings._test_override
    Settings._test_override = override  # type: ignore[assignment]
    try:
        yield override
    finally:
        Settings._test_override = previous  # type: ignore[assignment]


def _write_tiny_wav(path: Path, seconds: float = 0.2, sr: int = 24000) -> Path:
    """A REAL WAV via soundfile (the engine's own writer)."""
    import numpy as np
    import soundfile as sf

    n = max(int(sr * seconds), 8)
    data = (0.05 * np.sin(np.linspace(0.0, 40.0 * 3.14159, n))).astype(np.float32)
    sf.write(str(path), data, sr)
    return path


class _MsgBoxRecorder:
    """Stands in for the dialog module's QMessageBox (static modal calls)."""

    # button-flag constants referenced by callers (QMessageBox.Ok etc.)
    Ok = 0x400
    Yes = 0x4000
    No = 0x10000
    Cancel = 0x40000

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def warning(self, parent, title, text, *a, **k) -> object:
        self.calls.append(("warning", title, text))
        return 0

    def critical(self, parent, title, text, *a, **k) -> object:
        self.calls.append(("critical", title, text))
        return 0

    def information(self, parent, title, text, *a, **k) -> None:
        self.calls.append(("information", title, text))

    def titles(self) -> list[str]:
        return [t for _kind, t, _text in self.calls]


def _spin_until_status(app, dlg, prefixes=("✅", "❌", "⚠️", "🚫"), timeout_ms=15000) -> str:
    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        text = dlg.status_label.text()
        if text.startswith(tuple(prefixes)):
            return text
        time.sleep(0.02)
        waited += 20
    return dlg.status_label.text()


def _flush(app, rounds: int = 25) -> None:
    """Drain deferred QTimer.singleShot(0) modals (batch-B lesson 1)."""
    for _ in range(rounds):
        app.processEvents()
        time.sleep(0.004)


# ═══════════════════════════════════════════════════════════════════════════
# Layer 1 — pure characterization
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectLanguage:
    """core/tts/engine.py:64 — the canonical script router."""

    def test_empty_and_english(self):
        from core.tts.engine import detect_language

        assert detect_language("") == "en"
        assert detect_language("hello world this is english text") == "en"

    def test_persian_detected(self):
        from core.tts.engine import detect_language

        assert detect_language("این یک متن فارسی است") == "fa"

    def test_mixed_threshold_20_percent(self):
        from core.tts.engine import detect_language

        # 3 Arabic-script chars among 14 non-space chars -> ~0.21 > 0.2 -> fa
        assert detect_language("abc def ghi jk این") == "fa"
        # 1 Arabic-script char among ~10 -> 0.1 < 0.2 -> en
        assert detect_language("abc def ghi jkl م") == "en"

    def test_arabic_presentation_forms_detected(self):
        """The FB50-FDFF / FE70-FEFF blocks are covered (engine.py:61)."""
        from core.tts.engine import detect_language

        presentation = "\ufeb3\ufee3\ufedf\ufe8d\ufe8e"  # s-l-l-m in forms-A
        assert detect_language(presentation) == "fa"


class TestNormalizerFaNumbers:
    """core/tts/normalizer.py:199 — the deterministic Persian number words."""

    def test_units_and_teens(self):
        from core.tts.normalizer import _fa_number_to_words

        assert _fa_number_to_words(0) == "صفر"
        assert _fa_number_to_words(7) == "هفت"
        assert _fa_number_to_words(12) == "دوازده"
        assert _fa_number_to_words(19) == "نوزده"

    def test_tens_and_hundreds_with_connector(self):
        from core.tts.normalizer import _fa_number_to_words

        assert _fa_number_to_words(25) == "بیست و پنج"
        assert _fa_number_to_words(100) == "صد"
        assert _fa_number_to_words(123) == "صد و بیست و سه"
        assert _fa_number_to_words(999) == "نهصد و نود و نه"

    def test_thousands_bare_and_composed(self):
        from core.tts.normalizer import _fa_number_to_words

        assert _fa_number_to_words(1000) == "هزار"
        assert _fa_number_to_words(2000) == "دو هزار"
        assert _fa_number_to_words(1403) == "هزار و چهارصد و سه"

    def test_negative_and_huge_fallback(self):
        from core.tts.normalizer import _fa_number_to_words

        assert _fa_number_to_words(-5) == "منفی پنج"
        assert _fa_number_to_words(10**7) == str(10**7)  # above 10^6: digits

    def test_expand_fa_numbers(self):
        from core.tts.normalizer import _expand_fa_numbers

        assert _expand_fa_numbers("داریم ۱۲۳ می‌رود") == "داریم صد و بیست و سه می‌رود"
        assert _expand_fa_numbers("7 و 8") == "هفت و هشت"

    def test_expand_fa_numbers_decimals_expand_each_run(self):
        """Characterization: each digit RUN expands independently — the
        decimal point stays, both runs convert ("3.14" -> "سه.چهارده")."""
        from core.tts.normalizer import _expand_fa_numbers

        assert _expand_fa_numbers("3.14") == "سه.چهارده"


class TestNormalizerSplitting:
    def test_sentences_on_en_fa_enders_and_newlines(self):
        from core.tts.normalizer import _split_sentences

        parts = _split_sentences("First one. Second? Third! چهارم؟\nپنجم")
        assert len(parts) == 5
        assert parts[3] == "چهارم؟"

    def test_paragraphs_on_blank_lines(self):
        from core.tts.normalizer import _split_paragraphs

        assert _split_paragraphs("p one\n\np two") == ["p one", "p two"]


class TestTextNormalizerCore:
    """normalizer.py:269 — cache, context modes, fallback, disable."""

    def _make(self, **kw) -> object:
        from core.tts.normalizer import TextNormalizer

        return TextNormalizer(endpoint="http://localhost:9", api_key="", model="m", **kw)

    def test_llm_success_used_and_cached(self, monkeypatch):
        norm = self._make()
        calls: list[str] = []

        def fake_llm(text, language):
            calls.append(text)
            return f"norm<{text}>"

        monkeypatch.setattr(norm, "_call_llm", fake_llm)
        out1 = norm.normalize("The doctor went home.", "en")
        out2 = norm.normalize("The doctor went home.", "en")
        assert out1 == "norm<The doctor went home.>"
        assert out2 == out1
        assert calls == ["The doctor went home."]  # second hit = cache

    def test_abbreviation_sentence_split_characterization(self, monkeypatch):
        """Characterization: "Dr." splits like a sentence ender — the
        normalizer sends the abbreviation as its own chunk."""
        norm = self._make()
        seen: list[str] = []
        monkeypatch.setattr(norm, "_call_llm", lambda t, l: seen.append(t) or t)
        norm.normalize("Dr. Smith went home.", "en")
        assert seen == ["Dr.", "Smith went home."]

    def test_think_tags_stripped(self, monkeypatch):
        """The Ollama think-block is stripped INSIDE _call_llm (normalizer.py
        :424) — drive it through the real method with the transport mocked."""
        norm = self._make()
        tagged = "<" + "think" + ">reasoning here</" + "think" + ">normalized text"

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": tagged}}]}

        class _Session:
            def post(self, url, json=None, headers=None, timeout=None):
                return _Resp()

        monkeypatch.setattr("core.tts.normalizer.session_for_url", lambda url: _Session())
        out = norm.normalize("some input line", "en")
        assert out == "normalized text"

    def test_failure_falls_back_en_passthrough_fa_numbers(self, monkeypatch):
        norm = self._make()

        def boom(text, language):
            raise RuntimeError("endpoint down")

        monkeypatch.setattr(norm, "_call_llm", boom)
        assert norm.normalize("plain english words", "en") == "plain english words"
        assert norm.normalize("ما ۲ روز رفتیم", "fa") == "ما دو روز رفتیم"

    def test_three_failures_disable_llm_for_session(self, monkeypatch):
        norm = self._make()

        def boom(text, language):
            raise RuntimeError("nope")

        monkeypatch.setattr(norm, "_call_llm", boom)
        for i in range(4):
            norm.normalize(f"text number {i} here", "en")  # distinct: no cache hits
        assert norm._disabled is True
        # Disabled: fa takes the deterministic path with NO further LLM calls.
        assert norm.normalize("۴۵ عدد", "fa") == "چهل و پنج عدد"

    def test_fallback_result_is_cached_too(self, monkeypatch):
        """Characterization: the deterministic-fallback result is cached like
        a success — repeated identical text never re-counts as a failure."""
        norm = self._make()
        calls = []

        def boom(text, language):
            calls.append(text)
            raise RuntimeError("down")

        monkeypatch.setattr(norm, "_call_llm", boom)
        for _ in range(3):
            norm.normalize("same failing words", "en")
        assert calls == ["same failing words"]  # 1 attempt, then cached
        assert norm._failure_count == 1 and not norm._disabled

    def test_context_modes_shape_chunks(self, monkeypatch):
        seen: list[str] = []
        norm = self._make(context_mode="sentence")
        monkeypatch.setattr(norm, "_call_llm", lambda t, l: seen.append(t) or f"[{t}]")
        out = norm.normalize("one. two.", "en")
        assert seen == ["one.", "two."]
        assert out == "[one.] [two.]"

        norm_p = self._make(context_mode="paragraph")
        monkeypatch.setattr(norm_p, "_call_llm", lambda t, l: f"[{t}]")
        assert norm_p.normalize("para a\n\npara b", "en") == "[para a]\n\n[para b]"

        norm_s = self._make(context_mode="segment")
        monkeypatch.setattr(norm_s, "_call_llm", lambda t, l: f"[{t}]")
        assert norm_s.normalize("a. b. c.", "en") == "[a. b. c.]"

    def test_cache_keys_separate_language_and_prompt(self):
        norm = self._make(custom_prompt_en="E{text}", custom_prompt_fa="F{text}")
        k_en = norm._cache_key("same words", "en")
        k_fa = norm._cache_key("same words", "fa")
        assert k_en != k_fa
        norm2 = self._make(custom_prompt_en="OTHER{text}")
        assert norm2._cache_key("same words", "en") != k_en

    def test_cache_is_bounded(self, monkeypatch):
        norm = self._make()
        norm._cache_max = 5
        monkeypatch.setattr(norm, "_call_llm", lambda t, l: t.upper())
        for i in range(12):
            norm.normalize(f"line {i} of the test", "en")
        assert len(norm._cache) <= 5
        norm.clear_cache()
        assert norm._cache == {}

    def test_empty_text_short_circuits(self):
        norm = self._make()
        assert norm.normalize("", "en") == ""
        assert norm.normalize("   ", "fa") == "   "


class TestVoicesCatalog:
    """core/tts/voices.py — catalogs + the local-cache download helper."""

    def test_kokoro_catalog_shape(self):
        from core.tts.voices import KOKORO_DEFAULT_HOST_A, KOKORO_DEFAULT_HOST_B, KOKORO_VOICES

        ids = [v[0] for v in KOKORO_VOICES]
        assert len(ids) == len(set(ids))
        assert all(v[1].startswith("en-") for v in KOKORO_VOICES)
        assert KOKORO_DEFAULT_HOST_A in ids and KOKORO_DEFAULT_HOST_B in ids

    def test_kokoro_groups_and_labels(self):
        from core.tts.voices import kokoro_voice_groups, kokoro_voice_label

        groups = kokoro_voice_groups()
        assert groups[0][0] == "American Female"
        assert len(groups) == 4  # American/British × Female/Male
        assert kokoro_voice_label("af_heart") == "af_heart — warm, empathetic"
        assert kokoro_voice_label("not_a_voice") == "not_a_voice"

    def test_piper_catalog_removed_v0664(self):
        """V0.6.64: the Piper engine was removed entirely (user decision,
        remaining-surface item 4) — the catalog + helpers are GONE from
        core.tts.voices. Pin the removal so it cannot silently reappear."""
        import core.tts.voices as voices_mod

        for gone in (
            "PIPER_FA_VOICES",
            "PIPER_FA_DEFAULT",
            "piper_voice_label",
            "piper_voice_repo",
            "ensure_piper_voice",
        ):
            assert not hasattr(voices_mod, gone), f"{gone} should be removed (V0.6.64)"


class TestVoiceManager:
    """core/tts/voice_manager.py — reference voice pairs on disk."""

    def _make(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "utils.settings.Settings._test_override",
            _SettingsOverride({"tts.neutts_project_path": str(tmp_path / "nonexistent")}),
        )
        from core.tts.voice_manager import VoiceManager

        return VoiceManager(voices_dir=tmp_path / "refs")

    def test_presets_listed_with_readme(self, tmp_path, monkeypatch):
        vm = self._make(tmp_path, monkeypatch)
        names = [v["name"] for v in vm.list_voices()]
        assert names[:5] == ["dave", "jo", "greta", "juliette", "mateo"]
        assert (vm.voices_dir / "README.md").exists()

    def test_user_voice_pair_roundtrip(self, tmp_path, monkeypatch):
        vm = self._make(tmp_path, monkeypatch)
        wav = _write_tiny_wav(tmp_path / "my_voice.wav", 0.1, 16000)
        saved = vm.add_voice("My Voice!", wav, "hello there spoken words")
        assert saved.name == "my_voice_.wav"  # sanitized: space -> underscore
        got = vm.get_voice("my_voice_")
        assert got[0] == str(vm.voices_dir / "my_voice_.wav")
        assert got[1] == "hello there spoken words"

    def test_get_voice_missing_and_fallback_transcript(self, tmp_path, monkeypatch):
        vm = self._make(tmp_path, monkeypatch)
        assert vm.get_voice("nope") == (None, "")
        # wav present but txt missing -> generic fallback transcript
        wav = vm.voices_dir / "bare.wav"
        _write_tiny_wav(wav, 0.1, 16000)
        (vm.voices_dir / "bare.txt").write_text("   ", encoding="utf-8")
        path, text = vm.get_voice("bare")
        assert path == str(wav)
        assert text == "This is a reference voice sample."

    def test_add_voice_rejects_empty_and_long_names(self, tmp_path, monkeypatch):
        vm = self._make(tmp_path, monkeypatch)
        wav = _write_tiny_wav(tmp_path / "src.wav", 0.1, 16000)
        with pytest.raises(ValueError):
            vm.add_voice("", wav, "t")  # empty name after strip
        saved = vm.add_voice("a" * 60, wav, "t")
        assert len(saved.stem) == 40

    def test_remove_voice(self, tmp_path, monkeypatch):
        vm = self._make(tmp_path, monkeypatch)
        wav = _write_tiny_wav(tmp_path / "src.wav", 0.1, 16000)
        vm.add_voice("gone", wav, "text")
        assert vm.voice_exists("gone")
        assert vm.remove_voice("gone") is True
        assert not vm.voice_exists("gone")
        assert vm.remove_voice("gone") is False


class TestEngineCacheKeying:
    """core/tts/engine_cache.py — persistent-singleton keying."""

    @pytest.fixture(autouse=True)
    def _snapshot_engines(self):
        from core.tts import engine_cache as ec

        before = dict(ec._engines)
        yield
        ec._engines.clear()
        ec._engines.update(before)

    def test_kokoro_singleton_reused(self, monkeypatch):
        from core.tts import engine_cache as ec

        created: list = []

        class FakeKokoro:
            def __init__(self, log_callback=None):
                created.append(log_callback)
                self.last_error = None

        monkeypatch.setattr("core.tts.engine.KokoroEngine", FakeKokoro)
        e1 = ec.get_kokoro_engine(log_callback=lambda m, l="I": None)
        e2 = ec.get_kokoro_engine(log_callback=None)
        assert e1 is e2
        assert len(created) == 1
        assert ec.cached_engine_count() >= 1

    def test_piper_engine_cache_removed_v0664(self):
        """V0.6.64: get_piper_engine is GONE with the Piper engine."""
        from core.tts import engine_cache as ec

        assert not hasattr(ec, "get_piper_engine")

    def test_vibevoice_keyed_by_model_path(self):
        from core.tts import engine_cache as ec

        e1 = ec.get_vibevoice_engine(model_path="/m1", voices_dir="v", default_voice="c")
        e2 = ec.get_vibevoice_engine(model_path="/m2", voices_dir="v", default_voice="c")
        assert e1 is not e2 and hasattr(e1, "synthesize")

    def test_qwen_keyed_by_model_path(self):
        from core.tts import engine_cache as ec

        e1 = ec.get_qwen_tts_engine(model_path="/q1")
        e2 = ec.get_qwen_tts_engine(model_path="/q2")
        assert e1 is not e2


class TestTTSRouterMatrix:
    """core/tts/engine.py:469 — language/voice → engine routing."""

    def _router(self, **kw):
        from core.tts.engine import TTSRouter

        # V0.6.64: piper_binary/piper_voices_dir/fa_engine kwargs are GONE
        # with the Piper engine — the plain router has no path params.
        return TTSRouter(**kw)

    def test_fa_routes_to_coqui_v0664(self):
        """V0.6.64: Coqui XTTS v2 is the ONLY Persian engine of the legacy
        router (the Piper binary engine + the fa_engine selector were
        removed entirely — user decision, remaining-surface item 4)."""
        import core.tts.engine as engine_mod
        from core.tts.engine import CoquiTTSEngine

        assert not hasattr(engine_mod, "PiperEngine"), "PiperEngine must be gone (V0.6.64)"
        r = self._router()
        assert isinstance(r.persian_engine(), CoquiTTSEngine)

    def test_router_has_no_piper_params_v0664(self):
        """The piper_binary/piper_voices_dir/fa_engine constructor params
        are gone with the engine — the signature must not accept them."""
        import inspect

        from core.tts.engine import TTSRouter

        params = inspect.signature(TTSRouter.__init__).parameters
        for gone in ("piper_binary", "piper_voices_dir", "fa_engine"):
            assert gone not in params, f"TTSRouter still takes {gone} (V0.6.64)"

    def test_en_engine_kokoro(self):
        from core.tts.engine import KokoroEngine

        r = self._router(en_engine="kokoro")
        assert isinstance(r.english_engine(), KokoroEngine)

    def test_en_neutts_unconfigured_falls_back_to_kokoro(self):
        from core.tts.engine import KokoroEngine

        logs: list[str] = []
        r = self._router(en_engine="neutts", log_callback=lambda m, l="I": logs.append(m))
        eng = r.english_engine()
        assert isinstance(eng, KokoroEngine)
        assert any("falling back to Kokoro" in m for m in logs)

    def test_voice_overrides_engine_choice(self, monkeypatch, tmp_path):
        """V4.7.13: a Kokoro preset voice routes to Kokoro even when the
        configured English engine is NeuTTS (V0.6.64: the Piper-voice
        override branch is gone with the engine — fa voices route via
        persian_engine())."""
        from core.tts.engine import KokoroEngine

        r = self._router(en_engine="neutts")
        monkeypatch.setattr(KokoroEngine, "_synthesize", _fake_kokoro_synthesize)
        out = tmp_path / "a.wav"
        assert r.synthesize("hello", out, "en", "af_heart", 1.0) == out
        assert out.exists()


# shared fake _synthesize implementations (monkeypatched onto real classes)
def _fake_kokoro_synthesize(self, text, out_path, voice, speed) -> None:
    self.last_voice = voice
    _write_tiny_wav(Path(out_path), 0.1)


class TestTTSEngineBaseContract:
    """core/tts/engine.py:98 — the fail-soft wrapper every engine shares."""

    def _engine(self, impl):
        from core.tts.engine import TTSEngine

        class _E(TTSEngine):
            def _synthesize(self, text, out_path, voice, speed):
                impl(self, text, out_path, voice, speed)

        return _E()

    def test_empty_text_fails_soft(self, tmp_path):
        e = self._engine(lambda *a: None)
        assert e.synthesize("", tmp_path / "o.wav") is None
        assert e.last_error == "empty text"

    def test_exception_isolated_to_last_error(self, tmp_path):
        def boom(self, *a):
            raise RuntimeError("engine exploded")

        e = self._engine(boom)
        assert e.synthesize("words here", tmp_path / "o.wav") is None
        assert e.last_error == "engine exploded"

    def test_header_only_wav_rejected(self, tmp_path):
        import wave

        def write_header_only(self, _t, out_path, _v, _s):
            with wave.open(str(out_path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)

        e = self._engine(write_header_only)
        assert e.synthesize("words here", tmp_path / "o.wav") is None
        assert e.last_error == "produced empty audio file"


# ═══════════════════════════════════════════════════════════════════════════
# Layer 2 — service-level LIVE + contracts
# ═══════════════════════════════════════════════════════════════════════════


# V0.6.64: _FAKE_PIPER + TestPiperEngineLiveSubprocess (6 tests) were
# REMOVED with the Piper engine — the binary-subprocess path is gone
# (user decision, remaining-surface item 4: "Remove piper entirely").


class TestKokoroEngineLiveWithFakedPipeline:
    """engine.py:143 — the real _synthesize path (numpy concat + soundfile
    write) with torch/kokoro faked in sys.modules (both device branches)."""

    def _fake_torch(self, cuda: bool):
        import types

        mod = types.ModuleType("torch")
        mod.cuda = types.SimpleNamespace(
            is_available=lambda: cuda,
            get_device_name=lambda i: "Fake GPU",
            memory_allocated=lambda i: 0,
        )
        mod.version = types.SimpleNamespace(cuda="12.6" if cuda else None)
        return mod

    def test_cpu_branch_warns_and_uses_cpu(self, monkeypatch, tmp_path):
        import types

        made: list[dict] = []

        class FakeKPipeline:
            def __init__(self, lang_code="a", device="cpu"):
                made.append({"lang_code": lang_code, "device": device})

            def __call__(self, text, voice="af_heart", speed=1.0):
                import numpy as np

                yield "g", "p", np.zeros(240, dtype=np.float32)

        fake_kokoro = types.ModuleType("kokoro")
        fake_kokoro.KPipeline = FakeKPipeline
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(False))
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

        from core.tts.engine import KokoroEngine

        logs: list[tuple[str, str]] = []
        eng = KokoroEngine(log_callback=lambda m, l="I": logs.append((m, l)))
        out = tmp_path / "k.wav"
        assert eng.synthesize("hello there", out, "af_heart", 1.0) == out
        assert made == [{"lang_code": "a", "device": "cpu"}]
        assert any(l == "WARNING" and "CUDA NOT available" in m for m, l in logs)
        import soundfile as sf

        data, sr = sf.read(str(out))
        assert sr == 24000 and len(data) == 240

    def test_cuda_branch_uses_gpu(self, monkeypatch, tmp_path):
        import types

        made: list[dict] = []

        class FakeKPipeline:
            def __init__(self, lang_code="a", device="cpu"):
                made.append({"lang_code": lang_code, "device": device})
                self.model = None  # device-verify skipped path

            def __call__(self, text, voice="af_heart", speed=1.0):
                import numpy as np

                yield "g", "p", np.ones(120, dtype=np.float32)

        fake_kokoro = types.ModuleType("kokoro")
        fake_kokoro.KPipeline = FakeKPipeline
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(True))
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

        from core.tts.engine import KokoroEngine

        logs: list[tuple[str, str]] = []
        eng = KokoroEngine(log_callback=lambda m, l="I": logs.append((m, l)))
        out = tmp_path / "k.wav"
        assert eng.synthesize("hello there", out, None, 2.0) == out
        assert made == [{"lang_code": "a", "device": "cuda"}]
        assert any("GPU" in m and l == "INFO" for m, l in logs)

    def test_missing_torch_fails_soft(self, monkeypatch, tmp_path):
        monkeypatch.setitem(sys.modules, "torch", None)
        from core.tts.engine import KokoroEngine

        eng = KokoroEngine()
        out = tmp_path / "k.wav"
        assert eng.synthesize("hello there", out, "af_heart", 1.0) is None
        assert eng.last_error  # graceful: the error text is surfaced


class TestGpuEngineContracts:
    """qwen/vibevoice/sherpa — GPU/external engines (rig-checklist items).
    Constructor + validation + graceful-unavailable contracts only."""

    def test_qwen_init_resolves_device_without_cuda(self):
        from core.tts.qwen_tts_engine import QwenTtsEngine

        logs: list[tuple[str, str]] = []
        eng = QwenTtsEngine(model_path="/m", log_callback=lambda m, l="I": logs.append((m, l)))
        assert eng._device == "cpu"  # no torch in this sandbox
        assert any(l == "WARNING" and "CUDA requested but not available" in m for m, l in logs)

    def test_qwen_model_path_validation(self, tmp_path):
        from core.tts.qwen_tts_engine import QwenTtsEngine

        with pytest.raises(ValueError, match="model path not set"):
            QwenTtsEngine(model_path="")._ensure_model()
        with pytest.raises(FileNotFoundError, match="model folder not found"):
            QwenTtsEngine(model_path=str(tmp_path / "missing"))._ensure_model()

    def test_qwen_speakers_and_splitting(self):
        from core.tts.qwen_tts_engine import QWEN_TTS_KNOWN_SPEAKERS, QwenTtsEngine

        eng = QwenTtsEngine(model_path="/m")
        assert eng.get_available_speakers() == list(QWEN_TTS_KNOWN_SPEAKERS)
        assert len(QWEN_TTS_KNOWN_SPEAKERS) == 9
        short = "One. Two. Three."
        assert eng._split_text(short) == [short]
        long_text = "Sentence number one is here. " * 20
        parts = eng._split_text(long_text, max_chars=60)
        assert all(len(p) <= 60 or "," not in p for p in parts)
        assert "".join(parts).replace(" ", "").startswith("Sentencenumber")

    def test_qwen_timeout_constants(self):
        from core.tts.qwen_tts_engine import QWEN_CHUNK_TIMEOUT_S, QWEN_LOAD_TIMEOUT_S

        assert QWEN_LOAD_TIMEOUT_S == 120 and QWEN_CHUNK_TIMEOUT_S == 120

    def test_vibevoice_constants_and_english_voices(self):
        from core.tts.vibevoice_engine import (
            VIBEVOICE_ENGLISH_VOICES,
            VIBEVOICE_LINE_TIMEOUT_S,
            VIBEVOICE_LOAD_TIMEOUT_S,
            VIBEVOICE_VOICES,
        )

        assert VIBEVOICE_LOAD_TIMEOUT_S == 300 and VIBEVOICE_LINE_TIMEOUT_S == 600
        assert len(VIBEVOICE_VOICES) == 25
        assert len(VIBEVOICE_ENGLISH_VOICES) == 7
        assert all(v[3] == "English" for v in VIBEVOICE_ENGLISH_VOICES)

    def test_vibevoice_init_and_device(self):
        from core.tts.vibevoice_engine import VibeVoiceEngine

        eng = VibeVoiceEngine(model_path="/m", voices_dir="v", default_voice="en-Emma_woman")
        assert eng.get_device() == "unknown"
        bare = VibeVoiceEngine(model_path="", voices_dir="v")
        with pytest.raises(ValueError, match="model path not set"):
            bare._ensure_model()

    def test_sherpa_catalog_and_unknown_voice(self):
        from core.tts.sherpa_persian_engine import SHERPA_PERSIAN_VOICES, SherpaPersianEngine

        ids = [v[0] for v in SHERPA_PERSIAN_VOICES]
        assert "nima" in ids and len(ids) >= 4
        eng = SherpaPersianEngine(voice_id="bogus")  # no download at init
        with pytest.raises(ValueError, match="Unknown sherpa voice"):
            eng._ensure_model()

    def test_neutts_router_needs_paths(self):
        from core.tts.engine import TTSRouter

        r = TTSRouter(en_engine="neutts")
        with pytest.raises(RuntimeError, match="NeuTTS paths not configured"):
            _ = r.neutts

    def test_neutts_split_long_line(self):
        from core.tts.neutts_engine import _split_long_line

        assert _split_long_line("short text") == ["short text"]
        long = "word " * 120
        parts = _split_long_line(long, max_chars=100)
        assert all(len(p) <= 100 for p in parts) and len(parts) >= 5


@pytest.mark.live_llm
@pytest.mark.skipif(not _shim_available(), reason="zai-llamacpp shim on :3031 not running")
class TestNormalizerLiveShim:
    """The audio-side LLM path, LIVE through the :3031 shim
    (normalizer.py:385 — OpenAI-compatible /chat/completions)."""

    def test_live_en_normalization_round_trip(self):
        from core.tts.normalizer import TextNormalizer

        norm = TextNormalizer(endpoint=_SHIM_URL, api_key="", model=_SHIM_MODEL)
        out = norm.normalize("Dr. Smith reviewed 42 pages in 2024.", "en")
        assert isinstance(out, str) and out.strip()
        assert norm._cache  # the result was cached (idempotent second call)

    def test_live_fa_normalization_round_trip(self):
        from core.tts.normalizer import TextNormalizer

        norm = TextNormalizer(endpoint=_SHIM_URL, api_key="", model=_SHIM_MODEL)
        out = norm.normalize("این متن برای تست است.", "fa")
        assert isinstance(out, str) and out.strip()

    def test_live_failure_falls_back_deterministically(self):
        """A dead endpoint degrades to the deterministic fallback (en
        passthrough) without raising — the graceful-degradation contract."""
        from core.tts.normalizer import TextNormalizer

        norm = TextNormalizer(endpoint="http://localhost:9", api_key="", model="m")
        out = norm.normalize("plain fallback words", "en")
        assert out == "plain fallback words"


# ── Podcast audio assembly (engine faked at the engine_cache seam) ─────────


class _FakeTtsEngine:
    """Writes a REAL wav per call and records every call (voice, text)."""

    def __init__(self, seconds: float = 0.2, fail_on: set[str] | None = None):
        self.calls: list[dict] = []
        self.seconds = seconds
        self.fail_on = fail_on or set()
        self.last_error = None

    def synthesize(self, text, out_path, voice=None, speed=1.0, **kw):
        self.calls.append({"text": text, "voice": voice, "speed": speed, "path": str(out_path)})
        if text in self.fail_on:
            self.last_error = "fake tts failure for this line"
            return None
        _write_tiny_wav(Path(out_path), self.seconds)
        return Path(out_path)


class _FakeSettings:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._v = dict(values or {})

    def get(self, key, default=None):
        return self._v.get(key, default)


def _script(pairs: list[tuple[str, str]]):
    from core.podcast.script_generator import ScriptLine, ScriptResult

    return ScriptResult(
        lines=[
            ScriptLine(host=h, text=t, source_ref=f"src{i}", segment_type="content")
            for i, (h, t) in enumerate(pairs)
        ]
    )


class TestCrossfadeOverlap:
    """audio_generator.py:34 — the transition crossfade math."""

    def test_zero_overlap_concatenates(self):
        import numpy as np

        from core.podcast.audio_generator import _crossfade_overlap

        a, b = np.ones(10), np.full(10, 5.0)
        out = _crossfade_overlap(a, b, 0)
        assert len(out) == 20 and out[0] == 1.0 and out[-1] == 5.0

    def test_overlap_length_and_continuity(self):
        import numpy as np

        from core.podcast.audio_generator import _crossfade_overlap

        a, b = np.ones(100), np.full(100, 5.0)
        out = _crossfade_overlap(a, b, 40)
        assert len(out) == 100 + 100 - 40
        # in the mixed region the weights sum to 1 at every sample
        mixed = out[60:100]
        assert np.allclose(mixed, 1.0 * np.linspace(1, 0, 40) + 5.0 * np.linspace(0, 1, 40))

    def test_overlap_clamped_to_shorter_part(self):
        import numpy as np

        from core.podcast.audio_generator import _crossfade_overlap

        a, b = np.ones(10), np.full(30, 5.0)
        out = _crossfade_overlap(a, b, 1000)
        assert len(out) == 30  # clamped to len(a)=10 → 10+30-10


class TestAudioGeneratorDetectLanguage:
    def test_matches_canonical_detector_including_presentation_forms(self):
        """A1 (V0.6.0): the local copy missed the Arabic presentation-form
        blocks — Persian PDF-extracted text routed to the English branch."""
        from core.podcast.audio_generator import _detect_language
        from core.tts.engine import detect_language

        samples = [
            "این یک متن فارسی است",
            "english words only here",
            "\ufeb3\ufee3\ufedf\ufe8d\ufe8e",  # presentation forms-A
            "abc def ghi jkl این",
        ]
        for s in samples:
            assert _detect_language(s) == detect_language(s), repr(s)
        assert _detect_language("\ufeb3\ufee3\ufedf\ufe8d\ufe8e") == "fa"


class TestGeneratePodcastAudioAssembly:
    """audio_generator.py:169 — segment→voice mapping, cue handling, the
    stitch plan, per-engine dispatch — engine faked at its seam."""

    def _patch_kokoro(self, monkeypatch, engine: _FakeTtsEngine):
        monkeypatch.setattr("core.tts.engine_cache.get_kokoro_engine", lambda **kw: engine)

    def test_voice_mapping_and_real_output(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(seconds=0.2)
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script(
            [("A", "host A opening line"), ("B", "host B reply line"), ("A", "host A again")]
        )
        out = tmp_path / "pod.wav"
        progress: list[tuple[int, str]] = []
        result = generate_podcast_audio(
            script,
            out,
            "voiceA",
            "voiceB",
            _FakeSettings(),
            None,
            progress_callback=lambda pct, msg: progress.append((pct, msg)),
        )
        assert result == out and out.exists()
        # per-host voice mapping (A→voiceA, B→voiceB)
        voices = [c["voice"] for c in engine.calls]
        assert voices == ["voiceA", "voiceB", "voiceA"]
        # per-line texts passed clean to the engine
        assert [c["text"] for c in engine.calls] == [
            "host A opening line",
            "host B reply line",
            "host A again",
        ]
        # the output is a REAL 24 kHz wav
        import soundfile as sf

        data, sr = sf.read(str(out))
        assert sr == 24000 and len(data) > 0
        # progress reaches 100
        assert progress[-1] == (100, "✅ Podcast audio complete")

    def test_vocal_cues_stripped_and_silence_added(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(seconds=0.2)
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        plain = _script([("A", "plain line spoken")])
        cued = _script([("A", "plain line spoken [pause 0.4s]")])
        out1, out2 = tmp_path / "p1.wav", tmp_path / "p2.wav"
        generate_podcast_audio(plain, out1, "vA", "vB", _FakeSettings())
        generate_podcast_audio(cued, out2, "vA", "vB", _FakeSettings())
        import soundfile as sf

        d1, _ = sf.read(str(out1))
        d2, _ = sf.read(str(out2))
        # the [pause 0.4s] cue became 0.4s of appended silence
        assert len(d2) - len(d1) == 24000 * 0.4
        # the engine received the CLEAN text (cue stripped)
        assert engine.calls[-1]["text"] == "plain line spoken"

    def test_cue_only_line_makes_silence_without_tts_call(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(seconds=0.2)
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script([("A", "[pause 0.5s]"), ("B", "real line follows")])
        out = tmp_path / "cue.wav"
        assert generate_podcast_audio(script, out, "vA", "vB", _FakeSettings()) == out
        assert len(engine.calls) == 1  # no TTS call for the cue-only line
        assert engine.calls[0]["voice"] == "vB"
        import soundfile as sf

        data, sr = sf.read(str(out))
        assert sr == 24000
        # 0.5s cue silence + 0.2s speech, minus a 0..0.3s transition overlap
        duration = len(data) / 24000
        assert 0.39 < duration < 0.75, duration

    def test_failed_line_skipped_others_stitched(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(seconds=0.2, fail_on={"the failing line here"})
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script(
            [("A", "good line one"), ("B", "the failing line here"), ("A", "good two")]
        )
        out = tmp_path / "skip.wav"
        assert generate_podcast_audio(script, out, "vA", "vB", _FakeSettings()) == out
        import soundfile as sf

        data, _ = sf.read(str(out))
        # 2 good chunks of 0.2s + transitions — the failed one is absent
        assert 0.3 < len(data) / 24000 < 0.9

    def test_all_lines_fail_returns_none(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(fail_on={"x"})
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script([("A", "x"), ("B", "x")])
        out = tmp_path / "none.wav"
        assert generate_podcast_audio(script, out, "vA", "vB", _FakeSettings()) is None
        assert not out.exists()

    def test_empty_script_returns_none(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine()
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        out = tmp_path / "none.wav"
        assert generate_podcast_audio(_script([]), out, "vA", "vB", _FakeSettings()) is None
        assert engine.calls == []

    def test_vibevoice_without_model_path_fails_no_silent_fallback(self, tmp_path, monkeypatch):
        """V11.56.0: no engine switching — clear error, podcast fails."""
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script([("A", "a vibevoice line")])
        out = tmp_path / "vv.wav"
        logs: list[tuple[str, str]] = []
        assert (
            generate_podcast_audio(
                script,
                out,
                "vibevoice:en-Carter_man",
                "vB",
                _FakeSettings(),
                log_callback=lambda m, l="I": logs.append((m, l)),
            )
            is None
        )
        assert any(l == "ERROR" and "VibeVoice model path not set" in m for m, l in logs)
        assert not out.exists()

    def test_vibevoice_engine_no_output_stops_podcast(self, tmp_path, monkeypatch):
        """V11.57.0: a VibeVoice that produces nothing RAISES — the podcast
        stops at that line instead of skipping/death-spiralling."""
        monkeypatch.setattr(
            "core.tts.engine_cache.get_vibevoice_engine", lambda **kw: _NoOutputEngine()
        )
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script([("A", "first line"), ("B", "second line dies")])
        out = tmp_path / "vv2.wav"
        logs: list[tuple[str, str]] = []
        assert (
            generate_podcast_audio(
                script,
                out,
                "vibevoice:en-Carter_man",
                "vB",
                _FakeSettings({"tts.vibevoice_model_path": "/models/vv"}),
                log_callback=lambda m, l="I": logs.append((m, l)),
            )
            is None
        )
        assert any(l == "ERROR" and "FATAL" in m for m, l in logs)
        assert not out.exists()

    def test_same_host_silence_between_chunks(self, tmp_path, monkeypatch):
        engine = _FakeTtsEngine(seconds=0.2)
        self._patch_kokoro(monkeypatch, engine)
        from core.podcast.audio_generator import generate_podcast_audio

        script = _script([("A", "line one same host"), ("A", "line two same host")])
        out = tmp_path / "same.wav"
        generate_podcast_audio(script, out, "vA", "vB", _FakeSettings())
        import soundfile as sf

        data, _ = sf.read(str(out))
        # 0.2 + 0.15 (SILENCE_MS) + 0.2 = 0.55s — same-host insert, no overlap
        assert abs(len(data) / 24000 - 0.55) < 0.02


class _NoOutputEngine:
    """VibeVoice stand-in that produces nothing (V11.57.0 path)."""

    last_error = "fake vibevoice produced nothing"

    def synthesize(self, text, out_path, voice=None, speed=1.0, **kw):
        return None


class TestPodcastAudioHelpers:
    """core/outputs/podcast_audio.py — the parser + planning helpers."""

    def _gen(self):
        from core.outputs.podcast_audio import PodcastAudioGenerator

        gen = PodcastAudioGenerator.__new__(PodcastAudioGenerator)
        gen.log = lambda msg, level="INFO": None
        return gen

    def test_parse_speaker_line_shapes(self):
        from core.outputs.podcast_audio import _parse_speaker_line

        assert _parse_speaker_line("Host A: hello") == ("A", "hello")
        assert _parse_speaker_line("HostB- hi") == ("B", "hi")
        assert _parse_speaker_line("a: lower case") == ("A", "lower case")
        assert _parse_speaker_line("Speaker 1: one") == ("A", "one")
        assert _parse_speaker_line("Speaker 2: two") == ("B", "two")
        assert _parse_speaker_line("Just a sentence here.") is None

    def test_split_long_line(self):
        from core.outputs.podcast_audio import _split_long_line

        short = "short sentence."
        assert _split_long_line(short) == [short]
        long_text = "This is a long sentence. " * 30  # ~660 chars
        parts = _split_long_line(long_text, max_chars=100)
        assert all(len(p) <= 100 for p in parts) and len(parts) >= 6
        assert _split_long_line("") == []

    def test_strip_stage_directions(self):
        gen = self._gen()
        out = gen._strip_stage_directions(
            "Host A: first line\n[music intro]\nHost B: second [pause] line\nmusic: cue"
        )
        assert "[music intro]" not in out and "music:" not in out
        assert "Host B: second line" in out

    def test_parse_dialogue_skips_headers_and_bold(self):
        gen = self._gen()
        segs = gen._parse_dialogue("# Title\n**Host A:** bold line\n> quote\nHost B: plain")
        assert segs == [("A", "bold line"), ("B", "plain")]

    def test_resolve_host_voices_kokoro_branch(self):
        gen = self._gen()
        a, b = gen._resolve_host_voices("kokoro", "", "", "af_heart")
        assert (a, b) == ("am_michael", "af_heart")
        # same voice on both hosts -> B switched to a distinct one
        a2, b2 = gen._resolve_host_voices("kokoro", "af_heart", "af_heart", "af_heart")
        assert a2 == "af_heart" and b2 != "af_heart"

    def test_resolve_host_voices_neutts_branch(self):
        gen = self._gen()
        a, b = gen._resolve_host_voices("neutts", "", "", "af_heart")
        assert (a, b) == ("dave", "jo")

    def test_resolve_voice_matrix(self):
        gen = self._gen()
        # V0.6.64: fa routes to Coqui — the voice string is the Coqui speaker
        # (fa_voice passed through verbatim; empty = the configured speaker;
        # the English host voices are IGNORED for fa lines)
        assert gen._resolve_voice("A", "fa", "af_heart", "x", "en", "Ana", "kokoro") == "Ana"
        assert gen._resolve_voice("B", "fa", "not-a-voice", "x", "en", "", "kokoro") == ""
        # en + kokoro engine: host voice if kokoro preset else en_voice
        assert gen._resolve_voice("A", "en", "af_heart", "x", "bf_alice", "fa", "kokoro") == (
            "af_heart"
        )
        assert gen._resolve_voice("B", "en", "custom-name", "x", "bf_lily", "fa", "kokoro") == (
            "bf_lily"
        )
        # en + neutts engine: custom (non-catalog) host voice passes through
        assert gen._resolve_voice("A", "en", "custom-name", "x", "en", "fa", "neutts") == (
            "custom-name"
        )
        assert gen._resolve_voice("A", "en", "af_heart", "x", "en", "fa", "neutts") == "dave"

    def test_concat_wavs_real_pydub(self, tmp_path):
        import wave

        gen = self._gen()
        paths = []
        for i, n in enumerate((100, 200)):
            p = tmp_path / f"c{i}.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(8000)
                w.writeframes(b"\x00\x00" * n)
            paths.append(p)
        out = tmp_path / "cat.wav"
        gen._concat_wavs(paths, out)
        with wave.open(str(out), "rb") as w:
            assert w.getnframes() == 300  # 100 + 200, no gaps

    def test_concat_wavs_wave_fallback_when_pydub_unavailable(self, tmp_path, monkeypatch):
        import pydub

        monkeypatch.delattr(pydub, "AudioSegment")  # `from pydub import AudioSegment` fails
        gen = self._gen()
        import wave

        paths = []
        for i, n in enumerate((100, 150)):
            p = tmp_path / f"w{i}.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(8000)
                w.writeframes(b"\x00\x00" * n)
            paths.append(p)
        out = tmp_path / "cat_wave.wav"
        gen._concat_wavs(paths, out)
        with wave.open(str(out), "rb") as w:
            assert w.getnframes() == 250


# ═══════════════════════════════════════════════════════════════════════════
# Layer 3 — dialog-level drive (real SimpleWorker, engine faked at the seam)
# ═══════════════════════════════════════════════════════════════════════════


class _DialogEngine:
    """The fake TTS engine at the dialog's seam (core.tts.engine_cache).

    Doubles as the fake ``KokoroEngine`` class for the preview path (it
    accepts the ``log_callback=`` constructor kwarg the dialog passes).
    """

    def __init__(self, mode: str = "ok", log_callback=None) -> None:
        self.mode = mode
        self.calls: list[dict] = []
        self.last_error = None

    def get_device(self) -> str:
        return "cpu"

    def log(self, msg, level="INFO") -> None:
        return None

    def synthesize(self, text, out_path, voice=None, speed=1.0, style=None, **kw):
        self.calls.append(
            {"text": text, "voice": voice, "speed": speed, "style": style, "path": str(out_path)}
        )
        if self.mode == "fail":
            self.last_error = "fake engine could not synthesize"
            return None
        if self.mode == "cuda_error":
            raise RuntimeError("CUDA error: out of memory during synthesis")
        return _write_tiny_wav(Path(out_path), 0.2)


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTtsServiceDialogCharacterization:
    """Dialog-level pure helpers (no worker)."""

    def _dlg(self):
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import TtsServiceDialog

        return TtsServiceDialog(_StubController())

    def test_populate_voices_per_language(self):
        dlg = self._dlg()
        # default = auto → Kokoro + VibeVoice + Kokoro Farsi sections
        datas = [dlg.voice_combo.itemData(i) for i in range(dlg.voice_combo.count())]
        assert "af_heart" in datas
        assert any(d and str(d).startswith("vibevoice:") for d in datas)
        assert dlg.voice_combo.currentData() == "af_heart"  # first real voice

        idx = dlg.lang_combo.findData("en")
        dlg.lang_combo.setCurrentIndex(idx)
        datas_en = [dlg.voice_combo.itemData(i) for i in range(dlg.voice_combo.count())]
        assert "af_heart" in datas_en
        assert any(str(d).startswith("vibevoice:") for d in datas_en if d)

        idx = dlg.lang_combo.findData("fa")
        dlg.lang_combo.setCurrentIndex(idx)
        datas_fa = [dlg.voice_combo.itemData(i) for i in range(dlg.voice_combo.count())]
        assert [d for d in datas_fa if d != "__separator__"] == ["af_heart", "am_michael"]

    def test_style_profiles_shape(self):
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import TtsServiceDialog

        profiles = TtsServiceDialog._STYLE_PROFILES
        assert set(profiles) == {
            "natural",
            "inspiring",
            "enthusiastic",
            "calm",
            "authoritative",
            "friendly",
            "energetic",
            "dramatic",
        }
        assert profiles["natural"] == (1.0, "")
        assert profiles["dramatic"][0] == 0.80
        assert profiles["energetic"][0] == 1.15

    def test_default_output_name_format(self):
        import re

        dlg = self._dlg()
        dlg.text_input.setPlainText("one two three four five")
        name = dlg._default_output_name()
        assert re.fullmatch(r"Kokoro\[af_heart\]\[\d{8}-\d{6}\]\[5\]\.wav", name), name

    def test_collect_options_separator_falls_back_to_real_voice(self):
        dlg = self._dlg()
        # select the first separator item explicitly
        for i in range(dlg.voice_combo.count()):
            if dlg.voice_combo.itemData(i) == "__separator__":
                dlg.voice_combo.setCurrentIndex(i)
                break
        opts = dlg._collect_options()
        assert opts["voice"] not in ("", "__separator__")
        assert opts["language"] == "auto"
        assert opts["format"] == ".wav"
        assert opts["style"] == "natural"

    def test_is_cpu_tts_error_heuristic(self):
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import _is_cpu_tts_error

        assert _is_cpu_tts_error("CUDA error: out of memory")
        assert _is_cpu_tts_error("torch.cuda.is_available() returned False")
        assert _is_cpu_tts_error("device not usable")
        assert not _is_cpu_tts_error("file not found somewhere")
        assert not _is_cpu_tts_error("")


@pytest.mark.skipif(not _qt_available(), reason="PySide6/offscreen unavailable")
class TestTtsServiceDialogWorkerDrive:
    """The real SimpleWorker QThread: _on_process → _process → _on_finished
    with the engine faked at the core.tts.engine_cache seam (the boundary the
    dialog actually calls), modals stubbed on BOTH modules."""

    def _patch_modals(self, monkeypatch):
        import ui_qt.views.service_dialogs.dialogs.shared as shared_mod
        import ui_qt.views.service_dialogs.dialogs.tts_service_dialog as tts_mod

        recorded: list[tuple] = []
        monkeypatch.setattr(tts_mod, "_show_success_modal", lambda *a, **k: recorded.append((a, k)))
        monkeypatch.setattr(
            shared_mod, "_show_success_modal", lambda *a, **k: recorded.append((a, k))
        )
        box = _MsgBoxRecorder()
        monkeypatch.setattr(tts_mod, "QMessageBox", box)
        # shared.py's _on_process guards ("No input"/"No output") call
        # shared's OWN QMessageBox — patch that too or the real modal blocks
        monkeypatch.setattr(shared_mod, "QMessageBox", box)
        return recorded, box

    def _make(self, monkeypatch, engine, settings):
        monkeypatch.setattr(
            "ui_qt.views.service_dialogs.dialogs.tts_service_dialog._tts_cuda_available",
            lambda: True,
        )
        monkeypatch.setattr(
            "ui_qt.views.service_dialogs.dialogs.tts_service_dialog._tts_torch_cuda_tag",
            lambda: "12.6",
        )
        monkeypatch.setattr("core.tts.engine_cache.get_kokoro_engine", lambda **kw: engine)
        from utils.settings import Settings

        Settings._test_override = settings  # type: ignore[assignment]
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import TtsServiceDialog

        return TtsServiceDialog(_StubController())

    def teardown_method(self):
        from utils.settings import Settings

        Settings._test_override = None  # type: ignore[assignment]

    def test_full_wav_flow_lands_success(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, _box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("hello synthesized world")
        out = tmp_path / "driven.wav"
        dlg.out_path_edit.setText(str(out))
        dlg._on_process()

        status = _spin_until_status(app, dlg)
        _flush(app)

        assert status.startswith("✅"), status
        assert out.exists() and out.stat().st_size > 44
        # the engine got the ORIGINAL text (V11.42.1: no style prefix prepended)
        assert engine.calls[0]["text"] == "hello synthesized world"
        assert engine.calls[0]["voice"] == "af_heart"
        # the proof file records the engine used
        proof = out.with_suffix(".proof.txt")
        assert proof.exists()
        content = proof.read_text(encoding="utf-8")
        assert "ENGINE USED: Kokoro" in content
        # the deferred success modal fired exactly once with the real path
        assert len(recorded) == 1
        assert recorded[0][0][1] == "🎙️ TTS Complete"
        assert recorded[0][1]["file_path"] == str(out)
        assert not dlg.process_btn.isHidden()

    def test_style_speed_passed_engine_text_unmodified(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, _box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("dramatic reading of the line")
        dlg.style_combo.setCurrentIndex(7)  # Slow / dramatic
        dlg.out_path_edit.setText(str(tmp_path / "styled.wav"))
        dlg._on_process()

        _spin_until_status(app, dlg)
        _flush(app)

        assert engine.calls[0]["speed"] == 0.80  # dramatic profile multiplier
        assert engine.calls[0]["style"] == "dramatic"
        assert engine.calls[0]["text"] == "dramatic reading of the line"
        assert recorded

    def test_real_mp3_conversion_via_pydub(self, tmp_path, monkeypatch):
        """The .mp3 format branch converts the real WAV through pydub+ffmpeg
        (both live in this sandbox)."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, _box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("make an mp3 out of this line")
        dlg.fmt_combo.setCurrentIndex(1)  # MP3
        out = tmp_path / "driven.mp3"
        dlg.out_path_edit.setText(str(out))
        dlg._on_process()

        status = _spin_until_status(app, dlg)
        _flush(app)

        assert status.startswith("✅"), status
        assert out.exists() and out.stat().st_size > 200
        with open(out, "rb") as fh:
            head = fh.read(3)
        # an MPEG frame sync (0xFFEx) or an ID3 tag — definitely audio, not WAV
        assert head[:3] != b"RIF"
        assert not (tmp_path / "driven.wav").exists()

    def test_engine_failure_lands_error_no_modal(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, box = self._patch_modals(monkeypatch)
        engine = _DialogEngine(mode="fail")
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("this synthesis will fail")
        out = tmp_path / "fail.wav"
        dlg.out_path_edit.setText(str(out))
        dlg._on_process()

        status = _spin_until_status(app, dlg)
        _flush(app)

        assert status.startswith("❌"), status
        assert "fake engine could not synthesize" in status
        assert not out.exists() and not out.with_suffix(".proof.txt").exists()
        assert not recorded and not box.calls  # no success modal, no critical

    def test_cuda_error_mid_generation_shows_critical_modal(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, box = self._patch_modals(monkeypatch)
        engine = _DialogEngine(mode="cuda_error")
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("this will raise a cuda error")
        dlg.out_path_edit.setText(str(tmp_path / "cuda.wav"))
        dlg._on_process()

        status = _spin_until_status(app, dlg)
        _flush(app)

        assert status.startswith("🚫"), status
        assert "GPU/CUDA error" in status
        assert box.titles() == ["🚫 TTS Failed — GPU/CUDA Error"]
        assert not recorded  # no success modal on failure

    def test_vibevoice_without_path_falls_back_to_kokoro_cleanly(self, tmp_path, monkeypatch):
        """T1 (V0.6.0): the VibeVoice→Kokoro fallback used to pass the
        ``vibevoice:…`` string straight to Kokoro — the fallback engine then
        failed on the unknown voice. Now the prefix is dropped."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        recorded, _box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride({"tts.vibevoice_model_path": ""}))
        dlg.text_input.setPlainText("fallback engine line")
        # pick a VibeVoice voice from the combo
        for i in range(dlg.voice_combo.count()):
            data = dlg.voice_combo.itemData(i)
            if data and str(data).startswith("vibevoice:"):
                dlg.voice_combo.setCurrentIndex(i)
                break
        assert str(dlg.voice_combo.currentData()).startswith("vibevoice:")
        dlg.out_path_edit.setText(str(tmp_path / "fallback.wav"))
        dlg._on_process()

        status = _spin_until_status(app, dlg)
        _flush(app)

        assert status.startswith("✅"), status
        assert (tmp_path / "fallback.wav").exists()
        # the Kokoro fallback must NOT receive the vibevoice-prefixed string
        voice_arg = engine.calls[0]["voice"]
        assert voice_arg is None or not str(voice_arg).startswith("vibevoice:"), voice_arg

    def test_empty_text_guard_no_worker(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        _recorded, box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.out_path_edit.setText(str(tmp_path / "x.wav"))
        dlg._on_process()
        assert box.titles() == ["No input"]
        assert dlg._worker is None and engine.calls == []

    def test_missing_output_guard_no_worker(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
        _recorded, box = self._patch_modals(monkeypatch)
        engine = _DialogEngine()
        dlg = self._make(monkeypatch, engine, _SettingsOverride())
        dlg.text_input.setPlainText("some text here")
        dlg._on_process()
        assert box.titles() == ["No output"]
        assert dlg._worker is None and engine.calls == []

    def test_preview_worker_drive(self, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        _recorded, box = self._patch_modals(monkeypatch)
        self._make(monkeypatch, _DialogEngine(), _SettingsOverride())
        # the preview path instantiates KokoroEngine directly from
        # core.tts.engine — fake it at that seam (records its calls)
        preview_engine_cls = _DialogEngine
        monkeypatch.setattr("core.tts.engine.KokoroEngine", preview_engine_cls)
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import TtsServiceDialog

        dlg = TtsServiceDialog(_StubController())
        dlg.text_input.setPlainText("preview these words please")
        # stub the playback layer (headless)
        try:
            import PySide6.QtMultimedia as qtm

            class _FakePlayer:
                def __init__(self):
                    self.sources = []

                def setAudioOutput(self, *a):
                    pass

                def setSource(self, s):
                    self.sources.append(s)

                def play(self):
                    pass

            monkeypatch.setattr(qtm, "QMediaPlayer", _FakePlayer)
            monkeypatch.setattr(qtm, "QAudioOutput", lambda *a: object())
        except Exception:
            pass

        dlg._on_preview()
        deadline = 0
        while deadline < 15000:
            app.processEvents()
            if dlg.status_label.text().startswith("✅"):
                break
            time.sleep(0.02)
            deadline += 20
        _flush(app)
        assert dlg.status_label.text().startswith("✅ Preview"), dlg.status_label.text()
        assert dlg.preview_btn.isEnabled()
        assert not box.calls


class TestTtsServiceDialogProcessEngineMatrix:
    """The engine-selection matrix inside _process (voice prefix > language),
    driven directly (widget-free callable) with the engines faked."""

    def _patch(self, monkeypatch, engine, settings):
        monkeypatch.setattr("core.tts.engine_cache.get_kokoro_engine", lambda **kw: engine)
        from utils.settings import Settings

        Settings._test_override = settings  # type: ignore[assignment]

    def teardown_method(self):
        from utils.settings import Settings

        Settings._test_override = None  # type: ignore[assignment]

    def _dlg(self):
        from ui_qt.views.service_dialogs.dialogs.tts_service_dialog import TtsServiceDialog

        return TtsServiceDialog(_StubController())

    def test_vibevoice_with_model_path_uses_vibevoice_engine(self, monkeypatch):
        vv_engine = _DialogEngine()
        monkeypatch.setattr("core.tts.engine_cache.get_vibevoice_engine", lambda **kw: vv_engine)
        self._patch(
            monkeypatch,
            _DialogEngine(),
            _SettingsOverride(
                {
                    "tts.vibevoice_model_path": "/models/vibevoice",
                    "tts.vibevoice_voices_dir": "/voices",
                }
            ),
        )
        dlg = self._dlg()
        result = dlg._process(
            "vibevoice engine text", {"voice": "vibevoice:en-Emma_woman", "language": "auto"}
        )
        assert isinstance(result, str) and not result.startswith("Error")
        assert vv_engine.calls[0]["voice"] == "en-Emma_woman"
        assert vv_engine.calls[0]["path"].endswith(".wav")
        assert dlg._last_engine_name == "VibeVoice"

    def test_fa_detected_routes_kokoro_with_fa_default_voice(self, monkeypatch):
        engine = _DialogEngine()
        self._patch(monkeypatch, engine, _SettingsOverride())
        dlg = self._dlg()
        result = dlg._process("این متن فارسی است", {"voice": "", "language": "auto"})
        assert not str(result).startswith("Error")
        assert engine.calls[0]["voice"] == "af_heart"  # fa default
        assert dlg._last_engine_name == "Kokoro"

    def test_explicit_lang_en_overrides_detection(self, monkeypatch):
        engine = _DialogEngine()
        self._patch(monkeypatch, engine, _SettingsOverride())
        dlg = self._dlg()
        result = dlg._process("این متن فارسی است", {"voice": "", "language": "en"})
        assert not str(result).startswith("Error")
        assert dlg._last_engine_name == "Kokoro"

    def test_engine_returning_none_surfaces_last_error(self, monkeypatch):
        engine = _DialogEngine(mode="fail")
        self._patch(monkeypatch, engine, _SettingsOverride())
        dlg = self._dlg()
        result = dlg._process("text that fails", {"voice": "", "language": "en"})
        assert result == "Error: TTS engine failed: fake engine could not synthesize"

    def test_engine_exception_becomes_error_string(self, monkeypatch):
        engine = _DialogEngine(mode="cuda_error")
        self._patch(monkeypatch, engine, _SettingsOverride())
        dlg = self._dlg()
        result = dlg._process("boom", {"voice": "", "language": "en"})
        assert result.startswith("Error: CUDA error")
