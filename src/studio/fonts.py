"""Font lookup shared by the text layer and contact sheets (Pillow based).

Homebrew's ffmpeg ships without drawtext/libass, so all text is rasterized with Pillow.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path

from PIL import ImageFont

REPO_FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"

FONT_DIRS = [
    REPO_FONTS,
    Path.home() / "Library" / "Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/System/Library/Fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
    Path("/usr/share/fonts"),
    Path("C:/Windows/Fonts"),
]

# Defaults chosen for full Vietnamese (and general Latin) coverage.
DEFAULT_BOLD = ["BeVietnamPro-Bold", "Arial Bold", "Arial Unicode", "DejaVuSans-Bold", "arialbd"]
DEFAULT_REGULAR = ["BeVietnamPro-Regular", "Arial", "Arial Unicode", "DejaVuSans", "arial"]


@functools.lru_cache(maxsize=None)
def _index() -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for d in FONT_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                idx.setdefault(f.stem.lower(), f)
    return idx


def find_font(name: str | None, bold: bool = True) -> Path:
    """Resolve a font by path, exact file stem, or substring of the stem."""
    idx = _index()
    if name:
        p = Path(name).expanduser()
        if p.exists():
            return p
        key = name.lower()
        if key in idx:
            return idx[key]
        for stem, path in sorted(idx.items(), key=lambda kv: len(kv[0])):
            if key in stem:
                return path
        print(f"warning: font '{name}' not found, using default", file=sys.stderr)
    for cand in (DEFAULT_BOLD if bold else DEFAULT_REGULAR):
        if cand.lower() in idx:
            return idx[cand.lower()]
    raise LookupError("No usable font found; put a .ttf in assets/fonts/")


@functools.lru_cache(maxsize=256)
def load(name: str | None, size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(find_font(name, bold)), size=max(4, int(size)))
