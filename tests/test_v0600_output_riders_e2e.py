"""V0.6.0 (dedicated-tools campaign) — Task 7-a: the Full Conversion OUTPUT
RIDERS, end-to-end on small synthetic fixtures.

Inventory + trace (evidence-first, flag → module → entry function → inputs):
- Dispatch: ``core/pipeline/converter.py`` is a thin re-export of
  ``core/pipeline/converter_impl.py``; the Output-Studio loop lives in
  ``core/pipeline/conversion/output_runner.py:191`` ``run_output_studio``.
  OUTPUT_PLAN (:31-159) maps each ``ConversionRequest.output_*`` flag
  (``core/models/models.py:395-413``) to a generator class +
  OutputPaths subfolder.  Construction ``gen_cls(request, log_callback)``
  (:328); invocation routes (:335-345): evidence_map gets the 4-arg
  ``generate(summaries, segments, book_title, dir)``, flashcards gets the
  ``judge_results=`` kwarg, everything else ``generate(summaries,
  book_title, dir)``.
- Non-OUTPUT_PLAN riders: ``chapters_export.write_chapters_md`` via
  output_runner.py:241-251 (output_packets flag);
  ``citation_graph.generate_citation_graph`` via
  ``core/pipeline/conversion/summary_outputs.py:231-247`` (raw markdown +
  segments); ``anki_export.export_anki_deck`` via
  ``new_outputs.py:576-582`` (from FlashcardGenerator) or directly.
- LLM seam: every LLM-driven rider funnels through
  ``OutputGeneratorBase._call_llm`` (new_outputs.py:64).  We stub it per
  instance (deterministic fake) — no network, per the batch B/C lessons.
- Deterministic riders (no LLM at all): MindMapGenerator (mind_map.py:87),
  QuoteBankGenerator (quote_bank.py:49), EPUBGenerator (epub_output.py:28),
  AgentSkillGenerator (reference_outputs.py:304),
  generate_citation_graph (citation_graph.py:30),
  export_anki_deck (anki_export.py:22), write_chapters_md
  (chapters_export.py:72), service_formatters.write_output (:436).
- LLM riders with deterministic fallbacks: ExecutiveBriefingGenerator
  (new_outputs.py:189), FlashcardGenerator (:384), ObsidianKBGenerator
  (obsidian_kb.py:366), StudyGuideGenerator (study_guide.py:41),
  SocialMediaPackGenerator (social_media.py:53).  LLM-only (return None
  on failure): Glossary/Patterns/Cheatsheet (reference_outputs.py),
  QAGenerator (new_outputs.py:666).
- EvidenceMapGenerator (evidence_map.py:81): needs langextract; when the
  package is absent it writes a guidance HTML (the sandbox has no
  langextract — that IS the runtime path, characterized here).

Fixtures are synthetic generic content (Rule 1: content-agnostic — no
real-book text, names, or titles).  All output files are written under
pytest's tmp_path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

BOOK = "Synthetic Systems Book"

# ── synthetic chapter fixtures (generic, Rule 1) ─────────────────────────────


def _summary(
    heading: str = "Intro Chapter",
    exec_text: str = "",
    thorough: str = "",
    bullets: list[str] | None = None,
    success: bool = True,
):
    from core.models import SummaryResult

    return SummaryResult(
        chapter_heading=heading,
        executive_summary=exec_text,
        thorough_summary=thorough,
        bullet_points=bullets or [],
        success=success,
    )


def _two_chapters() -> list:
    """Two tiny synthetic chapters with generic systems-language content."""
    return [
        _summary(
            heading="Chapter 1: Systems & Methods",
            exec_text="Systems thinking treats wholes as primary and studies interactions.",
            thorough="A system is a set of interacting parts. Feedback loops regulate behaviour.",
            bullets=[
                "Systems have boundaries and feedback loops",
                "Open systems exchange material with their environment",
            ],
        ),
        _summary(
            heading="Chapter 2: Field Methods",
            exec_text="Field observation complements modelling in applied research.",
            thorough="Field methods ground abstract models in observed practice.",
            bullets=[
                "Field notes capture context that instruments miss",
                "Triangulation across sources strengthens conclusions",
            ],
        ),
    ]


def _make_request(**overrides):
    from tests.fixtures import make_minimal_request

    return make_minimal_request(**overrides)


def _gen(cls, **req_overrides):
    """Construct a rider exactly as output_runner.py:328 does."""
    return cls(_make_request(**req_overrides), log_callback=lambda msg, level="INFO": None)


def _fake_segments():
    """Segment stand-ins carrying .content (the evidence_map contract)."""
    return [
        SimpleNamespace(content="Raw source text of chapter one with claims."),
        SimpleNamespace(content="Raw source text of chapter two with methods."),
    ]


# ════════════════════════════════════════════════════════════════════════════
# Mind Map (deterministic) — mind_map.py:87
# ════════════════════════════════════════════════════════════════════════════


class TestMindMapRider:
    def test_generates_mermaid_block_and_outline(self, tmp_path):
        from core.outputs.mind_map import MindMapGenerator

        out = _gen(MindMapGenerator).generate(_two_chapters(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.MindMap.md"
        assert out.exists()
        md = out.read_text(encoding="utf-8")
        # Header + both renderings
        assert f"# Mind Map: {BOOK}" in md
        assert "```mermaid" in md and "```" in md
        assert "## Outline (plain text)" in md
        # Mermaid shape: mindmap root + chapters + capped points
        mermaid = md.split("```mermaid")[1].split("```")[0]
        assert mermaid.strip().startswith("mindmap")
        assert f"  root(({BOOK}))" in mermaid
        assert "Chapter 1 - Systems and Methods" in mermaid  # & → and, : → -
        assert "Chapter 2 - Field Methods" in mermaid
        assert "Systems have boundaries and feedback loops" in mermaid
        # Outline: nested bullets under the book root
        outline = md.split("## Outline (plain text)")[1]
        assert f"- **{BOOK}**" in outline
        assert "  - Chapter 1: Systems & Methods" in outline

    def test_mermaid_label_sanitisation(self):
        from core.outputs.mind_map import _mermaid_label

        assert _mermaid_label("") == ""
        # Mermaid-significant characters stripped
        assert "(" not in _mermaid_label("fn(x) [array] {braces} <tags>")
        assert '"' not in _mermaid_label('say "hi"')
        # & → and ; : → - ; list markers stripped
        assert _mermaid_label("A & B: C") == "A and B - C"
        assert _mermaid_label("1. Numbered point") == "Numbered point"
        assert _mermaid_label("- bullet text") == "bullet text"
        # Long labels truncate on a word boundary with ASCII ellipsis
        long = " ".join(["word"] * 40)
        lab = _mermaid_label(long)
        assert len(lab) <= 70 + 3 and lab.endswith("...")
        assert "…" not in lab

    def test_cap_five_points_per_chapter(self, tmp_path):
        from core.outputs.mind_map import MindMapGenerator

        s = _summary(bullets=[f"Point number {i} about systems" for i in range(9)])
        out = _gen(MindMapGenerator).generate([s], BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        mermaid = md.split("```mermaid")[1].split("```")[0]
        point_lines = [ln for ln in mermaid.splitlines() if ln.strip().startswith("Point number")]
        assert len(point_lines) == 5  # _MAX_POINTS_PER_CHAPTER

    def test_failed_summaries_only_yields_none(self, tmp_path):
        from core.outputs.mind_map import MindMapGenerator

        s = _summary(bullets=["Systems have boundaries and feedback loops"], success=False)
        assert _gen(MindMapGenerator).generate([s], BOOK, tmp_path) is None
        assert not (tmp_path / f"{BOOK}.MindMap.md").exists()


# ════════════════════════════════════════════════════════════════════════════
# Quote Bank (deterministic) — quote_bank.py:49
# ════════════════════════════════════════════════════════════════════════════


class TestQuoteBankRider:
    def test_extracts_long_quotes_with_page_citation(self, tmp_path):
        from core.outputs.quote_bank import QuoteBankGenerator

        long_q = "A system is a set of elements standing in interrelation among themselves and with the environment"
        short_q = "too short to count"
        s = _summary(
            heading="Chapter 1",
            thorough=f'<!-- original page 3 -->\nAs the text says "{long_q}" and later "{short_q}".',
        )
        out = _gen(QuoteBankGenerator).generate([s], BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.QuoteBank.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Quote Bank — {BOOK}" in md
        assert "## Chapter 1" in md
        assert f'> "{long_q}" *(p.3)*' in md
        assert short_q not in md  # below the 40-char floor

    def test_quote_extraction_delimiters_and_pages(self):
        from core.outputs.quote_bank import QuoteBankGenerator

        gen = _gen(QuoteBankGenerator)
        text = (
            "<!-- original page 7 -->\n"
            '"The first principle is that complexity emerges from simple interactions reliably"\n'
            "«Les systèmes ouverts échangent de la matière avec leur environnement, ce qui les distingue»\n"
            "<!-- original page 9 -->\n"
            '"Guillemets and double quotes are handled separately in every case"'
        )
        quotes = gen._extract_quotes(text)
        texts = [q for q, _ in quotes]
        assert len(quotes) == 3
        assert {page for _, page in quotes} == {7, 9}  # nearest preceding page
        assert all(len(t) >= 40 for t in texts)

    def test_no_quotes_still_writes_file(self, tmp_path):
        from core.outputs.quote_bank import QuoteBankGenerator

        s = _summary(thorough="No quotation marks appear in this plain summary text at all.")
        out = _gen(QuoteBankGenerator).generate([s], BOOK, tmp_path)
        assert out is not None and out.exists()
        assert "*No direct quotes found" in out.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# EPUB (deterministic, ebooklib) — epub_output.py:28
# ════════════════════════════════════════════════════════════════════════════


class TestEPUBRider:
    def test_ebooklib_epub_readback(self, tmp_path):
        from ebooklib import epub

        from core.outputs.epub_output import EPUBGenerator

        out = _gen(EPUBGenerator).generate(_two_chapters(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.epub"
        assert out.exists() and out.stat().st_size > 500
        book = epub.read_epub(str(out))
        assert book.title == BOOK
        docs = list(book.get_items_of_type(9))  # ITEM_DOCUMENT
        chapter_docs = [d for d in docs if d.file_name.startswith("ch_")]
        assert len(chapter_docs) == 2
        html1 = chapter_docs[0].get_content().decode("utf-8")
        assert "Executive Summary" in html1
        assert "Key Takeaways" in html1
        assert "Systems have boundaries and feedback loops" in html1
        assert book.toc and len(book.toc) == 2

    def test_chapter_xhtml_is_well_formed_with_special_chars(self, tmp_path):
        """D1 pin: & < > in headings/summaries must not break chapter XHTML."""
        import xml.etree.ElementTree as ET
        import zipfile

        from core.outputs.epub_output import EPUBGenerator

        s = _summary(
            heading="Chapter 1: Systems & Methods",
            exec_text="Alpha < beta and gamma.",
            bullets=["Feedback loops regulate output & input"],
        )
        out = _gen(EPUBGenerator).generate([s], BOOK, tmp_path)
        with zipfile.ZipFile(out) as zf:
            chapters = [n for n in zf.namelist() if n.endswith(".xhtml") and "nav" not in n]
            assert chapters
            for name in chapters:
                ET.fromstring(zf.read(name))  # raises if not well-formed
        html = zipfile.ZipFile(out).read([n for n in chapters if "ch_" in n][0]).decode("utf-8")
        # Escaped exactly once (no &amp;amp;)
        assert "Systems &amp; Methods" in html and "&amp;amp;" not in html

    def test_fallback_zip_writer_contract(self, tmp_path):
        """The no-ebooklib path: mimetype first + uncompressed, valid XHTML."""
        import xml.etree.ElementTree as ET
        import zipfile

        from core.outputs.epub_output import EPUBGenerator

        gen = _gen(EPUBGenerator)
        path = tmp_path / f"{BOOK}.epub"
        gen._generate_fallback(_two_chapters(), BOOK, path)
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            assert infos[0].filename == "mimetype"
            assert infos[0].compress_type == zipfile.ZIP_STORED
            assert zf.read("mimetype").decode() == "application/epub+zip"
            assert "META-INF/container.xml" in zf.namelist()
            # D1 pin: every chapter xhtml parses as XML (special chars escaped)
            for name in zf.namelist():
                if name.endswith(".xhtml"):
                    ET.fromstring(zf.read(name))


# ════════════════════════════════════════════════════════════════════════════
# Anki .apkg export (deterministic, genanki) — anki_export.py:22
# ════════════════════════════════════════════════════════════════════════════


class TestAnkiExportRider:
    CARDS = [
        (
            "What is a feedback loop?",
            "A path where output returns as input.",
            "book::ssb chapter::one",
            "src span",
        ),
        (
            "Why do boundaries matter?",
            "They define what interacts with the system.",
            "book::ssb",
            "",
        ),
    ]

    def test_exports_valid_apkg(self, tmp_path):
        from core.outputs.anki_export import export_anki_deck

        out = export_anki_deck(self.CARDS, BOOK, tmp_path, log_callback=lambda m, l: None)
        assert out == tmp_path / f"{BOOK}.apkg"
        assert out.exists() and out.stat().st_size > 1000
        with __import__("zipfile").ZipFile(out) as zf:
            names = zf.namelist()
            assert "collection.anki2" in names
            sqlite_bytes = zf.read("collection.anki2")
            assert sqlite_bytes.startswith(b"SQLite format 3")  # real Anki collection

    def test_empty_cards_return_none(self, tmp_path):
        from core.outputs.anki_export import export_anki_deck

        assert export_anki_deck([], BOOK, tmp_path) is None
        assert not (tmp_path / f"{BOOK}.apkg").exists()

    def test_parse_tags_sanitises_spaces(self):
        from core.outputs.anki_export import _parse_tags

        assert _parse_tags("") == []
        assert _parse_tags("book::ssb chapter::one") == ["book::ssb", "chapter::one"]
        assert _parse_tags("multi word tag") == ["multi", "word", "tag"]


# ════════════════════════════════════════════════════════════════════════════
# Citation graph (deterministic) — citation_graph.py:30
# ════════════════════════════════════════════════════════════════════════════


class TestCitationGraphRider:
    RAW_MD = (
        "Opening remarks.\n"
        "<!-- original page 1 -->\n"
        "Prior work differs by scope [1] and by method [2].\n"
        "<!-- original page 2 -->\n"
        "Later studies refine both directions [1, 3].\n"
    )

    def test_builds_index_and_mermaid_density(self, tmp_path):
        from core.outputs.citation_graph import generate_citation_graph

        s = _summary(heading="Chapter 1", thorough="The synthesis leans on method [2].")
        out = generate_citation_graph(
            summaries=[s],
            segments=_fake_segments(),
            raw_markdown=self.RAW_MD,
            book_title=BOOK,
            output_dir=tmp_path,
        )
        assert out == tmp_path / f"{BOOK}.Citations.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Citation Graph: {BOOK}" in md
        assert "**3 unique citations found across 2 pages.**" in md
        assert "## Citation Index" in md
        assert "| [1] | 1, 2 |" in md  # appears on both pages
        assert "| [3] | 2 |" in md
        assert "Chapter 1" in md  # chapter column from the summary
        assert "```mermaid" in md and "graph LR" in md
        assert 'subgraph "' in md  # per-chapter density subgraphs

    def test_no_citations_returns_none(self, tmp_path):
        from core.outputs.citation_graph import generate_citation_graph

        out = generate_citation_graph(
            summaries=[],
            segments=[],
            raw_markdown="Plain text without any bracketed numeric references.",
            book_title=BOOK,
            output_dir=tmp_path,
        )
        assert out is None
        assert not (tmp_path / f"{BOOK}.Citations.md").exists()

    def test_creates_parent_dirs(self, tmp_path):
        from core.outputs.citation_graph import generate_citation_graph

        out_dir = tmp_path / "nested" / "citations"
        out = generate_citation_graph(
            summaries=[],
            segments=[],
            raw_markdown="Ref [7].",
            book_title=BOOK,
            output_dir=out_dir,
        )
        assert out is not None and out.exists()


# ════════════════════════════════════════════════════════════════════════════
# Flashcards (LLM seam + fallback + anki piggyback) — new_outputs.py:384
# ════════════════════════════════════════════════════════════════════════════


class TestFlashcardsRider:
    def test_llm_path_writes_tsv_md_and_apkg(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import FlashcardGenerator

        gen = _gen(FlashcardGenerator)
        bullet = "Systems have boundaries and feedback loops"
        chapters = [_summary(heading="Intro Chapter", bullets=[bullet])]
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "Q: What separates a system from its environment? "
                "A: The boundary that delimits interactions."
            ),
        )
        out = gen.generate(chapters, BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.Flashcards.txt"
        tsv = out.read_text(encoding="utf-8")
        assert "#separator:tab" in tsv and "#html:false" in tsv and "#tags column:3" in tsv
        rows = [ln for ln in tsv.splitlines() if ln and not ln.startswith("#")]
        assert len(rows) == 1
        fields = rows[0].split("\t")
        assert len(fields) == 3  # no judge evidence → 3 columns
        assert fields[0].startswith("What separates")
        assert "book::synthetic_systems_book" in fields[2]
        # Readable MD sibling + the .apkg piggyback rider (genanki present)
        assert (tmp_path / f"{BOOK}.Flashcards.md").exists()
        assert (tmp_path / f"{BOOK}.apkg").exists()

    def test_judge_evidence_adds_fourth_column(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import FlashcardGenerator

        gen = _gen(FlashcardGenerator)
        bullet = "Systems have boundaries and feedback loops"
        chapters = [_summary(heading="Intro Chapter", bullets=[bullet])]
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "Q: What separates a system from its environment? "
                "A: The boundary that delimits interactions."
            ),
        )
        judge = SimpleNamespace(bullet_evidence={bullet: "verbatim source span of the keypoint"})
        out = gen.generate(chapters, BOOK, tmp_path, judge_results=[judge])
        tsv = out.read_text(encoding="utf-8")
        rows = [ln for ln in tsv.splitlines() if ln and not ln.startswith("#")]
        assert rows[0].split("\t")[3] == "verbatim source span of the keypoint"
        md = (tmp_path / f"{BOOK}.Flashcards.md").read_text(encoding="utf-8")
        assert "🛡️" in md and "verbatim source span" in md

    def test_deterministic_fallback_when_llm_fails(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import FlashcardGenerator

        gen = _gen(FlashcardGenerator)
        bullet = "Open systems exchange material with their environment"
        chapters = [_summary(heading="Intro Chapter", bullets=[bullet])]
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        out = gen.generate(chapters, BOOK, tmp_path)
        tsv = out.read_text(encoding="utf-8")
        rows = [ln for ln in tsv.splitlines() if ln and not ln.startswith("#")]
        assert len(rows) == 1
        fields = rows[0].split("\t")
        assert fields[0].startswith("What does the book say about:")
        assert fields[1] == bullet

    def test_parse_flashcard_line_formats(self):
        from core.outputs.new_outputs import FlashcardGenerator

        p = FlashcardGenerator._parse_flashcard_line
        assert p("What is X?\tIt is Y.") == ("What is X?", "It is Y.")
        assert p("Q: What is X? A: It is Y.") == ("What is X?", "It is Y.")
        assert p("Question: What? Answer: Thus.") == ("What?", "Thus.")
        assert p("**Q:** Bold? **A:** Yes.") == ("Bold?", "Yes.")
        assert p("Why does it end? The answer follows here.") == (
            "Why does it end?",
            "The answer follows here.",
        )
        assert p("just prose without markers") is None


# ════════════════════════════════════════════════════════════════════════════
# Obsidian KB — obsidian_kb.py:366
# ════════════════════════════════════════════════════════════════════════════


class TestObsidianRider:
    def test_vault_structure_frontmatter_and_wikilinks(self, tmp_path, monkeypatch):
        from core.outputs.obsidian_kb import ObsidianKBGenerator

        gen = _gen(ObsidianKBGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)  # deterministic fallback
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        vault = tmp_path / "Synthetic_Systems_Book.Obsidian"  # sanitised book name
        assert out == vault / "index.md"
        assert out.exists()
        # MOC frontmatter + chapter wikilinks
        idx = out.read_text(encoding="utf-8")
        assert idx.startswith("---")
        assert "type: moc" in idx
        assert "chapters: 2" in idx
        assert "- [[Chapter_1_Systems_Methods|Chapter 1: Systems & Methods]]" in idx
        assert "## Concept Index" in idx
        # Per-chapter note: frontmatter + sections + backlink
        note = (vault / "Chapter_1_Systems_Methods.md").read_text(encoding="utf-8")
        assert "type: chapter-note" in note
        assert "## Executive Summary" in note
        assert "## Key Points" in note
        assert "- Systems have boundaries and feedback loops" in note
        assert "- ↑ [[index|" in note

    def test_llm_synthesis_and_tags_used(self, tmp_path, monkeypatch):
        from core.outputs.obsidian_kb import ObsidianKBGenerator

        gen = _gen(ObsidianKBGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda *a, **k: (
                "Synthesis: These chapters form one continuous arc.\nTags: arc, model, loop"
            ),
        )
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        idx = out.read_text(encoding="utf-8")
        assert "These chapters form one continuous arc." in idx
        assert "arc" in idx and "loop" in idx  # LLM tags rendered in the tag block

    def test_duplicate_headings_get_unique_filenames(self, tmp_path, monkeypatch):
        from core.outputs.obsidian_kb import ObsidianKBGenerator

        gen = _gen(ObsidianKBGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        s1 = _summary(heading="Same Heading", bullets=["First unique bullet here"])
        s2 = _summary(heading="Same Heading", bullets=["Second unique bullet here"])
        gen.generate([s1, s2], BOOK, tmp_path)
        vault = tmp_path / "Synthetic_Systems_Book.Obsidian"
        assert (vault / "Same_Heading.md").exists()
        assert (vault / "Same_Heading_2.md").exists()

    def test_sanitize_filename(self):
        from core.outputs.obsidian_kb import _sanitize_filename

        assert _sanitize_filename("Chapter 1: Systems & Methods") == "Chapter_1_Systems_Methods"
        assert _sanitize_filename("///") == "untitled"
        assert _sanitize_filename("CON") == "CON_"  # Windows reserved


# ════════════════════════════════════════════════════════════════════════════
# Study Guide — study_guide.py:41
# ════════════════════════════════════════════════════════════════════════════


class TestStudyGuideRider:
    def test_full_llm_path_all_five_sections(self, tmp_path, monkeypatch):
        from core.outputs.study_guide import StudyGuideGenerator

        responses = iter(
            [
                # Call 1: objectives + glossary
                "LEARNING OBJECTIVES\n"
                "LO: Explain how feedback loops regulate a system.\n"
                "LO: Contrast open and closed systems.\n\n"
                "KEY TERMS\n"
                "Feedback loop: A path where output influences future input.\n"
                "Boundary: The interface separating a system from its environment.",
                # Call 2: concept Q&A (chapter::question::answer)
                "1. Intro Chapter::What is a feedback loop?::A path where output returns as input.\n"
                "2. Intro Chapter::Why do boundaries matter?::They define what may interact.",
                # Call 3: self-check + reflection
                "SELF-CHECK\nQ: Can you model a household budget as a system?\n\n"
                "REFLECTION\nR: Apply the feedback-loop idea to one routine this week.",
            ]
        )
        gen = _gen(StudyGuideGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: next(responses))
        chapters = [
            _summary(
                heading="Intro Chapter",
                exec_text="Systems thinking treats wholes as primary.",
                bullets=["Systems have boundaries and feedback loops"],
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.StudyGuide.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Study Guide: {BOOK}" in md
        assert "## How to Use This Guide" in md
        assert "1. Explain how feedback loops regulate a system." in md
        assert "## Key Terms" in md
        assert "| **Feedback loop** | A path where output influences future input. |" in md
        assert "### Intro Chapter" in md
        assert "**Q1.** What is a feedback loop?" in md
        assert "*A:* A path where output returns as input." in md
        assert "1. Can you model a household budget as a system?" in md
        assert "1. Apply the feedback-loop idea to one routine this week." in md

    def test_deterministic_fallback_when_llm_fails(self, tmp_path, monkeypatch):
        from core.outputs.study_guide import StudyGuideGenerator

        gen = _gen(StudyGuideGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        chapters = [
            _summary(
                heading="Intro Chapter",
                exec_text="Systems thinking treats wholes as primary.",
                bullets=["Systems have boundaries and feedback loops"],
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        # Objectives + glossary fall back deterministically
        assert "Explain the following idea:" in md
        assert "| **Key concept** |" in md or "| **" in md
        assert "_No concept Q&A could be generated" in md
        # Self-check / reflection ship default prompts
        assert "In your own words, what is the central thesis of the book?" in md
        assert "Pick one concept and describe how you could apply it this week." in md


# ════════════════════════════════════════════════════════════════════════════
# Social Media Pack — social_media.py:53
# ════════════════════════════════════════════════════════════════════════════


class TestSocialRider:
    def test_llm_path_full_pack(self, tmp_path, monkeypatch):
        from core.outputs.social_media import SocialMediaPackGenerator

        responses = iter(
            [
                # X thread call
                "1/ Systems thinking starts with drawing boundaries.\n"
                "2/ Feedback loops are what make systems self-regulating.",
                # LinkedIn + hooks + hashtags call
                "LINKEDIN\nWorked through a systems primer this week.\nThree shifts for teams.\n\n"
                "HOOKS\nH: One diagram changed how I plan projects.\n\n"
                "HASHTAGS\nTAGS: systems, feedback, models",
            ]
        )
        gen = _gen(SocialMediaPackGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: next(responses))
        chapters = [
            _summary(
                heading="Intro Chapter", bullets=["Systems have boundaries and feedback loops"]
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.Social.md"
        md = out.read_text(encoding="utf-8")
        assert "## X / Twitter Thread" in md
        assert "**1/2** Systems thinking starts with drawing boundaries." in md
        assert "## Hook Variations (A/B test these)" in md
        assert "1. One diagram changed how I plan projects." in md
        assert "## LinkedIn Post" in md
        assert "Worked through a systems primer this week." in md
        assert "## Hashtags" in md
        assert "#systems #feedback #models" in md

    def test_fallback_pack_when_llm_unreachable(self, tmp_path, monkeypatch):
        """Failed call → placeholder note for the thread, fallbacks for the rest."""
        from core.outputs.social_media import SocialMediaPackGenerator

        gen = _gen(SocialMediaPackGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        chapters = [
            _summary(
                heading="Intro Chapter", bullets=["Systems have boundaries and feedback loops"]
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert "## X / Twitter Thread" in md
        assert "_Thread generation failed — see log._" in md  # designed degrade
        assert "Just finished working through" in md  # fallback LinkedIn
        assert "## Hook Variations" in md  # default 3 hooks
        assert "## Hashtags" in md and "#booksummary" in md

    def test_fallback_tweets_when_llm_output_unparseable(self, tmp_path, monkeypatch):
        """A truthy-but-empty LLM response reaches the deterministic tweet path."""
        from core.outputs.social_media import SocialMediaPackGenerator

        gen = _gen(SocialMediaPackGenerator)
        # Two calls: whitespace-only thread response, then None for linkedin.
        responses = iter(["\n\n", None])
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: next(responses))
        chapters = [
            _summary(
                heading="Intro Chapter", bullets=["Systems have boundaries and feedback loops"]
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert f"**1/1** {BOOK}: Systems have boundaries and feedback loops" in md

    def test_truncate_tweet_hard_limit(self):
        from core.outputs.social_media import _truncate_tweet

        short = "short tweet"
        assert _truncate_tweet(short) == short
        long = "word " * 80  # 400 chars
        cut = _truncate_tweet(long)
        assert len(cut) <= 271  # _TWEET_MAX + ellipsis, well under 280
        assert cut.endswith("…")

    def test_no_bullets_returns_none(self, tmp_path):
        from core.outputs.social_media import SocialMediaPackGenerator

        chapters = [_summary(heading="Intro Chapter", bullets=[])]
        assert _gen(SocialMediaPackGenerator).generate(chapters, BOOK, tmp_path) is None


# ════════════════════════════════════════════════════════════════════════════
# Executive Briefing — new_outputs.py:189
# ════════════════════════════════════════════════════════════════════════════


class TestBriefingRider:
    def test_llm_response_wrapped_into_briefing(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import ExecutiveBriefingGenerator

        gen = _gen(ExecutiveBriefingGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "Both chapters argue that modelling beats intuition when systems interact."
            ),
        )
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.Briefing.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Executive Briefing: {BOOK}" in md
        assert "modelling beats intuition" in md
        assert "*Generated from 2 chapter summaries.*" in md

    def test_truncation_detected_and_retry_wins(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import ExecutiveBriefingGenerator

        responses = iter(
            [
                "cut off mid sentence without terminal punct",  # no punctuation
                "The complete retry synthesis that ends properly with a period.",
            ]
        )
        calls: list[int] = []

        def fake(prompt, temperature=None, max_tokens=4096):
            calls.append(max_tokens)
            return next(responses)

        gen = _gen(ExecutiveBriefingGenerator)
        monkeypatch.setattr(gen, "_call_llm", fake)
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert "The complete retry synthesis" in md
        assert "cut off mid sentence" not in md
        assert calls == [8192, 16384]  # first call then the truncation retry

    def test_fallback_briefing_when_llm_fails(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import ExecutiveBriefingGenerator

        gen = _gen(ExecutiveBriefingGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert "**Executive Briefing (auto-generated fallback)**" in md
        assert "**Core Thesis:**" in md
        assert "1. Systems have boundaries and feedback loops" in md


# ════════════════════════════════════════════════════════════════════════════
# Q&A study questions — new_outputs.py:666
# ════════════════════════════════════════════════════════════════════════════


class TestQARider:
    def test_llm_path_groups_pairs_by_chapter(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import QAGenerator

        gen = _gen(QAGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "Q: What is a feedback loop?\nA: A path where output returns as input.\n\n"
                "Q: Why triangulate sources?\nA: Independent evidence weakens single-source bias."
            ),
        )
        chapters = [
            _summary(
                heading="Intro Chapter",
                exec_text="Systems thinking treats wholes as primary and interactions as causal.",
            )
        ]
        out = gen.generate(chapters, BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.StudyQuestions.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Study Questions: {BOOK}" in md
        assert "**2 questions across 1 chapter(s)**" in md
        assert "**Q1: What is a feedback loop?**" in md
        assert "A: A path where output returns as input." in md
        assert "**Q2: Why triangulate sources?**" in md

    def test_llm_failure_returns_none_no_file(self, tmp_path, monkeypatch):
        from core.outputs.new_outputs import QAGenerator

        gen = _gen(QAGenerator)
        monkeypatch.setattr(gen, "_call_llm", lambda *a, **k: None)
        chapters = [
            _summary(
                heading="Intro Chapter", exec_text="Systems thinking treats wholes as primary."
            )
        ]
        assert gen.generate(chapters, BOOK, tmp_path) is None
        assert not (tmp_path / f"{BOOK}.StudyQuestions.md").exists()


# ════════════════════════════════════════════════════════════════════════════
# Glossary / Patterns / Cheatsheet / Agent Skill — reference_outputs.py
# ════════════════════════════════════════════════════════════════════════════


class TestReferenceOutputsRiders:
    def test_glossary_sorted_entries(self, tmp_path, monkeypatch):
        from core.outputs.reference_outputs import GlossaryGenerator

        gen = _gen(GlossaryGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "Feedback loop: A path where output influences future input. (Chapter: Intro Chapter)\n"
                "Boundary: The interface separating a system from its environment."
            ),
        )
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.Glossary.md"
        md = out.read_text(encoding="utf-8")
        assert f"# Glossary: {BOOK}" in md and "**2 terms**" in md
        assert md.index("## Boundary") < md.index("## Feedback loop")  # alphabetical
        assert "*Chapter: Intro Chapter*" in md

    def test_patterns_grouped_by_category(self, tmp_path, monkeypatch):
        from core.outputs.reference_outputs import PatternsGenerator

        gen = _gen(PatternsGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "[Modelling] Feedback loop: A path where output influences future input. (Chapter: Intro Chapter)\n"
                "[Modelling] Boundary drawing: Delimiting what counts as inside.\n"
                "[Fieldwork] Triangulation: Cross-checking independent sources."
            ),
        )
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert "**3 patterns across 2 categories**" in md
        assert "## Fieldwork" in md and "## Modelling" in md  # sorted categories
        assert "### Triangulation" in md and "### Feedback loop" in md

    def test_cheatsheet_wraps_response(self, tmp_path, monkeypatch):
        from core.outputs.reference_outputs import CheatsheetGenerator

        gen = _gen(CheatsheetGenerator)
        monkeypatch.setattr(
            gen,
            "_call_llm",
            lambda prompt, temperature=None, max_tokens=4096: (
                "## Decision Rules\n\n- If outputs return as input, expect oscillation.\n"
            ),
        )
        out = gen.generate(_two_chapters(), BOOK, tmp_path)
        md = out.read_text(encoding="utf-8")
        assert f"# Cheatsheet: {BOOK}" in md
        assert "If outputs return as input, expect oscillation." in md

    def test_agent_skill_is_deterministic(self, tmp_path):
        from core.outputs.reference_outputs import AgentSkillGenerator

        out = _gen(AgentSkillGenerator).generate(_two_chapters(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.SKILL.md"
        md = out.read_text(encoding="utf-8")
        assert "## Core Mental Models" in md
        assert "### Chapter 1: Systems & Methods" in md
        assert "- Systems have boundaries and feedback loops" in md
        assert "## Chapter Index" in md
        assert "1. Chapter 1: Systems & Methods" in md


# ════════════════════════════════════════════════════════════════════════════
# Evidence Map (langextract absent → guidance path) — evidence_map.py:81
# ════════════════════════════════════════════════════════════════════════════


def _langextract_missing() -> bool:
    try:
        import langextract  # noqa: F401

        return False
    except ImportError:
        return True


class TestEvidenceMapRider:
    def test_pair_summaries_segments_contract(self):
        from core.outputs.evidence_map import EvidenceMapGenerator

        gen = EvidenceMapGenerator(None, log_callback=lambda m, l: None)
        summaries = [_summary(heading="Chapter 1", thorough="Fallback source text.")]
        pairs = gen._pair_summaries_segments(summaries, _fake_segments())
        assert pairs[0][0] == "Chapter 1"
        assert pairs[0][1] == "Raw source text of chapter one with claims."
        # No segments → falls back to the thorough summary text
        pairs = gen._pair_summaries_segments(summaries, None)
        assert pairs[0][1] == "Fallback source text."

    def test_guidance_html_written_when_langextract_missing(self, tmp_path):
        from core.outputs.evidence_map import EvidenceMapGenerator

        if not _langextract_missing():
            pytest.skip("langextract installed — guidance path not reachable")
        gen = EvidenceMapGenerator(_make_request(), log_callback=lambda m, l: None)
        out = gen.generate(_two_chapters(), _fake_segments(), BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.EvidenceMap.html"
        assert out.exists()
        html = out.read_text(encoding="utf-8")
        assert "langextract is not installed" in html
        assert "pip install langextract" in html
        assert 'class="banner alarm"' in html  # flagged, not silent

    def test_no_chapters_still_returns_html(self, tmp_path):
        from core.outputs.evidence_map import EvidenceMapGenerator

        gen = EvidenceMapGenerator(None, log_callback=lambda m, l: None)
        out = gen.generate([], None, BOOK, tmp_path)
        assert out == tmp_path / f"{BOOK}.EvidenceMap.html"
        assert "No chapters were available" in out.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# Chapters export (the packets intermediate) — chapters_export.py:72
# ════════════════════════════════════════════════════════════════════════════


class TestChaptersExport:
    def test_write_and_read_roundtrip(self, tmp_path):
        from core.outputs.chapters_export import read_chapters_md, write_chapters_md

        path = tmp_path / "sub" / f"{BOOK}.Chapters.md"
        out = write_chapters_md(_two_chapters(), BOOK, path)
        assert out == path and path.exists()
        text = path.read_text(encoding="utf-8")
        assert f"# {BOOK}" in text
        assert "## Table of Contents" in text
        assert "1. Chapter 1: Systems & Methods" in text
        assert "### Executive Summary" in text and "### Bullet Points" in text
        title, summaries = read_chapters_md(path)
        assert title == BOOK
        assert len(summaries) == 2
        assert summaries[0].chapter_heading == "Chapter 1: Systems & Methods"
        assert "Systems thinking treats wholes" in summaries[0].executive_summary
        assert "Systems have boundaries and feedback loops" in summaries[0].bullet_points

    def test_read_rejects_garbage(self, tmp_path):
        from core.outputs.chapters_export import read_chapters_md

        bad = tmp_path / "bad.md"
        bad.write_text("no structure at all here", encoding="utf-8")
        with pytest.raises(ValueError):
            read_chapters_md(bad)
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            read_chapters_md(empty)


# ════════════════════════════════════════════════════════════════════════════
# Service formatters — service_formatters.py:436 (the format matrix)
# ════════════════════════════════════════════════════════════════════════════


def _reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401

        return True
    except ImportError:
        return False


_SAMPLE_MD = (
    "# Sample Note\n\n"
    "## Executive Summary\n\n"
    "The note summarises a synthetic chapter about systems.\n\n"
    "## Key Takeaways\n\n"
    "- Systems have boundaries\n"
    "- Feedback loops regulate behaviour\n"
)


class TestServiceFormattersMatrix:
    def test_md_plain(self, tmp_path):
        from core.outputs.service_formatters import write_output

        path = tmp_path / "out.md"
        ok, msg = write_output(_SAMPLE_MD, path, fmt=".md")
        assert ok and "Wrote out.md" in msg
        assert path.read_text(encoding="utf-8") == _SAMPLE_MD

    def test_md_obsidian_variant(self, tmp_path):
        from core.outputs.service_formatters import write_output

        path = tmp_path / "note.md"
        ok, _ = write_output(
            _SAMPLE_MD,
            path,
            fmt="md",  # extension-less accepted
            obsidian=True,
            title="Sample Note",
            source_filename="sample.pdf",
            tags=["systems", "summary"],
        )
        assert ok
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert 'title: "Sample Note"' in text
        assert 'source: "[[sample.pdf]]"' in text
        assert "  - systems" in text
        assert "> [!summary] Executive Summary" in text
        assert "> [!info] Key Takeaways" in text
        assert "**Source:** [[sample.pdf]]" in text

    def test_docx_real_file(self, tmp_path):
        from core.outputs.service_formatters import write_output

        path = tmp_path / "out.docx"
        ok, msg = write_output(_SAMPLE_MD, path, fmt=".docx", title="Sample Note")
        assert ok, msg
        import docx

        d = docx.Document(str(path))
        paras = [p.text for p in d.paragraphs]
        assert "Sample Note" in paras
        assert "Executive Summary" in paras
        assert "The note summarises a synthetic chapter about systems." in paras
        assert "Systems have boundaries" in paras

    @pytest.mark.skipif(not _reportlab_available(), reason="ReportLab unavailable")
    def test_pdf_via_reportlab_backend(self, tmp_path):
        """The WeasyPrint path needs `markdown` (absent here) → ReportLab."""
        from core.outputs.service_formatters import write_output

        path = tmp_path / "out.pdf"
        ok, msg = write_output(_SAMPLE_MD, path, fmt=".pdf", title="Sample Note")
        assert ok, msg
        import pypdf

        reader = pypdf.PdfReader(str(path))
        assert len(reader.pages) >= 1

    def test_unknown_format_defaults_to_md(self, tmp_path):
        from core.outputs.service_formatters import write_output

        path = tmp_path / "out.txt"
        ok, msg = write_output(_SAMPLE_MD, path, fmt="doc")  # not in the matrix
        assert ok and "unknown fmt, used .md" in msg
        assert path.read_text(encoding="utf-8") == _SAMPLE_MD

    def test_docx_backend_failure_falls_back_to_md(self, tmp_path, monkeypatch):
        import core.outputs.service_formatters as sf

        monkeypatch.setattr(sf, "write_docx", lambda *a, **k: False)
        path = tmp_path / "out.docx"
        ok, msg = sf.write_output(_SAMPLE_MD, path, fmt=".docx")
        assert not ok and "python-docx unavailable" in msg
        assert not path.exists()
        assert (tmp_path / "out.md").read_text(encoding="utf-8") == _SAMPLE_MD

    def test_pdf_backend_failure_falls_back_to_md(self, tmp_path, monkeypatch):
        import core.outputs.service_formatters as sf

        monkeypatch.setattr(sf, "write_pdf", lambda *a, **k: False)
        path = tmp_path / "out.pdf"
        ok, msg = sf.write_output(_SAMPLE_MD, path, fmt=".pdf")
        assert not ok and "PDF backend unavailable" in msg
        assert not path.exists()
        assert (tmp_path / "out.md").read_text(encoding="utf-8") == _SAMPLE_MD


# ════════════════════════════════════════════════════════════════════════════
# Dispatch smoke: run_output_studio with the deterministic riders
# (output_runner.py:191 — flags → real generator classes → real files)
# ════════════════════════════════════════════════════════════════════════════


class _RunnerPaths:
    """Minimal OutputPaths stand-in: the subfolder attrs OUTPUT_PLAN uses."""

    def __init__(self, base: Path):
        self.base = base
        for attr in ("mindmap_dir", "quote_bank_dir", "epub_dir", "skill_dir"):
            d = base / attr.replace("_dir", "")
            d.mkdir(parents=True, exist_ok=True)
            setattr(self, attr, d)


class TestRunnerDispatchSmoke:
    def test_deterministic_flags_dispatch_to_real_files(self, tmp_path):
        from core.pipeline.conversion.output_runner import run_output_studio

        paths = _RunnerPaths(tmp_path)
        logs: list[str] = []
        request = _make_request(
            output_mindmap=True,
            output_quote_bank=True,
            output_epub=True,
            output_skill=True,
        )
        summaries = [
            _summary(
                heading="Chapter 1: Systems & Methods",
                thorough='The text states "interacting parts form a durable whole" plainly.',
                exec_text="Systems thinking treats wholes as primary.",
                bullets=["Systems have boundaries and feedback loops"],
            )
        ]
        results = run_output_studio(
            request=request,
            summaries=summaries,
            segments=_fake_segments(),
            book_title=BOOK,
            paths=paths,
            log=lambda msg, level="INFO": logs.append(msg),
            update_status=lambda status: None,
        )
        assert results["output_mindmap"] == "✅ done"
        assert results["output_quote_bank"] == "✅ done"
        assert results["output_epub"] == "✅ done"
        assert results["output_skill"] == "✅ done"
        assert (paths.mindmap_dir / f"{BOOK}.MindMap.md").exists()
        assert (paths.quote_bank_dir / f"{BOOK}.QuoteBank.md").exists()
        assert (paths.epub_dir / f"{BOOK}.epub").exists()
        assert (paths.skill_dir / f"{BOOK}.SKILL.md").exists()
        # The dispatcher logs the rider banners (log msg, not status label)
        assert any("Generating mind map" in m for m in logs)
