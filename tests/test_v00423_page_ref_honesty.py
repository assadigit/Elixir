"""V0.4.23 (audit V0.4.22, H4 / backlog #2): page-ref injector honesty.

The V0.4.22 ch.4 run shipped 8 bullets whose "(p. 77/85/94/103)" locators
were machine ESTIMATES (position-based, from start_page/end_page) yet
presented as verified citations. The injector now ships ``(p. ~X)`` and
is idempotent against its own output.
"""

from __future__ import annotations

import re

from core.summarisation.postchecks.garble.page_refs import inject_page_refs


def _src(start: int = 77, end: int = 112) -> str:
    return f"---\nstart_page: {start}\nend_page: {end}\n---\n\nChapter body.\n"


KD_TEXT = (
    "- First distinction about approach versus syndrome\n"
    "- Second distinction about criteria lists\n"
    "- Third distinction about theoretical framing\n"
)


class TestPageRefEstimateHonesty:
    def test_estimates_carry_the_tilde(self):
        out, issues = inject_page_refs(KD_TEXT, "key_distinctions", _src())
        for line in out.split("\n"):
            if line.startswith("- "):
                assert re.search(r"\(p\. ~\d+\)$", line), line
        assert not re.search(r"\(p\. \d+\)", out), "no bare (p. X) citations may ship"

    def test_issue_detail_names_the_estimate_mark(self):
        _out, issues = inject_page_refs(KD_TEXT, "key_distinctions", _src())
        assert issues and issues[0].detector == "page_ref_injector"
        assert "(p. ~X)" in issues[0].detail
        assert "ESTIMATED" in issues[0].detail

    def test_idempotent_on_rerun(self):
        once, _ = inject_page_refs(KD_TEXT, "key_distinctions", _src())
        twice, issues = inject_page_refs(once, "key_distinctions", _src())
        assert twice == once, "a (p. ~X) line must not be injected twice"
        assert issues == []

    def test_model_provided_refs_untouched(self):
        text = (
            "- A bullet with a real model-derived citation (p. 89).\n- A bullet without any ref\n"
        )
        out, _ = inject_page_refs(text, "key_distinctions", _src())
        lines = out.split("\n")
        assert lines[0].endswith("(p. 89)."), lines[0]
        assert re.search(r"\(p\. ~\d+\)$", lines[1]), lines[1]

    def test_no_frontmatter_no_injection(self):
        out, issues = inject_page_refs(KD_TEXT, "key_distinctions", "no frontmatter here")
        assert out == KD_TEXT
        assert issues == []
