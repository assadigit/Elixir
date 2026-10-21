"""Lucide-style line icons rendered to QPixmap / QIcon on the fly.

We embed a small curated set of Lucide (https://lucide.dev) icon path data
(24×24 viewBox, stroke-based, 1.75–2px) and render them to pixmaps in any
colour, so icons always match the active theme.  This avoids shipping binary
icon assets and keeps the app a single, self-contained Python package.

Usage::

    from ui_qt.components.icons import icon, pixmap

    gear = icon("settings", color="#D4A574", size=20)
    btn.setIcon(gear)

    # or a pixmap for labels / custom painting
    pm = pixmap("book", color=theme_manager.palette.text_primary, size=28)
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# ─────────────────────────────────────────────────────────────────────────────
# Icon path data (Lucide, 24×24 viewBox).  Each entry is the inner SVG markup
# (paths / circles / polygons).  Stroke is applied via the wrapping <svg>.
# ─────────────────────────────────────────────────────────────────────────────

ICONS: dict[str, str] = {
    "book": ('<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>'),
    "newspaper": (
        '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>'
        '<path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>'
    ),
    "file-text": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'
    ),
    "folder": (
        '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>'
    ),
    "folder-open": (
        '<path d="m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>'
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "sliders-horizontal": (
        '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/>'
        '<line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/>'
        '<line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/>'
        '<line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/>'
        '<line x1="16" x2="16" y1="18" y2="22"/>'
    ),
    "sun": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2"/><path d="M12 20v2"/>'
        '<path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>'
        '<path d="M2 12h2"/><path d="M20 12h2"/>'
        '<path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'
    ),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "flask": (
        '<path d="M4.5 3h15"/><path d="M6 3v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V3"/>'
        '<path d="M6 14h12"/>'
    ),
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "refresh": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M8 16H3v5"/>'
    ),
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "scan": (
        '<path d="M3 7V5a2 2 0 0 1 2-2h2"/>'
        '<path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
        '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/>'
        '<path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
        '<path d="M7 12h10"/>'
    ),
    "layers": (
        '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>'
        '<path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>'
        '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>'
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
        '<circle cx="9" cy="9" r="2"/>'
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
    ),
    "table": (
        '<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M3 9h18"/><path d="M3 15h18"/>'
    ),
    "sigma": '<path d="M18 7V4H6l6 8-6 8h12v-3"/>',
    "layout": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>'
    ),
    "cpu": (
        '<rect width="16" height="16" x="4" y="4" rx="2"/>'
        '<rect width="6" height="6" x="9" y="9" rx="1"/>'
        '<path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/>'
        '<path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>'
    ),
    "cloud": ('<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>'),
    "sparkles": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .962 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.962 0z"/>'
        '<path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>'
    ),
    "file-output": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<path d="M14 2v6h6"/><path d="M9 14l2 2 2-2"/><path d="M11 16V11"/>'
    ),
    "scissors": (
        '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
        '<path d="M20 4 8.12 15.88"/><path d="M14.47 14.48 20 20"/>'
        '<path d="M8.12 8.12 12 12"/>'
    ),
    "alert-triangle": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        '<path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "info": ('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'),
    # V13.31.0: shield icon for Hallucination Audit tab
    "shield": ('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>'),
    "list-checks": (
        '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/>'
        '<path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>'
        '<path d="M2 12h20"/>'
    ),
    "wand": (
        '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/>'
        '<path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M15 9h0"/>'
        '<path d="M17.8 6.2 19 5"/><path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/>'
    ),
    "rocket": (
        '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91 0z"/>'
        '<path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
        '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>'
        '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'
    ),
    "save": (
        '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
        '<path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>'
    ),
    "rotate-ccw": (
        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
    ),
    "eye": (
        '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "key": (
        '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
        '<path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>'
    ),
    "languages": (
        '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/>'
        '<path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>'
    ),
    "mic": (
        '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>'
    ),
    "plus": ('<path d="M5 12h14"/><path d="M12 5v14"/>'),
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>'
    ),
    "pencil": (
        '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>'
        '<path d="m15 5 4 4"/>'
    ),
    "message-square": ('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
    "bookmark": ('<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>'),
    "zap": (
        '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'
    ),
}


def _svg(name: str, color: str, size: int, stroke: float = 1.85) -> str:
    """Wrap an icon's inner markup into a complete coloured SVG string."""
    inner = ICONS.get(name)
    if inner is None:
        raise KeyError(f"Unknown icon: {name!r}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{inner}</svg>"
    )


