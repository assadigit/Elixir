"""V0.6.61 -- the off-thread scan + the sha256 contract.

THE TRIGGER (the V0.6.60 worklog's next-phase candidates #2 + #3):

  2. "The residual V0.6.59 accepted risk: a deliberately crafted GGUF
     in a scanned dir can still cost ~0.5s of UI-thread parse time --
     the off-thread scan remains the future fix (the downloader dialog
     itself is already fully threaded)."
  3. "A full-file sha256 cross-check on download (the HF API exposes
     the xet hash) -- nicety; the header check + size check + ETag
     resume already cover the realistic failure modes."

WHAT V0.6.61 ADDS
-----------------
  1. THE OFF-THREAD SCAN: the GGUF combo's disk scan (settings read +
     directory walk + GGUF header reads -- the V0.6.59 catalog) now
     runs on a SimpleWorker. The combo shows a "(scanning…)"
     placeholder and populates when the result lands; a refresh
     requested mid-scan is remembered and re-dispatched (the
     browse-during-scan race). The scan closure touches NO widget --
     pinned by AST (no "self." inside the nested worker function).
     Plain-Python flags (not the worker object's is_running()) guard
     re-entry: a deleteLater'd QObject wrapper must never be touched
     again after it finishes.
  2. THE SHA256 CONTRACT: every DOWNLOAD_CATALOG entry carries the
     handy-computer PUBLISHED sha256 (the HF API's lfs.sha256 -- the
     content hash, MECHANISM PROVEN LIVE this session: whisper-tiny-
     Q4_K_M.gguf downloaded in full, its sha256 matched the API value
     byte-for-byte). download() hashes the stream incrementally (the
     resume path hashes the .part prefix first -- chunked, never
     slurped), and a mismatch deletes the wrong bytes + reports the
     honest error: a CORRUPTED download can never be installed. This
     closes the last realistic corruption hole: a file with a valid
     GGUF header + the right size but garbage tensor bytes would
     otherwise pass every check and crash the CLI minutes into a run.

LIVE EVIDENCE this session:
  - lfs.sha256 for all 5 catalog files fetched (turbo Q5_K_M
    977b5db4…3203e36 etc. -- pinned below).
  - whisper-tiny-Q4_K_M.gguf (43,621,792 bytes) downloaded in full:
    sha256 = 86e1100470df173fa9079f941e33e4d52d11c03923407dd1ec51fd
    1937d8e609 == the API's lfs.sha256. The API hash IS the content
    hash.
  - The tiny file also parsed with the V0.6.59 reader: verified
    whisper / 'Whisper Tiny' / Q4_K_M / 38M.

TEST LAYOUT
-----------
  A. the off-thread scan      -- dialog AST pins (house style)
  B. the sha256 download      -- hermetic server (reused from v0660)
  C. the catalog hashes       -- pinned to the live-verified values
  D. the downloader dialog    -- AST pins (passes + reports the hash)
"""

from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# House precedent (test_p2_summarizer_* / test_v0660 cross-test
# imports): reuse the v0660 hermetic HTTP server (whose own fixtures
# reuse the v0659 GGUF byte builder -- verified against the real
# handy-computer header shape).
from test_v0660_model_downloader import _make_remote_whisper, _Server  # noqa: E402

_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_DL_DIALOG = (
    _project_root / "ui_qt" / "views" / "service_dialogs" / "model_download_dialog.py"
)

from core.transcribe import model_downloader as md  # noqa: E402


@pytest.fixture()
def srv():
    """The v0660 hermetic server (Range/206 + If-Range + ETag + the
    lie modes), instantiated locally -- fixtures themselves are not
    cross-importable, the server class is."""
    s = _Server()
    yield s
    s.close()


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


def _cancel_after_one_chunk(srv, dest, **kw):
    """The shared helper: cancel a download after exactly one chunk ->
    a .part + sidecar holding chunk_bytes of the file."""
    flag = {"stop": False}

    def _cancel() -> bool:
        return flag["stop"]

    def _on_progress(p: dict) -> None:
        if p["done"] > 0:
            flag["stop"] = True

    res = md.download(
        srv.url("model.gguf"),
        dest,
        on_progress=_on_progress,
        should_cancel=_cancel,
        chunk_bytes=256 * 1024,
        timeout=10,
        **kw,
    )
    assert res["cancelled"] is True
    return res


