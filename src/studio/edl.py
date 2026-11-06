"""Edit Decision List (EDL): the whole edit as one JSON file.

See skills/edl/reference.md for the full schema. Times are seconds (floats).
Clip `in`/`out` are SOURCE times; text/caption/audio `start`/`end`/`at` are TIMELINE times.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from .workspace import Workspace

PRESETS = {
    "tiktok": {"width": 1080, "height": 1920, "fps": 30},
    "reels": {"width": 1080, "height": 1920, "fps": 30},
    "shorts": {"width": 1080, "height": 1920, "fps": 30},
    "vertical": {"width": 1080, "height": 1920, "fps": 30},
    "youtube": {"width": 1920, "height": 1080, "fps": 30},
    "1080p": {"width": 1920, "height": 1080, "fps": 30},
    "720p": {"width": 1280, "height": 720, "fps": 30},
    "4k": {"width": 3840, "height": 2160, "fps": 30},
    "square": {"width": 1080, "height": 1080, "fps": 30},
    "portrait": {"width": 1080, "height": 1350, "fps": 30},
}

OUTPUT_DEFAULTS = {
    "fit": "cover",          # cover | contain | blur | fill
    "bg": "#000000",
    "crf": 20,
    "encoder_preset": "medium",
    "loudness": -14,          # integrated LUFS target; null disables normalization
    "audio_bitrate": "192k",
    "sample_rate": 48000,
}

XFADE_TYPES = {
    "fade", "fadeblack", "fadewhite", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "smoothleft", "smoothright", "smoothup",
    "smoothdown", "circleopen", "circleclose", "circlecrop", "rectcrop", "distance", "pixelize",
    "radial", "hblur", "zoomin", "squeezeh", "squeezev", "diagtl", "diagtr", "diagbl", "diagbr",
    "hlslice", "hrslice", "vuslice", "vdslice", "fadegrays",
}


@dataclass
class Placed:
    """A clip resolved onto the timeline."""
    index: int
    clip: dict
    kind: str                 # video | image | color
    path: Path | None
    media_id: str | None
    info: dict
    duration: float           # on the timeline, after speed
    start: float              # timeline start (includes the incoming transition overlap)
    transition: float = 0.0   # overlap with previous clip

    @property
    def end(self) -> float:
        return self.start + self.duration

    @property
    def src_in(self) -> float:
        return float(self.clip.get("in", 0.0))

    @property
    def speed(self) -> float:
        return float(self.clip.get("speed", 1.0))


@dataclass
class Plan:
    edl: dict
    output: dict
    clips: list[Placed] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.clips[-1].end if self.clips else 0.0


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def resolve_output(edl: dict, first_visual: dict | None) -> dict:
    out = dict(OUTPUT_DEFAULTS)
    o = copy.deepcopy(edl.get("output", {}))
    preset = o.pop("preset", None)
    if preset:
        if preset not in PRESETS:
            raise SystemExit(f"unknown output preset '{preset}'. Known: {', '.join(PRESETS)}")
        out.update(PRESETS[preset])
    out.update(o)
    if "width" not in out or "height" not in out:
        if first_visual and first_visual.get("width"):
            w, h = first_visual["width"], first_visual["height"]
            scale = min(1.0, 1920 / max(w, h))  # default: source aspect, at most 1080p
            out.setdefault("width", int(w * scale))
            out.setdefault("height", int(h * scale))
        else:
            for k, v in PRESETS["1080p"].items():
                out.setdefault(k, v)
    if "fps" not in out:
        fps = (first_visual or {}).get("fps") or 30
        out["fps"] = min(60, round(fps))
    out["width"] = int(out["width"]) // 2 * 2
    out["height"] = int(out["height"]) // 2 * 2
    return out


def plan(ws: Workspace, edl: dict) -> Plan:
    clips = edl.get("clips") or []
    p = Plan(edl=edl, output={})
    placed: list[Placed] = []
    first_visual = None
    cursor = 0.0

    for i, c in enumerate(clips):
        where = f"clips[{i}]"
        if "color" in c:
            kind, path, mid, info = "color", None, None, {"type": "color"}
            dur = float(c.get("duration", 2.0))
        else:
            src = c.get("src")
            if not src:
                p.errors.append(f"{where}: needs `src` (media id or path) or `color`")
                continue
            mid, path = ws.resolve_src(src)
            if not path.exists():
                p.errors.append(f"{where}: source not found: {src}")
                continue
            info = ws.info_for(src)
            kind = info.get("type")
            if kind == "audio":
                p.errors.append(f"{where}: {src} is audio-only; put it in `audio` instead")
                continue
            if kind == "image":
                dur = float(c.get("duration", 3.0))
            else:
                src_dur = float(info.get("duration") or 0)
                cin = float(c.get("in", 0))
                cout = float(c.get("out", src_dur))
                if cout > src_dur + 0.05:
                    p.warnings.append(f"{where}: out={cout} beyond source duration {src_dur:.2f}; clamped")
                    cout = src_dur
                    c = {**c, "out": src_dur}
                if cin < 0 or cout <= cin:
                    p.errors.append(f"{where}: invalid range in={cin} out={cout}")
                    continue
                speed = float(c.get("speed", 1.0))
                if speed <= 0:
                    p.errors.append(f"{where}: speed must be > 0")
                    continue
                dur = (cout - cin) / speed
            if first_visual is None:
                first_visual = info

        trans = 0.0
        t = c.get("transition")
        if t and placed:
            ttype = t.get("type", "fade")
            if ttype not in XFADE_TYPES:
                p.errors.append(f"{where}: unknown transition '{ttype}'")
            trans = min(float(t.get("duration", 0.5)), placed[-1].duration * 0.9, dur * 0.9)
        start = cursor - trans
        placed.append(Placed(i, c, kind, path, mid, info, dur, start, trans))
        cursor = start + dur

    p.clips = placed
    if not clips:
        p.errors.append("EDL has no clips")
    p.output = resolve_output(edl, first_visual)

    total = p.duration
    for k, a in enumerate(edl.get("audio") or []):
        if not a.get("src"):
            p.errors.append(f"audio[{k}]: needs `src`")
            continue
        _, ap = ws.resolve_src(a["src"])
        if not ap.exists():
            p.errors.append(f"audio[{k}]: source not found: {a['src']}")
        if float(a.get("at", 0)) >= total > 0:
            p.warnings.append(f"audio[{k}]: starts at {a.get('at')} after the video ends ({total:.2f})")
    for k, t in enumerate(edl.get("text") or []):
        if "text" not in t:
            p.errors.append(f"text[{k}]: needs `text`")
    for k, im in enumerate(edl.get("images") or []):
        if not im.get("src") or not ws.resolve_src(im["src"])[1].exists():
            p.errors.append(f"images[{k}]: source not found: {im.get('src')}")
    return p


def timeline_table(p: Plan) -> str:
    from .analyze import fmt_time

    rows = [f"{'#':>3}  {'timeline':<21} {'dur':>6}  source"]
    for c in p.clips:
        src = c.clip.get("src") or f"color {c.clip.get('color')}"
        rng = ""
        if c.kind == "video":
            rng = f" [{c.src_in:.2f} → {float(c.clip.get('out', c.info.get('duration', 0))):.2f}]"
            if c.speed != 1:
                rng += f" x{c.speed}"
        tr = f"  <- {c.clip['transition'].get('type', 'fade')} {c.transition:.2f}s" if c.transition else ""
        rows.append(f"{c.index:>3}  {fmt_time(c.start):>9} → {fmt_time(c.end):<9} {c.duration:6.2f}  {src}{rng}{tr}")
    o = p.output
    rows.append(f"total {fmt_time(p.duration)} ({p.duration:.2f}s)  output {o['width']}x{o['height']}@{o['fps']} fit={o['fit']}")
    return "\n".join(rows)
