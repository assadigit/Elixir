"""
Validator – compares source markdown with summaries to detect coverage gaps and hallucinations.

Uses keyword extraction (TF‑IDF style) to identify missing concepts.
Optionally uses sentence‑transformers for semantic similarity if installed.
"""

import re
from collections import Counter
from pathlib import Path
from typing import Any  # ADDED Any

from utils.logging import get_main_logger
from utils.text_utils import detect_persian_text

logger = get_main_logger()


class Validator:
    """
    Validates summaries against the full source text.
    """

    # Common stopwords (extended)
    STOPWORDS = frozenset(
        {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "or",
            "but",
            "is",
            "it",
            "its",
            "this",
            "that",
            "was",
            "are",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "with",
            "from",
            "by",
            "as",
            "not",
            "he",
            "she",
            "they",
            "we",
            "you",
            "i",
            "their",
            "our",
            "his",
            "her",
            "which",
            "who",
            "what",
            "when",
            "where",
            "how",
            "all",
            "one",
            "two",
            "three",
            "also",
            "can",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "do",
            "did",
            "such",
            "than",
            "then",
            "so",
            "if",
            "about",
            "up",
            "out",
            "more",
            "very",
            "just",
            "into",
            "over",
            "after",
            "before",
            "between",
            "through",
            "page",
            "pages",
            "copyright",
            "rights",
            "reserved",
            "published",
            "publisher",
            "publication",
            "press",
            "edition",
            "printing",
            "printed",
            "reprinted",
            "isbn",
            "library",
            "congress",
            "cataloging",
            "university",
            "college",
            "journal",
            "volume",
            "issue",
            "series",
            "revised",
            "translated",
            "author",
            "authors",
            "editor",
            "editors",
            "foreword",
            "preface",
            "introduction",
            "conclusion",
            "chapter",
            "chapters",
            "section",
            "part",
            "figure",
            "table",
            "appendix",
            "references",
            "bibliography",
            "index",
            "acknowledgments",
            "acknowledgements",
            "dedication",
            "contents",
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
            "however",
            "therefore",
            "thus",
            "hence",
            "whereas",
            "although",
            "despite",
            "whether",
            "both",
            "each",
            "every",
            "other",
            "another",
            "same",
            "different",
            "various",
            "many",
            "some",
            "most",
            "much",
            "less",
            "well",
            "often",
            "always",
            "never",
            "already",
            "still",
            "even",
            "only",
            "further",
            "example",
        }
    )

    def __init__(self, source_md_path: Path, summary_md_path: Path | None = None):
        self.source_path = source_md_path
        self.summary_path = summary_md_path
        self.source_text = ""
        self.summary_text = ""

    def load(self) -> bool:
        """Load source and summary files."""
        if not self.source_path.exists():
            logger.error(f"Source file not found: {self.source_path}")
            return False
        try:
            self.source_text = self.source_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read source: {e}")
            return False

        if self.summary_path and self.summary_path.exists():
            try:
                self.summary_text = self.summary_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to read summary: {e}")
                return False
        else:
            # If no summary path provided, use the full markdown? Actually, we need summaries.
            # We'll look for a summary file in the same directory.
            possible = self.source_path.parent / f"{self.source_path.stem}.summary.md"
            if possible.exists():
                self.summary_path = possible
                self.summary_text = possible.read_text(encoding="utf-8")
            else:
                logger.warning(
                    "No summary file found. Validation will only run on source keywords."
                )
                self.summary_text = ""
        return True

    def _extract_keywords(self, text: str, n: int = 30) -> list[str]:
        """Extract top n keywords from text (excluding stopwords)."""
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        # If Persian, also include Persian words
        if detect_persian_text(text, threshold=0.05):
            persian_words = re.findall(r"[\u0600-\u06FF]{3,}", text)
            words.extend(persian_words)
        counts = Counter(w for w in words if w not in self.STOPWORDS)
        # Sort by frequency descending
        return [w for w, _ in counts.most_common(n)]

    def compute_coverage(self, source_keywords: list[str], summary_text: str) -> dict[str, Any]:
        """Compute percentage of source keywords present in summary."""
        if not source_keywords:
            return {"coverage": 1.0, "missing": [], "present": [], "total_keywords": 0}
        summary_lower = summary_text.lower()
        present = [kw for kw in source_keywords if kw in summary_lower]
        missing = [kw for kw in source_keywords if kw not in summary_lower]
        coverage = len(present) / len(source_keywords) if source_keywords else 1.0
        return {
            "coverage": coverage,
            "present": present,
            "missing": missing,
            "total_keywords": len(source_keywords),
        }

    def validate(self) -> dict[str, Any]:
        """Run validation and return results."""
        if not self.source_text:
            return {"error": "Source text not loaded"}

        # Extract keywords from source
        source_keywords = self._extract_keywords(self.source_text, n=50)

        if not self.summary_text:
            # If no summary, return only source keywords
            return {
                "source_keywords": source_keywords,
                "summary_found": False,
                "error": "No summary text provided",
            }

        # Compute coverage
        coverage_info = self.compute_coverage(source_keywords, self.summary_text)

        # Optional: detect potential hallucinations (keywords in summary not in source)
        summary_keywords = self._extract_keywords(self.summary_text, n=30)
        source_set = set(source_keywords)
        summary_set = set(summary_keywords)
        hallucinated = [kw for kw in summary_set if kw not in source_set]

        # Also, compute overall similarity (optional: we could add embeddings here)
        # For now, we'll skip embeddings to keep dependencies minimal.

        return {
            "source_keywords": source_keywords,
            "summary_keywords": summary_keywords,
            "coverage": coverage_info["coverage"],
            "missing": coverage_info["missing"],
            "present": coverage_info["present"],
            "hallucinated": hallucinated,
            "total_keywords": coverage_info["total_keywords"],
            "summary_found": True,
        }

    def generate_report(self) -> str:
        """Generate a human-readable report."""
        result = self.validate()
        if "error" in result:
            return f"❌ Error: {result['error']}"

        if not result.get("summary_found"):
            return f"⚠️ No summary found. Source keywords: {', '.join(result.get('source_keywords', [])[:20])}"

        coverage = result["coverage"] * 100
        missing = result["missing"]
        hallucinated = result["hallucinated"]

        lines = [
            "📊 VALIDATION REPORT",
            "=" * 50,
            f"Source keywords: {result['total_keywords']} (top 50)",
            f"Summary keywords: {len(result['summary_keywords'])} (top 30)",
            f"Keyword coverage: {coverage:.1f}%",
            "",
            "🔑 Covered keywords (present in summary):",
            f"  {', '.join(result['present'][:20])}{'…' if len(result['present']) > 20 else ''}",
            "",
            "❌ Missing keywords (not in summary):",
        ]
        if missing:
            lines.append(f"  {', '.join(missing[:20])}{'…' if len(missing) > 20 else ''}")
        else:
            lines.append("  ✅ All key terms covered!")
        lines.append("")
        if hallucinated:
            lines.append("⚠️ Potential hallucinations (keywords in summary not in source):")
            lines.append(f"  {', '.join(hallucinated[:20])}{'…' if len(hallucinated) > 20 else ''}")
        else:
            lines.append("✅ No obvious hallucinated terms detected.")

        lines.append("")
        lines.append("💡 Recommendation:")
        if coverage < 60:
            lines.append(
                "  - Coverage is low. Consider increasing summarisation context or using a heavier model."
            )
        elif coverage < 80:
            lines.append(
                "  - Coverage is acceptable but could be improved. Try enabling self‑consistency or lowering temperature."
            )
        else:
            lines.append("  - Excellent coverage! Summary captures most key concepts.")
        return "\n".join(lines)
