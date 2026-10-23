"""V0.6.60 -- the model downloader: "the GGUF is on Hugging Face, the
app knows what's there -- download it for me."

The V0.6.59 release made "just select the gguf model" work for a file
already on disk. The follow-up gap (the worklog's next-phase candidate
#2, plus the operator's original request phrasing -- "can you make the
backend for it yourself"): when the model is NOT on disk yet, the only
fix offered was a manual browser download. V0.6.60 closes the loop:

  1. core/transcribe/model_downloader.py (NEW, Qt-free stdlib leaf):
     the curated handy-computer catalog (every entry's repo/filename/
     exact size verified LIVE against the HF API this session), probe()
     (HEAD -- size + range support, never raises), download() (streamed
     with .part resume, per-chunk progress with speed/ETA, cancel,
     atomic rename, size sanity), verify_download() (the V0.6.59 catalog
     gate re-used: GGUF magic + whisper architecture from the file's own
     header), and default_download_dir() (lands the file exactly where
     the V0.6.59 scan looks first).
  2. ui_qt/.../model_download_dialog.py (NEW): a downloader dialog --
     the catalog list with a details panel + per-entry tooltips (the
     recommended badge, size, note), progress bar + live speed/ETA
     line, cancel, open-folder, and a on_installed callback so the
     parent dialog saves + selects the model when it lands (download →
     selected, one flow). Network NEVER touches the UI thread
     (SimpleWorker -- the house _llm_test_worker precedent).
  3. The transcribe dialog's GGUF row grows a "⬇ Get models" button,
     and every combo entry now carries a rich details TOOLTIP (the
     worklog's candidate #3: name/params/quant/size/path + what the
     header PROVED, vs what was only guessed from the name).

LIVE EVIDENCE this session (the catalog pins mirror it):
  - handy-computer/whisper-large-v3-turbo-gguf ships
    whisper-large-v3-turbo-{F16,Q4_K_M,Q5_K_M,Q6_K,Q8_0}.gguf with
    sizes 1625935520 / 536069728 / 619628128 / 692536928 / 886381760.
  - handy-computer/whisper-large-v3-gguf: F16 3107236640, Q4_K_M
    997303008, Q5_K_M 1161143008, Q6_K 1297130208, Q8_0 1668741440.
  - The turbo Q5_K_M header was range-requested and parsed with the
    V0.6.59 reader: general.architecture='whisper',
    general.name='Whisper Large v3 Turbo', general.size_label='809M',
    file_type=17 (Q5_K_M), 589 tensors, 67 KVs.
  - The resolve URLs answer HEAD with accept-ranges: bytes (302 → CDN).

TEST LAYOUT
-----------
  A. catalog integrity       -- live-verified entries, one recommended
  B. probe                   -- hermetic local HTTP server (HEAD/Range)
  C. download               -- happy / cancel / resume / ignore-range /
                               no-resume / nested dir / 404 /
                               cb-raises / declared-size lie
  D. verify_download        -- the catalog gate + size cross-check
  E. default_download_dir   -- where the scan looks first
  F. format helpers         -- progress line / tooltip formatting
  G. dialog integration     -- AST pins (the house style: no PySide6
                               in this sandbox)
"""

from __future__ import annotations

import ast
import http.server
import sys
import threading
from pathlib import Path

import pytest

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# House precedent (test_p2_summarizer_* cross-test imports): reuse the
# v0659 GGUF byte builder, itself verified against the real
# handy-computer header shape.
from test_v0659_whisper_gguf_catalog import build_whisper_gguf  # noqa: E402

_DIALOG = (
    _project_root
    / "ui_qt"
    / "views"
    / "service_dialogs"
    / "dialogs"
    / "transcribe_service_dialog.py"
)
_DL_DIALOG = _project_root / "ui_qt" / "views" / "service_dialogs" / "model_download_dialog.py"
_CATALOG_LEAF = _project_root / "core" / "transcribe" / "model_catalog.py"
_DOWNLOADER_LEAF = _project_root / "core" / "transcribe" / "model_downloader.py"

from core.transcribe import model_catalog as mc  # noqa: E402
from core.transcribe import model_downloader as md  # noqa: E402

