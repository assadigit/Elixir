"""V0.6.19 (W-e2): a pure-Python validator for podcast scripts.

Why this exists
---------------
Before V0.6.19, the wizard's "Generate Podcast" button called
``generate_podcast_audio`` directly with whatever script the user had
edited. If the script was malformed — empty lines, a line with the
wrong host value (e.g., "C" instead of "A"/"B"), a 200-line monster
that would take 4 hours to synthesize, a single line with no voice
assigned — the failure surfaced MID-GENERATION, after the user had
already waited for the TTS subprocess to spin up and the first line
to synthesize. The error message was "Podcast generation STOPPED at
line N" with no preview of what would go wrong.

This module flips that around. The wizard's "Generate Podcast" button
calls ``validate_script(script, host_a_voice, host_b_voice, settings)``
FIRST; the result is a list of (severity, message) tuples. Errors
block generation (the wizard shows them in a red banner); warnings
allow generation (yellow banner, "Continue anyway?" button); info
just logs. The user sees the problem BEFORE the TTS subprocess starts,
not after.

The validator is deliberately pure-Python — no Qt, no torch, no
soundfile — so it can run in any context (the wizard UI, a CLI, a
test, a future web view) and so it can be unit-tested without any
heavy deps.

The validation rules (each maps to a real failure mode the audio
generator or the operator's report named):

  ERROR-level (blocks generation):
    E1. Empty script (zero lines) — ``generate_podcast_audio`` returns
        None with "No script lines to synthesize".
    E2. A line with an invalid host value (not "A" or "B") — the audio
        generator's ``voice = host_a_voice if line.host == "A" else
        host_b_voice`` would silently assign Host B's voice to any
        non-"A" value, including typos like "a" / "Host A" / "".
    E3. A line with empty text AND no vocal cues — TTS would receive
        "" and either crash or produce a 0-byte WAV.
    E4. Host B voice is empty in conversational mode — every Host B
        line would synthesize with voice="" which the engine's
        ``or "af_heart"`` fallback patches SILENTLY; the validator
        makes it explicit so the user knows.

  WARNING-level (allows generation, but worth flagging):
    W1. Script longer than 50 lines — at ~5s/line on CPU that's a 4-
        minute generation; the user should know.
    W2. Script shorter than 3 lines — likely too short for a real
        podcast; the user may have edited too aggressively.
    W3. No intro segment — the script's first line should be tagged
        ``segment_type="intro"`` per the script_generator contract;
        if it isn't, the script may have been hand-edited.
    W4. No conclusion segment — same; the script's last line should
        be ``segment_type="conclusion"``.
    W5. Host A voice is empty (lecture mode tolerates this — Kokoro
        fallback; but the user should be told).

  INFO-level (just logs, doesn't block or warn):
    I1. The script's title is empty — the audio file will be saved as
        ``podcast_YYYYMMDD_HHMMSS.wav`` instead of the title.
    I2. The script has bullets_input but bullets_missing > 0 — the
        anti-hallucination system force-inserted those bullets; the
        script may have low coverage.
    I3. A line's source_ref is empty — the anti-hallucination audit
        trail has a gap for that line.

The validator returns a ``ValidationResult`` (a small dataclass) with
``.issues`` (the list of (severity, message) tuples), ``.errors``
(the ERROR-level subset), ``.warnings`` (the WARNING subset), and
``.infos`` (the INFO subset), plus a ``.ok`` property (True iff no
errors). The wizard's button calls ``result.ok`` to decide whether
to proceed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from core.podcast.script_generator import ScriptResult

# Hard thresholds — the values the audio generator's own behavior
# implies (a 200-line script at 4 it/s on CPU = ~1 hour; the operator
# would have cancelled long before). Tunable, but changing them is a
# behavior change that should be pinned by a test.
MAX_REASONABLE_LINE_COUNT = 50
MIN_REASONABLE_LINE_COUNT = 3


# Severity constants — string literals so the validator has no enum
# dependency and tests can assert on exact values.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

Severity = str  # one of the three constants above


@dataclass
class ValidationIssue:
    """One issue found by the validator.

    ``severity`` is one of ``SEVERITY_ERROR`` / ``SEVERITY_WARNING``
    / ``SEVERITY_INFO``. ``code`` is a stable identifier (e.g.
    ``"E2_INVALID_HOST"``) the wizard can switch on for custom
    messaging. ``message`` is the human-readable text the wizard
    shows the user. ``line_index`` is the 0-based index of the
    offending line (or None for script-level issues).
    """

    severity: Severity
    code: str
    message: str
    line_index: int | None = None

    def __post_init__(self) -> None:
        if self.severity not in (SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO):
            raise ValueError(
                f"ValidationIssue.severity must be one of "
                f"{SEVERITY_ERROR!r}/{SEVERITY_WARNING!r}/{SEVERITY_INFO!r}, "
                f"got {self.severity!r}"
            )


@dataclass
class ValidationResult:
    """The result of validating a script.

    ``.ok`` is True iff there are no ERROR-level issues (warnings and
    infos are allowed). The wizard's "Generate Podcast" button checks
    ``.ok``; if False, it shows the errors in a red banner and does
    NOT call ``generate_podcast_audio``. If True, it proceeds (and
    optionally shows warnings in a yellow banner with a "Continue
    anyway?" confirm).
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_INFO]

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        """``bool(result)`` is True iff ``result.ok`` — so callers can
        write ``if validate_script(...):`` instead of
        ``if validate_script(...).ok:``."""
        return self.ok