# ═════════════════════════════════════════════════════════════════════════════
# A. the off-thread scan -- dialog AST pins (the house style: no
#    PySide6 in this sandbox; structure + wiring are pinned, the scan
#    behavior itself is Qt-free in the catalog and already pinned).
# ═════════════════════════════════════════════════════════════════════════════


class TestOffThreadScan:
    @pytest.fixture(scope="class")
    def dialog_tree(self):
        return ast.parse(_DIALOG.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def dialog_src(self):
        return _DIALOG.read_text(encoding="utf-8")

    def test_refresh_spawns_a_worker_not_disk_io(self, dialog_tree):
        """THE pin: _refresh_cpp_models must run its scan on a
        SimpleWorker -- the V0.6.59 residual UI-freeze risk (a crafted
        GGUF could cost ~0.5s of UI-thread parse per file) is closed
        only if the scan genuinely leaves the UI thread. V0.6.61
        review fix: presence-only was too weak (a decorative worker +
        a synchronous scan would pass) -- the catalog calls must live
        ONLY inside the worker closure, never at the method's top
        level."""
        refresh = _method(dialog_tree, "_refresh_cpp_models")
        assert "SimpleWorker" in ast.unparse(refresh)
        closure = next(
            (n for n in ast.walk(refresh)
             if isinstance(n, ast.FunctionDef) and n.name != "_refresh_cpp_models"),
            None,
        )
        assert closure is not None, "the scan closure is missing"
        closure_src = ast.unparse(closure)
        for catalog_call in ("scan_model_dirs", "describe_model_file", "model_search_dirs"):
            assert catalog_call in closure_src, (
                f"{catalog_call} must run inside the worker closure"
            )
        # and NOT outside it: AST-identity filtering (string surgery on
        # unparse output is formatting-fragile) -- every call to the
        # catalog must live INSIDE the closure's subtree.
        closure_node_ids = {id(n) for n in ast.walk(closure)}
        outside_calls = [
            n.lineno for n in ast.walk(refresh)
            if id(n) not in closure_node_ids
            and isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("scan_model_dirs", "describe_model_file", "model_search_dirs")
        ]
        assert not outside_calls, (
            f"catalog disk-IO calls at lines {outside_calls} run OUTSIDE the "
            "worker closure -- the UI thread would touch the disk"
        )

    def test_scan_closure_touches_no_widget(self, dialog_tree, dialog_src):
        """Thread safety, pinned TWO ways (V0.6.61 review fix -- the
        plain string sweep was evadable by aliasing): (1) no "self."
        text; (2) the closure's FREE VARIABLES must all be module
        globals (imports) — any reference to dialog state (self, a
        local alias, a widget) would surface as a free name that is
        not a module-level import."""
        refresh = _method(dialog_tree, "_refresh_cpp_models")
        closures = [
            n for n in ast.walk(refresh)
            if isinstance(n, ast.FunctionDef) and n.name != "_refresh_cpp_models"
        ]
        assert closures, "the scan closure is missing from _refresh_cpp_models"
        module_imports = {
            n.names[i].asname or n.names[i].name.split(".")[0]
            for n in ast.walk(dialog_tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for i in range(len(n.names))
        }
        module_imports |= {
            n.targets[0].id
            for n in dialog_tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Name)
        }
        import builtins
        for closure in closures:
            body = ast.unparse(closure)
            assert "self." not in body, (
                f"the worker closure {closure.name!r} touches dialog state"
            )
            loads, stores, args = set(), set(), set()
            for n in ast.walk(closure):
                if isinstance(n, ast.Name):
                    (loads if isinstance(n.ctx, ast.Load) else stores).add(n.id)
                elif isinstance(n, ast.arguments):
                    for a in list(n.args) + list(n.kwonlyargs):
                        args.add(a.arg)
            free = loads - stores - args - set(dir(builtins))
            non_module = free - module_imports
            assert not non_module, (
                f"the closure {closure.name!r} references non-module names "
                f"{sorted(non_module)} -- dialog state captured on the "
                "worker thread (thread-safety violation)"
            )

    def test_the_worker_handle_stays_write_only(self, dialog_tree):
        """V0.6.61 review fix: self._cpp_scan_worker is a LIFETIME
        ANCHOR only (the auto-deleteLater'd worker must never be
        touched again). Pin: it may appear ONLY as an assignment
        target -- a read anywhere (an is_running() guard in some
        future method) reintroduces the deleted-wrapper crash."""
        bad_reads = [
            n.lineno for n in ast.walk(dialog_tree)
            if isinstance(n, ast.Attribute) and n.attr == "_cpp_scan_worker"
            and not isinstance(n.ctx, ast.Store)
        ]
        assert not bad_reads, (
            f"self._cpp_scan_worker is READ at lines {bad_reads} -- the "
            "handle must stay write-only (deleteLater'd wrapper)"
        )

    def test_the_scan_placeholder_is_shown_while_scanning(self, dialog_tree):
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "(scanning" in refresh
        # the placeholder itself is added with signals blocked (no
        # spurious _on_cpp_model_selected save of the placeholder)
        assert "blockSignals" in refresh

    def test_plain_flag_guard_not_qobject_is_running(self, dialog_tree, dialog_src):
        """The re-entry guard must be a plain-Python flag: a
        deleteLater'd SimpleWorker wrapper must never be asked
        is_running() again (PySide6 raises RuntimeError on a deleted
        C++ object -- the second 🔄 click would crash)."""
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "_cpp_scan_running" in refresh
        assert "is_running()" not in refresh, (
            "the scan guard must not call is_running() on a possibly-"
            "deleteLater'd worker object"
        )

    def test_flags_initialized_before_the_first_scan(self, dialog_tree):
        """The V0.6.55 construction-order class, EXTENDED: the guard
        flags must exist BEFORE __init__ calls _refresh_cpp_models()
        (which now reads them) -- the exact AttributeError shape the
        dialog died of in V0.6.53/55."""
        init = _method(dialog_tree, "__init__")
        calls = [
            n.lineno for n in ast.walk(init)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_refresh_cpp_models"
        ]
        assert calls, "__init__ must call _refresh_cpp_models()"
        first_call = min(calls)
        for flag in ("_cpp_scan_running", "_cpp_scan_pending"):
            assigns = [
                n.lineno for n in ast.walk(init)
                if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == flag
            ]
            assert assigns, f"self.{flag} never initialized in __init__"
            assert max(assigns) < first_call, (
                f"self.{flag} initialized at {max(assigns)} but the first "
                f"_refresh_cpp_models() call is at {first_call}"
            )

    def test_scan_result_lands_in_a_populate_method(self, dialog_tree):
        """The populate contract (V0.6.59, unchanged): saved-first,
        selected, blockSignals, per-item tooltips, the empty
        placeholder offering the download -- now in the finished-slot
        _on_cpp_models_scanned."""
        populate = ast.unparse(_method(dialog_tree, "_on_cpp_models_scanned"))
        for needle in (
            "addItem", "setItemData", "ToolTipRole", "setCurrentIndex",
            "blockSignals", "(no Whisper", "Get models",
        ):
            assert needle in populate, f"{needle!r} missing from _on_cpp_models_scanned"
        # and the worker's finished signal is wired to it
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "_on_cpp_models_scanned" in refresh

    def test_the_worker_failure_path_is_honest(self, dialog_tree):
        """The scan closure is best-effort throughout, but the worker
        machinery itself failing must leave an honest retryable state
        (not a stuck 'scanning…' placeholder forever)."""
        failed = ast.unparse(_method(dialog_tree, "_on_cpp_models_scan_failed"))
        assert "_cpp_scan_running" in failed  # the flag is RELEASED
        assert "blockSignals" in failed
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "_on_cpp_models_scan_failed" in refresh  # wired

    def test_the_browse_during_scan_race_is_remembered(self, dialog_tree):
        """A refresh requested while a scan is in flight (the operator
        browsed to a file while the dialog-open scan was still walking
        a big Downloads dir) must be REMEMBERED and re-dispatched when
        the in-flight scan lands -- otherwise the picked model never
        appears (the in-flight scan started before the setting was
        saved)."""
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "_cpp_scan_pending" in refresh  # set when mid-scan
        populate = ast.unparse(_method(dialog_tree, "_on_cpp_models_scanned"))
        assert "_cpp_scan_pending" in populate  # re-dispatched on landing
        assert "_refresh_cpp_models" in populate  # the re-dispatch itself

    def test_the_scan_still_uses_the_catalog(self, dialog_tree):
        """The V0.6.59 contract: the scan closure still goes through
        core.transcribe.model_catalog (scan_model_dirs /
        model_search_dirs) -- the worker changed WHERE it runs, not
        WHAT it scans."""
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "model_catalog" in refresh
        assert "scan_model_dirs" in refresh
        assert "model_search_dirs" in refresh

    def test_the_tooltip_facts_are_built_in_the_scan(self, dialog_tree):
        """The V0.6.60 tooltip contract: the per-item tooltips are
        built where the items are built (the scan closure -- on the
        worker thread, from the header the scan already read)."""
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "format_model_tooltip" in refresh
        assert "format_model_display" in refresh


# ═════════════════════════════════════════════════════════════════════════════
# B. the sha256 download -- hermetic server (the v0660 machinery)
# ═════════════════════════════════════════════════════════════════════════════


class TestSha256Download:
    def test_matching_hash_passes_and_reports_it(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        good = hashlib.sha256(data).hexdigest()
        res = md.download(
            srv.url("model.gguf"),
            tmp_path,
            expected_sha256=good,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is True
        assert res["sha256_ok"] is True
        assert (tmp_path / "model.gguf").read_bytes() == data

    def test_wrong_hash_fails_deletes_the_bytes_and_names_both(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        bad = "0" * 64
        res = md.download(
            srv.url("model.gguf"),
            tmp_path,
            expected_sha256=bad,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is False
        assert res["cancelled"] is False
        assert res["sha256_ok"] is False
        err = str(res["error"])
        assert "sha256" in err.lower()
        # V0.6.61 review fix: BOTH hashes are named (the full expected
        # AND the got digest) -- the paste-back settles it outright.
        assert bad in err
        assert hashlib.sha256(data).hexdigest() in err
        # the wrong bytes are DELETED (resuming them would reproduce
        # the same wrong bytes -- they are garbage, not progress)
        assert not (tmp_path / "model.gguf").exists()
        assert not (tmp_path / "model.gguf.part").exists()

    def test_no_expected_hash_leaves_it_unchecked_and_honest(self, srv, tmp_path):
        _make_remote_whisper(srv, "model.gguf", 600_000)
        res = md.download(
            srv.url("model.gguf"), tmp_path, chunk_bytes=256 * 1024, timeout=10
        )
        assert res["ok"] is True
        assert res["sha256_ok"] is None  # not checked, honestly

    def test_resumed_download_verifies_the_whole_file(self, srv, tmp_path):
        """The resume path hashes the .part prefix first (chunked,
        never slurped) and continues -- the sha guarantee survives a
        cancel+resume."""
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        good = hashlib.sha256(data).hexdigest()
        dest = tmp_path / "dest"
        dest.mkdir()
        _cancel_after_one_chunk(srv, dest)  # .part holds 256 KiB
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is True
        assert res["resumed_from"] == 256 * 1024
        assert res["sha256_ok"] is True
        assert (dest / "model.gguf").read_bytes() == data

    def test_republished_remote_restart_forwards_the_hash(self, srv, tmp_path):
        """V0.6.61 review fix (the misleading name is gone): a
        republished remote forces the If-Range 200 restart, and the
        RESTART must forward expected_sha256 -- the fresh full-body
        bytes still have to prove out against the published hash."""
        _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        _cancel_after_one_chunk(srv, dest)  # .part + sidecar hold 256 KiB of OLD
        # the remote is republished: different bytes, different etag
        new_data = bytes((i * 11 + 5) % 256 for i in range(600_000))
        srv.httpd.files["model.gguf"] = new_data
        srv.httpd.etag = '"etag-v2"'
        good_new = hashlib.sha256(new_data).hexdigest()
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good_new,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        # If-Range mismatches -> restart from zero -> full new bytes
        # -> the FORWARDED hash still verifies them
        assert res["ok"] is True
        assert res["resumed_from"] == 0
        assert res["sha256_ok"] is True
        assert (dest / "model.gguf").read_bytes() == new_data

    def test_shrunk_remote_416_restart_forwards_the_hash(self, srv, tmp_path):
        """V0.6.61 review fix (the leaf reviewer's SHOULD-FIX): the
        recursive 416 restart path must forward expected_sha256 too.
        The shrunk scenario (v0660's) + a hash: the fresh full-body
        restart of the TINY replacement file proves out."""
        _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        _cancel_after_one_chunk(srv, dest)  # .part holds 256 KiB of the OLD big file
        # the remote shrinks below the .part -> the Range 416s ->
        # probe sees size != part -> one fresh restart from zero
        tiny = b"GGUF" + b"\x00" * 96  # 100 bytes
        srv.httpd.files["model.gguf"] = tiny
        good_tiny = hashlib.sha256(tiny).hexdigest()
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good_tiny,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is True
        assert res["resumed_from"] == 0
        assert res["sha256_ok"] is True  # the RESTART verified the fresh bytes
        assert (dest / "model.gguf").read_bytes() == tiny

    def test_corrupted_resume_prefix_fails_the_hash_and_deletes(self, srv, tmp_path):
        """V0.6.61 review fix (the leaf reviewer's SHOULD-FIX): the
        RESUME-route mismatch deletion, pinned directly. A .part whose
        prefix was corrupted on disk (bit rot / an interrupted outer
        tool) + a matching etag -> a genuine 206 resume -> the combined
        digest is wrong -> _sha_fail deletes everything."""
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        good = hashlib.sha256(data).hexdigest()
        dest = tmp_path / "dest"
        dest.mkdir()
        _cancel_after_one_chunk(srv, dest)  # .part + sidecar, 256 KiB
        # corrupt one byte of the .part prefix (the etag sidecar still
        # matches -- the server happily serves the 206 suffix)
        part = dest / "model.gguf.part"
        raw = bytearray(part.read_bytes())
        raw[100] ^= 0xFF
        part.write_bytes(bytes(raw))
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is False
        assert res["cancelled"] is False
        assert res["sha256_ok"] is False
        # the combined digest (corrupted prefix + real suffix) is NAMED
        combined = hashlib.sha256(bytes(raw) + data[256 * 1024 :]).hexdigest()
        assert combined in str(res["error"])
        # and the wrong bytes are deleted, nothing installed
        assert not (dest / "model.gguf").exists()
        assert not (dest / "model.gguf.part").exists()
        assert not (dest / "model.gguf.part.etag").exists()

    def test_a_cdnc_like_server_that_ignores_if_range_is_caught_by_the_hash(
        self, srv, tmp_path
    ):
        """THE LIVE-DISCOVERED behavior, pinned: Hugging Face's xet CDN
        serves 206 even when If-Range STALE-matches (probed live this
        session: Range bytes=1000- + a bogus If-Range -> 206, not 200).
        The V0.6.60 ETag/If-Range defense is therefore server-dependent
        -- against the real CDN a stale .part + a republished remote
        WOULD mix bytes, and the sha256 is the gate that actually
        catches it. This pin reproduces that CDN behavior exactly: the
        server honors Range but ignores If-Range validation."""
        old_data = _make_remote_whisper(srv, "model.gguf", 600_000)
        good_old = hashlib.sha256(old_data).hexdigest()
        dest = tmp_path / "dest"
        dest.mkdir()
        _cancel_after_one_chunk(srv, dest)  # .part + sidecar hold 256 KiB of OLD
        # the remote is republished (different bytes) BUT the server
        # ignores If-Range validation -- it serves the 206 anyway
        new_data = bytes((i * 13 + 7) % 256 for i in range(600_000))
        srv.httpd.files["model.gguf"] = new_data
        srv.httpd.etag = '"etag-v2"'
        srv.httpd.ignore_if_range = True
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good_old,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        # the mixed file (old prefix + new suffix) has the right SIZE
        # and would pass the header check -- only the hash catches it
        assert res["ok"] is False
        assert res["sha256_ok"] is False
        assert res["resumed_from"] == 256 * 1024  # the 206 really resumed
        mixed = hashlib.sha256(old_data[: 256 * 1024] + new_data[256 * 1024 :]).hexdigest()
        assert mixed in str(res["error"])
        # and the corrupt mix never lands under the real name
        assert not (dest / "model.gguf").exists()
        assert not (dest / "model.gguf.part").exists()

    def test_416_already_complete_recovery_verifies_the_hash(self, srv, tmp_path):
        """The 416 'already complete' recovery must not skip the hash
        gate: a complete-size .part with WRONG bytes is deleted, not
        renamed into place."""
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        # a 'complete' .part with corrupted bytes + a matching sidecar
        corrupted = bytearray(data)
        corrupted[-1] ^= 0xFF
        (dest / "model.gguf.part").write_bytes(bytes(corrupted))
        (dest / "model.gguf.part.etag").write_text('"etag-v1"', encoding="utf-8")
        good = hashlib.sha256(data).hexdigest()
        res = md.download(
            srv.url("model.gguf"),
            dest,
            expected_sha256=good,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is False
        assert res["sha256_ok"] is False
        assert "sha256" in str(res["error"]).lower()
        # the corrupted bytes are gone; nothing was installed
        assert not (dest / "model.gguf").exists()
        assert not (dest / "model.gguf.part").exists()

    def test_a_short_read_is_reported_before_any_hash_confusion(self, srv, tmp_path):
        """The declared-size lie (v0660's pin) still reports the
        INCOMPLETE error -- the hash check must not mask it (the file
        never reached the expected size)."""
        _make_remote_whisper(srv, "model.gguf", 600_000)
        srv.httpd.lie_extra = 5000
        res = md.download(
            srv.url("model.gguf"),
            tmp_path,
            expected_sha256=hashlib.sha256(b"anything").hexdigest(),
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is False
        assert "incomplete" in str(res["error"]).lower()
        assert (tmp_path / "model.gguf.part").exists()  # kept for resume


# ═════════════════════════════════════════════════════════════════════════════
# C. the catalog hashes -- pinned to the live-verified HF API values
# ═════════════════════════════════════════════════════════════════════════════


class TestCatalogHashes:
    def test_every_entry_carries_a_wellformed_sha256(self):
        for spec in md.DOWNLOAD_CATALOG:
            assert spec.sha256, f"{spec.key} has no sha256"
            assert len(spec.sha256) == 64 and all(
                c in "0123456789abcdef" for c in spec.sha256
            ), f"{spec.key}: not a 64-hex sha256"

    def test_the_hashes_are_the_live_verified_values(self):
        """Pinned to the HF API state verified LIVE this session (and
        the MECHANISM proven: whisper-tiny-Q4_K_M.gguf downloaded in
        full -- its sha256 matched the API's lfs.sha256 exactly)."""
        by_key = {s.key: s.sha256 for s in md.DOWNLOAD_CATALOG}
        assert by_key["large-v3-turbo-Q5_K_M"] == (
            "977b5db4e004349dffd1ab9caa10ba5aaba3fc3edd3ba72cadb84328a3203e36"
        )
        assert by_key["large-v3-turbo-Q8_0"] == (
            "b2e30cc286bc9f3aba4db9099fc7403543497c05ce7100d0d83091ddfd25a183"
        )
        assert by_key["large-v3-turbo-F16"] == (
            "e1d0144e9afc9f479d9e51fc92c7dea9dc36059655eeb3819f16ad2de779046a"
        )
        assert by_key["large-v3-Q5_K_M"] == (
            "6053d0fd69a0fd48b8fea5ea7a52b9e0cde389343566fa30e453a1b2b258dc38"
        )
        assert by_key["large-v3-Q8_0"] == (
            "2fa1a5f179f8a511a53e2108db270aa4af3ce08cd976af4180e2854666bb4ba3"
        )

    def test_the_hashes_are_unique(self):
        hashes = [s.sha256 for s in md.DOWNLOAD_CATALOG]
        assert len(hashes) == len(set(hashes))


# ═════════════════════════════════════════════════════════════════════════════
# D. the downloader dialog -- AST pins (the hash is passed + reported)
# ═════════════════════════════════════════════════════════════════════════════


class TestDownloadDialogHashWiring:
    @pytest.fixture(scope="class")
    def src(self):
        return _DL_DIALOG.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tree(self, src):
        return ast.parse(src)

    def test_the_worker_passes_the_published_hash(self, tree):
        work = ast.unparse(_method(tree, "_download_work"))
        assert "sha256" in work

    def test_the_success_message_names_the_sha256_proof(self, tree):
        done = ast.unparse(_method(tree, "_on_download_done"))
        assert "sha256" in done

    def test_the_failure_path_can_mention_the_hash_error(self, tree):
        """Not a structural requirement (the generic error box shows
        any error text) -- but the CANCEL/verify branches must not
        crash on the new result key."""
        done = ast.unparse(_method(tree, "_on_download_done"))
        assert "sha256_ok" in done
