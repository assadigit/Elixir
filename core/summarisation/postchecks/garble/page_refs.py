"""V0.4.19 — the KD/TT page-reference injector.

``inject_page_refs`` moved VERBATIM from ``garble.py`` during the V0.4.19
de-monolithization (deterministic fallback when the model ignores the
page-citation prompt instruction).
"""

from __future__ import annotations

from core.summarisation.postchecks.shared import Issue

# ─────────────────────────────────────────────────────────────────────────────
# V0.4.16 (audit): page-ref injector for KD/TT — deterministic fallback
# when the model ignores the MANDATORY page-citation prompt instruction.
# ─────────────────────────────────────────────────────────────────────────────


def inject_page_refs(
    text: str,
    field_label: str,
    source_text: str = "",
) -> tuple[str, list[Issue]]:
    """V0.4.16: inject page references into KD/TT bullets that lack them.

    If the model ignores the MANDATORY page-citation prompt instruction,
    this post-check adds an approximate page ref to each bullet based on
    the chapter's start_page and end_page from the YAML frontmatter.

    The page is estimated from the bullet's position in the field text:
    - First 1/3 of bullets -> first 1/3 of pages
    - Middle 1/3 -> middle 1/3 of pages
    - Last 1/3 -> last 1/3 of pages

    Content-agnostic: works on any chapter with YAML frontmatter.
    """
    issues: list[Issue] = []
    if not text or not source_text:
        return text, issues

    try:
        import re as _re

        # Extract start_page and end_page from the source YAML frontmatter.
        fm_match = _re.search(r"start_page:\s*(\d+)", source_text)
        em_match = _re.search(r"end_page:\s*(\d+)", source_text)
        if not fm_match or not em_match:
            return text, issues  # no page info — can't inject
        start_page = int(fm_match.group(1))
        end_page = int(em_match.group(1))
        page_range = end_page - start_page
        if page_range <= 0:
            return text, issues

        # Find bullet lines that DON'T already have a page ref.
        lines = text.split("\n")
        bullet_indices = [i for i, ln in enumerate(lines) if ln.startswith("- ")]
        if not bullet_indices:
            return text, issues

        injected = 0
        for idx_pos, line_idx in enumerate(bullet_indices):
            line = lines[line_idx]
            # Check if the line already has a page ref like (p. 53).
            if _re.search(r"\(p\.\s*\d", line):
                continue  # already has a page ref
            # Estimate the page based on position in the bullet list.
            position_ratio = idx_pos / max(len(bullet_indices), 1)
            estimated_page = start_page + int(page_range * position_ratio)
            # Add the page ref at the end of the line (before any trailing whitespace).
            line_stripped = line.rstrip()
            lines[line_idx] = f"{line_stripped} (p. {estimated_page})"
            injected += 1

        if injected > 0:
            text = "\n".join(lines)
            issues.append(
                Issue(
                    detector="page_ref_injector",
                    severity="fix",
                    field=field_label,
                    snippet=text[:60],
                    detail=(
                        f"injecting page refs: added (p. X) to {injected} "
                        f"bullet(s) that lacked page citations (model ignored "
                        f"the MANDATORY prompt instruction; pages estimated "
                        f"from start_page={start_page}, end_page={end_page})"
                    ),
                )
            )
    except Exception as e:
        from core.summarisation.postchecks.shared import logger

        logger.warning("page-ref injector crashed (non-fatal): %s: %s", type(e).__name__, e)
    return text, issues
