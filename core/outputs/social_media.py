"""V4.1.0: Social Media Pack generator.

Repurposes the book's key points into ready-to-post social media content:

  1. **X / Twitter thread** — 8-12 numbered tweets, each ≤ 280 characters
  2. **LinkedIn long-form post** — hook + body + call-to-action
  3. **Hook variations** — 3 one-liner openers to A/B test
  4. **Hashtag set** — 8-15 relevant hashtags

The generator makes 2 LLM calls:
  · one for the X thread (with a hard 280-char-per-tweet guard)
  · one combined call for the LinkedIn post, hooks, and hashtags

Every section degrades gracefully: a failed call leaves a clear placeholder
note rather than crashing the whole pack.

Output: ``<BookTitle>.Social.md``
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.models import SummaryResult
from core.outputs.new_outputs import OutputGeneratorBase

# V18.20.4.12 (T-c3): atomic output writes — a crash / disk-full mid-write
# can no longer leave a truncated .md behind (temp file + os.replace).
from utils.atomic_io import atomic_write_text

# X/Twitter limit. We leave a small margin for the "N/" numbering prefix.

logger = logging.getLogger(__name__)

_TWEET_MAX = 270


def _truncate_tweet(text: str, limit: int = _TWEET_MAX) -> str:
    """Hard-truncate a tweet to ``limit`` chars on a word boundary."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Walk back to the last whitespace to avoid cutting a word in half.
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.;:!?—-") + "…"