# ═════════════════════════════════════════════════════════════════════════════
# The hermetic HTTP server -- GET/HEAD + Range (206) support, request
# recording (the resume pins need PROOF the Range header was sent),
# a Range-ignore mode, and a declared-size lie mode.
# ═════════════════════════════════════════════════════════════════════════════


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    """Serves self.server.files{path: bytes}. Records every request
    (method, path, Range + If-Range headers) into self.server.requests.
    Sends an ETag and HONORS If-Range (a stale If-Range is served a
    full-body 200 -- the republished-remote restart pin)."""

    server_version = "ElixirTestServer/0.6.60"

    def log_message(self, *args):  # silence -- test output stays clean
        pass

    def _serve(self, send_body: bool) -> None:
        path = self.path.split("?")[0].lstrip("/")
        data = self.server.files.get(path)  # type: ignore[attr-defined]
        if data is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        etag = getattr(self.server, "etag", '"etag-v1"')
        self.server.requests.append(  # type: ignore[attr-defined]
            {
                "method": self.command,
                "path": self.path,
                "range": self.headers.get("Range"),
                "if_range": self.headers.get("If-Range"),
            }
        )
        start = 0
        rng = self.headers.get("Range") or ""
        range_ok = not getattr(self.server, "ignore_range", False)  # type: ignore[attr-defined]
        if_range = self.headers.get("If-Range")
        if (
            range_ok
            and if_range is not None
            and if_range != etag
            and not getattr(self.server, "ignore_if_range", False)  # type: ignore[attr-defined]
        ):
            range_ok = False  # the remote changed: full-body restart
        if range_ok and rng.startswith("bytes=") and rng.endswith("-"):
            try:
                start = int(rng[6:-1])
            except ValueError:
                start = 0
        if start >= len(data):
            self.send_response(416)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = data[start:]
        # The lie mode: declare MORE bytes than we will ever send --
        # the client's final size sanity must catch the short read.
        declared = len(body) + getattr(self.server, "lie_extra", 0)  # type: ignore[attr-defined]
        if start > 0:
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(declared))
        self.end_headers()
        if send_body:
            step = 64 * 1024
            for i in range(0, len(body), step):
                self.wfile.write(body[i : i + step])

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        self._serve(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(send_body=False)


class _Server:
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), _RangeHandler)
        self.httpd.files = files or {}
        self.httpd.requests = []
        self.httpd.ignore_range = False
        self.httpd.ignore_if_range = (
            False  # V0.6.61: the xet-CDN mode (serves 206 despite a stale If-Range -- probed live)
        )
        self.httpd.lie_extra = 0
        self.httpd.etag = '"etag-v1"'
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        self.port = self.httpd.server_address[1]

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}/{path}"

    @property
    def requests(self):
        return self.httpd.requests

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture()
def srv():
    s = _Server()
    yield s
    s.close()


