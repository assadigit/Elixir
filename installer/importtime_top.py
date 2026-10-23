"""V0.6.63: top-N slowest imports on the startup path (``python -X importtime``).

Runs ``python -X importtime -c "import main"`` in the repo and reports the
slowest modules by self-time and by cumulative time — the data behind the
"top 5 slowest imports" startup report. (``import main`` executes the module
level of main.py — the pre-Qt startup: settings import, crash arm, torch
probe, gpu-probe write — but opens no window.)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_LINE = re.compile(r"^import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(\S+)$")


def main() -> None:
    proc = subprocess.run(  # noqa: S603 — fixed argv
        [sys.executable, "-X", "importtime", "-c", "import main"],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=300,
    )
    rows = []
    for line in proc.stderr.splitlines():
        m = _LINE.match(line.strip())
        if m:
            self_us, cum_us, name = int(m.group(1)), int(m.group(2)), m.group(3)
            rows.append((self_us, cum_us, name))
    if not rows:
        print("importtime: no parseable output (stderr follows)")
        print(proc.stderr[-2000:])
        sys.exit(1)

    total_ms = sum(r[0] for r in rows) / 1000.0
    print(f"import profile: {len(rows)} modules, {total_ms:.0f} ms total self-time")
    print("\ntop 5 slowest imports (self time):")
    for self_us, _cum, name in sorted(rows, reverse=True)[:5]:
        print(f"  {self_us / 1000.0:9.1f} ms  {name}")
    print("\ntop 5 slowest imports (cumulative):")
    for _self_us, cum_us, name in sorted(rows, key=lambda r: r[1], reverse=True)[:5]:
        print(f"  {cum_us / 1000.0:9.1f} ms  {name}")


if __name__ == "__main__":
    main()
