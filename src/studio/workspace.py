"""A workspace is any folder the user edits videos in.

Layout (created by `cstudio init`):

    <workspace>/
      studio.json               project marker + settings
      .studio/media.json        index of every source: id -> probe info
      .studio/analysis/<id>/    scenes, silence, loudness, transcript, contact sheets
      .studio/proxy/<id>.mp4    optional low-res copies for fast previews
      edits/*.edl.json          edit decision lists (the edit itself)
      renders/                  rendered outputs

Sources can live anywhere (inside the workspace or not); they are referenced by path.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from . import ff

MARKER = "studio.json"
MEDIA_EXT = ff.IMAGE_EXT | ff.AUDIO_EXT | {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".3gp"}
SKIP_DIRS = {".studio", "renders", "node_modules", ".git"}


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    # -- discovery -----------------------------------------------------------
    @classmethod
    def find(cls, start: Path | None = None) -> "Workspace":
        p = (start or Path.cwd()).resolve()
        if p.is_file():
            p = p.parent
        for cand in [p, *p.parents]:
            if (cand / MARKER).exists():
                return cls(cand)
        raise SystemExit(
            f"No {MARKER} found from {p} upward. Run `cstudio init` in the folder you edit in."
        )

    @classmethod
    def init(cls, root: Path, name: str | None = None) -> "Workspace":
        root.mkdir(parents=True, exist_ok=True)
        ws = cls(root)
        marker = ws.root / MARKER
        if not marker.exists():
            marker.write_text(json.dumps({
                "name": name or ws.root.name,
                "created": _dt.date.today().isoformat(),
            }, indent=2, ensure_ascii=False) + "\n")
        for d in (ws.state, ws.state / "analysis", ws.root / "edits", ws.root / "renders"):
            d.mkdir(parents=True, exist_ok=True)
        return ws

    # -- paths ---------------------------------------------------------------
    @property
    def state(self) -> Path:
        return self.root / ".studio"

    def analysis_dir(self, media_id: str) -> Path:
        d = self.state / "analysis" / media_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def proxy_path(self, media_id: str) -> Path:
        return self.state / "proxy" / f"{media_id}.mp4"

    def rel(self, p: Path) -> str:
        p = Path(p).resolve()
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    def abs(self, p: str | Path) -> Path:
        q = Path(p).expanduser()
        return q if q.is_absolute() else (self.root / q)

    # -- media index ---------------------------------------------------------
    @property
    def media_file(self) -> Path:
        return self.state / "media.json"

    def media(self) -> dict:
        if self.media_file.exists():
            return json.loads(self.media_file.read_text())
        return {}

    def save_media(self, media: dict) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        self.media_file.write_text(json.dumps(media, indent=2, ensure_ascii=False) + "\n")

    def media_id_for(self, path: Path, media: dict) -> str:
        rel = self.rel(path)
        for mid, info in media.items():
            if info.get("path") == rel:
                return mid
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem).strip("-").lower() or "media"
        mid, n = base, 2
        while mid in media:
            mid, n = f"{base}-{n}", n + 1
        return mid

    def resolve_src(self, src: str) -> tuple[str | None, Path]:
        """Map an EDL `src` (media id or path) to (media_id, absolute path)."""
        media = self.media()
        if src in media:
            return src, self.abs(media[src]["path"])
        path = self.abs(src)
        rel = self.rel(path)
        for mid, info in media.items():
            if info.get("path") == rel:
                return mid, path
        return None, path

    def info_for(self, src: str) -> dict:
        mid, path = self.resolve_src(src)
        media = self.media()
        if mid and mid in media:
            return media[mid]
        return ff.probe(path)


def collect_media(paths: list[Path]) -> list[Path]:
    """Expand files/folders into a sorted list of media files."""
    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if SKIP_DIRS & set(f.parts):
                    continue
                if f.is_file() and f.suffix.lower() in MEDIA_EXT:
                    found.append(f)
        elif p.is_file():
            found.append(p)
    seen, out = set(), []
    for f in found:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            out.append(f)
    return out
