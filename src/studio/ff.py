"""Thin wrappers around ffmpeg / ffprobe."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


class FFError(RuntimeError):
    pass


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise FFError(f"`{binary}` not found on PATH. Install it (macOS: brew install ffmpeg).")
    return path


def run(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command, raising FFError with the tail of stderr on failure."""
    cmd = [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=capture, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-25:])
        raise FFError(f"command failed ({proc.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return proc


def ffmpeg(args: list[str], **kw) -> subprocess.CompletedProcess:
    return run([require("ffmpeg"), "-hide_banner", "-nostdin", "-y", *args], **kw)


def hwaccel_args() -> list[str]:
    """Hardware decode for analysis passes (big speedup on 4K phone footage)."""
    return ["-hwaccel", "videotoolbox"] if sys.platform == "darwin" else []


def _fps(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "0"):
        return None
    try:
        return round(float(Fraction(rate)), 3)
    except (ValueError, ZeroDivisionError):
        return None


def probe(path: str | Path) -> dict:
    """Return a compact, display-oriented description of a media file."""
    path = Path(path)
    if not path.exists():
        raise FFError(f"file not found: {path}")
    out = run([
        require("ffprobe"), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    v = next((s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        kind = "image"
    elif v is None and a is not None:
        kind = "audio"
    elif v is not None:
        kind = "video"
    else:
        kind = "unknown"

    info: dict = {"path": str(path), "type": kind}
    dur = fmt.get("duration") or (v or a or {}).get("duration")
    if kind != "image" and dur:
        info["duration"] = round(float(dur), 3)

    if v is not None:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rotation = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rotation = int(sd["rotation"])
        if kind == "image":
            try:  # stills carry orientation in EXIF, which ffprobe does not apply
                from PIL import Image
                if Image.open(path).getexif().get(274, 1) in (5, 6, 7, 8):
                    rotation = 90
            except Exception:
                pass
        if abs(rotation) % 180 == 90:
            w, h = h, w  # ffmpeg auto-rotates on decode; report display size
        info.update({"width": w, "height": h})
        if rotation:
            info["rotation"] = rotation
        if kind == "video":
            info["fps"] = _fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate"))
            info["vcodec"] = v.get("codec_name")
            trc = v.get("color_transfer")
            if trc in ("smpte2084", "arib-std-b67"):
                info["hdr"] = trc  # PQ / HLG: colors may look washed out without tone mapping
    info["has_audio"] = a is not None
    if a is not None:
        info["sample_rate"] = int(a.get("sample_rate", 0) or 0)
        info["channels"] = a.get("channels")
    return info
