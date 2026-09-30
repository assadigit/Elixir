r"""V0.5.7 (audit V0.5.6): the "Maj sey" name-extraction garble fix.

The V0.5.6 ch.6 conversion log (``audit/results/bench_v056_ch6_paranoid/
Broken Structures Salman Akhtar_v0.5.6_20260927-001944-3599809e.conversion
.log.md`` line 679) recorded the gap-fill batch spending rounds 2-4 hunting
a theorist called ``"Maj sey"`` — a name that does NOT appear as a real
author in the source chapter (only as the OCR-garbled line 419:
``… Maj sey 1302 UIed) sUINUAS`` on the user's local copy of the source).
The V18.20.3.4 attribution veto correctly rejected every attempt to write a
bullet for this fake author (line 717: ``⏹️  V18.20.3.4: Giving up on 'Maj
sey' — mention-only attempt also failed the attribution veto; no
attribution-safe bullet exists for this author``). The V0.5.6 deterministic
floor (line 843) then logged ``theorists 69/75 in final bullets (missing:
['Allodi', 'Jack', 'Siever and Kendler', 'Varghesi', 'Maj sey'])`` — the
``+1`` author vs V0.5.5's 74-author floor is the regex-induced ``"Maj
sey"`` OCR-artifact.

ROOT CAUSE
----------
``extract_citations`` Pattern 1 (parenthetical ``Author (Year)``) and
Pattern 2 (inline ``Author Year``) had a buggy ``(?:\s+[a-z]{1,4})?`` group
AFTER the capitalized surname token ``[A-Z][a-zA-Z]+``. The group matched
ANY 1-4 letter lowercase word — so OCR-garble ``Maj sey 1302`` was
extracted as ``{author: 'Maj sey', years: '1302', type: 'inline'}`` (Pattern
2: ``Maj`` + `` sey`` matched the buggy group, then ``1302`` matched the
year). A 14th-century theorist.

FIX (this commit)
----------------
- REMOVES the buggy ``(?:\s+[a-z]{1,4})?`` after-token group.
- ADDS a ``_CIT_PARTICLE_PREFIX`` BEFORE-token group restricted to the
  closed class of generic Romance/Germanic/Arabic surname particles
  (``van`` / ``von`` / ``de`` / ``del`` / ``di`` / ``da`` / ``du`` /
  ``la`` / ``le`` / ``les`` / ``den`` / ``der`` / ``ter`` / ``ten`` /
  ``ben`` / ``abu`` / ``ibn`` / ``al`` / ``el`` / ``st`` / ``lo``).
  Multi-word particle-prefix surnames (``van der Waerden (1927)``) are now
  captured as ONE token (was: only ``Waerden`` — the particle prefix was
  lost).
- EXTENDS the hyphenated-surname group from ``[-\\u2013][A-Z]`` (which
  required the second part to be Capitalized, so ``Maj-sey`` with a
  lowercase second part was silently skipped) to the shared ``NAME_SEP``
  class (which allows lowercase second parts). This ALSO closes the
  V18.15.5.1 (DEBT-08) bug: ``Smith—Jones (1983)`` (em-dash) was captured
  with author ``"Jones"`` only — now it's captured as the full compound
  ``Smith—Jones``. The V0.5.4 ``_SUMMARY_CITATION_RE`` in
  ``attribution.py`` already used ``NAME_SEP`` via DEBT-08 — the V0.5.7
  source-side extractor is now consistent with that summary-side mirror.

CONTENT-AGNOSTIC (Rule 1 ✓): the particle list is the closed class of
generic surname particles (no book content). The ``"Maj sey"`` /
``"Maj-sey"`` / ``"van der Waerden"`` strings in the tests below are
TEST FIXTURES (per AGENTS.md, tests are exempt from the Rule-1 deny-list).
The production regex + coverage check are built from runtime-extracted
author lists, no hardcoded names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Stub the optional heavy deps exactly like tests/test_v054_extract_citations.py
# (markitdown not installed in the sandbox; the stub keeps the eager
# core.pipeline→core.pdf import chain loadable for any transitive imports).
from core.preprocessing.citations_regex import NAME_SEP
from core.preprocessing.deterministic_analyzer import (
    _CIT_PARTICLE_PREFIX,
    _CIT_PARTICLES,
    extract_citations,
)

# The paranoid chapter's source text lives in docs/ground_truth/ (Rule 4
# provenance: ground-truth files are the audit evidence, NOT runtime code
# — they are deliberately NOT scanned by the Rule-1 deny-list test). The
# ground_truth file is the SAME source the V0.5.6 rig ran against (it
# contains the OCR-garbled line 419 ``Maj sey 1302`` — the V0.5.6 garble).
_CH6_SOURCE_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs/ground_truth"
    / "001_6 - PARANOID PERSONALITY DISORDER.md"
)


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.7 brief test 1: hyphenated surname (lowercase second part) NOT split
# ═══════════════════════════════════════════════════════════════════════════


class TestHyphenatedSurnameNotSplit:
    """V0.5.7: hyphenated surnames with a LOWERCASE second part (e.g.
    ``"Maj-sey"``) are captured as ONE token (was: NO MATCH — the
    pre-V0.5.7 regex required ``[A-Z]`` after the hyphen, so the lowercase
    second part failed the constraint and the whole surname was silently
    skipped).
    """

    def test_hyphenated_surname_not_split(self):
        """``"Maj-sey (1984) noted the gullibility."`` → ``extract_citations``
        returns ``"Maj-sey"`` (one token, NOT split into ``"Maj"`` + ``"sey"``).

        Pre-V0.5.7: ``"Maj-sey (1984)"`` returned NO match (the regex's
        ``[-\\u2013][A-Z]`` group required the second part to start with
        a Capital letter — the lowercase ``"sey"`` failed the constraint).
        Post-V0.5.7: the regex's ``NAME_SEP[a-zA-Z]+`` group accepts any
        letter case in the second part, so ``"Maj-sey"`` is captured as
        ONE token.
        """
        text = "Maj-sey (1984) noted the gullibility."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "Maj-sey" in authors, (
            f"V0.5.7: hyphenated surname 'Maj-sey' MUST be captured as one "
            f"token (was: pre-V0.5.7 silently skipped — the lowercase "
            f"second part 'sey' failed the [A-Z] requirement); got "
            f"{sorted(authors)}"
        )

    def test_hyphenated_surname_inline_form(self):
        """The inline form ``"Maj-sey 1984 noted..."`` (no parens) is also
        captured as ONE token via Pattern 2 (the inline ``Author Year``
        regex shares the V0.5.7 fix).
        """
        text = "Maj-sey 1984 noted the gullibility."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "Maj-sey" in authors, (
            f"V0.5.7 Pattern 2 (inline): hyphenated surname 'Maj-sey' MUST "
            f"be captured as one token; got {sorted(authors)}"
        )

    def test_compound_surname_unchanged(self):
        """Regression guard: the standard Capitalized-second-part compound
        ``"Chasseguet-Smirgel (1984)"`` is STILL captured as one token
        (the V0.5.7 fix extends but does not narrow — the existing
        Capitalized-second-part case is preserved).
        """
        text = "Chasseguet-Smirgel (1984) theorized it."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "Chasseguet-Smirgel" in authors, (
            f"regression guard: 'Chasseguet-Smirgel' MUST still be captured "
            f"as one token; got {sorted(authors)}"
        )

    def test_em_dash_compound_no_longer_truncated(self):
        """V0.5.7 closes the V18.15.5.1 (DEBT-08) bug: em-dash /
        typographic-hyphen compounds (``"Smith—Jones (1983)"``) were
        captured with author ``"Jones"`` only (the FIRST surname was
        silently dropped). Now the full compound is captured (the V0.5.7
        fix unified the source-side extractor's hyphen class with the
        shared ``NAME_SEP`` constant the V0.5.4 ``_SUMMARY_CITATION_RE``
        in ``attribution.py`` already used via DEBT-08).
        """
        for sep in ["\u2014", "\u2010", "\u2011", "-", "\u2013"]:
            text = f"Smith{sep}Jones (1983) reviewed."
            cits = extract_citations(text)
            authors = {c["author"] for c in cits}
            assert f"Smith{sep}Jones" in authors, (
                f"V0.5.7 (DEBT-08 closure): 'Smith{sep}Jones' (sep={sep!r}) "
                f"MUST be captured as one token; got {sorted(authors)}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.7 brief test 2: multi-word particle-prefix surname NOT split
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiWordSurnameNotSplit:
    """V0.5.7: particle-prefix surnames (``"van der Waerden"`` /
    ``"de la Cruz"``) are captured as ONE token (was: only the capitalized
    token — the particle prefix was lost).
    """

    def test_multi_word_surname_not_split(self):
        """``"van der Waerden (1927)"`` → ``extract_citations`` returns
        ``"van der Waerden"`` (one token).

        Pre-V0.5.7: returned ``"Waerden"`` only — the buggy
        ``(?:\\s+[a-z]{1,4})?`` group was AFTER the capitalized token,
        so it could only match a particle AFTER the surname (which never
        happens in real citation text). Particles BEFORE the surname
        (van / von / de / der / etc.) were silently dropped.
        """
        text = "van der Waerden (1927) proved it."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "van der Waerden" in authors, (
            f"V0.5.7: particle-prefix surname 'van der Waerden' MUST be "
            f"captured as one token (was: only 'Waerden' — the particle "
            f"prefix was lost); got {sorted(authors)}"
        )

    def test_de_la_cruz_surname(self):
        """``"de la Cruz (1990) theorized."`` → captured as ``"de la Cruz"``
        (one token, two particles ``de`` + ``la``).
        """
        text = "de la Cruz (1990) theorized."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "de la Cruz" in authors, (
            f"V0.5.7: two-particle-prefix surname 'de la Cruz' MUST be "
            f"captured as one token; got {sorted(authors)}"
        )

    def test_particle_prefix_in_mid_sentence(self):
        """``"Wrote van der Waerden (1927) about."`` — the particle-prefix
        surname is captured even when it appears mid-sentence (the
        ``(?<!\\w)`` lookbehind enforces the word boundary before the
        particle, so a non-word char before the particle still allows the
        match).
        """
        text = "Wrote van der Waerden (1927) about."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "van der Waerden" in authors, (
            f"V0.5.7: particle-prefix surname mid-sentence MUST still be "
            f"captured; got {sorted(authors)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.7 brief test 3: the V0.5.6 "Maj sey" garble — reproduced + fixed
# ═══════════════════════════════════════════════════════════════════════════


class TestMajSeyGarbleReproducedAndFixed:
    """V0.5.7: the V0.5.6 ``"Maj sey"`` OCR-garble extraction is fixed.

    The V0.5.6 conv log line 679 showed the gap-fill batch spending 3
    rounds (2, 3, 4) trying to attribute a bullet to ``"Maj sey"`` — a
    name that was extracted from the source chapter's OCR-garbled line
    419 (``Maj sey 1302 UIed) sUINUAS`` on the user's local copy of the
    source). The V18.20.3.4 attribution veto correctly rejected every
    attempt (line 717) — ``"Maj sey"`` is not a real author. But the
    deterministic floor (line 843) still logged ``"Maj sey"`` as a
    missing theorist (69/75 — the ``+1`` author vs V0.5.5's 74-author
    floor was the regex-induced OCR-artifact).

    The V0.5.7 fix prevents the regex from extracting ``"Maj sey"`` in
    the first place — the buggy ``(?:\\s+[a-z]{1,4})?`` after-token group
    that matched ANY 1-4 letter lowercase word is removed; the
    particle-prefix handling is now done by the BEFORE-token
    ``_CIT_PARTICLE_PREFIX`` restricted to the closed particle class.
    """

    def test_maj_sey_garble_not_extracted_parenthetical(self):
        """``"Maj sey (1984) noted the gullibility."`` → ``extract_citations``
        returns NO ``"Maj sey"`` entry. The buggy after-token group that
        captured the lowercase ``" sey"`` particle AFTER ``"Maj"`` is
        gone; the BEFORE-token particle-prefix group restricted to the
        closed particle class does NOT match ``"Maj"`` (it's a
        Capitalized word, not a particle).
        """
        text = "Maj sey (1984) noted the gullibility."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "Maj sey" not in authors, (
            f"V0.5.7: the V0.5.6 'Maj sey' OCR-garble MUST NOT be extracted "
            f"(the buggy after-token particle group is removed); got "
            f"{sorted(authors)}"
        )

    def test_maj_sey_garble_not_extracted_inline(self):
        """``"Maj sey 1302 noted the gullibility."`` (the V0.5.6 source
        line shape — inline ``Author Year`` form) → NO ``"Maj sey"`` entry.

        This is the EXACT shape that the V0.5.6 rig's source chapter had
        on its OCR-garbled line 419 (``Maj sey 1302 UIed) sUINUAS``) —
        the regex's Pattern 2 (inline ``Author Year``) captured ``Maj
        sey`` + ``1302`` as a 14th-century theorist. The V0.5.7 fix
        removes the buggy after-token particle group from Pattern 2 as
        well, so the OCR-garble is no longer extracted.
        """
        text = "Maj sey 1302 noted the gullibility."
        cits = extract_citations(text)
        authors = {c["author"] for c in cits}
        assert "Maj sey" not in authors, (
            f"V0.5.7 Pattern 2 (inline): the V0.5.6 'Maj sey 1302' "
            f"OCR-garble MUST NOT be extracted (the buggy after-token "
            f"particle group is removed); got {sorted(authors)}"
        )
        # Belt-and-braces: no entry with the implausible year 1302 either.
        assert all(c["years"] != "1302" for c in cits), (
            f"V0.5.7: the implausible 14th-century year '1302' (the V0.5.6 "
            f"garble's year) MUST NOT appear in any extracted citation's "
            f"years field; got {[(c['author'], c['years']) for c in cits]}"
        )

    def test_maj_sey_garble_reproduced_on_v056_source(self):
        """Run ``extract_citations`` on the V0.5.6 source chapter
        (``docs/ground_truth/001_6 - PARANOID PERSONALITY DISORDER.md``,
        the audit ground-truth file that contains the OCR-garbled line
        419 ``Maj sey 1302 UIed) sUINUAS``) → the V0.5.7 fix ensures
        ``"Maj sey"`` is NOT in the extracted author list.

        Pre-V0.5.7 (the V0.5.6 behavior): the regex extracted 75 unique
        authors including ``"Maj sey"`` (the +1 vs V0.5.5's 74-author
        floor). Post-V0.5.7: the regex extracts 74 unique authors (no
        ``"Maj sey"`` — matching V0.5.5's count).
        """
        if not _CH6_SOURCE_PATH.exists():
            pytest.skip(f"source chapter not found at {_CH6_SOURCE_PATH}")
        source = _CH6_SOURCE_PATH.read_text()
        cits = extract_citations(source)
        authors = {c["author"] for c in cits}
        assert "Maj sey" not in authors, (
            f"V0.5.7: running extract_citations on the V0.5.6 source chapter "
            f" MUST NOT extract the 'Maj sey' OCR-garble (the buggy "
            f"after-token particle group is removed); got 'Maj sey' in the "
            f"author set. Total authors: {len(authors)}"
        )
        # The V0.5.6 conv log line 639 said 75 authors; V0.5.5 = 74.
        # V0.5.7 should match V0.5.5's 74 (no Maj sey).
        assert len(authors) == 74, (
            f"V0.5.7: extract_citations on the V0.5.6 source chapter should "
            f"return 74 unique authors (the V0.5.5 count — the +1 in V0.5.6 "
            f"was the regex-induced 'Maj sey' OCR-artifact, now removed); "
            f"got {len(authors)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.7 brief test 4: no split-name garbles in the source chapter output
# ═══════════════════════════════════════════════════════════════════════════


class TestNoSplitNameGarblesInSourceChapter:
    """V0.5.7: running ``extract_citations`` on the actual source chapter
    produces NO split-name garbles in the output (no author token with an
    internal space that should be a single token, no implausibly-old
    author names extracted from OCR-garbled source lines).
    """

    def test_no_split_name_garbles_in_source(self):
        """Scan the extracted author set for ANY author with an internal
        space (which would indicate either a particle-prefix surname —
        legitimate, like ``"van der Waerden"`` — or a garble like
        ``"Maj sey"``). For each multi-word author, the particle tokens
        must ALL be in the closed ``_CIT_PARTICLES`` class — otherwise
        it's a garble (a non-particle word captured as part of the
        surname).
        """
        if not _CH6_SOURCE_PATH.exists():
            pytest.skip(f"source chapter not found at {_CH6_SOURCE_PATH}")
        source = _CH6_SOURCE_PATH.read_text()
        cits = extract_citations(source)
        authors = {c["author"] for c in cits}
        # The closed class of particles (mirrors _CIT_PARTICLES in
        # deterministic_analyzer.py — Rule 1: closed class, no book content).
        particle_set = {
            "van",
            "von",
            "de",
            "del",
            "di",
            "da",
            "du",
            "la",
            "le",
            "les",
            "den",
            "der",
            "ter",
            "ten",
            "ben",
            "abu",
            "ibn",
            "al",
            "el",
            "st",
            "lo",
        }
        for a in authors:
            if " " not in a:
                continue  # single-token surname, skip
            # Multi-word author — every non-Capitalized token MUST be a
            # particle (otherwise it's a garble like "Maj sey" where "sey"
            # isn't a particle but matched the buggy after-token group).
            tokens = a.split()
            # The multi-author connector "and"/"&" is allowed (Slater and
            # Roth is a multi-author citation, not a garble).
            non_connector_tokens = [t for t in tokens if t not in ("and", "&")]
            # The first Capitalized token + any subsequent Capitalized
            # tokens are the surname proper; the lowercase tokens MUST be
            # particles.
            for t in non_connector_tokens:
                if t[0].islower():
                    assert t.lower() in particle_set, (
                        f"V0.5.7 garble scan: multi-word author {a!r} has a "
                        f"lowercase token {t!r} that is NOT in the closed "
                        f"particle class — this is a name-extraction "
                        f"garble (a non-particle word captured as part of "
                        f"the surname, the V0.5.6 'Maj sey' bug class)."
                    )

    def test_no_implausibly_old_authors(self):
        """Scan the extracted citations for ANY implausibly-old year (the
        V0.5.6 garble was ``"Maj sey 1302"`` — the 14th-century year
        1302 came from the OCR-garbled line 419). The V0.5.7 fix
        prevents the regex from extracting the OCR-garble at all (the
        year ``1302`` is no longer paired with the fake author ``"Maj
        sey"``).
        """
        if not _CH6_SOURCE_PATH.exists():
            pytest.skip(f"source chapter not found at {_CH6_SOURCE_PATH}")
        source = _CH6_SOURCE_PATH.read_text()
        cits = extract_citations(source)
        # The V0.5.6 garble had year 1302. The V0.5.7 fix prevents the
        # author from being extracted, so no citation should have year
        # 1302 (the implausible 14th-century year is no longer paired
        # with any author).
        implausible_years = [c for c in cits if c["years"] == "1302"]
        assert implausible_years == [], (
            f"V0.5.7: no citation should have the implausible 14th-century "
            f"year '1302' (the V0.5.6 garble's year, paired with the fake "
            f"author 'Maj sey' on the OCR-garbled line 419); got "
            f"{implausible_years}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# V0.5.7 internal: the particle prefix constants are well-formed
# ═══════════════════════════════════════════════════════════════════════════


class TestParticlePrefixConstants:
    """V0.5.7 internal: the ``_CIT_PARTICLES`` + ``_CIT_PARTICLE_PREFIX``
    constants are well-formed (closed class, no book content; mirrors
    ``_ALLOWED_SOLID_PREFIXES`` in ``author_garbage.py``).
    """

    def test_particles_is_closed_class_no_book_content(self):
        """``_CIT_PARTICLES`` is a closed regex alternation of generic
        Romance/Germanic/Arabic surname particles — no book content
        (Rule 1 content-agnostic). The list MUST contain only the
        documented particle words (van, von, de, del, di, da, du, la,
        le, les, den, der, ter, ten, ben, abu, ibn, al, el, st, lo) +
        the ``\\s+`` separator.
        """
        # Extract the alternation words from the regex string.
        # ``_CIT_PARTICLES`` has shape ``(?:word1|word2|...|wordN)\\s+``.
        body = _CIT_PARTICLES.removeprefix("(?:").removesuffix(r")\s+")
        words = body.split("|")
        expected = {
            "van",
            "von",
            "de",
            "del",
            "di",
            "da",
            "du",
            "la",
            "le",
            "les",
            "den",
            "der",
            "ter",
            "ten",
            "ben",
            "abu",
            "ibn",
            "al",
            "el",
            "st",
            "lo",
        }
        assert set(words) == expected, (
            f"V0.5.7: _CIT_PARTICLES must be exactly the closed class of "
            f"generic surname particles — no book content (Rule 1). Got "
            f"{words}"
        )
        # Content-agnostic (Rule 1 ✓): no book-derived author names
        # (Croewe / Jack / Bak / Morey / Ndtei / Rettersol / Lowenthal /
        # Munro / Maj-sey / Ovessey) leak into the particle class.
        book_authors = {
            "croewe",
            "jack",
            "bak",
            "morey",
            "ndtei",
            "rettersol",
            "lowenthal",
            "munro",
            "maj-sey",
            "ovessey",
            "wurmser",
            "varghesi",
            "conlon",
            "reid",
        }
        leaked = book_authors & {w.lower() for w in words}
        assert not leaked, (
            f"V0.5.7 Rule 1 violation: book-derived author names leaked "
            f"into the _CIT_PARTICLES closed class: {leaked}"
        )

    def test_particle_prefix_lookbehind_anchored(self):
        """``_CIT_PARTICLE_PREFIX`` starts with ``(?<!\\w)`` — the
        negative lookbehind enforces a word boundary before the particle
        so a Capitalized token like ``"Maj"`` is NOT consumed as a
        particle fragment of ``"aj Sey"`` (the V0.5.6 bug surfaced when
        the regex backtracked into the interior of a Capitalized token).
        """
        assert _CIT_PARTICLE_PREFIX.startswith(r"(?<!\w)"), (
            f"V0.5.7: _CIT_PARTICLE_PREFIX MUST start with (?<!\\w) — the "
            f"negative lookbehind enforces the word boundary so a "
            f"Capitalized token's interior is not consumed as a particle "
            f"fragment. Got {_CIT_PARTICLE_PREFIX!r}"
        )

    def test_name_sep_constant_unchanged(self):
        """Regression guard: the V18.15.5.1 (DEBT-08) ``NAME_SEP`` constant
        is unchanged by the V0.5.7 fix (the V0.5.7 fix uses NAME_SEP via
        the shared import, not a redefined local copy).

        NAME_SEP is a regex character-class string (escape sequences like
        ``\\u2013``), so we verify by compiling + matching each Unicode
        separator char against it (rather than a naive ``in`` substring
        test, which would look for the literal escape chars).
        """
        import re

        # NAME_SEP is a character class — wrap it in [] is already done
        # by the constant itself; compile it as-is and check each char.
        name_sep_re = re.compile(NAME_SEP)
        # The 5 Unicode dash/hyphen variants (DEBT-08).
        for sep in ["-", "\u2013", "\u2014", "\u2010", "\u2011"]:
            assert name_sep_re.search(sep), (
                f"V0.5.7 regression guard: NAME_SEP must match {sep!r} "
                f"(the {ord(sep)} Unicode dash/hyphen variant — DEBT-08 "
                f"closed the V18.15.5.1 known bug by sharing the full "
                f"NAME_SEP class with the source-side extractor)"
            )
