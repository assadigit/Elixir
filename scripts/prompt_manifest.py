#!/usr/bin/env python3
"""Phase 1.4 (V0.14) — prompt-bank version manifest generator.

Freezes the identity of every prompt template under ``prompts/`` into
``tests/golden/prompt_manifest.json`` (relative path + SHA-256 + size per
file, plus an aggregate integrity hash). The freeze test
(``tests/test_golden_freeze.py``) regenerates the manifest in memory and
fails on ANY drift — so an accidental prompt edit, reformat, or merge
mistake is caught by CI even when no functional test notices.

Why: prompts are behavior. The summarisation pipeline's output is a direct
function of the prompt bank, but prompts are plain ``.md`` files that
review like documentation. The manifest turns them into a versioned,
diff-gated contract — the "prompt-version" half of the Phase 1 golden
freeze (the other half is the frozen pipeline outputs).

Usage:
  python scripts/prompt_manifest.py            # write tests/golden/prompt_manifest.json
  python scripts/prompt_manifest.py --check    # verify (exit 1 on drift)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
MANIFEST_PATH = PROJECT_ROOT / "tests" / "golden" / "prompt_manifest.json"

# Prompt files that are documentation, not pipeline inputs. (None currently —
# everything under prompts/ is loadable by PromptManager. Kept as a hook so
# future additions don't silently weaken the gate.)
EXCLUDES: set[str] = set()


def build_manifest() -> dict:
    files = sorted(
        p
        for p in PROMPTS_DIR.rglob("*.md")
        if p.relative_to(PROMPTS_DIR).as_posix() not in EXCLUDES
    )
    entries = []
    for p in files:
        data = p.read_bytes()
        entries.append(
            {
                "path": p.relative_to(PROMPTS_DIR).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    # Aggregate integrity hash: over (path, sha256) pairs in sorted order —
    # stable across machines and independent of JSON formatting.
    agg = hashlib.sha256()
    for e in entries:
        agg.update(f"{e['path']}:{e['sha256']}\n".encode())
    # NOTE: generated_for_version is INFORMATIONAL (when the manifest was
    # last regenerated) — it is deliberately NOT part of the identity that
    # --check / the freeze test compare, so a VERSION bump never trips the
    # gate. Prompt identity = files + manifest_sha256, nothing else.
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    return {
        "schema": 1,
        "generated_for_version": version,
        "prompts_dir": "prompts/",
        "file_count": len(entries),
        "manifest_sha256": agg.hexdigest(),
        "files": entries,
    }


def manifest_identity(manifest: dict) -> dict:
    """The identity fields drift-gates compare (version field excluded —
    it is regeneration metadata, not prompt identity)."""
    return {
        "file_count": manifest["file_count"],
        "manifest_sha256": manifest["manifest_sha256"],
        "files": manifest["files"],
    }


def write_manifest() -> Path:
    manifest = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return MANIFEST_PATH


def check_manifest() -> int:
    if not MANIFEST_PATH.exists():
        print(f"FAIL: manifest missing: {MANIFEST_PATH}", file=sys.stderr)
        return 1
    current = build_manifest()
    committed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest_identity(current) == manifest_identity(committed):
        print(
            f"OK: prompt manifest matches ({current['file_count']} files, "
            f"agg {current['manifest_sha256'][:12]}…)"
        )
        return 0
    # Drift — report exactly what changed.
    cur_by_path = {e["path"]: e for e in current["files"]}
    com_by_path = {e["path"]: e for e in committed["files"]}
    added = sorted(set(cur_by_path) - set(com_by_path))
    removed = sorted(set(com_by_path) - set(cur_by_path))
    changed = sorted(
        p
        for p in set(cur_by_path) & set(com_by_path)
        if cur_by_path[p]["sha256"] != com_by_path[p]["sha256"]
    )
    print("FAIL: prompt manifest drift detected:", file=sys.stderr)
    for p in added:
        print(f"  + {p}", file=sys.stderr)
    for p in removed:
        print(f"  - {p}", file=sys.stderr)
    for p in changed:
        print(f"  ~ {p} (content changed)", file=sys.stderr)
    print(
        "\nIf intentional: regenerate with  python scripts/prompt_manifest.py  "
        "and re-freeze golden outputs (scripts/bench_chapter.py --save-golden).",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prompt-bank version manifest")
    parser.add_argument(
        "--check", action="store_true", help="verify the committed manifest (exit 1 on drift)"
    )
    args = parser.parse_args(argv)
    if args.check:
        return check_manifest()
    path = write_manifest()
    m = json.loads(path.read_text(encoding="utf-8"))
    print(f"wrote {path} — {m['file_count']} prompt files, agg {m['manifest_sha256'][:12]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
