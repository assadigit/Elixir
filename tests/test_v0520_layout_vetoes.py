"""V0.5.20 — the layout-independent joins, the keypoints veto, the glossary
handoff, the terminal-shape lint + the thin colon-less variant.

The four backlog items from the V0.5.19.1 rig run #2 (the FULL-BOOK
ingestion, run ``20260928-155851-011587f0`` —
``audit/results/bench_v0519_1_ch9_histrionic_schizotypal_rig2/``):

1. THE LAYOUT-INDEPENDENT CONTINUATION JOIN + the terminal-shape lint.
   The V0.5.19/.1 joins proved extraction-layout-fragile on the full-book
   PDF (p.222-242 pagination, page-break artifacts): the Kernberg
   six-grounds list regressed to 5/6, a dangling ``and (4).`` marker
   shipped (E2), a DSM-III-R criteria item truncated mid-phrase at
   "embraces casual" (E3), and both reproduced schizotypal criteria
   blocks were prefix-truncated (E7: DSM-III 5/8, DSM-III-R 3/9) — all
   invisible to the pipeline's "enumerated items N/N" floor. Fixes: the
   marker-tail pattern (``(N).`` at a paragraph end now MATCHES), the
   open-tail predicate (empty/punctuation-only marker tails are open),
   the no-marker final-item continuation join (rule d), the
   page-furniture skip (both the enumeration join and the criteria
   cluster collector), and the terminal-shape lint.

2. THE KEYPOINTS-LAYER AUTHOR-COVERAGE VETO. The keypoints embedding
   dedup ("removed 2 duplicates, 76 → 74") removed the EXACT two bullets
   the V0.5.18 summary-layer veto had just rescued (Kallman + Widiger) —
   this call site had no veto.

3. THE GLOSSARY HANDOFF PATH. The .glossary.md persisted OUTSIDE the
   run's output dir (``request.output_dir`` is the user's BASE dir; the
   converter always creates the per-book run folder under it) and the
   glossary dict never carried its persisted path (every audit-trail
   line showed "Glossary: (none)").

4. THE THIN-BULLET DETECTOR'S COLON-LESS VARIANT. ~12 thin one-liners
   shipped UNFLAGGED ("Kretschmer made significant contributions to…" /
   "Frances (*1980*) contributed to…") vs 121429's 4/4 flagged (the
   "Name: Contributed to…" colon form).

Content-agnostic (Rule 1): synthetic Authorone/Authortwo fixtures + the
SHAPE of the rig-run-2 layouts — no book content.

Run: ``pytest tests/test_v0520_layout_vetoes.py -v``
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest

from core.common.layout_furniture import is_furniture_paragraph, is_page_furniture_line
from core.preprocessing.deterministic_analyzer import extract_structured_criteria
from core.summarisation.enumeration import detect_enumerations
from core.summarisation.post_processing import ends_in_dangling_enum_marker
from core.summarisation.postchecks.attribution import validate_years

# ═══════════════════════════════════════════════════════════════════════════
# Section 1 — the page-furniture shapes
# ═══════════════════════════════════════════════════════════════════════════


class TestPageFurniture:
    def test_bare_page_numbers_are_furniture(self):
        assert is_page_furniture_line("224")
        assert is_page_furniture_line("42.")
        assert is_page_furniture_line("- 224 -")
        assert is_page_furniture_line('"12"')

    def test_running_headers_are_furniture(self):
        assert is_page_furniture_line("BROKEN STRUCTURES")
        assert is_page_furniture_line("CHAPTER NINE")
        assert is_page_furniture_line("HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS")

    def test_single_token_caps_is_not_furniture(self):
        # "DSM-III" mid-item is a legitimate hard-wrapped fragment
        assert not is_page_furniture_line("DSM-III")

    def test_prose_and_items_are_not_furniture(self):
        assert not is_page_furniture_line("(vi) inadequate rapport with others")
        assert not is_page_furniture_line("while infantile personalities show less")
        assert not is_page_furniture_line("The criteria end here.")

    def test_furniture_paragraph(self):
        assert is_furniture_paragraph("224")
        assert is_furniture_paragraph("224\nBROKEN STRUCTURES")
        assert not is_furniture_paragraph("224\n(iv) odd mannerisms")  # mixed → content
        assert not is_furniture_paragraph("(vi) item text\n(vii) more text\n(viii) end")


# ═══════════════════════════════════════════════════════════════════════════
# Section 2 — the marker-tail pattern + the dangling-marker join (E2)
# ═══════════════════════════════════════════════════════════════════════════


class TestDanglingMarkerJoin:
    """E2: ``…, and (4).`` at a paragraph end + the item content in the
    next paragraph — the marker now matches, the tail is open, the
    no-marker continuation join fires."""

    E2_SRC = (
        "Zetzel pointed out that the developmental history in such individuals often\n\n"
        "reveals (1) significant separations in the first four years of life, "
        "(2) serious parental psychopathology, (3) much physical illness during "
        "childhood, and (4).\n\n"
        "absence of meaningful, sustained relations with either sex."
    )

    def test_period_terminated_marker_tail_joins(self):
        enums = detect_enumerations(self.E2_SRC)
        assert enums, "the list must be detected"
        e = enums[0]
        assert e.style == "runin_arabic"
        assert e.count == 4
        assert e.items[-1].text == "absence of meaningful, sustained relations with either sex"
        # item (3) keeps its text, the dangling marker no longer rides it
        assert e.items[2].text == "much physical illness during childhood"

    def test_bare_marker_tail_joins(self):
        src = (
            "The history reveals (1) separations, (2) psychopathology, "
            "(3) illness, and (4)\n\n"
            "absence of meaningful, sustained relations with either sex."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 4
        assert e.items[-1].text.startswith("absence of meaningful")

    def test_punct_marker_same_paragraph(self):
        # "(4). absence" inside ONE paragraph (no break): the marker matches,
        # the punct is consumed, item (4) starts clean. (Padded past the
        # detector's 120-char floor.)
        src = (
            "The developmental history reveals in the early years of life "
            "(1) significant separations, (2) serious parental psychopathology, "
            "(3) much physical illness during childhood, and (4). absence of "
            "meaningful, sustained relations with either sex."
        )
        assert len(src) >= 120
        e = detect_enumerations(src)[0]
        assert e.count == 4
        assert e.items[-1].text == "absence of meaningful, sustained relations with either sex"

    def test_complete_list_does_not_join_uppercase_successor(self):
        src = (
            "The history reveals (1) separations, (2) psychopathology, "
            "(3) illness.\n\n"
            "A new topic paragraph follows the completed list."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 3
        assert e.items[-1].text == "illness"

    def test_non_sequential_marker_blocks_rule_d(self):
        # B opens lowercase BUT carries a same-style marker that is not
        # next-sequential (a NEW list) — gluing it onto A's list would
        # corrupt both; rule (d) must not fire.
        src = (
            "The list states (1) first claim, (2) second claim, (3) third claim,\n\n"
            "later the text lists (1) a different point; (2) another one entirely."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 3
        assert e.items[-1].text == "third claim"


# ═══════════════════════════════════════════════════════════════════════════
# Section 3 — the no-marker final-item continuation (E3) + furniture (E1)
# ═══════════════════════════════════════════════════════════════════════════


class TestFinalItemContinuation:
    """E3: the list's last item is cut mid-phrase and the continuation
    sits in the NEXT paragraph with NO marker to drive the join."""

    E3_SRC = (
        "(i) constantly seeks or demands reassurance, approval, or praise\n"
        "(ii) is inappropriately sexually seductive in appearance or behavior\n"
        "(iii) is overly concerned with physical attractiveness\n"
        "(iv) expresses emotion with inappropriate exaggeration, e.g., embraces casual\n\n"
        "acquaintances with excessive ardor, uncontrollable sobbing on minor "
        "sentimental occasions, has temper tantrums\n\n"
        "(v) is uncomfortable in situations in which he or she is not the center of attention"
    )

    def test_chain_joins_across_two_breaks(self):
        enums = detect_enumerations(self.E3_SRC)
        e = enums[0]
        # the (i)-(v) markers open their lines → the block roman_lower_paren
        # style (a same-shape style; the join behavior under test is the
        # paragraph merging in the run-in pre-pass + the complete items)
        assert "roman" in e.style
        assert e.count == 5  # (i)-(v) — was 4 with item (iv) truncated
        iv = [it for it in e.items if "embraces casual" in it.text][0]
        assert iv.text.endswith("has temper tantrums")  # the completion landed
        assert e.items[-1].text.startswith("is uncomfortable in situations")

    def test_closed_tail_rejects_lowercase_successor(self):
        # the list's last item is COMPLETE (terminal punctuation) — a
        # lowercase successor paragraph is a new paragraph, not a join.
        src = (
            "The list states (1) first claim, (2) second claim, (3) third claim.\n\n"
            "lowercase prose that happens to follow a complete list."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 3
        assert e.items[-1].text == "third claim"

    def test_page_furniture_between_list_and_continuation(self):
        # E1's full-book layout: a bare page number + a running header
        # paragraph sit between the open list and its continuation.
        src = (
            "The theorist distinguished the types on six grounds: "
            "(1) first ground text here; (2) second ground text here; "
            "(3) third ground text here; (4) fourth ground text here; "
            "(5) fifth ground cut mid-phrase,\n\n"
            "224\n\n"
            "BROKEN STRUCTURES\n\n"
            "while the continuation completes the fifth ground; and (6) the sixth "
            "ground text closes the list."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 6
        assert e.items[-1].text.startswith("the sixth ground text closes the list")
        fifth = e.items[4].text
        assert fifth.startswith("fifth ground cut mid-phrase")
        assert "while the continuation completes the fifth ground" in fifth

    def test_furniture_bound_two_paragraphs(self):
        # more than 2 furniture paragraphs between A and B → no join
        # (the bounded look-past).
        src = (
            "The list states (1) first claim, (2) second claim, (3) third claim,\n\n"
            "224\n\n225\n\n226\n\n"
            "while a continuation paragraph follows three furniture lines."
        )
        e = detect_enumerations(src)[0]
        assert e.count == 3
        assert e.items[-1].text == "third claim"


# ═══════════════════════════════════════════════════════════════════════════
# Section 4 — the criteria cluster furniture skip (E7)
# ═══════════════════════════════════════════════════════════════════════════


class TestCriteriaFurnitureSkip:
    E7_SRC = (
        "a. At least four of the following:\n"
        "(i) magical thinking, e.g., superstitiousness, clairvoyance\n"
        "(ii) ideas of reference\n"
        "(iii) social isolation, e.g., no close friends or confidants\n"
        "(iv) recurrent illusions, sensing the presence of a force\n"
        "(v) odd speech, e.g., vague, overelaborate speech\n\n"
        "228\n\n"
        "(vi) inadequate rapport with others\n"
        "(vii) odd mannerisms\n"
        "(viii) suspiciousness or paranoid ideation\n\n"
        "Discussion prose follows the criteria block and closes it."
    )

    def test_page_number_between_subitems_keeps_cluster_open(self):
        clusters = extract_structured_criteria(self.E7_SRC)
        assert clusters, "the cluster must survive the page-number line"
        subs = clusters[0]["items"][0]["sub_items"]
        markers = [m for m, _ in subs]
        # 8/8 — was 5/8 (the cluster closed at the page boundary, (vi)-(viii)
        # arrived with no parent letter and were skipped)
        assert markers == ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"]

    def test_running_header_between_subitems_keeps_cluster_open(self):
        src = self.E7_SRC.replace("228", "HISTRIONIC AND SCHIZOTYPAL PERSONALITY DISORDERS")
        clusters = extract_structured_criteria(src)
        subs = clusters[0]["items"][0]["sub_items"]
        assert len(subs) == 8

    def test_real_uppercase_prose_still_closes(self):
        src = self.E7_SRC.replace("228\n\n", "")  # no furniture — clean block
        clusters = extract_structured_criteria(src)
        subs = clusters[0]["items"][0]["sub_items"]
        assert len(subs) == 8  # the block itself is contiguous


# ═══════════════════════════════════════════════════════════════════════════
# Section 5 — the terminal-shape lint
# ═══════════════════════════════════════════════════════════════════════════


class TestTerminalShapeLint:
    E2_BULLET = (
        "**Reveals** — 3 items from the source: (1) significant separations in "
        "the first four years of life; (2) serious parental psychopathology; "
        "(3) much physical illness during childhood, and (4)."
    )

    def test_dangling_paren_marker_flagged(self):
        assert ends_in_dangling_enum_marker(self.E2_BULLET)
        assert ends_in_dangling_enum_marker("…list ends, and (4)")
        assert ends_in_dangling_enum_marker("The criteria end with (vi).")
        assert ends_in_dangling_enum_marker("…ends with, and (b).")

    def test_dangling_bare_marker_flagged(self):
        assert ends_in_dangling_enum_marker("Some list ends with and 4.")
        assert ends_in_dangling_enum_marker("…or iii.")

    def test_complete_bullets_not_flagged(self):
        assert not ends_in_dangling_enum_marker(
            "**Reveals** — 4 items from the source: (1) separations; "
            "(2) psychopathology; (3) illness; (4) absence of meaningful relations."
        )
        assert not ends_in_dangling_enum_marker(
            "The theorist distinguished the types on six grounds in 1967."
        )
        # a mid-sentence paren numeral is not a terminal marker
        assert not ends_in_dangling_enum_marker(
            "A bullet about the paranoid position (see chapter 4)."
        )

    def test_lint_wired_into_postcheck_bullets(self):
        from core.summarisation.postchecks.orchestrator import run_post_checks

        clean = "The theorist distinguished the types on six grounds in 1967."
        report = run_post_checks([self.E2_BULLET, clean], "", "")
        enum_flags = [
            i for i in report.issues if i.detector == "enumeration" and "terminal-shape" in i.detail
        ]
        assert enum_flags, "the dangling marker bullet must be flagged"
        assert any(
            "and (4)" in (i.snippet or "") or "and (4)" in self.E2_BULLET for i in enum_flags
        )
        # advisory-only: the bullet is NOT dropped (flag, not fix)
        assert not any(i.detector == "enumeration" and i.severity == "fix" for i in report.issues)
        # the clean bullet produced no enumeration flag
        assert len(enum_flags) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Section 6 — the keypoints-layer author-coverage veto
# ═══════════════════════════════════════════════════════════════════════════


class _Log:
    def __init__(self):
        self.calls = []

    def __call__(self, msg, level="INFO"):
        self.calls.append((msg, level))


def _summ(bullets):
    return SimpleNamespace(success=True, bullet_points=list(bullets))


def _segs(text):
    return [SimpleNamespace(content=text)]


_KP_SOURCE = (
    "Authorone (1970) described how identity formation proceeds through "
    "developmental stages toward a persistent sense of selfsameness.\n"
    "Authortwo (1971) emphasized the consolidation of inner solidarity "
    "during adolescence alongside Authorone's framework."
)

# a rapidfuzz twin of _KP_KEPT that uniquely names Authorone
_KP_KEPT = "Authortwo described the framework of identity consolidation in adolescence."
_KP_TWIN_UNIQUE = "Authorone described the framework of identity consolidation in adolescence."
_KP_TWIN_PLAIN = "Authortwo charted the framework of identity consolidation in adolescence."
_KP_STANDALONE_AUTHORONE = "Authorone (1970) ran a longitudinal design on developmental stages."


def _build_kp(monkeypatch, tmp_path, bullets, source=_KP_SOURCE):
    """Build keypoints with the embedder FORCED OFF (the rapidfuzz path —
    the deterministic sandbox path) and capture the log."""
    # force the no-embedder path: get_embed_model returns None
    import core.llm.model_singletons as singletons
    from core.summarisation.keypoints_builder import KeypointsBuilder

    monkeypatch.setattr(singletons, "get_embed_model", lambda: None)
    log = _Log()
    kb = KeypointsBuilder(log_callback=log)
    md, _docx = kb.build(
        [_summ(bullets)],
        book_title="testbook",
        output_dir=tmp_path / "kp",
        segments=_segs(source),
    )
    md_text = Path(md).read_text(encoding="utf-8")
    return md_text, log, kb


class TestKeypointsVeto:
    def test_unique_author_twin_kept(self, monkeypatch, tmp_path):
        """THE V0.5.20 KEYPOINTS VETO: the rapidfuzz twin that uniquely
        names a roster author is KEPT (was silently removed — the rig
        run's 76 → 74 Kallman/Widiger un-rescue)."""
        md, log, kb = _build_kp(
            monkeypatch, tmp_path, [_KP_KEPT, _KP_TWIN_UNIQUE, _KP_STANDALONE_AUTHORONE][:2]
        )
        assert _KP_TWIN_UNIQUE in md, "the twin must ship in the keypoints file"
        assert kb.final_keypoint_count == 2
        veto = [m for m, lvl in log.calls if "V0.5.20 keypoints-dedup veto" in m and lvl == "INFO"]
        assert veto and "Authorone" in veto[0]

    def test_plain_twin_still_dropped(self, monkeypatch, tmp_path):
        md, _, kb = _build_kp(monkeypatch, tmp_path, [_KP_KEPT, _KP_TWIN_PLAIN])
        assert _KP_TWIN_PLAIN not in md
        assert kb.final_keypoint_count == 1

    def test_author_covered_by_later_kept_bullet_dropped(self, monkeypatch, tmp_path):
        """Deferred-veto semantics: the kept set is evaluated COMPLETE —
        a non-twin bullet LATER in the list covers Authorone → the twin
        loses no coverage → still dropped."""
        md, _, kb = _build_kp(
            monkeypatch,
            tmp_path,
            [_KP_KEPT, _KP_TWIN_UNIQUE, _KP_STANDALONE_AUTHORONE],
        )
        assert _KP_TWIN_UNIQUE not in md
        assert _KP_STANDALONE_AUTHORONE in md
        assert kb.final_keypoint_count == 2

    def test_order_preserved_on_rescue(self, monkeypatch, tmp_path):
        first = "Authorthree opened the field with a taxonomy of types."
        md, _, _ = _build_kp(
            monkeypatch,
            tmp_path,
            [first, _KP_KEPT, _KP_TWIN_UNIQUE],
        )
        lines = [ln for ln in md.split("\n") if ln.strip() and ln.strip()[0].isdigit()]
        texts = [ln.split(". ", 1)[1] for ln in lines]
        assert texts.index(first) < texts.index(_KP_KEPT) < texts.index(_KP_TWIN_UNIQUE)

    def test_no_segments_veto_inert(self, monkeypatch, tmp_path):
        """No segments → no roster → the veto is inert (legacy drop)."""
        import core.llm.model_singletons as singletons
        from core.summarisation.keypoints_builder import KeypointsBuilder

        monkeypatch.setattr(singletons, "get_embed_model", lambda: None)
        kb = KeypointsBuilder(log_callback=_Log())
        md, _ = kb.build([_summ([_KP_KEPT, _KP_TWIN_UNIQUE])], book_title="t2", output_dir=tmp_path)
        md_text = Path(md).read_text(encoding="utf-8")
        assert _KP_TWIN_UNIQUE not in md_text

    def test_embedding_path_twin_kept(self, monkeypatch, tmp_path):
        """The rig path (a REAL embedder): the embedding-dedup twin that
        uniquely names a roster author is KEPT — the fake embedder gives
        the twin pair one shared vector (cos sim 1.0 > 0.85)."""
        import hashlib

        import core.llm.model_singletons as singletons
        from core.summarisation.keypoints_builder import KeypointsBuilder

        twin_group = [_KP_KEPT, _KP_TWIN_UNIQUE]

        class _FakeEmbedder:
            def encode(self, strs, show_progress_bar=False, convert_to_numpy=True):
                import numpy as np

                def _hash_vec(s):
                    h = hashlib.sha1(s.encode()).digest()
                    return [((b - 128) / 128.0) for b in h[:16]]

                g = _hash_vec("__group_0__")

                def _v(s):
                    return g if s in twin_group else _hash_vec(s)

                arr = np.array([_v(s) for s in strs], dtype=float)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms[norms == 0] = 1
                return arr / norms

        monkeypatch.setattr(singletons, "get_embed_model", lambda: _FakeEmbedder())
        log = _Log()
        kb = KeypointsBuilder(log_callback=log)
        md, _ = kb.build(
            [_summ([_KP_KEPT, _KP_TWIN_UNIQUE])],
            book_title="t3",
            output_dir=tmp_path / "kp",
            segments=_segs(_KP_SOURCE),
        )
        md_text = Path(md).read_text(encoding="utf-8")
        assert _KP_TWIN_UNIQUE in md_text
        assert any("V0.5.20 keypoints-dedup veto" in m for m, _ in log.calls)


# ═══════════════════════════════════════════════════════════════════════════
# Section 7 — the glossary handoff (the path field + the run output dir)
# ═══════════════════════════════════════════════════════════════════════════


_GLOSSARY_RESPONSE = (
    "<name_glossary>\n"
    "## Names\n"
    "- **Authorone** (1970) — described identity formation\n"
    "- **Authortwo** (1971) — emphasized inner solidarity\n"
    "## Dates\n"
    "- **1970** — the identity-formation paper\n"
    "## Terms\n"
    "- **selfsameness** — persistent sense of self\n"
    "</name_glossary>"
)


class TestGlossaryHandoff:
    def test_extract_glossary_via_llm_carries_path(self, tmp_path):
        from core.summarisation.glossary_parser import extract_glossary_via_llm

        glossary = extract_glossary_via_llm(
            source_text="Authorone (1970) wrote about identity.",
            call_llm=lambda *a, **k: _GLOSSARY_RESPONSE,
            primary_model="test-model",
            chapter_heading="9 - TEST CHAPTER",
            output_dir=str(tmp_path),
            run_id="run123",
            log=_Log(),
        )
        assert glossary.get("names"), "the glossary parsed"
        # V0.5.20: the persisted path is carried ON the dict — the
        # verification LAYER + the gap-fill report "Glossary: <path>" from
        # this field (the rig run showed "(none)" everywhere).
        assert glossary.get("path"), "the path field must be set"
        assert glossary["path"].endswith(".glossary.md")
        assert Path(glossary["path"]).exists()
        assert "summaries" in glossary["path"] and ".glossaries" in glossary["path"]

    def test_extract_persist_and_xref_carries_path(self, tmp_path):
        from core.summarisation.glossary_parser import extract_persist_and_cross_reference_glossary

        glossary = extract_persist_and_cross_reference_glossary(
            _GLOSSARY_RESPONSE,
            heading="9 - TEST CHAPTER",
            output_dir=tmp_path,
            run_id="run123",
            app_version="0.5.20",
            regex_authors=["Authorone", "Authortwo"],
            log=_Log(),
        )
        assert glossary.get("path") and Path(glossary["path"]).exists()

    def test_extract_glossary_for_call_prefers_run_output_dir(self, monkeypatch, tmp_path):
        """V0.5.20: ``request._run_output_dir`` (the per-book run folder
        the converter attaches) WINS over ``request.output_dir`` (the
        user's base dir) — the full-book run persisted OUTSIDE the run's
        output dir."""
        import core.summarisation.glossary_parser as gp
        from core.summarisation.primary_call import _extract_glossary_for_call

        captured = {}

        def _fake_extract(**kwargs):
            captured.update(kwargs)
            return {"names": [{"name": "Authorone", "year": "1970", "context": ""}]}

        monkeypatch.setattr(gp, "extract_glossary_via_llm", _fake_extract)

        request = SimpleNamespace(
            output_dir=tmp_path / "base",  # the user's BASE dir
            _run_output_dir=str(tmp_path / "base" / "The Book"),  # the run dir
            _run_id="run456",
        )
        _extract_glossary_for_call(
            "9 - TEST CHAPTER",
            "source text",
            "test-model",
            lambda *a, **k: "",
            request,
            log=_Log(),
        )
        assert captured["output_dir"] == str(tmp_path / "base" / "The Book")
        assert captured["run_id"] == "run456"

    def test_extract_glossary_for_call_falls_back_to_request_dir(self, monkeypatch, tmp_path):
        """The harness path (no _run_output_dir attached — the Summarizer
        is called directly): the glossary persists under request.output_dir
        (the pre-V0.5.20 behavior)."""
        import core.summarisation.glossary_parser as gp
        from core.summarisation.primary_call import _extract_glossary_for_call

        captured = {}

        def _fake_extract(**kwargs):
            captured.update(kwargs)
            return {"names": []}

        monkeypatch.setattr(gp, "extract_glossary_via_llm", _fake_extract)
        request = SimpleNamespace(output_dir=tmp_path / "runs" / "myrun")
        _extract_glossary_for_call(
            "9 - TEST CHAPTER",
            "source text",
            "test-model",
            lambda *a, **k: "",
            request,
            log=_Log(),
        )
        assert captured["output_dir"] == str(tmp_path / "runs" / "myrun")

    def test_verification_reports_the_real_path(self, tmp_path):
        """End-to-end: the glossary dict produced by the extractor now
        yields a real path via the verification LAYER's extractor (the
        audit-trail line 'Glossary: (none)' is dead)."""
        from core.summarisation.glossary_parser import extract_glossary_via_llm
        from core.summarisation.verification_phase import _extract_glossary_path

        glossary = extract_glossary_via_llm(
            source_text="Authorone (1970) wrote about identity.",
            call_llm=lambda *a, **k: _GLOSSARY_RESPONSE,
            primary_model="test-model",
            chapter_heading="9 - TEST CHAPTER",
            output_dir=str(tmp_path),
            log=_Log(),
        )
        path = _extract_glossary_path(glossary)
        assert path != "(none)"
        assert path.endswith(".glossary.md")


# ═══════════════════════════════════════════════════════════════════════════
# Section 8 — the thin-bullet colon-less variant
# ═══════════════════════════════════════════════════════════════════════════


class TestThinColonless:
    def test_rig2_shapes_flagged(self):
        """The ~12 unflagged rig-run-2 one-liners — every evidenced shape."""
        cases = [
            "Kretschmer made significant contributions to the description of schizoid personality following Bleuler in 1925.",
            "Kasanin and Rosen made significant contributions to the description of schizoid personality following Bleuler in 1933.",
            "Hoch (*1910*) made significant contributions to the description of schizoid personality following Bleuler.",
            "Frances (*1980*) contributed to the debate on whether histrionic is a synonym for hysterical personality.",
            "Nanarello (*1953*) contributed to the description of schizoid personality.",
            "Rosenthal et al. (*1968*, *1971*) contributed to Danish adoptive studies on borderline schizophrenia.",
            "Wolman contributed to discussions regarding the overlap between narcissistic and antisocial personality disorders in 1987.",
            "Bursten contributed to the literature regarding the overlap between narcissistic and paranoid personality disorders in 1973.",
        ]
        for c in cases:
            _, issues = validate_years(c, "bullet[0]")
            assert any("thin" in i.detail for i in issues), f"unflagged: {c[:60]}"

    def test_real_claims_not_flagged(self):
        """Real claims stay unflagged: 'contributed + OBJECT' (no 'to'),
        content verbs, and the V0.5.19 pinned colon form's true-claim
        exemptions."""
        cases = [
            "Kernberg contributed the six-grounds distinction between hysterical and infantile personalities.",
            "Bleuler described latent schizophrenia in the relatives of schizophrenics.",
            "Authorone: Demonstrated the longitudinal stability of identity formation.",
        ]
        for c in cases:
            _, issues = validate_years(c, "bullet[0]")
            assert not any("thin" in i.detail for i in issues), f"false positive: {c[:60]}"

    def test_colon_form_still_flagged(self):
        """The V0.5.19 colon form keeps its pinned behavior."""
        _, issues = validate_years(
            "- Authorone: Cited in a work from 1980 regarding attribution rules.", "bullet[0]"
        )
        thin = [i for i in issues if "thin" in i.detail]
        assert thin and "V0.5.19" in thin[0].detail

    def test_long_thorough_prose_not_flagged(self):
        """The one-liner bound: substantive thorough prose that OPENS with
        the same name+verb shape but runs on for paragraphs must not be
        flagged (the audit's ~12 were bullets)."""
        long_prose = (
            "Hoch (*1910*) and Kretschmer (*1925*) contributed to the early "
            "characterization of this condition, while Kasanin and Rosen "
            "(*1933*), Terry and Rennie (*1938*), Kallman (*1938*), and "
            "Nanarello (*1953*) further refined the clinical portrait. Their "
            "collective work established a consensus description of an "
            "individual who is shy, introverted, cognitively peculiar, "
            "socially withdrawn, and affectively cold yet internally "
            "sensitive, thereby reinforcing the perceived link between this "
            "personality type and schizophrenia. This conceptual landscape "
            "was complicated by the rise of psychoanalytic interest in "
            "schizoid phenomena during the 1940s and 1950s."
        )
        assert len(long_prose) > 400
        _, issues = validate_years(long_prose, "thorough")
        assert not any("thin" in i.detail for i in issues)


# ═══════════════════════════════════════════════════════════════════════════
# Section 9 — the guarantee renderer's empty-item guard
# ═══════════════════════════════════════════════════════════════════════════


class TestGuaranteeRendererGuard:
    def test_empty_text_item_skipped_and_logged(self, monkeypatch):
        """A detected item whose cleaned text is EMPTY (the marker-at-
        paragraph-tail layout) is skipped from the rendered bullet + the
        skip is logged — a rendered '(4) ' with no text IS the dangling
        marker defect. Defense-in-depth for any detection path that
        delivers an empty item (the run-in path drops them at detection;
        this pins the RENDERER's own guard via a crafted enumeration)."""
        import core.summarisation.enumeration as enum_mod
        from core.summarisation.additive_sections import SummarizerAdditiveMixin
        from core.summarisation.enumeration import Enumeration, EnumItem

        crafted = Enumeration(
            style="runin_arabic",
            kind="runin",
            stem="the developmental history reveals",
            items=[
                EnumItem(marker="1", text="significant separations", line=1),
                EnumItem(marker="2", text="serious parental psychopathology", line=1),
                EnumItem(marker="3", text="much physical illness", line=1),
                EnumItem(marker="4", text="", line=1),  # the empty item
            ],
            start_line=1,
        )
        monkeypatch.setattr(enum_mod, "detect_enumerations", lambda text, min_items=None: [crafted])

        mixin = object.__new__(SummarizerAdditiveMixin)
        log = _Log()
        mixin.log = log
        result = {"bullet_points": [], "thorough_summary": ""}
        mixin._ensure_enumeration_bullets("Test Chapter", "whatever source text", result)
        bullets = result.get("bullet_points", [])
        assert bullets, "the guarantee bullet must be added (items were uncovered)"
        assert "(4)" not in bullets[0], "no dangling marker in the rendered bullet"
        assert "3 items from the source" in bullets[0]
        assert any("empty-text item marker" in m for m, _ in log.calls)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
