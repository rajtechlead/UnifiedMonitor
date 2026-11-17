"""Generate branding/icon.ico from the UniMonitor brand palette.

Run from the repo root:  python scripts/make_icon.py

Windows installer (NSIS) and the PyInstaller executable both need a real .ico,
so this is checked in rather than generated at build time.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BRAND_BLUE = (23, 118, 210, 255)  # #1776D2
WHITE = (255, 255, 255, 255)
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size: int) -> Image.Image:
    scale = 8  # draw large, then downsample for crisp edges
    canvas = size * scale
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(canvas * 0.22)
    draw.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=radius, fill=BRAND_BLUE)

    # Shield silhouette
    cx = canvas / 2
    top = canvas * 0.22
    width = canvas * 0.46
    bottom = canvas * 0.80
    shield = [
        (cx - width / 2, top),
        (cx + width / 2, top),
        (cx + width / 2, top + (bottom - top) * 0.55),
        (cx, bottom),
        (cx - width / 2, top + (bottom - top) * 0.55),
    ]
    draw.polygon(shield, fill=WHITE)

    # Inner check mark
    draw.line(
        [
            (cx - width * 0.22, canvas * 0.46),
            (cx - width * 0.03, canvas * 0.58),
            (cx + width * 0.26, canvas * 0.36),
        ],
        fill=BRAND_BLUE,
        width=max(2, int(canvas * 0.055)),
        joint="curve",
    )
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "branding" / "icon.ico"
    images = [draw_icon(size) for size in SIZES]
    images[-1].save(target, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