class SocialMediaPackGenerator(OutputGeneratorBase):
    """V4.1: Generate a social media pack from keypoints."""

    def generate(
        self,
        summaries: list[SummaryResult],
        book_title: str,
        output_dir: Path,
    ) -> Path | None:
        """Generate ``BookName.Social.md`` and return its path."""
        chapters = [s for s in summaries if s.success]
        if not chapters:
            self.log("  ℹ️ Social pack: No chapter summaries available.", "INFO")
            return None

        all_bullets: list[str] = []
        for s in chapters:
            if s.bullet_points:
                all_bullets.extend(
                    bp.strip().lstrip("-•* ").strip() for bp in s.bullet_points if bp.strip()
                )

        if not all_bullets:
            self.log("  ℹ️ Social pack: No keypoints to work with.", "INFO")
            return None

        self.log(f"  📱 Generating social media pack from {len(all_bullets)} keypoints…", "INFO")

        # Cap the bullets fed to the prompts to keep them manageable.
        bullets_text = "\n".join(f"- {bp}" for bp in all_bullets[:35])

        # ── Section 1: X / Twitter thread ────────────────────────────────
        thread = self._gen_x_thread(book_title, bullets_text)

        # ── Section 2+3+4: LinkedIn + hooks + hashtags (one call) ─────────
        linkedin, hooks, hashtags = self._gen_linkedin_and_meta(book_title, bullets_text)

        md = self._assemble_markdown(
            book_title=book_title,
            thread=thread,
            linkedin=linkedin,
            hooks=hooks,
            hashtags=hashtags,
        )

        output_path = output_dir / f"{book_title}.Social.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)  # V7.6.0 R5: lazy dir
        try:
            atomic_write_text(output_path, md, encoding="utf-8")
        except Exception as e:
            self.log(f"  ⚠️ Social pack: failed to write file: {e}", "WARNING")
            return None

        self.log(f"  ✅ Social media pack saved to: {output_path}", "SUCCESS")
        return output_path

    # ══════════════════════════════════════════════════════════════════════
    # LLM-driven section generators
    # ══════════════════════════════════════════════════════════════════════

    def _gen_x_thread(self, book_title: str, bullets_text: str) -> list[str]:
        """One LLM call → X/Twitter thread as a list of tweet strings."""
        prompt = self.prompt_manager.render_template(
            "outputs/social_x_thread",
            book_title=book_title,
            bullets_text=bullets_text,
        )
        resp = self._call_llm(prompt, temperature=0.6, max_tokens=2048)
        if not resp:
            self.log("  ⚠️ Social pack: X thread generation failed.", "DEBUG")
            return []

        resp = self._strip_thinking(resp)
        tweets: list[str] = []
        for line in resp.splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip a leading "N/" or "N." numbering the model may have added.
            line = re.sub(r"^\d+\s*[/\.)\-]\s*", "", line)
            tweet = _truncate_tweet(line)
            if tweet:
                tweets.append(tweet)

        if not tweets:
            # Deterministic fallback: one synthetic tweet per top bullet.
            for bp in bullets_text.splitlines()[:10]:
                bp = bp.lstrip("- ").strip()
                if bp:
                    tweets.append(_truncate_tweet(f"{book_title}: {bp}"))
        return tweets

    def _gen_linkedin_and_meta(
        self, book_title: str, bullets_text: str
    ) -> tuple[str, list[str], list[str]]:
        """One LLM call → (LinkedIn post, hook variations, hashtags)."""
        prompt = self.prompt_manager.render_template(
            "outputs/social_linkedin",
            book_title=book_title,
            bullets_text=bullets_text,
        )
        resp = self._call_llm(prompt, temperature=0.5, max_tokens=2048)
        linkedin = ""
        hooks: list[str] = []
        hashtags: list[str] = []

        if resp:
            resp = self._strip_thinking(resp)
            section = None
            post_lines: list[str] = []
            for line in resp.splitlines():
                stripped = line.strip()
                upper = stripped.upper()
                if upper == "LINKEDIN" or (upper.startswith("LINKEDIN") and len(stripped) < 30):
                    section = "li"
                    continue
                if upper == "HOOKS" or (upper.startswith("HOOKS") and len(stripped) < 30):
                    if section == "li":
                        linkedin = "\n".join(post_lines).strip()
                        post_lines = []
                    section = "hooks"
                    continue
                if upper == "HASHTAGS" or (upper.startswith("HASHTAGS") and len(stripped) < 30):
                    if section == "hooks":
                        section = "tags"
                    continue
                if section == "li":
                    post_lines.append(line)
                elif section == "hooks" and upper.startswith("H:"):
                    h = stripped.split(":", 1)[1].strip().lstrip("-• ").strip()
                    if h:
                        hooks.append(h)
                elif section == "tags" and upper.startswith("TAGS:"):
                    raw = stripped.split(":", 1)[1].strip()
                    hashtags = [re.sub(r"[^a-zA-Z0-9_]", "", t).strip() for t in raw.split(",")]
                    hashtags = [t for t in hashtags if t][:15]
            # Flush any trailing LinkedIn content if no HOOKS section followed.
            if post_lines and not linkedin:
                linkedin = "\n".join(post_lines).strip()

        # Fallbacks so sections are never empty.
        if not linkedin:
            linkedin = self._fallback_linkedin(book_title, bullets_text)
        if not hooks:
            hooks = [
                f"What if everything in “{book_title}” boiled down to one idea?",
                f"I read “{book_title}” so you don't have to. Here's the gist:",
                f"Three things from “{book_title}” changed how I think today.",
            ]
        if not hashtags:
            base = re.sub(r"[^a-zA-Z0-9]", "", book_title).lower()
            hashtags = [base, "booksummary", "reading", "learning", "nonfiction", "ideas"][:6]
        return linkedin, hooks, hashtags

    # ══════════════════════════════════════════════════════════════════════
    # Deterministic fallback
    # ══════════════════════════════════════════════════════════════════════

    def _fallback_linkedin(self, book_title: str, bullets_text: str) -> str:
        """Minimal LinkedIn post built straight from the keypoints."""
        top = [bp.lstrip("- ").strip() for bp in bullets_text.splitlines() if bp.strip()][:3]
        body = "\n\n".join(f"• {bp}" for bp in top)
        return (
            f"Just finished working through “{book_title}”. Here are the ideas "
            f"that stuck:\n\n{body}\n\nWhat would you add?"
        )

    # ══════════════════════════════════════════════════════════════════════
    # Assembly
    # ══════════════════════════════════════════════════════════════════════

    def _assemble_markdown(
        self,
        book_title: str,
        thread: list[str],
        linkedin: str,
        hooks: list[str],
        hashtags: list[str],
    ) -> str:
        lines: list[str] = []
        lines.append(f"# Social Media Pack: {book_title}")
        lines.append("")
        lines.append(
            "> Ready-to-post content repurposed from the book's key points. "
            "Tweak the voice to match your brand before publishing."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # X / Twitter thread
        lines.append("## X / Twitter Thread")
        lines.append("")
        if thread:
            lines.append(f"*{len(thread)} tweets. Each is ≤ 280 characters. Copy-paste in order.*")
            lines.append("")
            for i, tweet in enumerate(thread, 1):
                lines.append(f"**{i}/{len(thread)}** {tweet}")
                lines.append("")
            lines.append("---")
            lines.append("")
        else:
            lines.append("_Thread generation failed — see log._")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Hook variations
        lines.append("## Hook Variations (A/B test these)")
        lines.append("")
        for i, h in enumerate(hooks, 1):
            lines.append(f"{i}. {h}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # LinkedIn
        lines.append("## LinkedIn Post")
        lines.append("")
        lines.append("```")
        lines.append(linkedin)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Hashtags
        lines.append("## Hashtags")
        lines.append("")
        if hashtags:
            tag_str = " ".join(f"#{t}" for t in hashtags)
            lines.append(tag_str)
        else:
            lines.append("_No hashtags generated._")
        lines.append("")

        return "\n".join(lines)
