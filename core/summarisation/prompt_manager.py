"""Prompt Bank — user-editable prompt templates for summarisation & outputs.

Prompts are stored as ``.md`` files in ``~/.elixir/prompts/`` (user copies)
and ``prompts/`` (built-in presets).  Each file uses ``{{variable}}`` placeholders
that are substituted by :meth:`PromptManager.render` / :meth:`PromptManager.render_template`.

V16.0.4 (PROMPT-OVERHAUL) extensions:
* Subdirectory support — ``name`` may be ``"summarisation/additive_sections"``,
  ``"pdf/toc_extract"``, ``"outputs/glossary"``, etc.  Top-level names
  (``"default"``, ``"academic"``, ...) still work for backward compatibility.
* Arbitrary kwargs — :meth:`render_template` accepts ``**variables`` so any
  prompt can use any placeholder names, not only ``heading`` / ``text`` /
  ``language``.  :meth:`render` is kept as a thin backward-compatible wrapper
  for the legacy three-argument API used by the existing ``default.md`` /
  ``academic.md`` / ``technical.md`` / ``creative.md`` / ``simplified_default.md``
  presets.
* Recursive user-dir seeding — on first run the entire builtin tree (including
  subdirectories) is mirrored into ``~/.elixir/prompts/``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# V18.5 (Phase 3, Task 3.5): YAML front-matter pattern for prompt versioning.
# Prompts may optionally start with:
#   ---
#   version: "18.5.0"
#   compatible_model_class: "low_bit_quant"
#   ---
# The front-matter is parsed (simple key:value, no nested YAML), stripped
# before rendering (so the LLM never sees it), and the resolved version is
# logged at DEBUG level on first render of each prompt name.
_FRONTMATTER_RE = re.compile(
    r'\A---\s*\n(.*?)\n---\s*\n?',  # captures the block between --- delimiters
    re.DOTALL,
)
# Track which prompt names we've already logged the version for (avoid spam).
_logged_versions: set = set()

# Built-in presets shipped with the app — resolve from multiple candidate
# locations to handle different install layouts (dev, PyInstaller bundle, etc.)
_BUILTIN_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "prompts",   # core/summarisation/../../prompts
    Path(__file__).resolve().parent.parent.parent / "prompts",  # one more level up
    Path.cwd() / "prompts",                                # current working directory
]
_BUILTIN_DIR = next((p for p in _BUILTIN_CANDIDATES if p.exists()), _BUILTIN_CANDIDATES[0])
# User-customised prompts live here (copied from builtins on first run)
_USER_DIR = Path.home() / ".elixir" / "prompts"

_DEFAULT_PROMPT_NAME = "default"


class PromptManager:
    """Manages prompt templates: built-in presets + user customisations.

    A *name* may be either flat (``"default"``) or namespaced with a
    subdirectory (``"summarisation/additive_sections"``).  The on-disk file
    is always ``<dir>/<name>.md`` — for flat names the file lives at the
    root of the prompts directory; for namespaced names it lives inside the
    named subdirectory.
    """

    def __init__(self) -> None:
        self._ensure_user_dir()

    # ------------------------------------------------------------------ #
    # First-run seeding
    # ------------------------------------------------------------------ #
    def _ensure_user_dir(self) -> None:
        """V17.0.0: ALWAYS re-sync built-in prompts to user dir on every run.
        No version check, no conditions — just overwrite everything.
        V0.08 (P2): logs via the module logger (was print()) so re-syncs land
        in the app log (stderr console + rotating file handlers) like the rest
        of core.
        """
        import shutil as _shutil
        _USER_DIR.mkdir(parents=True, exist_ok=True)
        if not _BUILTIN_DIR.exists():
            logger.warning("PromptManager: built-in dir %s does not exist!", _BUILTIN_DIR)
            return
        _copied = 0
        for _src in _BUILTIN_DIR.rglob("*.md"):
            _rel = _src.relative_to(_BUILTIN_DIR)
            _dest = _USER_DIR / _rel
            _dest.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(_src, _dest)
            _copied += 1
        logger.info("PromptManager: re-synced %d built-in prompts to %s", _copied, _USER_DIR)


    # ------------------------------------------------------------------ #
    # Listing / save / delete (UI helpers)
    # ------------------------------------------------------------------ #
    def list_prompts(self) -> list[str]:
        """Return available prompt names (relative path without ``.md``)."""
        names = set()
        for d in [_BUILTIN_DIR, _USER_DIR]:
            if d.exists():
                for f in d.rglob("*.md"):
                    rel = f.relative_to(d)
                    # Use forward slashes for cross-platform consistency
                    name = str(rel.with_suffix("")).replace("\\", "/")
                    names.add(name)
        return sorted(names)

    def load_prompt(self, name: str) -> str | None:
        """Load a prompt template by name. Returns ``None`` if not found.

        ``name`` may be ``"default"`` (flat) or ``"summarisation/additive_sections"``
        (namespaced).  User copy wins over builtin.
        """
        rel = self._name_to_rel(name)
        for d in [_USER_DIR, _BUILTIN_DIR]:
            p = d / rel
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")
        return None

    def save_prompt(self, name: str, content: str) -> None:
        """Save a prompt template to the user directory."""
        rel = self._name_to_rel(name)
        dest = _USER_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    def delete_prompt(self, name: str) -> bool:
        """Delete a user prompt. Returns True if deleted."""
        rel = self._name_to_rel(name)
        p = _USER_DIR / rel
        if p.exists() and p.is_file():
            p.unlink()
            return True
        return False

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self, name: str, heading: str, text: str, language: str = "") -> str | None:
        """Backward-compatible wrapper: render with the legacy 3 variables.

        Kept for the existing ``default.md`` / ``academic.md`` / ``technical.md``
        / ``creative.md`` / ``simplified_default.md`` presets and any caller
        still using the original 3-argument API.
        """
        return self.render_template(name, heading=heading, text=text, language=language)

    def render_template(self, name: str, **variables: str) -> str | None:
        """Load and render a prompt template, substituting every ``{{key}}``
        placeholder with the matching value in ``variables``.

        Substitution is a simple string replace (no Jinja2 dependency).
        Unknown placeholders are left untouched — this lets prompts embed
        literal ``{`` / ``}`` braces (e.g. JSON examples) without escaping.

        V18.2.21 (Phase 1.1 — prompt-injection defense): the ``text``
        variable (the untrusted chapter content) is passed through
        ``core.llm.prompt_sanitizer.wrap_untrusted`` before substitution.
        This (a) wraps it in ``<untrusted_source>`` fence tags so the model
        treats it as DATA, and (b) HTML-escapes any of the model's own
        output tags (``</executive_summary>`` etc.) found inside the chapter
        text so a crafted PDF cannot break the response parser or inject
        ``<system>`` instructions. Book-agnostic (Key Decision #3). Other
        variables (heading, language, src_text) are not sanitized — only
        ``text`` is the untrusted ingestion surface.

        V18.5 (Phase 3, Task 3.5): strips YAML front-matter (``version:``,
        ``compatible_model_class:``) from the top of the template before
        rendering, and logs the resolved version at DEBUG level on first
        render of each prompt name. The front-matter never reaches the LLM.
        """
        template = self.load_prompt(name)
        if template is None:
            logger.warning("PromptManager: prompt '%s' not found", name)
            return None

        # V18.5 (Phase 3, Task 3.5): parse + strip front-matter.
        template = self._strip_and_log_frontmatter(name, template)

        for key, value in variables.items():
            if value is None:
                value = ""
            value = str(value)
            # V18.2.21 (Phase 1.1): sanitize the untrusted chapter text.
            # Only the `text` variable is untrusted PDF content; `heading`,
            # `language`, `src_text` (used in additive_sections) are either
            # app-controlled or already-trusted. We sanitize `text` AND
            # `src_text` (the latter is also chapter content, just a
            # truncated slice used in followup prompts).
            if key in ("text", "src_text") and value:
                # V18.2.29: Skip the sanitizer for low-bit quant models
                # (IQ2_XXS/XS/IQ1). The <untrusted_source> fence tags confuse
                # the low-bit quant — it treats them as semantic content and
                # produces garbled output (the V18.2.18 "the oreticians"
                # regression was traced to this). For these models the raw
                # text is safer than the wrapped text.
                # V18.3 (Phase 1.1): replaced inline regex with model_taxonomy.
                from core.llm.model_taxonomy import is_low_bit_quant
                _pm_model = getattr(self, "primary_model", "") or ""
                _skip_sanitizer = is_low_bit_quant(_pm_model)
                if _skip_sanitizer:
                    logger.debug(
                        "V18.2.29: skipping prompt_sanitizer for low-bit "
                        "model '%s' (fence tags confuse the quant)",
                        _pm_model,
                    )
                else:
                    try:
                        from core.llm.prompt_sanitizer import is_untrusted_wrapped, wrap_untrusted
                        if not is_untrusted_wrapped(value):
                            value = wrap_untrusted(
                                value,
                                log_callback=lambda msg, level: logger.log(
                                    getattr(logging, level, logging.WARNING), msg
                                ),
                            ).text
                    except Exception as exc:
                        # Defense-in-depth: never let the sanitizer block a
                        # conversion. If it crashes, fall through with the raw
                        # text (the fence wrapping is a hardening, not a gate).
                        logger.debug(
                            "prompt_sanitizer.wrap_untrusted failed (%s: %s) — "
                            "substituting raw text (injection defense degraded)",
                            type(exc).__name__, exc,
                        )
            template = template.replace("{{" + key + "}}", value)
        # V0.05 (rig audit F9b): source-relative length placeholders + the
        # legacy-absolute-number backstop. When the caller passed the chapter
        # ``text`` (every summarisation prompt does), the scaled targets are
        # computed from it and substituted; templates without the placeholders
        # and user-edited copies still carrying the old absolute ranges
        # ("800-1200 word", "20-40 distinct", …) get them replaced with the
        # scaled numbers — the expansion-by-instruction class can never
        # re-enter through an edited template.
        if "text" in variables and variables.get("text"):
            try:
                from core.summarisation.length_policy import (
                    apply_backstop,
                    bullet_range_phrase,
                    count_source_words,
                    exec_words_phrase,
                    thorough_words_phrase,
                )
                _sw = count_source_words(str(variables["text"]))
                _scaled = {
                    "exec_words": exec_words_phrase(_sw),
                    "bullet_range": bullet_range_phrase(_sw),
                    "thorough_words": thorough_words_phrase(_sw),
                }
                for _pk, _pv in _scaled.items():
                    template = template.replace("{{" + _pk + "}}", _pv)
                template = apply_backstop(template, _sw)
            except Exception as _lp_e:
                logger.debug(
                    "length-policy substitution skipped (%s: %s) — template"
                    " rendered unchanged",
                    type(_lp_e).__name__, _lp_e,
                )
        return template

    def get_default(self) -> str:
        """Return the name of the default prompt."""
        return _DEFAULT_PROMPT_NAME

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_frontmatter(template: str) -> tuple[dict[str, str], str]:
        """V18.5 (Phase 3, Task 3.5): Parse YAML front-matter from a prompt template.

        If the template starts with ``---\\n...\\n---``, extracts the
        key:value pairs between the delimiters (simple parsing — no nested
        YAML, no lists, just ``key: value`` lines). Returns
        ``(frontmatter_dict, body_without_frontmatter)``.

        If no front-matter is present, returns ``({}, template)`` unchanged.
        Quotes around values are stripped: ``version: "18.5.0"`` → ``"18.5.0"``.
        """
        m = _FRONTMATTER_RE.match(template)
        if not m:
            return {}, template
        block = m.group(1)
        body = template[m.end():]
        fm: dict[str, str] = {}
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            # Strip surrounding quotes: "18.5.0" → 18.5.0
            if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                val = val[1:-1]
            fm[key] = val
        return fm, body

    def _strip_and_log_frontmatter(self, name: str, template: str) -> str:
        """V18.5 (Phase 3, Task 3.5): Strip front-matter + log the version.

        Called from ``render_template`` before variable substitution. Parses
        the front-matter (if any), logs the resolved ``version`` and
        ``compatible_model_class`` at DEBUG level on the FIRST render of each
        prompt name (avoids log spam on subsequent renders), and returns the
        body without the front-matter (so the LLM never sees it).
        """
        fm, body = self._parse_frontmatter(template)
        if fm and name not in _logged_versions:
            _version = fm.get("version", "unversioned")
            _model_class = fm.get("compatible_model_class", "any")
            logger.debug(
                "PromptManager: rendering '%s' (version=%s, "
                "compatible_model_class=%s)",
                name, _version, _model_class,
            )
            _logged_versions.add(name)
        return body

    @staticmethod
    def _name_to_rel(name: str) -> Path:
        """Convert a prompt name (possibly namespaced) to a relative Path."""
        # Normalize backslashes (Windows) and split on "/"
        parts = [p for p in name.replace("\\", "/").split("/") if p and p != "."]
        if not parts:
            return Path(f"{_DEFAULT_PROMPT_NAME}.md")
        return Path(*parts).with_suffix(".md")
