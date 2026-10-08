"""core/transcribe/model_downloader.py -- V0.6.60: the Whisper GGUF
downloader.

THE STORY THIS CLOSES
---------------------
V0.6.59 made "just select the gguf model" work for a file already on
disk: the GGUF combo lists every Whisper .gguf the catalog finds, and
the engine verifies the file from its own header before the run. The
remaining gap (the V0.6.59 worklog's next-phase candidate #2): when the
model is NOT on disk yet, every error message ends with "download a
Whisper GGUF ... from handy-computer/whisper-large-v3-gguf on Hugging
Face" -- a manual browser trip, a manual folder pick, and (the classic
rig failure) a model that lands in Downloads where the operator then
can't find it. V0.6.60 closes the loop INSIDE the app:

  DOWNLOAD_CATALOG -- the curated handy-computer entries, every
      repo/filename/size verified LIVE against the HF API this session
      (whisper-large-v3-turbo-{F16,Q4_K_M,Q5_K_M,Q6_K,Q8_0}.gguf in
      handy-computer/whisper-large-v3-turbo-gguf; whisper-large-v3-*
      in handy-computer/whisper-large-v3-gguf). The turbo Q5_K_M is
      the RECOMMENDED entry -- the V0.6.58 speed ledger's verdict
      (~4-8x faster than large-v3, near-identical accuracy). Sizes are
      display hints; download() re-probes the real size live.
  probe(url)      -- HEAD (follows the HF 302 -> CDN redirect): size +
      accepts-ranges, honestly reported, never raises.
  download(url)   -- streamed to <dest>/<name>.part with HTTP Range
      RESUME (a cancelled/interrupted download continues where it
      stopped), per-chunk progress callbacks carrying speed + ETA, a
      should_cancel() hook checked every chunk, a final size sanity
      check, and an atomic os.replace into place (a model file is
      never half-visible under its real name).
  verify_download(path) -- the V0.6.59 catalog gate re-used: GGUF
      magic + whisper architecture read from the downloaded file's OWN
      header, plus an optional exact-size cross-check against the
      catalog entry.
  default_download_dir() -- lands the file exactly where the V0.6.59
      scan looks FIRST (C:\\transcribe.cpp\\models, else the exe's
      models/ folder, else ~/Downloads), so the moment the download
      finishes the GGUF combo sees it.

Qt-free, stdlib-only leaf (the house pattern: the sandbox has no
PySide6, so all of this is behaviorally testable everywhere; the dialog
runs download() on a SimpleWorker -- network never touches the UI
thread).
"""

from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.transcribe.model_catalog import (
    DEFAULT_MODELS_DIR,
    validate_whisper_model,
)

#: The hermetic tests pin the catalog's LIVE-verified sizes; if
#: handy-computer republishes a file, the pin trips and the hints get
#: refreshed DELIBERATELY (download() re-probes the real size anyway).
HF_BASE = "https://huggingface.co"

PROBE_TIMEOUT_S = 15.0
DOWNLOAD_TIMEOUT_S = 60.0
CHUNK_BYTES = 256 * 1024

_MIN_PROGRESS_CB_S = 0.0  # every chunk: ~27 emits/s for a 1.6 GB / 60 s pull


def _ua_headers(extra: dict | None = None) -> dict:
    h = {"User-Agent": "Elixir-TranscribeService/0.6.60 (+model downloader)"}
    if extra:
        h.update(extra)
    return h


def _fmt_bytes(num_bytes: float) -> str:
    """Human-readable size (the catalog's display convention; the leaf
    keeps its own copy so it never imports the engine)."""
    try:
        gb = num_bytes / (1024**3)
        if gb >= 1.0:
            return f"{gb:.1f} GB"
        mb = num_bytes / (1024**2)
        if mb >= 1.0:
            return f"{mb:.1f} MB"
        return f"{max(0, int(num_bytes))} B"
    except Exception:
        return "?"