def validate_script(
    script: ScriptResult,
    host_a_voice: str = "",
    host_b_voice: str = "",
    is_conversational: bool = True,
) -> ValidationResult:
    """Validate a podcast script before audio generation.

    Args:
        script: the ScriptResult to validate.
        host_a_voice: the voice name/ID for Host A (may be empty —
            Kokoro fallback patches this silently in lecture mode).
        host_b_voice: the voice name/ID for Host B (may be empty in
            lecture mode; is an ERROR in conversational mode if any
            Host B line exists).
        is_conversational: True for 2-host mode, False for lecture
            (1-host) mode. In lecture mode, Host B lines are an error.

    Returns:
        a ValidationResult with .issues, .errors, .warnings, .infos,
        and .ok (True iff no errors).
    """
    issues: list[ValidationIssue] = []
    lines = script.lines
    total = len(lines)

    # E1. Empty script.
    if total == 0:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_ERROR,
                code="E1_EMPTY_SCRIPT",
                message=(
                    "The script is empty — there are no lines to synthesize. "
                    "Generate or import a script first."
                ),
            )
        )
        # No point checking line-level issues if there are no lines.
        return ValidationResult(issues=issues)

    # E2 + E3. Per-line checks.
    for i, line in enumerate(lines):
        # E2. Invalid host value.
        if line.host not in ("A", "B"):
            issues.append(
                ValidationIssue(
                    severity=SEVERITY_ERROR,
                    code="E2_INVALID_HOST",
                    message=(
                        f"Line {i + 1} has an invalid host value: "
                        f"{line.host!r}. Host must be 'A' or 'B'. "
                        f"(If you edited the script JSON by hand, check "
                        f"the 'host' field on line {i + 1}.)"
                    ),
                    line_index=i,
                )
            )
        # E2b. Host B line in lecture mode.
        if not is_conversational and line.host == "B":
            issues.append(
                ValidationIssue(
                    severity=SEVERITY_ERROR,
                    code="E2_HOST_B_IN_LECTURE_MODE",
                    message=(
                        f"Line {i + 1} is assigned to Host B, but the "
                        f"script is in lecture (1-host) mode. Either "
                        f"switch to conversational mode or re-assign "
                        f"line {i + 1} to Host A."
                    ),
                    line_index=i,
                )
            )
        # E3. Empty text (no cues either — the audio generator strips
        # cues before checking, so a line that's JUST cues is fine, but
        # a line with neither text nor cues is dead).
        # NOTE: we don't have the cue-stripped text here without
        # importing strip_vocal_cues; the audio generator already
        # handles "just cues" lines by inserting silence. So this
        # check only fires for lines with truly empty text.
        if not line.text or not line.text.strip():
            issues.append(
                ValidationIssue(
                    severity=SEVERITY_ERROR,
                    code="E3_EMPTY_LINE",
                    message=(
                        f"Line {i + 1} has empty text. Either remove the line or add some dialogue."
                    ),
                    line_index=i,
                )
            )

    # E4. Host B voice empty in conversational mode with Host B lines.
    if is_conversational and not host_b_voice:
        has_host_b = any(line.host == "B" for line in lines)
        if has_host_b:
            issues.append(
                ValidationIssue(
                    severity=SEVERITY_ERROR,
                    code="E4_HOST_B_VOICE_EMPTY",
                    message=(
                        "The script has Host B lines but no Host B voice "
                        "is set. Pick a voice for Host B in the Settings "
                        "section before generating."
                    ),
                )
            )

    # W1. Script too long.
    if total > MAX_REASONABLE_LINE_COUNT:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_WARNING,
                code="W1_SCRIPT_TOO_LONG",
                message=(
                    f"The script has {total} lines — at ~5s per line on "
                    f"CPU, that's ~{(total * 5) // 60} minutes of "
                    f"generation time. Consider trimming to under "
                    f"{MAX_REASONABLE_LINE_COUNT} lines for a faster run."
                ),
            )
        )

    # W2. Script too short.
    if 0 < total < MIN_REASONABLE_LINE_COUNT:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_WARNING,
                code="W2_SCRIPT_TOO_SHORT",
                message=(
                    f"The script has only {total} line(s) — that's likely "
                    f"too short for a real podcast. Did you edit too "
                    f"aggressively?"
                ),
            )
        )

    # W3. No intro segment.
    if lines[0].segment_type != "intro":
        issues.append(
            ValidationIssue(
                severity=SEVERITY_WARNING,
                code="W3_NO_INTRO",
                message=(
                    f"The script's first line is tagged "
                    f"{lines[0].segment_type!r}, not 'intro'. The "
                    f"script_generator contract expects the first line "
                    f"to be the intro. (Hand-edited scripts may violate "
                    f"this — fine to proceed, but the audit trail has a "
                    f"gap.)"
                ),
                line_index=0,
            )
        )

    # W4. No conclusion segment.
    if lines[-1].segment_type != "conclusion":
        issues.append(
            ValidationIssue(
                severity=SEVERITY_WARNING,
                code="W4_NO_CONCLUSION",
                message=(
                    f"The script's last line is tagged "
                    f"{lines[-1].segment_type!r}, not 'conclusion'. "
                    f"The script_generator contract expects the last "
                    f"line to be the conclusion."
                ),
                line_index=total - 1,
            )
        )

    # W5. Host A voice empty (lecture mode tolerates this).
    if not host_a_voice:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_WARNING,
                code="W5_HOST_A_VOICE_EMPTY",
                message=(
                    "No Host A voice is set — the audio generator will "
                    "use the Kokoro 'af_heart' fallback. Pick a voice in "
                    "the Settings section for a different sound."
                ),
            )
        )

    # I1. Empty title.
    if not script.title:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_INFO,
                code="I1_EMPTY_TITLE",
                message=(
                    "The script has no title — the audio file will be "
                    "saved as 'podcast_YYYYMMDD_HHMMSS.wav' instead of "
                    "a named file."
                ),
            )
        )

    # I2. Missing bullets (anti-hallucination force-inserted).
    if script.bullets_input and script.bullets_missing:
        issues.append(
            ValidationIssue(
                severity=SEVERITY_INFO,
                code="I2_BULLETS_FORCE_INSERTED",
                message=(
                    f"The anti-hallucination system force-inserted "
                    f"{len(script.bullets_missing)} of "
                    f"{len(script.bullets_input)} bullets (the LLM "
                    f"skipped them on the first pass). Coverage is "
                    f"{script.coverage_pct:.0f}%."
                ),
            )
        )

    # I3. Empty source_ref on any line.
    for i, line in enumerate(lines):
        if not line.source_ref:
            issues.append(
                ValidationIssue(
                    severity=SEVERITY_INFO,
                    code="I3_EMPTY_SOURCE_REF",
                    message=(
                        f"Line {i + 1} has no source_ref — the anti-"
                        f"hallucination audit trail has a gap for this "
                        f"line. (Fine to proceed, but if the script was "
                        f"hand-edited, consider adding a source_ref.)"
                    ),
                    line_index=i,
                )
            )

    return ValidationResult(issues=issues)


