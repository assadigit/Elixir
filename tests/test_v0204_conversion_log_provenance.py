"""V0.20.4 (Quality Campaign) — Tests for the conversion-log header provenance stamp.

The conversion log now self-identifies its app version + run_id in the
HEADER (the 3rd line), the same self-identification the summary files have.
This makes it impossible to confuse an old log with a new one: the very
first comment in every conversion log reads
``<!-- generated-by: Elixir v<version> | run_id=<id> -->``.

Root cause this fixes: the V0.20.3 ch.2 audits found the user uploading the
old V0.18 conversion log alongside the new V0.20.3 summary (3 consecutive
runs). The log's only version line was ~line 61 (App version: 0.18, from the
settings logger), buried in the settings dump — easy to miss. A header-level
stamp makes the version + run_id unmissable.
"""

from __future__ import annotations

import re
from pathlib import Path

from utils.logging import ConversionLogger


class TestConversionLogProvenanceStamp:
    """V0.20.4: the conversion log header carries a provenance stamp with the
    app version + a conversion run_id, parseable by core.system.provenance."""

    def test_log_header_has_provenance_stamp(self, tmp_path: Path):
        """The conversion log's 3rd line is a provenance comment with the app
        version + a run_id — the same format the summary files use."""
        logger = ConversionLogger(tmp_path, "TestBook")
        logger.log("test message", "INFO")
        logger.close()
        text = logger.log_path.read_text(encoding="utf-8")
        # The header: line 1 title, line 2 blank, line 3 "Started at:", line 4
        # blank, line 5 the provenance stamp.
        lines = text.splitlines()
        assert lines[0] == "# Conversion Log: TestBook"
        assert lines[2].startswith("Started at:")
        # The provenance stamp is a comment with the app version + run_id.
        stamp_lines = [l for l in lines if l.startswith("<!-- generated-by: Elixir")]
        assert len(stamp_lines) == 1, f"exactly one provenance stamp; got {stamp_lines}"
        stamp = stamp_lines[0]
        # The stamp matches the provenance parser's regex.

        # parse_provenance expects the stamp in a summary-shaped file, but
        # the regex is the same — test the raw regex directly.
        m = re.search(
            r"generated-by:\s*Elixir v(?P<version>\S+)\s*\|\s*run_id=(?P<run_id>[A-Za-z0-9_-]+)",
            stamp,
        )
        assert m, f"stamp {stamp!r} does not match the provenance regex"
        version = m.group("version")
        run_id = m.group("run_id")
        # The version is non-empty (reads from the VERSION file).
        assert version, "the app version must be stamped"
        # The run_id is the conversion-level identifier (YYYYMMDD-HHMMSS-<8hex>).
        assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{8}$", run_id), (
            f"run_id {run_id!r} must be YYYYMMDD-HHMMSS-<8hex>"
        )

    def test_log_overwrites_on_new_run(self, tmp_path: Path):
        """V0.20.4 root cause + V0.4.25 upgrade: the log used to open the SAME
        stable path in 'w' mode, so a new run overwrote the old log (and the
        operator's file-transfer cache kept serving the first upload's bytes
        for 20+ "genuinely new" runs). Since V0.4.25 each run writes its OWN
        run-stamped file — both logs coexist, each stamped with its own
        version + run_id in the filename AND the header."""
        # First run
        logger1 = ConversionLogger(tmp_path, "TestBook")
        logger1.log("first run", "INFO")
        logger1.close()
        first_text = logger1.log_path.read_text(encoding="utf-8")
        first_stamp = [
            l for l in first_text.splitlines() if l.startswith("<!-- generated-by: Elixir")
        ][0]

        # Second run — its own uniquely-named log (no collision, no truncation)
        logger2 = ConversionLogger(tmp_path, "TestBook")
        logger2.log("second run", "INFO")
        logger2.close()
        second_text = logger2.log_path.read_text(encoding="utf-8")
        second_stamp = [
            l for l in second_text.splitlines() if l.startswith("<!-- generated-by: Elixir")
        ][0]

        # The two stamps have DIFFERENT run_ids (each run generates a new one).
        assert first_stamp != second_stamp, (
            "each new ConversionLogger generates a new run_id; the stamps must differ"
        )
        # V0.4.25: each run's log is its own file — both survive.
        assert logger1.log_path != logger2.log_path
        assert logger1.log_path.exists() and logger2.log_path.exists()
        # Each log carries ONLY its own run's content.
        assert "first run" in first_text and "first run" not in second_text
        assert "second run" in second_text

    def test_conversion_run_id_attribute_exists(self, tmp_path: Path):
        """The ConversionLogger exposes the conversion run_id as an attribute
        so the converter/Summarizer can read it (for correlation with the
        summary files' run_id)."""
        logger = ConversionLogger(tmp_path, "TestBook")
        assert hasattr(logger, "_conversion_run_id")
        assert logger._conversion_run_id, "the conversion run_id must be set"
        assert re.match(r"^\d{8}-\d{6}-[0-9a-f]{8}$", logger._conversion_run_id)
        logger.close()

    def test_stamp_never_breaks_log_on_import_failure(self, tmp_path: Path, monkeypatch):
        """If the provenance import crashes, the log is still created — the
        stamp is skipped, but the log file is valid (fail-open)."""
        import core.system.provenance as prov_mod

        # Make get_app_version raise during the _open() call.
        def _boom():
            raise RuntimeError("get_app_version exploded")

        monkeypatch.setattr(prov_mod, "get_app_version", _boom)
        logger = ConversionLogger(tmp_path, "TestBook")
        logger.log("test", "INFO")
        logger.close()
        text = logger.log_path.read_text(encoding="utf-8")
        # The log was created with a valid header even though the stamp failed.
        assert "# Conversion Log: TestBook" in text
        assert "Started at:" in text