def _fmt_speed(bps: float) -> str:
    return f"{bps / (1024 * 1024):.1f} MB/s"


# ── The catalog ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DownloadSpec:
    """One downloadable Whisper GGUF (a handy-computer release file)."""

    key: str
    repo: str
    filename: str
    family: str
    quant: str
    params: str
    size_hint: int
    recommended: bool = False
    note: str = ""
    #: The PUBLISHED sha256 (the HF API's lfs.sha256 -- the content
    #: hash; the mechanism was proven live against whisper-tiny-
    #: Q4_K_M.gguf: downloaded in full, its sha256 matched the API
    #: value byte-for-byte). download() verifies the stream against
    #: it when given -- a corrupted file can never be installed.
    sha256: str | None = None

    def url(self) -> str:
        return hf_url(self.repo, self.filename)

    def display_name(self) -> str:
        return f"Whisper {self.family.replace('-', ' ').title()}"

    def display(self) -> str:
        """The catalog-list one-liner (dialog-facing)."""
        badge = "★ " if self.recommended else ""
        return f"{badge}{self.display_name()} · {self.quant} · {_fmt_bytes(self.size_hint)}"

    def details(self) -> str:
        """The multi-line details panel text (dialog-facing)."""
        rec = "RECOMMENDED — " if self.recommended else ""
        return (
            f"{self.display_name()} · {self.params} · {self.quant}\n"
            f"File: {self.filename} ({_fmt_bytes(self.size_hint)})\n"
            f"Source: huggingface.co/{self.repo}\n"
            f"{rec}{self.note}"
        )


def hf_url(repo: str, filename: str) -> str:
    """The canonical HF resolve URL (302 -> CDN; answers HEAD with
    accept-ranges: bytes -- verified live this session)."""
    return f"{HF_BASE}/{repo}/resolve/main/{filename}"


#: Turbo first: the V0.6.58 speed ledger's pick for the rig. Sizes are
#: the LIVE HF API bytes for each file, verified this session.
DOWNLOAD_CATALOG: list[DownloadSpec] = [
    DownloadSpec(
        key="large-v3-turbo-Q5_K_M",
        repo="handy-computer/whisper-large-v3-turbo-gguf",
        filename="whisper-large-v3-turbo-Q5_K_M.gguf",
        family="large-v3-turbo",
        quant="Q5_K_M",
        params="809M",
        size_hint=619_628_128,
        recommended=True,
        note=(
            "The speed/quality sweet spot for a GPU rig: ~4-8x faster "
            "than large-v3 with near-identical accuracy on most audio "
            "(the V0.6.58 speed ledger's pick)."
        ),
        sha256="977b5db4e004349dffd1ab9caa10ba5aaba3fc3edd3ba72cadb84328a3203e36",
    ),
    DownloadSpec(
        key="large-v3-turbo-Q8_0",
        repo="handy-computer/whisper-large-v3-turbo-gguf",
        filename="whisper-large-v3-turbo-Q8_0.gguf",
        family="large-v3-turbo",
        quant="Q8_0",
        params="809M",
        size_hint=886_381_760,
        note="Turbo at higher fidelity — noticeably sharper on noisy audio.",
        sha256="b2e30cc286bc9f3aba4db9099fc7403543497c05ce7100d0d83091ddfd25a183",
    ),
    DownloadSpec(
        key="large-v3-turbo-F16",
        repo="handy-computer/whisper-large-v3-turbo-gguf",
        filename="whisper-large-v3-turbo-F16.gguf",
        family="large-v3-turbo",
        quant="F16",
        params="809M",
        size_hint=1_625_935_520,
        note="Turbo, unquantized (fp16) — maximum turbo fidelity, largest turbo file.",
        sha256="e1d0144e9afc9f479d9e51fc92c7dea9dc36059655eeb3819f16ad2de779046a",
    ),
    DownloadSpec(
        key="large-v3-Q5_K_M",
        repo="handy-computer/whisper-large-v3-gguf",
        filename="whisper-large-v3-Q5_K_M.gguf",
        family="large-v3",
        quant="Q5_K_M",
        params="1.5B",
        size_hint=1_161_143_008,
        note=(
            "Maximum accuracy (the full 1.5B model) — slower than "
            "turbo; the reference Whisper large-v3."
        ),
        sha256="6053d0fd69a0fd48b8fea5ea7a52b9e0cde389343566fa30e453a1b2b258dc38",
    ),
    DownloadSpec(
        key="large-v3-Q8_0",
        repo="handy-computer/whisper-large-v3-gguf",
        filename="whisper-large-v3-Q8_0.gguf",
        family="large-v3",
        quant="Q8_0",
        params="1.5B",
        size_hint=1_668_741_440,
        note=(
            "Maximum accuracy + fidelity — the engine's documented "
            "default model (C:\\transcribe.cpp\\models)."
        ),
        sha256="2fa1a5f179f8a511a53e2108db270aa4af3ce08cd976af4180e2854666bb4ba3",
    ),
]


