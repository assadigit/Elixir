"""V0.6.63: generate installer/elixir.ico — the app icon.

The repo ships no .ico (assets/logo.txt is ASCII art; assets/icons/*.txt are
text notes), so per the build contract a simple, deterministic icon is
generated: an amber rounded square with a white geometric "E" (three bars +
spine — no font dependency, byte-identical output on every run).

Usage::

    python installer/make_icon.py           # writes installer/elixir.ico

The generated .ico is committed; this script exists so the artifact stays
reproducible.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "elixir.ico"

SIZE = 256  # master size; Pillow emits the full size ladder into the .ico

# Flat amber (potion gold) on white letterform.
BG = (217, 119, 6, 255)  # #D97706
BG_DARK = (180, 95, 5, 255)  # subtle bottom shade for depth
FG = (255, 255, 255, 255)


def _rounded_square(draw: ImageDraw.ImageDraw, size: int, radius: int) -> None:
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
    # Bottom shade band (flat design hint of depth)
    draw.rounded_rectangle(
        [0, size * 0.62, size - 1, size - 1],
        radius=radius,
        fill=BG_DARK,
    )
    draw.rounded_rectangle([0, 0, size - 1, int(size * 0.62)], radius=radius, fill=BG)


def _letter_e(draw: ImageDraw.ImageDraw, size: int) -> None:
    """Geometric E: left spine + three horizontal bars (no fonts)."""
    m = size * 0.28  # margin
    w = size - 2 * m  # letter box width
    spine = size * 0.085
    bar_h = size * 0.072
    gap = (w - spine - 3 * bar_h) / 2.0
    x0 = m
    # Spine (full height)
    draw.rounded_rectangle(
        [x0, m, x0 + spine, size - m], radius=bar_h / 2, fill=FG
    )
    # Top, middle, bottom bars
    ys = [m, m + bar_h + gap, size - m - bar_h]
    for y in ys:
        draw.rounded_rectangle(
            [x0, y, m + w, y + bar_h], radius=bar_h / 2, fill=FG
        )


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _rounded_square(draw, SIZE, radius=int(SIZE * 0.22))
    _letter_e(draw, SIZE)
    return img


def main() -> None:
    img = build()
    img.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