def _make_remote_whisper(srv: _Server, name: str, total_bytes: int = 600_000) -> bytes:
    """A remote 'model file': a REAL whisper GGUF header (the v0659
    builder) padded to total_bytes so the download loop iterates
    multiple chunks."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as fh:
        build_whisper_gguf(Path(fh.name))
        data = Path(fh.name).read_bytes()
    data = data + b"\x00" * (total_bytes - len(data))
    srv.httpd.files[name] = data
    return data


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"method {name!r} not found")


# ═════════════════════════════════════════════════════════════════════════════
# A. catalog integrity -- the curated entries mirror the LIVE-verified
#    HF API state (checked this session; sizes are display hints the
#    downloader re-probes at runtime).
# ═════════════════════════════════════════════════════════════════════════════


class TestCatalogIntegrity:
    def test_every_entry_is_a_real_handy_computer_file(self):
        for spec in md.DOWNLOAD_CATALOG:
            assert spec.repo.startswith("handy-computer/"), spec
            assert spec.filename.startswith("whisper-"), spec
            assert spec.filename.endswith(".gguf"), spec
            assert spec.family in spec.filename, spec
            assert spec.quant in spec.filename, spec
            assert spec.params, spec
            # a real model is at least 100 MB at these sizes
            assert spec.size_hint > 100_000_000, spec

    def test_catalog_sizes_are_the_live_verified_bytes(self):
        """Pinned to the HF API state verified LIVE this session -- if
        handy-computer republishes a file, this pin trips and the hints
        get refreshed DELIBERATELY (the downloader re-probes anyway)."""
        by_key = {s.key: s.size_hint for s in md.DOWNLOAD_CATALOG}
        assert by_key["large-v3-turbo-Q5_K_M"] == 619_628_128
        assert by_key["large-v3-turbo-Q8_0"] == 886_381_760
        assert by_key["large-v3-turbo-F16"] == 1_625_935_520
        assert by_key["large-v3-Q5_K_M"] == 1_161_143_008
        assert by_key["large-v3-Q8_0"] == 1_668_741_440

    def test_keys_are_unique_and_resolvable(self):
        keys = [s.key for s in md.DOWNLOAD_CATALOG]
        assert len(keys) == len(set(keys)), "duplicate catalog keys"
        for spec in md.DOWNLOAD_CATALOG:
            assert md.catalog_by_key(spec.key) is spec
        assert md.catalog_by_key("no-such-model") is None

    def test_exactly_one_recommended_and_it_is_turbo(self):
        """The V0.6.58 speed ledger's verdict: turbo is the rig's
        speed/quality sweet spot -- the downloader must say so."""
        recs = [s for s in md.DOWNLOAD_CATALOG if s.recommended]
        assert len(recs) == 1
        assert recs[0].family == "large-v3-turbo"
        assert recs[0].quant == "Q5_K_M"
        # the recommended badge is visible in the display line
        assert "★" in recs[0].display()

    def test_hf_url_shape(self):
        assert md.hf_url("handy-computer/x", "a.gguf") == (
            "https://huggingface.co/handy-computer/x/resolve/main/a.gguf"
        )
        for spec in md.DOWNLOAD_CATALOG:
            # the LITERAL shape, not url() re-invoked (tautology fix)
            assert spec.url() == (
                f"https://huggingface.co/{spec.repo}/resolve/main/{spec.filename}"
            )

    def test_display_lines_carry_family_quant_and_size(self):
        for spec in md.DOWNLOAD_CATALOG:
            line = spec.display()
            assert spec.quant in line
            assert "MB" in line or "GB" in line
            # params are part of the detail surface, not the one-liner
            assert spec.params


# ═════════════════════════════════════════════════════════════════════════════
# B. probe -- HEAD, never raises, honest error text
# ═════════════════════════════════════════════════════════════════════════════


class TestProbe:
    def test_probe_reports_size_and_range_support(self, srv):
        data = _make_remote_whisper(srv, "model.gguf", 300_000)
        res = md.probe(srv.url("model.gguf"), timeout=10)
        assert res["ok"] is True
        assert res["size"] == len(data)
        assert res["accepts_ranges"] is True
        assert res["error"] is None

    def test_probe_404_is_ok_false_with_the_code_in_the_error(self, srv):
        res = md.probe(srv.url("missing.gguf"), timeout=10)
        assert res["ok"] is False
        assert res["size"] is None
        assert "404" in (res["error"] or "")

    def test_probe_dead_port_never_raises(self):
        # port 1 on localhost: nothing listens there in this sandbox
        res = md.probe("http://127.0.0.1:1/nope.gguf", timeout=2)
        assert res["ok"] is False
        assert res["error"]


# ═════════════════════════════════════════════════════════════════════════════
# C. download -- streamed, resumable, cancellable, atomic
# ═════════════════════════════════════════════════════════════════════════════


class TestDownload:
    def test_happy_path_downloads_the_exact_bytes_atomically(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        res = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is True
        assert res["cancelled"] is False
        assert res["error"] is None
        final = Path(res["path"])
        assert final == dest / "model.gguf"
        assert final.read_bytes() == data
        # atomic: no .part (or sidecar) residue after success
        assert not final.with_name(final.name + ".part").exists()
        assert not final.with_name(final.name + ".part.etag").exists()

    def test_url_filename_is_always_a_bare_name(self, srv, tmp_path):
        """Traversal stripping (the fresh-eyes review's pin): the
        on-disk name comes from the URL's LAST segment as a bare
        filename -- a crafted URL can never write outside dest."""
        assert md._url_filename("http://h/a/b/model.gguf") == "model.gguf"
        assert md._url_filename("http://h/../../etc/passwd.gguf") == "passwd.gguf"
        assert md._url_filename("http://h/x/") == "model.gguf"
        assert md._url_filename("http://h/..") == "model.gguf"
        # a host-only URL yields a (weird but) BARE contained name:
        # no separator, no dot-dot, never a path
        host_only = md._url_filename("http://h")
        assert host_only and "/" not in host_only and host_only not in (".", "..")

    def test_progress_callbacks_fire_with_speed_and_pct(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        seen: list[dict] = []
        res = md.download(
            srv.url("model.gguf"),
            tmp_path,
            on_progress=seen.append,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is True
        assert len(seen) >= 2, "at least the initial + a data-bearing callback"
        assert seen[0]["done"] == 0
        last = seen[-1]
        assert last["done"] == len(data)
        assert last["pct"] == 100.0
        assert last["total"] == len(data)
        assert last["speed_bps"] > 0

    def test_cancel_mid_download_keeps_the_part_file(self, srv, tmp_path):
        _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
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
        )
        assert res["ok"] is False
        assert res["cancelled"] is True
        assert res["path"] is None
        part = dest / "model.gguf.part"
        assert part.exists()
        assert part.stat().st_size == 256 * 1024  # exactly one chunk landed
        # V0.6.60 review fix: the ETag sidecar lands BESIDE the .part
        # (resume bookkeeping) and survives the cancel with it.
        sidecar = dest / "model.gguf.part.etag"
        assert sidecar.exists()
        assert sidecar.read_text(encoding="utf-8") == '"etag-v1"'

    def test_resume_sends_the_range_header_and_completes(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        # 1. cancel after one chunk -> .part holds 256 KiB
        flag = {"stop": False}

        def _cancel() -> bool:
            return flag["stop"]

        def _on_progress(p: dict) -> None:
            if p["done"] > 0:
                flag["stop"] = True

        first = md.download(
            srv.url("model.gguf"),
            dest,
            on_progress=_on_progress,
            should_cancel=_cancel,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert first["cancelled"] is True
        srv.requests.clear()
        # 2. resume: the server must see the Range header, answer 206
        second = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert second["ok"] is True
        assert second["resumed_from"] == 256 * 1024
        gets = [r for r in srv.requests if r["method"] == "GET"]
        assert gets, "the resume must actually hit the server"
        assert gets[0]["range"] == "bytes=262144-", gets
        # V0.6.60 review fix: the resume also carries If-Range so a
        # republished remote can never be mixed into a stale prefix.
        assert gets[0]["if_range"] == '"etag-v1"', gets
        assert (dest / "model.gguf").read_bytes() == data
        # and the sidecar bookkeeping is gone once the file completes
        assert not (dest / "model.gguf.part.etag").exists()

    def test_republished_remote_restarts_instead_of_mixing(self, srv, tmp_path):
        """THE corrupt-file pin (the fresh-eyes review's dynamic proof):
        a blind Range resume against a republished remote welds the
        stale prefix to the fresh suffix -- a file that PASSES the size
        check and the header check. The ETag sidecar + If-Range must
        turn that into a clean full-body restart."""
        old_data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        # 1. cancel after one chunk -> .part + sidecar hold 256 KiB of OLD
        flag = {"stop": False}

        def _cancel() -> bool:
            return flag["stop"]

        def _on_progress(p: dict) -> None:
            if p["done"] > 0:
                flag["stop"] = True

        first = md.download(
            srv.url("model.gguf"),
            dest,
            on_progress=_on_progress,
            should_cancel=_cancel,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert first["cancelled"] is True
        # 2. the remote is republished: different bytes, different etag
        new_data = bytes((i * 7 + 3) % 256 for i in range(700_000))
        srv.httpd.files["model.gguf"] = new_data
        srv.httpd.etag = '"etag-v2"'
        srv.requests.clear()
        # 3. resume: If-Range mismatches -> the server answers a
        # full-body 200 -> a clean restart, NEVER a mixed file
        second = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert second["ok"] is True
        assert second["resumed_from"] == 0
        final = (dest / "model.gguf").read_bytes()
        assert final == new_data
        assert final != old_data[: len(final)]

    def test_part_without_a_sidecar_is_never_trusted(self, srv, tmp_path):
        """A .part with no ETag sidecar (a crash before the sidecar was
        written, or a foreign file) must restart from zero, never
        append blindly."""
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "model.gguf.part").write_bytes(data[:100_000])  # no sidecar
        srv.requests.clear()
        res = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is True
        assert res["resumed_from"] == 0
        gets = [r for r in srv.requests if r["method"] == "GET"]
        assert gets and gets[0]["range"] is None, "no Range may be sent"
        assert (dest / "model.gguf").read_bytes() == data

    def test_416_when_remote_shrunk_restarts_from_zero(self, srv, tmp_path):
        """The 416 dead end (fresh-eyes review): the remote SHRANK below
        the .part. The retry must probe, see the size mismatch, and
        restart from zero -- not re-send the unsatisfiable Range
        forever."""
        _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        flag = {"stop": False}

        def _cancel() -> bool:
            return flag["stop"]

        def _on_progress(p: dict) -> None:
            if p["done"] > 0:
                flag["stop"] = True

        first = md.download(
            srv.url("model.gguf"),
            dest,
            on_progress=_on_progress,
            should_cancel=_cancel,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert first["cancelled"] is True  # .part holds 256 KiB
        # the remote is replaced by a much smaller file (the etag is
        # KEPT matching so the Range IS honored -- start >= len(data)
        # is what triggers the 416)
        tiny = b"GGUF" + b"\x00" * 96  # 100 bytes
        srv.httpd.files["model.gguf"] = tiny
        res = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is True
        assert res["resumed_from"] == 0
        assert (dest / "model.gguf").read_bytes() == tiny

    def test_416_already_complete_recovers_without_a_transfer(self, srv, tmp_path):
        """The other 416 shape: the .part is already the COMPLETE file
        (a cancel between the last chunk write and the rename). The
        probe sees part == remote size and finalizes with ZERO body
        bytes moved."""
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        # simulate the crash-after-last-write: full .part + sidecar
        (dest / "model.gguf.part").write_bytes(data)
        (dest / "model.gguf.part.etag").write_text('"etag-v1"', encoding="utf-8")
        srv.requests.clear()
        res = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is True
        assert res.get("recovered") == "already-complete"
        assert res["size"] == len(data)
        final = dest / "model.gguf"
        assert final.read_bytes() == data
        assert not final.with_name(final.name + ".part").exists()
        assert not final.with_name(final.name + ".part.etag").exists()
        # only the 416 GET (empty body) + the recovery HEAD happened
        gets = [r for r in srv.requests if r["method"] == "GET"]
        heads = [r for r in srv.requests if r["method"] == "HEAD"]
        assert len(gets) == 1 and gets[0]["range"] == "bytes=600000-"
        assert len(heads) == 1

    def test_server_ignoring_range_restarts_from_zero(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "model.gguf.part").write_bytes(b"\xab" * 100_000)  # stale junk part
        # a sidecar with the CURRENT etag: the part is trusted, so the
        # Range IS sent -- and the server ignores it (plain 200)
        (dest / "model.gguf.part.etag").write_text('"etag-v1"', encoding="utf-8")
        srv.httpd.ignore_range = True
        srv.requests.clear()
        res = md.download(srv.url("model.gguf"), dest, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is True
        assert res["resumed_from"] == 0  # a 200 means: no resume happened
        gets = [r for r in srv.requests if r["method"] == "GET"]
        assert gets and gets[0]["range"] == "bytes=100000-"  # the Range was sent
        assert (dest / "model.gguf").read_bytes() == data

    def test_resume_false_starts_over(self, srv, tmp_path):
        data = _make_remote_whisper(srv, "model.gguf", 600_000)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "model.gguf.part").write_bytes(b"\xcd" * 100_000)
        # a valid sidecar: only resume=False can justify the restart
        (dest / "model.gguf.part.etag").write_text('"etag-v1"', encoding="utf-8")
        srv.requests.clear()
        res = md.download(
            srv.url("model.gguf"),
            dest,
            resume=False,
            chunk_bytes=256 * 1024,
            timeout=10,
        )
        assert res["ok"] is True
        assert res["resumed_from"] == 0
        gets = [r for r in srv.requests if r["method"] == "GET"]
        assert gets and gets[0]["range"] is None  # no Range was sent
        assert (dest / "model.gguf").read_bytes() == data

    def test_destination_directory_is_created(self, srv, tmp_path):
        _make_remote_whisper(srv, "model.gguf", 300_000)
        nested = tmp_path / "a" / "b" / "c"
        res = md.download(srv.url("model.gguf"), nested, timeout=10)
        assert res["ok"] is True
        assert (nested / "model.gguf").exists()

    def test_404_is_an_honest_error_and_leaves_no_file(self, srv, tmp_path):
        res = md.download(srv.url("missing.gguf"), tmp_path, timeout=10)
        assert res["ok"] is False
        assert res["cancelled"] is False
        assert "404" in (res["error"] or "")
        assert res["path"] is None
        assert list(tmp_path.iterdir()) == []

    def test_a_raising_progress_callback_never_kills_the_download(self, srv, tmp_path):
        _make_remote_whisper(srv, "model.gguf", 300_000)

        def _bad_cb(p: dict) -> None:
            raise RuntimeError("a broken UI hook must not corrupt the file")

        res = md.download(srv.url("model.gguf"), tmp_path, on_progress=_bad_cb, timeout=10)
        assert res["ok"] is True

    def test_declared_size_lie_is_caught_and_part_kept_for_resume(self, srv, tmp_path):
        _make_remote_whisper(srv, "model.gguf", 600_000)
        srv.httpd.lie_extra = 5000  # server declares 5000 bytes more than it sends
        res = md.download(srv.url("model.gguf"), tmp_path, chunk_bytes=256 * 1024, timeout=10)
        assert res["ok"] is False
        assert res["cancelled"] is False
        # the honest error + the .part kept for a later resume
        assert res["error"] and "incomplete" in res["error"].lower()
        assert res["path"] is None
        assert (tmp_path / "model.gguf.part").exists()


# ═════════════════════════════════════════════════════════════════════════════
# D. verify_download -- the V0.6.59 catalog gate, re-used
# ═════════════════════════════════════════════════════════════════════════════


class TestVerifyDownload:
    def test_a_real_whisper_gguf_passes_with_header_proof(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-turbo-Q5_K_M.gguf")
        res = md.verify_download(f)
        assert res["ok"] is True
        assert res["problem"] is None
        assert res["info"]["verified"] is True
        assert res["info"]["architecture"] == "whisper"

    def test_size_cross_check_against_the_catalog_entry(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-turbo-Q5_K_M.gguf")
        spec = md.catalog_by_key("large-v3-turbo-Q5_K_M")
        res = md.verify_download(f, spec=spec)
        # header fine, size differs from the live catalog hint
        assert res["ok"] is True
        assert res["size_ok"] is False

    def test_junk_is_rejected_with_the_gguf_fix_text(self, tmp_path):
        f = tmp_path / "not-a-model.gguf"
        f.write_bytes(b"this is not a gguf at all")
        res = md.verify_download(f)
        assert res["ok"] is False
        assert "GGUF" in (res["problem"] or "")

    def test_missing_file_is_rejected_not_raised(self, tmp_path):
        res = md.verify_download(tmp_path / "ghost.gguf")
        assert res["ok"] is False
        assert res["problem"]


# ═════════════════════════════════════════════════════════════════════════════
# E. default_download_dir -- land the file where the scan looks first
# ═════════════════════════════════════════════════════════════════════════════


class TestDefaultDownloadDir:
    def test_the_documented_models_dir_wins_when_it_exists(self, tmp_path):
        rig = tmp_path / "models"
        rig.mkdir()
        assert md.default_download_dir(models_dir=str(rig)) == str(rig)

    def test_falls_back_to_the_exe_models_folder(self, tmp_path):
        exe_dir = tmp_path / "tool"
        exe_dir.mkdir()
        exe = exe_dir / "transcribe-cli.exe"
        exe.write_bytes(b"stub")
        got = md.default_download_dir(
            exe_path=str(exe),
            home=str(tmp_path / "no-home"),
            models_dir=str(tmp_path / "nope"),
        )
        assert got == str(exe_dir / "models")

    def test_falls_back_to_downloads(self, tmp_path):
        home = tmp_path / "home"
        (home / "Downloads").mkdir(parents=True)
        got = md.default_download_dir(
            exe_path=None, home=str(home), models_dir=str(tmp_path / "nope")
        )
        assert got == str(home / "Downloads")

    def test_last_resort_is_the_documented_default_created(self, tmp_path, monkeypatch):
        # nothing exists anywhere -> the documented rig layout, created
        target = tmp_path / "fresh" / "models"
        monkeypatch.setattr(md, "DEFAULT_MODELS_DIR", str(target))
        got = md.default_download_dir(
            exe_path=None, home=str(tmp_path / "empty-home"), models_dir=None
        )
        assert got == str(target)
        assert target.is_dir()

    def test_posix_never_literal_creates_the_windows_default(self, tmp_path, monkeypatch):
        """The POSIX pollution guard (the fresh-eyes review's pin): with
        the REAL Windows-shaped constant and nothing existing anywhere,
        default_download_dir must NOT mkdir a literal 'C:\\transcribe.cpp'
        folder in the CWD (repo pollution -- it actually happened once
        this session)."""
        import os as _os

        cwd = tmp_path / "workdir"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        # the REAL constant, unpatched, on a POSIX host
        assert not md.DEFAULT_MODELS_DIR.startswith("/") or _os.name == "nt"
        got = md.default_download_dir(
            exe_path=None, home=str(tmp_path / "no-home"), models_dir=None
        )
        assert got  # something honest is always returned
        assert (cwd / "C:\\transcribe.cpp").exists() is False
        assert list(cwd.iterdir()) == [], "the CWD must stay untouched"


# ═════════════════════════════════════════════════════════════════════════════
# F. format helpers -- the dialog-facing one-liners
# ═════════════════════════════════════════════════════════════════════════════


class TestFormatHelpers:
    def test_progress_line_carries_size_pct_speed_and_eta(self):
        line = md.format_progress_line(
            {
                "done": 300_000_000,
                "total": 600_000_000,
                "pct": 50.0,
                "speed_bps": 25.0 * 1024 * 1024,
                "eta_s": 12.0,
            }
        )
        assert "MB" in line
        assert "50%" in line
        assert "25.0 MB/s" in line
        assert "ETA 12s" in line

    def test_progress_line_without_total_stays_honest(self):
        line = md.format_progress_line({"done": 100, "total": None, "pct": None})
        assert "?" in line

    def test_model_tooltip_lists_the_facts(self, tmp_path):
        f = build_whisper_gguf(tmp_path / "whisper-large-v3-turbo-Q5_K_M.gguf")
        info = mc.describe_model_file(f)
        tip = mc.format_model_tooltip(info)
        assert "File:" in tip
        assert "Size:" in tip
        assert "Architecture: whisper" in tip
        assert "Parameters: 1.5B" in tip
        assert "header-verified" in tip

    def test_model_tooltip_flags_legacy_ggml(self, tmp_path):
        info = {
            "path": r"C:\m\ggml-large-v3.bin",
            "name": "ggml-large-v3.bin",
            "size_bytes": 1000,
            "size_text": "1000 B",
            "family": "large-v3",
            "quant": None,
            "language": None,
            "legacy_ggml": True,
            "is_gguf": False,
            "verified": False,
            "architecture": None,
            "meta_name": None,
            "size_label": None,
            "gguf_version": None,
        }
        tip = mc.format_model_tooltip(info)
        assert "legacy" in tip

    def test_model_tooltip_names_the_en_variant(self):
        info = {
            "path": "/x/whisper-medium.en.gguf",
            "name": "whisper-medium.en.gguf",
            "size_bytes": 10,
            "size_text": "10 B",
            "family": "medium",
            "quant": None,
            "language": "en",
            "legacy_ggml": False,
            "is_gguf": True,
            "verified": True,
            "architecture": "whisper",
            "meta_name": None,
            "size_label": None,
            "gguf_version": None,
        }
        tip = mc.format_model_tooltip(info)
        assert "Language: en" in tip

    def test_model_tooltip_is_honest_about_unparsable_headers(self):
        info = {
            "path": "/x/y.gguf",
            "name": "y.gguf",
            "size_bytes": 5,
            "size_text": "5 B",
            "family": None,
            "quant": None,
            "language": None,
            "legacy_ggml": False,
            "is_gguf": True,
            "verified": False,
            "architecture": None,
            "meta_name": None,
            "size_label": None,
            "gguf_version": None,
        }
        tip = mc.format_model_tooltip(info)
        assert "not parsable" in tip


# ═════════════════════════════════════════════════════════════════════════════
# G. dialog integration -- AST pins (the house style: no PySide6 in
#    this sandbox; structure + wiring are pinned, behavior is Qt-free
#    in the leaves).
# ═════════════════════════════════════════════════════════════════════════════


class TestTranscribeDialogIntegration:
    @pytest.fixture(scope="class")
    def dialog_tree(self):
        return ast.parse(_DIALOG.read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    def dialog_src(self):
        return _DIALOG.read_text(encoding="utf-8")

    def test_download_button_is_built_before_engine_change(self, dialog_tree):
        """The V0.6.55 BLOCKER-class pin, EXTENDED to the new button:
        every widget _on_engine_changed's siblings touch must exist
        before the explicit call (the exact construction-order
        AttributeError class V0.6.53/55 died of). The button lives in
        the cpp row; the row itself must also precede the call."""
        build = _method(dialog_tree, "_build_options")
        call_lines = [
            n.lineno
            for n in ast.walk(build)
            if isinstance(n, (ast.Expr, ast.Assign))
            and isinstance(getattr(n, "value", None), ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == "_on_engine_changed"
        ]
        assert call_lines, "_build_options must call self._on_engine_changed()"
        first_call = min(call_lines)
        for widget in ("cpp_model_download_btn", "cpp_model_combo", "cpp_model_row"):
            assign_lines = [
                n.lineno
                for n in ast.walk(build)
                if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == widget
            ]
            assert assign_lines, f"{widget} never assigned in _build_options"
            assert max(assign_lines) < first_call

    def test_download_button_is_wired_and_labeled(self, dialog_tree, dialog_src):
        build = _method(dialog_tree, "_build_options")
        body = ast.unparse(build)
        assert "Get models" in dialog_src
        assert "cpp_model_download_btn" in body
        assert "_open_model_downloader" in body  # the .clicked.connect target

    def test_open_model_downloader_launches_the_dialog_with_the_callback(self, dialog_tree):
        handler = ast.unparse(_method(dialog_tree, "_open_model_downloader"))
        assert "ModelDownloadDialog" in handler
        assert "on_installed" in handler

    def test_installed_model_is_saved_selected_and_logged(self, dialog_tree):
        handler = ast.unparse(_method(dialog_tree, "_on_model_installed"))
        assert "transcribe.transcribe_cpp_model" in handler
        assert "_refresh_cpp_models" in handler

    def test_empty_combo_placeholder_offers_the_download(self, dialog_tree):
        # V0.6.61: the populate moved to the finished-slot
        # _on_cpp_models_scanned (the off-thread scan) — the pin
        # follows the contract, deliberately.
        populate = ast.unparse(_method(dialog_tree, "_on_cpp_models_scanned"))
        assert "(no Whisper" in populate
        assert "Get models" in populate

    def test_combo_entries_carry_details_tooltips(self, dialog_tree):
        # V0.6.61: the tooltips are BUILT where the items are built
        # (the scan closure inside _refresh_cpp_models — on the worker
        # thread, from the header the scan already read) and APPLIED
        # where the combo is populated (_on_cpp_models_scanned — the
        # off-thread scan moved the populate; the pin follows).
        refresh = ast.unparse(_method(dialog_tree, "_refresh_cpp_models"))
        assert "format_model_tooltip" in refresh
        populate = ast.unparse(_method(dialog_tree, "_on_cpp_models_scanned"))
        assert "setItemData" in populate
        assert "ToolTipRole" in populate


class TestModelDownloadDialogIntegration:
    @pytest.fixture(scope="class")
    def src(self):
        assert _DL_DIALOG.exists(), (
            "ui_qt/views/service_dialogs/model_download_dialog.py is missing"
        )
        return _DL_DIALOG.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tree(self, src):
        return ast.parse(src)  # raises on a syntax error

    def test_class_shape_and_title(self, tree, src):
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        assert "ModelDownloadDialog" in classes
        assert "QDialog" in src
        assert "Whisper" in src  # the window title names the model family

    def test_uses_the_downloader_leaf_and_its_catalog(self, src):
        assert "model_downloader" in src
        assert "DOWNLOAD_CATALOG" in src

    def test_network_never_touches_the_ui_thread(self, src):
        assert "SimpleWorker" in src
        assert "should_cancel" in src

    def test_cancel_flag_wiring(self, src):
        assert "_cancel_flag" in src

    def test_downloaded_file_is_verified_before_install(self, src):
        assert "verify_download" in src

    def test_on_installed_receives_the_downloaded_path(self, tree, src):
        assert "on_installed" in src
        # the success path hands the path to the callback
        assert "self._on_installed" in src

    def test_open_folder_affordance(self, src):
        assert "QDesktopServices" in src

    def test_progress_bar_is_driven_by_the_worker(self, src):
        assert "progress.emit" in src  # the worker's progress signal (specific)
        assert "progress_bar" in src
        assert "setValue" in src

    def test_destination_is_shown_and_uses_default_download_dir(self, src):
        assert "default_download_dir" in src


class TestCatalogTooltipLeaf:
    """format_model_tooltip lives in the Qt-free catalog leaf so its
    behavior is pinned hermetically (done above) AND referenced by the
    dialog (pinned above)."""

    def test_leaf_declares_the_helper(self):
        src = _CATALOG_LEAF.read_text(encoding="utf-8")
        assert "def format_model_tooltip" in src