def catalog_by_key(key: str) -> DownloadSpec | None:
    for spec in DOWNLOAD_CATALOG:
        if spec.key == key:
            return spec
    return None


# ── probe ───────────────────────────────────────────────────────────────────


def probe(url: str, timeout: float = PROBE_TIMEOUT_S) -> dict:
    """HEAD the URL (redirects followed -- HF resolve -> CDN): the
    real size + range support. Honest failure, never raises.

    Returns {"ok", "url", "status", "size", "accepts_ranges", "error"}.
    """
    out = {
        "ok": False,
        "url": url,
        "status": None,
        "size": None,
        "accepts_ranges": False,
        "error": None,
    }
    try:
        req = urllib.request.Request(url, method="HEAD", headers=_ua_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out["status"] = getattr(resp, "status", None)
            try:
                out["size"] = int(resp.headers.get("Content-Length") or 0) or None
            except (TypeError, ValueError):
                out["size"] = None
            out["accepts_ranges"] = (
                (resp.headers.get("Accept-Ranges") or "").strip().lower() == "bytes"
            )
            out["ok"] = 200 <= int(getattr(resp, "status", 200) or 200) < 300
            if not out["ok"]:
                out["error"] = f"HTTP {out['status']}"
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["error"] = f"HTTP {e.code} {e.reason}"
    except Exception as e:  # noqa: BLE001 -- best-effort probe, never raises
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# ── download ─────────────────────────────────────────────────────────────────


def _progress_dict(
    done: int, total: int | None, resumed_from: int, t0: float, path: Path
) -> dict:
    elapsed = max(1e-9, time.monotonic() - t0)
    moved = max(0, done - resumed_from)
    speed = moved / elapsed if moved > 0 else 0.0
    eta = None
    if total and done < total and speed > 0:
        eta = (total - done) / speed
    return {
        "done": done,
        "total": total,
        "pct": (100.0 * done / total) if total else None,
        "speed_bps": speed,
        "eta_s": eta,
        "resumed_from": resumed_from,
        "path": str(path),
    }


def _safe_cb(on_progress, prog: dict) -> None:
    """A broken UI hook must never corrupt the download (the house
    best-effort style)."""
    if on_progress is None:
        return
    try:
        on_progress(prog)
    except Exception:  # noqa: BLE001
        pass


def _fail(error: str, part: Path | None = None, **extra) -> dict:
    out = {
        "ok": False,
        "cancelled": False,
        "path": None,
        "part_path": str(part) if part and part.exists() else None,
        "size": 0,
        "resumed_from": 0,
        "error": error,
    }
    out.update(extra)
    return out


def _url_filename(url: str) -> str:
    """The download's on-disk name from the URL — a BARE name (any
    directory components stripped: a crafted URL can never traverse
    out of the destination folder). pathlib keeps '..' as a real
    component (only '.' is dropped), so the dot-dot case is caught
    explicitly."""
    tail = url.rsplit("/", 1)[-1].split("?")[0]
    name = Path(tail).name
    if name in ("", ".", ".."):
        return "model.gguf"
    return name


def _hash_file(
    path: Path,
    hasher,
    chunk_bytes: int = 1024 * 1024,
    should_cancel: Callable[[], bool] | None = None,
) -> tuple[str | None, bool]:
    """Chunked-hashed sha256 of a local file (worker-thread helper:
    NEVER slurp a 1.6 GB model). Returns (digest, cancelled): digest
    is None on any IO problem; cancelled=True when should_cancel fired
    mid-read (the caller keeps the .part — it is still good bytes)."""
    try:
        with open(path, "rb") as fh:
            while True:
                if should_cancel is not None and should_cancel():
                    return None, True
                b = fh.read(chunk_bytes)
                if not b:
                    break
                hasher.update(b)
        return hasher.hexdigest(), False
    except OSError:
        return None, False


def _sha_fail(expected: str, got: str, part: Path, size: int = 0, resumed_from: int = 0) -> dict:
    """The sha256 mismatch verdict: the bytes are WRONG (corrupted in
    flight, or the source is lying) -- resuming them would reproduce
    the same wrong bytes, so they are DELETED, and the error names
    both hashes so the paste-back settles it."""
    try:
        part.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        part.with_name(part.name + ".etag").unlink(missing_ok=True)
    except OSError:
        pass
    return _fail(
        f"sha256 mismatch — the downloaded bytes do not match what "
        f"Hugging Face published (expected {expected}, got {got}); "
        f"the wrong bytes were deleted — retry the download",
        part=None,
        size=size,
        resumed_from=resumed_from,
        sha256_ok=False,
    )


def download(
    url: str,
    dest_dir,
    filename: str | None = None,
    *,
    on_progress: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    resume: bool = True,
    chunk_bytes: int = CHUNK_BYTES,
    timeout: float = DOWNLOAD_TIMEOUT_S,
    expected_sha256: str | None = None,
) -> dict:
    """Stream ``url`` into ``dest_dir/filename`` with resume, progress
    and cancel. Never raises; the verdict is the returned dict:

      ok=True          -> {"path", "size", "resumed_from", "sha256_ok", ...}
      cancelled=True    -> .part kept for a later resume
      ok=False + error -> honest text; .part kept when it holds bytes

    Resume: an existing ``<name>.part`` continues via an HTTP Range
    request when the server honors it (206); a server that ignores
    Range (plain 200) restarts from zero. The completed file is renamed
    into place ATOMICALLY (os.replace) -- a model is never half-visible
    under its real name -- and a final size sanity check catches a
    short read (server lied or connection died mid-body).

    V0.6.61 -- the sha256 contract: when ``expected_sha256`` is given
    (the catalog's PUBLISHED hash -- the HF API's lfs.sha256, the
    content hash, mechanism proven live), the stream is hashed
    incrementally (the resume path hashes the .part prefix first,
    chunked, never slurped) and a mismatch DELETES the wrong bytes:
    a corrupted file -- valid GGUF header, right size, garbage tensor
    data -- can never be installed under its real name.
    """
    dest = Path(dest_dir)
    final = dest / (Path(filename).name if filename else _url_filename(url))
    part = final.with_name(final.name + ".part")
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _fail(f"cannot create destination folder: {e}")

    # V0.6.60 review fix: resume is only trusted when the .part carries
    # its ETag sidecar AND the server honors If-Range (a 206). A
    # republished remote + a blind Range resume = a mixed old-prefix /
    # new-suffix file that PASSES the size check (the fresh-eyes review
    # proved it dynamically) -- the sidecar makes the mismatch show up
    # as a plain 200 full-body restart instead. A .part with NO
    # sidecar (a crash before the sidecar was written, or a foreign
    # file) is never trusted: restart from zero.
    sidecar = part.with_name(part.name + ".etag")
    start = 0
    etag = None
    if resume and part.exists() and sidecar.exists():
        try:
            etag = sidecar.read_text(encoding="utf-8").strip() or None
            start = part.stat().st_size
        except OSError:
            etag = None
            start = 0

    try:
        headers = _ua_headers()
        if start > 0:
            headers = dict(headers)
            headers["Range"] = f"bytes={start}-"
            if etag:
                headers["If-Range"] = etag
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            # A 200 (or 416) means the server did NOT honor the range
            # (ignored, or the remote CHANGED under the If-Range):
            # restart from zero so the file is never corrupted by an
            # appended full body.
            resuming = start > 0 and status == 206
            if not resuming:
                start = 0
            total = None
            content_range = resp.headers.get("Content-Range") or ""
            if content_range.startswith("bytes "):
                # "bytes <start>-<end>/<total>" -- the authoritative total
                try:
                    total = int(content_range.split("/")[-1])
                except (IndexError, ValueError):
                    total = None
            if total is None:
                try:
                    length = int(resp.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    length = 0
                total = (start + length) if (length and resuming) else (length or None)
            # the sidecar is written BEFORE the first body byte: if the
            # process dies mid-download, the next attempt either
            # resumes (matching etag) or restarts -- never mixes.
            new_etag = resp.headers.get("ETag")
            try:
                if new_etag:
                    sidecar.write_text(new_etag, encoding="utf-8")
                else:
                    sidecar.unlink(missing_ok=True)
            except OSError:
                pass
            t0 = time.monotonic()
            done = start
            # V0.6.61: the incremental hasher. The .part prefix (a
            # resume) is hashed from disk FIRST -- chunked, on this
            # worker thread, never slurped -- so the guarantee covers
            # the WHOLE file, prefix + freshly streamed bytes.
            hasher = hashlib.sha256() if expected_sha256 else None
            if hasher is not None and start > 0:
                # V0.6.61 review fix: the prefix hash honors should_cancel
                # too (a 1.6 GB prefix read must never ignore the 🔄/✖
                # button for seconds); a cancel keeps the .part.
                prefix_digest, prefix_cancelled = _hash_file(
                    part, hasher, chunk_bytes, should_cancel
                )
                if prefix_cancelled:
                    return {
                        "ok": False,
                        "cancelled": True,
                        "path": None,
                        "part_path": str(part),
                        "size": start,
                        "resumed_from": start,
                        "sha256_ok": None,
                        "error": None,
                    }
                if prefix_digest is None:
                    return _fail(
                        f"cannot read {part.name} to hash the resume prefix"
                    )
            # initial callback (0% / resumed state) then per-chunk
            _safe_cb(on_progress, _progress_dict(done, total, start, t0, final))
            cancelled = False
            with open(part, "ab" if resuming else "wb") as fh:
                while True:
                    if should_cancel is not None and should_cancel():
                        cancelled = True
                        break
                    chunk = resp.read(chunk_bytes)
                    if not chunk:
                        break
                    fh.write(chunk)
                    if hasher is not None:
                        hasher.update(chunk)
                    done += len(chunk)
                    if time.monotonic() - t0 >= _MIN_PROGRESS_CB_S:
                        _safe_cb(
                            on_progress, _progress_dict(done, total, start, t0, final)
                        )
            if cancelled:
                return {
                    "ok": False,
                    "cancelled": True,
                    "path": None,
                    "part_path": str(part),
                    "size": done,
                    "resumed_from": start,
                    "sha256_ok": None,
                    "error": None,
                }
            actual = part.stat().st_size
            if total is not None and actual != total:
                # short read: keep .part for a resume, report honestly
                return _fail(
                    f"download incomplete ({actual} of {total} bytes) — "
                    f"{part.name} kept for resume",
                    part=part,
                    size=actual,
                    resumed_from=start,
                    sha256_ok=None,
                )
            if hasher is not None:
                got = hasher.hexdigest()
                if got != expected_sha256:
                    return _sha_fail(
                        expected_sha256, got, part, size=actual, resumed_from=start
                    )
                sha256_ok = True
            else:
                sha256_ok = None
            os.replace(part, final)  # atomic: complete or absent, never partial
            try:
                sidecar.unlink(missing_ok=True)  # the resume bookkeeping goes with it
            except OSError:
                pass
            _safe_cb(
                on_progress,
                _progress_dict(actual, total or actual, start, t0, final),
            )
            return {
                "ok": True,
                "cancelled": False,
                "path": str(final),
                "part_path": None,
                "size": actual,
                "resumed_from": start,
                "sha256_ok": sha256_ok,
                "error": None,
            }
    except urllib.error.HTTPError as e:
        if e.code == 416 and start > 0:
            # V0.6.60 review fix (the 416 dead end): the Range is
            # unsatisfiable -- the remote SHRANK below the .part (a
            # republished, smaller file), or the .part is ALREADY the
            # complete file (a cancel between the last chunk write and
            # the os.replace). Blindly retrying re-sends the same
            # unsatisfiable Range forever; instead: probe the fresh
            # size -- equal to the .part means "already complete" (the
            # rename finishes now, zero bytes moved), anything else
            # means the remote changed under us (one fresh restart).
            pr = probe(url, timeout=timeout)
            part_size = None
            try:
                part_size = part.stat().st_size
            except OSError:
                part_size = None
            if pr["ok"] and pr["size"] is not None and part_size == pr["size"]:
                # V0.6.61: the sha gate applies HERE too — a
                # complete-size .part with wrong bytes is deleted, not
                # renamed into place (the recovery must not bypass the
                # contract).
                if expected_sha256:
                    # V0.6.61 review fix: cancel is honored here too (a
                    # 1.6 GB hash read must never ignore the ✖ button);
                    # the .part is kept — it is still good bytes.
                    got, hash_cancelled = _hash_file(
                        part, hashlib.sha256(), chunk_bytes, should_cancel
                    )
                    if hash_cancelled:
                        return {
                            "ok": False,
                            "cancelled": True,
                            "path": None,
                            "part_path": str(part),
                            "size": part_size or 0,
                            "resumed_from": 0,
                            "sha256_ok": None,
                            "error": None,
                        }
                    if got is None or got != expected_sha256:
                        return _sha_fail(
                            expected_sha256, got or "<unreadable>", part,
                            size=part_size or 0,
                        )
                try:
                    os.replace(part, final)
                except OSError as rename_err:
                    return _fail(f"cannot finalize completed download: {rename_err}", part=part)
                # V0.6.61 review fix: the bookkeeping unlink is SEPARATE
                # from the rename's try — a failing unlink after a
                # successful rename must not report ok=False while the
                # final file IS installed.
                try:
                    sidecar.unlink(missing_ok=True)
                except OSError:
                    pass
                return {
                    "ok": True,
                    "cancelled": False,
                    "path": str(final),
                    "part_path": None,
                    "size": part_size or 0,
                    "resumed_from": 0,
                    "sha256_ok": bool(expected_sha256) or None,
                    "error": None,
                    "recovered": "already-complete",
                }
            # the remote changed: restart once from zero (no Range can 416)
            # V0.6.61: the hash is FORWARDED (the restart's bytes must
            # still prove out against the published sha256).
            return download(
                url,
                dest_dir,
                filename=filename,
                on_progress=on_progress,
                should_cancel=should_cancel,
                resume=False,
                chunk_bytes=chunk_bytes,
                timeout=timeout,
                expected_sha256=expected_sha256,
            )
        return _fail(f"HTTP {e.code} {e.reason}", part=part)
    except Exception as e:  # noqa: BLE001 -- best-effort, never raises
        return _fail(f"{type(e).__name__}: {e}", part=part)


# ── verify + where to land the file ────────────────────────────────────────


def verify_download(path, spec: DownloadSpec | None = None) -> dict:
    """The post-download gate: the V0.6.59 catalog's own validation
    (GGUF magic + whisper architecture from the file's header) plus an
    optional exact-size cross-check against the catalog entry.

    size_ok is tri-state: True/False (vs. the catalog hint) or None
    (no hint given) -- a mismatch is a WARNING (HF may have republished
    the file; the header check is authoritative), surfaced to the
    operator, not a hard failure.
    """
    ok, info, problem = validate_whisper_model(path)
    size_ok = None
    if ok and spec is not None:
        try:
            size_ok = Path(path).stat().st_size == spec.size_hint
        except OSError:
            size_ok = None
    return {"ok": ok, "info": info, "problem": problem, "size_ok": size_ok}


def default_download_dir(
    exe_path: str | None = None,
    home: str | None = None,
    models_dir: str | None = None,
) -> str:
    """Where a downloaded model should LAND so the V0.6.59 scan finds
    it immediately (first-listed locations win):

      1. ``models_dir`` when it exists (the caller's explicit choice)
      2. C:\\transcribe.cpp\\models -- the rig's documented layout
         (Windows-shaped; on a non-Windows host it is skipped, not
         literal-created -- see the is_absolute guard below)
      3. the CLI exe's ``models/`` folder (a portable install)
      4. ~/Downloads
      5. the first CREATABLE of the above (exe/models, the documented
         default, the explicit dir, ~/Downloads)

    Never raises; the download itself reports a bad destination
    honestly.
    """
    home_dir = Path(home) if home else Path.home()
    default_dir = Path(DEFAULT_MODELS_DIR)
    # The documented rig layout is a WINDOWS path. On a POSIX host it
    # would be a RELATIVE path with backslashes in the name -- never
    # treat that as a location (and NEVER mkdir it: a literal
    # 'C:\\transcribe.cpp' folder in the CWD is repo pollution).
    usable_default = default_dir if os.name == "nt" or default_dir.is_absolute() else None
    candidates: list[Path] = []
    if models_dir:
        candidates.append(Path(models_dir))
    if usable_default is not None:
        candidates.append(usable_default)
    if exe_path:
        try:
            p = Path(exe_path)
            exe_dir = p if p.is_dir() else p.parent
            candidates.append(exe_dir / "models")
        except Exception:  # noqa: BLE001
            pass
    candidates.append(home_dir / "Downloads")
    for d in candidates:
        try:
            if d.is_dir():
                return str(d)
        except OSError:
            continue
    # Nothing exists yet: create the first creatable, in priority
    # order (the exe's models folder keeps a portable install
    # self-contained; the documented default matches the rig layout).
    creation_order: list[Path] = []
    if exe_path:
        try:
            p = Path(exe_path)
            exe_dir = p if p.is_dir() else p.parent
            creation_order.append(exe_dir / "models")
        except Exception:  # noqa: BLE001
            pass
    if usable_default is not None:
        creation_order.append(usable_default)
    if models_dir:
        creation_order.append(Path(models_dir))
    creation_order.append(home_dir / "Downloads")
    for d in creation_order:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return str(d)
        except OSError:
            continue
    return str(home_dir / "Downloads")


# ── the dialog-facing one-liners ─────────────────────────────────────────────


def format_progress_line(p: dict) -> str:
    """The live progress line: '572.2 MB / 1.1 GB · 50% · 25.0 MB/s ·
    ETA 12s'. Honest when the total is unknown ('?')."""
    done = p.get("done") or 0
    total = p.get("total")
    parts = [f"{_fmt_bytes(done)} / {_fmt_bytes(total) if total else '?'}"]
    pct = p.get("pct")
    if pct is not None:
        parts.append(f"{pct:.0f}%")
    speed = p.get("speed_bps") or 0
    if speed > 0:
        parts.append(_fmt_speed(speed))
    eta = p.get("eta_s")
    if eta is not None and eta >= 0:
        parts.append(f"ETA {eta:.0f}s")
    return " · ".join(parts)
