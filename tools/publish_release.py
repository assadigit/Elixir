#!/usr/bin/env python3
"""V0.6.5 — the one-command GitHub Release publisher.

Every version ships with a GitHub Release (the standing rule added to
AGENTS.md in V0.6.5): the notes live in ``release_notes/VX.Y.Z.md`` in
the repo, and this script creates/updates the release for a tag and
uploads the zip asset.

Usage (the one-off token procedure — the token never lands in the repo,
the logs, or the notes):

    python tools/publish_release.py V0.6.5 \
        --zip download/Elixir-V0.6.5.zip \
        --token ghp_...

Backfill every version that has notes but no release yet:

    python tools/publish_release.py --all --token ghp_...

Dry run (no network):

    python tools/publish_release.py V0.6.5 --zip ... --dry-run

Security notes:
  - The token is accepted from --token or the GITHUB_TOKEN env var and
    is NEVER written anywhere (no config file, no log line).
  - The release body comes verbatim from release_notes/<tag>.md.
  - Repo: assadigit/elixir (override with --repo owner/name).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "assadigit/elixir"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"  # asset uploads use a different host


def _read_notes(tag: str) -> str:
    """The release body: release_notes/<tag>.md, verbatim."""
    notes = REPO_ROOT / "release_notes" / f"{tag}.md"
    if not notes.exists():
        raise SystemExit(f"❌ No release notes for {tag}: {notes} missing")
    return notes.read_text(encoding="utf-8")


def _api(
    method: str,
    path: str,
    token: str,
    repo: str,
    *,
    payload: dict | None = None,
    accept: str = "application/vnd.github+json",
) -> tuple[int, dict | bytes]:
    url = path if path.startswith("http") else f"{API}/repos/{repo}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "elixir-release-publisher")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def _find_asset_endpoint(release: dict, name: str) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            return asset["url"]  # the upload URL endpoint (for replace)
    return None


def publish_release(
    tag: str,
    *,
    token: str,
    repo: str = DEFAULT_REPO,
    zip_path: Path | None = None,
    dry_run: bool = False,
    make_latest: bool = True,
) -> bool:
    body = _read_notes(tag)
    print(f"📦 {tag}: notes {len(body):,} chars" + (f", asset {zip_path}" if zip_path else ""))

    if dry_run:
        print(
            f"   (dry-run) would create/update release {tag} on {repo}"
            + (" and upload the asset" if zip_path else "")
        )
        return True

    # Does the release already exist?
    status, existing = _api("GET", f"releases/tags/{tag}", token, repo)
    payload = {
        "tag_name": tag,
        "name": tag,
        "body": body,
        "draft": False,
        "prerelease": False,
    }
    if make_latest:
        payload["make_latest"] = "true"

    if status == 200:
        release_id = existing["id"]
        status, updated = _api("PATCH", f"releases/{release_id}", token, repo, payload=payload)
        if status != 200:
            print(f"❌ update failed: {status} {updated}")
            return False
        print(f"   ✅ release updated (id {release_id})")
    else:
        # The tag itself must exist on the remote (pushed with the release
        # commit). Creating the release attaches to it.
        status, created = _api("POST", "releases", token, repo, payload=payload)
        if status not in (201,):
            print(f"❌ create failed: {status} {created}")
            return False
        release_id = created["id"]
        print(f"   ✅ release created (id {release_id})")

    # Upload / replace the zip asset.
    if zip_path is not None:
        if not zip_path.exists():
            print(f"❌ asset missing: {zip_path}")
            return False
        asset_name = zip_path.name
        # Replace an existing asset of the same name (delete first — the
        # upload endpoint rejects duplicates).
        status, release = _api("GET", f"releases/{release_id}", token, repo)
        if status == 200:
            endpoint = _find_asset_endpoint(release, asset_name)
            if endpoint:
                del_status, _ = _api("DELETE", endpoint, token, repo)
                if del_status not in (204,):
                    print(f"   ⚠️ old asset delete returned {del_status} (continuing)")
        # V0.6.5 fix: asset uploads go to uploads.github.com, NOT
        # api.github.com (the API host 404s the multipart upload).
        upload_url = f"{UPLOADS}/repos/{repo}/releases/{release_id}/assets?name={asset_name}"
        # Raw binary upload (the shared _api helper JSON-encodes payloads).
        req = urllib.request.Request(upload_url, data=zip_path.read_bytes(), method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Content-Type", "application/zip")
        req.add_header("User-Agent", "elixir-release-publisher")
        try:
            with urllib.request.urlopen(req, timeout=600):
                print(f"   ✅ asset uploaded: {asset_name} ({zip_path.stat().st_size:,} bytes)")
        except urllib.error.HTTPError as e:
            print(f"❌ asset upload failed: {e.code} {e.read()[:200]!r}")
            return False

    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("tag", nargs="?", help="e.g. V0.6.5 (or omit with --all)")
    ap.add_argument("--all", action="store_true", help="publish every release_notes/*.md tag")
    ap.add_argument("--zip", type=Path, default=None, help="the release asset to upload")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--token",
        default=None,
        help="GitHub token (or set GITHUB_TOKEN). Never stored anywhere.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # V0.6.6 (review-loop A3): --all never forwarded --zip to the per-tag
    # publish call, so `--all --zip X` silently published every release
    # with ZERO assets and exited 0 (a Rule-6 break). Each tag ships its
    # OWN zip — uploading one zip to six releases is never what the
    # caller meant, so reject the combination instead of guessing.
    if args.all and args.zip is not None:
        ap.error(
            "--zip uploads ONE tag's asset and cannot be combined with --all "
            "(each tag ships its own zip — run once per tag)"
        )

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token and not args.dry_run:
        print("❌ No token: pass --token or set GITHUB_TOKEN")
        return 2

    if args.all:
        tags = sorted(p.stem for p in (REPO_ROOT / "release_notes").glob("V*.md"))
        if not tags:
            print("❌ no release_notes/V*.md files")
            return 2
        print(f"Publishing {len(tags)} release(s): {', '.join(tags)}")
        ok = True
        for t in tags:
            # Only the newest is "Latest".
            ok = (
                publish_release(
                    t,
                    token=token or "",
                    repo=args.repo,
                    dry_run=args.dry_run,
                    make_latest=(t == tags[-1]),
                )
                and ok
            )
        return 0 if ok else 1

    if not args.tag:
        ap.error("pass a tag (V0.6.5) or --all")
    ok = publish_release(
        args.tag, token=token or "", repo=args.repo, zip_path=args.zip, dry_run=args.dry_run
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
