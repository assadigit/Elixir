"""Round-4 §10 — the reference overlay + pixel-difference evidence.

Pairs the approved reference (508782d6-4b80-48be-9046-d081ce258b75.png,
1536×1024) with the app captured at the SAME canvas size and framing
(now5_reference.png), producing:

  * now5_overlay.png  — the two frames averaged (structural differences
                        read as ghosting; identical regions stay clean)
  * now5_difference.png — a amplified per-pixel difference heatmap

Both frames are full app-window renders INCLUDING the ~21 px backdrop
margins, so the shells align without any manual registration.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

root = Path(__file__).resolve().parent.parent
ref = Image.open(root / "508782d6-4b80-48be-9046-d081ce258b75.png").convert("RGB")
app = Image.open(root / "now5_reference.png").convert("RGB")
assert ref.size == app.size, (ref.size, app.size)

# ── the overlay: straight 50/50 average ─────────────────────────────────────
overlay = Image.blend(ref, app, 0.5)
overlay.save(root / "now5_overlay.png")

# ── the amplified difference ────────────────────────────────────────────────
diff = ImageChops.difference(ref, app)
# amplify so small deltas are visible; clamp at 255
r, g, b = diff.split()
r = r.point(lambda v: min(255, v * 3))
g = g.point(lambda v: min(255, v * 3))
b = b.point(lambda v: min(255, v * 3))
Image.merge("RGB", (r, g, b)).save(root / "now5_difference.png")

# ── the numbers: mean absolute delta over the whole canvas + the shell ──────
import numpy as np  # noqa: E402

a = np.asarray(ref, dtype=np.int16)
b = np.asarray(app, dtype=np.int16)
d = np.abs(a - b)
mean_all = d.mean()
# the shell interior (drop the 21 px backdrop margins + 2 px hairline)
shell = d[23 : 1024 - 23, 23 : 1536 - 23]
mean_shell = shell.mean()
# the fraction of shell pixels that are near-identical (<8/255 delta)
near = (shell.max(axis=2) < 8).mean()
print(f"mean|Δ| canvas={mean_all:.2f}/255 shell={mean_shell:.2f}/255")
print(f"shell pixels within 8/255 of the reference: {near:.1%}")

# ── a side-by-side comparison sheet for the report ──────────────────────────
sheet = Image.new("RGB", (1536, 1024 + 36 + 1024), (255, 255, 255))
sheet.paste(ref, (0, 0))
sheet.paste(app, (0, 1024 + 36))
sheet.save(root / "now5_side_by_side.png")
print("saved now5_overlay.png, now5_difference.png, now5_side_by_side.png")
