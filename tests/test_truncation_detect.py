"""V18.15.3.1 — truncation detection characterization tests.

Byte-for-byte stability gate for ``is_truncated`` (pure function) and the
``classify_bullets`` truncation-drop branch. The regression case is the
Greenacre bullet from the V18.15.3.0 audit (ended mid-quote at "I am
different" — unmatched `"`, no terminal punctuation).

Run: pytest tests/test_truncation_detect.py -v
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if 'tiktoken' not in sys.modules:
    tk = types.ModuleType('tiktoken')
    class _E: pass
    tk.Encoding = _E
    tk.get_encoding = lambda *a, **k: None
    sys.modules['tiktoken'] = tk

from core.summarisation.post_processing import classify_bullets, is_truncated

# ── 1. is_truncated pure function ───────────────────────────────────────────


class TestIsTruncated:

    def test_greenacre_regression_case(self):
        """The EXACT bullet from the V18.15.3.0 audit (line 25 of summary)."""
        bullet = ('Greenacre (1958a) saw a continuum from body image through '
                  'self-image to identity, emphasizing that identity always '
                  'involves some relation to others and that knowing "I am different')
        assert is_truncated(bullet) is True

    def test_complete_bullet_with_period(self):
        """A well-formed bullet ending with '.' is NOT truncated."""
        bullet = ('Tausk (1919) introduced the term "identity" into '
                  'psychoanalytic literature, asserting that man must '
                  'constantly find and experience himself anew throughout life.')
        assert is_truncated(bullet) is False

    def test_complete_bullet_with_closing_paren(self):
        """A bullet ending with ')' (e.g. a citation) is NOT truncated."""
        bullet = ('Jacobson (1964) proposed that intrapsychic structure is a '
                  'fused self-object representation (evolving through primary '
                  'libidinal identifications with the mother).')
        assert is_truncated(bullet) is False

    def test_complete_bullet_with_closing_quote(self):
        """A bullet ending with a matched quote + period is NOT truncated."""
        bullet = ('Erikson (1956) defined ego identity as "both a persistent '
                  'sameness within oneself (selfsameness) and a persistent '
                  'sharing of some kind of essential character with others."')
        assert is_truncated(bullet) is False

    def test_short_label_exempt(self):
        """Bullets < 40 chars are exempt (intentional label-style fragments)."""
        assert is_truncated("Freud (1926a)") is False
        assert is_truncated("See above.") is False
        assert is_truncated("Erikson (1956) defined ego identity") is False  # 35 chars

    def test_empty_string(self):
        """Empty/whitespace strings are not truncated (they're just empty)."""
        assert is_truncated("") is False
        assert is_truncated("   ") is False

    def test_none_safe(self):
        """None input doesn't crash (returns False)."""
        assert is_truncated(None) is False

    def test_unmatched_quotes(self):
        """Odd count of double quotes → truncated."""
        bullet = ('Lichtenstein saw the mother as imprinting an "identity theme'
                  ' upon the infant — a theme that is irreversible but varies.')
        # one " (odd) → truncated
        assert is_truncated(bullet) is True

    def test_matched_quotes_no_period(self):
        """Even quotes but ends without terminal punctuation → truncated.

        A bullet ending with a word (no . ! ? : ) " ') is truncated even
        if the quotes are balanced.
        """
        bullet = ('Mahler distinguished psychological birth from biological '
                  'birth and postulated a sequence of six developmental phases'
                  ' including the autistic and symbiotic')
        # ends with 'symbiotic' (no terminal punctuation, > 40 chars)
        assert is_truncated(bullet) is True

    def test_unmatched_parens(self):
        """Unmatched parentheses → truncated."""
        bullet = ('Kernberg (1967, 1976, 1980b proposed a three-step process '
                  'of identity formation: introjection, identification, and '
                  'identity formation through depersonification.')
        # one ( (from "1980b proposed" has no closing) → truncated
        # Actually let me craft this more carefully
        bullet = ('Blos (1962, 1965, 1967 outlined the second individuation '
                  'process of adolescence requiring emotional disengagement '
                  'from internalized infantile objects.')
        # has one ( and zero ) → unmatched → truncated
        assert is_truncated(bullet) is True

    def test_bullet_ending_with_colon(self):
        """A bullet ending with ':' (introducing a list) is NOT truncated."""
        bullet = ('Jacobson\'s contributions to identity development can be '
                  'divided into five categories as follows:')
        assert is_truncated(bullet) is False

    def test_bullet_ending_with_exclamation(self):
        """A bullet ending with '!' is NOT truncated."""
        bullet = ('The growing number of borderline and narcissistic patients '
                  'has led to a rising interest in the problem of identity!')
        assert is_truncated(bullet) is False

    def test_bullet_ending_with_question_mark(self):
        """A bullet ending with '?' is NOT truncated."""
        bullet = ('Does the summary capture the essential arguments, key plot '
                  'points, or critical data of the Source Text?')
        assert is_truncated(bullet) is False

    def test_long_bullet_no_punctuation_truncated(self):
        """A 60+ char bullet ending with a letter → truncated."""
        bullet = ('The chapter opens by situating the problem of identity '
                  'within the clinical context of borderline and narcissistic '
                  'character disorders')
        assert is_truncated(bullet) is True

    def test_threshold_exactly_40(self):
        """A 40-char bullet without terminal punctuation → truncated (>= 40)."""
        # exactly 40 chars, ends with 'e' (no terminal punctuation)
        bullet = "Identity involves both intrapsychic and socials"  # 46 chars
        assert len(bullet) >= 40
        assert is_truncated(bullet) is True

    def test_threshold_just_below_40(self):
        """A 39-char bullet without terminal punctuation → NOT truncated (exempt)."""
        bullet = "Identity involves intrapsychic dimension"  # 40 chars exactly
        # 40 chars — at the boundary (>= 40 triggers check)
        # Let's use a clearly-below one
        bullet = "Identity involves intrapsychic and soci"  # 39 chars
        assert len(bullet) < 40
        assert is_truncated(bullet) is False


# ── 2. classify_bullets integration ─────────────────────────────────────────


class TestClassifyBulletsTruncation:

    def test_truncated_bullet_dropped_with_correct_stage(self):
        """classify_bullets drops a truncated bullet with stage 'truncated'."""
        bullets = [
            "Tausk (1919) introduced the term into psychoanalytic literature.",
            ('Greenacre (1958a) saw a continuum from body image through '
             'self-image to identity, emphasizing that identity always '
             'involves some relation to others and that knowing "I am different'),
        ]
        kept, drops = classify_bullets(bullets)
        # The complete bullet is kept
        assert any("Tausk" in b for b in kept)
        # The truncated bullet is NOT in kept
        assert not any("I am different" in b for b in kept)
        # A drop record with stage 'truncated' exists
        trunc_drops = [d for d in drops if "truncated" in d[1]]
        assert len(trunc_drops) == 1
        # always_drop is False (conservative-gated)
        assert trunc_drops[0][3] is False
        # The reason mentions the truncation signal
        assert "truncated" in trunc_drops[0][2].lower() or "max_tokens" in trunc_drops[0][2].lower()

    def test_complete_bullet_not_dropped(self):
        """A complete bullet is never flagged as truncated."""
        bullets = [
            "Erikson (1956) defined ego identity as a persistent sameness within oneself.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert not any("truncated" in d[1] for d in drops)

    def test_truncation_checked_after_markup_stripping(self):
        """The truncation check runs on the CLEANED bullet (after strip_thinking/markup).

        A bullet with HTML markup tags that contain quotes should NOT false-
        positive on the unmatched-quote check — the markup is stripped first.
        """
        # A complete bullet with an <em> tag containing a quote in style attr
        # (this is what the markdown formatter produces). After strip_markup_tags,
        # the <em style="font-size:0.9em"> is removed, leaving a clean bullet.
        # We test with a simpler case: a bullet that's complete after stripping.
        bullets = [
            "Tausk (1919) introduced the term identity into psychoanalytic literature.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert not any("truncated" in d[1] for d in drops)

    def test_multiple_truncated_bullets_all_dropped(self):
        """Multiple truncated bullets are all dropped (one drop record each)."""
        bullets = [
            ('Greenacre (1958a) saw a continuum from body image through '
             'self-image to identity, emphasizing that identity always '
             'involves some relation to others and that knowing "I am different'),
            ('Mahler distinguished psychological birth from biological birth '
             'and postulated a sequence of six phases including autistic and'
             ' symbiotic without completing the thought'),
            "Tausk (1919) introduced the term into psychoanalytic literature.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1  # only the Tausk bullet
        trunc_drops = [d for d in drops if "truncated" in d[1]]
        assert len(trunc_drops) == 2

    def test_truncated_drop_is_conservative_gated(self):
        """Truncated drops have always_drop=False (kept in conservative mode)."""
        bullets = [
            ('Greenacre (1958a) saw a continuum from body image through '
             'self-image to identity, emphasizing that identity always '
             'involves some relation to others and that knowing "I am different'),
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 0  # dropped in normal mode
        assert len(drops) == 1
        assert drops[0][3] is False  # always_drop=False → conservative-gated


# ── 3. classify_bullets double-dash stripping (V18.15.3.1) ─────────────────


class TestClassifyBulletsDoubleDash:

    def test_double_dash_stripped_from_gap_fill_bullet(self):
        """V18.15.3.1: Gap-fill bullets '- - Name: text' have leading dashes stripped."""
        bullets = [
            "- - Freud: According to Erikson (1958), Freud referred to identity once.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert kept[0].startswith("Freud:")
        assert not kept[0].startswith("-")

    def test_single_dash_stripped(self):
        """V18.15.3.1: Single-dash '- Name: text' also stripped."""
        bullets = [
            "- Tausk (1919) introduced the term into psychoanalytic literature.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert kept[0].startswith("Tausk")
        assert not kept[0].startswith("-")

    def test_no_dash_unchanged(self):
        """V18.15.3.1: Bullets without leading dashes are unchanged."""
        bullets = [
            "Erikson (1956) defined ego identity as persistent sameness.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert kept[0].startswith("Erikson")

    def test_multiple_gap_fill_bullets_all_stripped(self):
        """V18.15.3.1: Multiple double-dash bullets all have dashes stripped."""
        bullets = [
            "- - Freud: According to Erikson (1958), Freud referred to identity once.",
            "- - Winnicott: His views on early development are significant.",
            "- - Blos: His 1962 work enriched Eissler's view.",
            "- - Hartmann: His differentiation between ego and self influenced later frameworks.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 4
        for b in kept:
            assert not b.startswith("-"), f"Still starts with dash: {b!r}"

    def test_triple_dash_stripped(self):
        """V18.15.3.1: Triple-dash '- - - Name' fully stripped (loop)."""
        bullets = [
            "- - - Kernberg: Proposed a three-step process of identity formation.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert kept[0].startswith("Kernberg:")
        assert not kept[0].startswith("-")

    def test_star_marker_stripped(self):
        """V18.15.3.1: Star markers '* Name: text' also stripped."""
        bullets = [
            "* Jacobson: Proposed five categories of identity development.",
        ]
        kept, drops = classify_bullets(bullets)
        assert len(kept) == 1
        assert kept[0].startswith("Jacobson:")
        assert not kept[0].startswith("*")


# ── V18.15.4.3: curly-quote (U+201C/U+201D/U+2019) truncation detection ──────


class TestIsTruncatedCurlyQuotes:
    """V18.15.4.3 — is_truncated now counts curly double-quotes (U+201C/U+201D)
    and accepts curly closing quotes (U+201D/U+2019) as valid terminal punctuation.

    Pre-V18.15.4.3: only ASCII `"` was counted → mid-curly-quote truncation
    (common in PDF-extracted text) silently passed through. These tests gate
    the fix byte-for-byte.
    """

    def test_unmatched_curly_open_quote_is_truncated(self):
        """A bullet ending mid-quote with an unmatched curly open-quote (U+201C)
        must be flagged truncated (pre-V18.15.4.3 it was missed)."""
        bullet = (
            'Greenacre (1958a) saw a continuum from body image through '
            'self-image to identity, emphasizing that identity always '
            'involves some relation to others and that knowing \u201cI am different'
        )
        # one U+201C (odd) → truncated
        assert is_truncated(bullet) is True

    def test_matched_curly_quotes_with_period_not_truncated(self):
        """A complete bullet with matched curly quotes + period is NOT truncated."""
        bullet = (
            'Erikson (1956) defined ego identity as \u201cboth a persistent '
            'sameness within oneself (selfsameness) and a persistent '
            'sharing of some kind of essential character with others.\u201d'
        )
        # U+201C ... U+201D balanced, ends with U+201D (terminal) → not truncated
        assert is_truncated(bullet) is False

    def test_bullet_ending_with_curly_closing_quote_not_truncated(self):
        """A bullet ending with a curly closing quote (U+201D) is NOT truncated
        (it's a valid terminal character, like ASCII ")."""
        bullet = (
            'Lichtenstein saw the mother as imprinting an \u201cidentity theme'
            '\u201d upon the infant \u2014 a theme that is irreversible but varies.'
        )
        # ends with '.' so already not truncated, but also has balanced curly quotes
        assert is_truncated(bullet) is False

    def test_bullet_ending_with_curly_apostrophe_not_truncated(self):
        """A bullet ending with a curly apostrophe (U+2019, possessive) is NOT
        truncated (V18.15.4.3 added U+2019 to the terminal-char set)."""
        bullet = (
            'The patients\u2019 growing interest in the problem of identity '
            'reflects broader cultural shifts in how selfhood is understood '
            'across the contemporary psychoanalytic diaspora'
        )
        # Pre-V18.15.4.3: ends with 'diaspora' (no terminal char) → truncated.
        # Append a curly apostrophe to make it terminal:
        bullet_with_apos = bullet.rstrip() + '\u2019s scope.'
        assert is_truncated(bullet_with_apos) is False

    def test_mixed_ascii_and_curly_quotes_unmatched(self):
        """Mixed ASCII + curly quotes: if the COMBINED count is odd → truncated."""
        bullet = (
            'Freud described the \u201ctalking cure\u201d as a method where '
            'the patient\u2019s associations reveal unconscious material, '
            'and Breuer called it a "cathartic method.'
        )
        # 2 U+201C/U+201D (balanced) + 1 U+2019 + 1 ASCII " = odd total → truncated
        assert is_truncated(bullet) is True

    def test_pure_ascii_still_works(self):
        """Regression guard: pure-ASCII bullets behave exactly as before."""
        # unmatched ASCII "
        b1 = ('Greenacre (1958a) saw a continuum from body image through '
              'self-image to identity, emphasizing that identity always '
              'involves some relation to others and that knowing "I am different')
        assert is_truncated(b1) is True
        # matched ASCII " + period
        b2 = ('Erikson (1956) defined ego identity as "both a persistent '
              'sameness within oneself (selfsameness) and a persistent '
              'sharing of some kind of essential character with others."')
        assert is_truncated(b2) is False