def format_issues_for_display(
    result: ValidationResult,
    log: Callable[[str, str], None] | None = None,
) -> str:
    """Format a ValidationResult as a multi-line string for the wizard's
    status banner. Optionally also writes each issue to a log callback.

    The format:

        ERROR (2):
          [E2_INVALID_HOST] Line 3 has an invalid host value: 'C'. ...
          [E4_HOST_B_VOICE_EMPTY] The script has Host B lines but...

        WARNING (1):
          [W1_SCRIPT_TOO_LONG] The script has 75 lines — at ~5s per...

        INFO (1):
          [I1_EMPTY_TITLE] The script has no title — the audio file...

    If there are no issues, returns "✅ No issues found — the script is
    ready to generate.".
    """
    if not result.issues:
        msg = "✅ No issues found — the script is ready to generate."
        if log:
            log(msg, "INFO")
        return msg

    parts: list[str] = []
    for severity, label in (
        (SEVERITY_ERROR, "ERROR"),
        (SEVERITY_WARNING, "WARNING"),
        (SEVERITY_INFO, "INFO"),
    ):
        subset = [i for i in result.issues if i.severity == severity]
        if not subset:
            continue
        parts.append(f"{label} ({len(subset)}):")
        for issue in subset:
            line = f"  [{issue.code}] {issue.message}"
            parts.append(line)
            if log:
                log(f"  [{issue.code}] {issue.message}", severity.upper())

    return "\n".join(parts)