def pixmap(name: str, color: str = "#E8EAED", size: int = 20) -> QPixmap:
    """Render icon ``name`` to a QPixmap at the given colour and size.

    Renders at 2× the target size then scales down smoothly — eliminates
    the pixelation/jaggies that appear when scaling a 24×24 viewBox up to
    large sizes (64px+).
    """
    scale = 2  # supersample for crisp rendering
    render_size = size * scale
    svg = _svg(name, color, render_size)
    pm_hi = QPixmap(render_size, render_size)
    pm_hi.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pm_hi)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    renderer.render(painter)
    painter.end()
    # scale down to target size with smooth transformation
    pm = pm_hi.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


# V18.20.4.8: O-b6 icon cache — keyed by the (name, colour, size) tuple.
_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}


def icon(name: str, color: str = "#E8EAED", size: int = 20) -> QIcon:
    """Render icon ``name`` to a QIcon (cached per name/colour/size)."""
    key = (name, color, size)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    built = QIcon(pixmap(name, color, size))
    _ICON_CACHE[key] = built
    return built


def icon_for_mode(name: str, is_dark: bool, size: int = 20) -> QIcon:
    """Convenience: pick a sensible default colour for the active mode."""
    return icon(name, "#E8EAED" if is_dark else "#1A1D23", size)


# ─────────────────────────────────────────────────────────────────────────────
# V4.7.25: PNG asset support with SVG fallback
# ─────────────────────────────────────────────────────────────────────────────


def _project_root() -> Path:
    """Return the project root directory (repo root / PyInstaller bundle)."""
    from app_paths import bundle_dir  # V0.6.63: bundle-aware

    return bundle_dir()


def _assets_dir() -> Path:
    """Return the assets directory path."""
    return _project_root() / "assets"


def load_png_icon(name: str, size: int = 64) -> QPixmap | None:
    """Load a PNG icon from ``assets/icons/{name}.png``.

    Returns None if the file doesn't exist (caller should fall back to SVG).

    The PNG is scaled to ``size`` × ``size`` with smooth transformation.
    Transparent PNGs are supported.
    """
    png_path = _assets_dir() / "icons" / f"{name}.png"
    if not png_path.exists():
        return None
    pm = QPixmap(str(png_path))
    if pm.isNull():
        return None
    # Scale with smooth transformation for crisp rendering
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def load_brand_logo(height: int = 28) -> QPixmap | None:
    """Load the brand logo PNG from ``assets/logo.png``.

    Returns None if the file doesn't exist (caller should fall back to the
    SVG book icon). The logo is scaled to the requested height while
    preserving aspect ratio.
    """
    logo_path = _assets_dir() / "logo.png"
    if not logo_path.exists():
        return None
    pm = QPixmap(str(logo_path))
    if pm.isNull():
        return None
    # Scale to requested height, preserving aspect ratio
    scaled = pm.scaledToHeight(height, Qt.SmoothTransformation)
    return scaled


def pixmap_with_png_fallback(
    name: str,
    color: str = "#E8EAED",
    size: int = 64,
    svg_fallback: str | None = None,
) -> QPixmap:
    """Return a pixmap for icon ``name``: PNG if available, else SVG.

    Args:
        name:          the PNG filename key (e.g., "normal_book" — looks for
                       assets/icons/{name}.png). This is typically the preset key.
        color:         color for the SVG fallback icon.
        size:          target size in pixels.
        svg_fallback:  the SVG icon name to use if PNG doesn't exist
                       (e.g., "book"). If None, uses ``name`` as the SVG icon
                       name (which may fail if ``name`` isn't a valid SVG icon).

    Usage::

        from ui_qt.components.icons import pixmap_with_png_fallback
        # Looks for assets/icons/normal_book.png, falls back to SVG "book"
        pm = pixmap_with_png_fallback("normal_book", color=p.accent, size=64, svg_fallback="book")
        label.setPixmap(pm)
    """
    png = load_png_icon(name, size)
    if png is not None:
        return png
    # Fall back to SVG — use svg_fallback if provided, else use name
    svg_name = svg_fallback if svg_fallback else name
    return pixmap(svg_name, color, size)
