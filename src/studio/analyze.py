"""Turn media into things Claude can read: numbers, text and contact-sheet images."""

from __future__ import annotations

import json
import math
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from . import ff, fonts


def fmt_time(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:04.1f}" if h else f"{m}:{s:04.1f}"


# -- scenes ------------------------------------------------------------------
def detect_scenes(path: Path, threshold: float = 0.3) -> list[float]:
    """Timestamps (s) where the picture changes sharply (cuts, big camera moves)."""
    proc = ff.ffmpeg([
        *ff.hwaccel_args(), "-i", path, "-an",
        "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ])
    return [round(float(t), 3) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]


# -- audio: silence + loudness in one pass -----------------------------------
def audio_stats(path: Path, noise_db: float = -35, min_silence: float = 0.5) -> dict:
    proc = ff.ffmpeg([
        "-i", path, "-vn",
        "-af", f"silencedetect=n={noise_db}dB:d={min_silence},ebur128=peak=true",
        "-f", "null", "-",
    ])
    err = proc.stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", err)]
    silences = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        silences.append({"start": round(max(0.0, s), 3), "end": round(e, 3) if e else None})
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    lufs = re.search(r"I:\s+(-?[0-9.]+) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[0-9.]+) dBFS", summary)
    lra = re.search(r"LRA:\s+(-?[0-9.]+) LU", summary)
    return {
        "integrated_lufs": float(lufs.group(1)) if lufs else None,
        "true_peak_dbfs": float(peak.group(1)) if peak else None,
        "loudness_range_lu": float(lra.group(1)) if lra else None,
        "silence_threshold_db": noise_db,
        "silences": silences,
    }


def black_segments(path: Path, min_dur: float = 0.1) -> list[dict]:
    proc = ff.ffmpeg([
        *ff.hwaccel_args(), "-i", path, "-an",
        "-vf", f"scale=320:-2,blackdetect=d={min_dur}:pix_th=0.10", "-f", "null", "-",
    ])
    return [
        {"start": float(a), "end": float(b)}
        for a, b in re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", proc.stderr)
    ]


# -- frames & contact sheets -------------------------------------------------
def extract_frame(path: Path, t: float, out: Path, width: int = 640) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ff.ffmpeg([
        "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1",
        "-vf", f"scale={width}:-2", "-q:v", "3", out,
    ])
    return out


def contact_sheet(
    path: Path,
    out: Path,
    *,
    start: float = 0.0,
    end: float | None = None,
    count: int = 12,
    cols: int = 4,
    thumb_w: int = 360,
    label: str = "",
    times: list[float] | None = None,
) -> dict:
    """Grid of frames, each stamped with its timestamp in the file."""
    info = ff.probe(path)
    dur = info.get("duration") or 0.0
    if times is None:
        end = min(end, dur) if end is not None else dur
        span = max(0.0, end - start)
        count = max(1, count)
        times = [start + span * (i + 0.5) / count for i in range(count)]
    times = [min(t, max(0.0, dur - 0.05)) for t in times]

    with tempfile.TemporaryDirectory() as td:
        def grab(it):
            i, t = it
            f = Path(td) / f"{i:04d}.jpg"
            try:
                extract_frame(path, t, f, width=thumb_w)
                return f
            except ff.FFError:
                return None

        with ThreadPoolExecutor(max_workers=6) as pool:
            files = list(pool.map(grab, enumerate(times)))
        imgs = [Image.open(f).convert("RGB") if f else None for f in files]
        tw = thumb_w
        th = max((im.height for im in imgs if im), default=int(thumb_w * 9 / 16))
        cols = min(cols, len(times))
        rows = math.ceil(len(times) / cols)
        bar = 26
        header = 30 if label else 0
        sheet = Image.new("RGB", (cols * tw, header + rows * (th + bar)), "#111")
        draw = ImageDraw.Draw(sheet)
        f_small = fonts.load(None, 18)
        if label:
            draw.text((8, 5), label, font=fonts.load(None, 20), fill="#fff")
        for i, (t, im) in enumerate(zip(times, imgs)):
            x, y = (i % cols) * tw, header + (i // cols) * (th + bar)
            if im:
                sheet.paste(im, (x, y + bar))
            draw.text((x + 6, y + 3), f"#{i + 1}  {fmt_time(t)}  ({t:.2f}s)", font=f_small, fill="#ffd400")
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out, quality=85)
    return {"sheet": str(out), "times": [round(t, 3) for t in times]}


def make_proxy(path: Path, out: Path, height: int = 720) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ff.ffmpeg([
        "-i", path, "-vf", f"scale=-2:'min({height},ih)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out,
    ])
    return out


# -- full ingest of one source ----------------------------------------------
def ingest_one(ws, mid: str, info: dict, *, proxy: bool = False, scene_threshold: float = 0.3) -> dict:
    src = ws.abs(info["path"])
    adir = ws.analysis_dir(mid)
    summary: dict = {"id": mid, "type": info["type"]}

    if info["type"] == "image":
        th = adir / "thumb.jpg"
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.thumbnail((640, 640))
        im.save(th, quality=85)
        summary["sheets"] = [ws.rel(th)]
    elif info["type"] == "video":
        dur = info.get("duration", 0)
        scenes = detect_scenes(src, scene_threshold)
        (adir / "scenes.json").write_text(json.dumps({"threshold": scene_threshold, "cuts": scenes}, indent=2))
        summary["scene_cuts"] = len(scenes)
        # about one frame per 2.5 s, 8..48 frames, 24 frames per sheet
        n = int(min(48, max(8, dur / 2.5)))
        sheets = []
        per = 24
        for k in range(math.ceil(n / per)):
            times = [dur * (i + 0.5) / n for i in range(k * per, min(n, (k + 1) * per))]
            r = contact_sheet(src, adir / f"sheet_{k + 1}.jpg", times=times,
                              thumb_w=240 if info.get("height", 0) > info.get("width", 0) else 360,
                              cols=6 if info.get("height", 0) > info.get("width", 0) else 4,
                              label=f"{mid}  ({fmt_time(dur)})  sheet {k + 1}")
            sheets.append(ws.rel(Path(r["sheet"])))
        summary["sheets"] = sheets

    if info.get("has_audio"):
        stats = audio_stats(src)
        (adir / "audio.json").write_text(json.dumps(stats, indent=2))
        summary["lufs"] = stats["integrated_lufs"]
        summary["silences"] = len(stats["silences"])

    if proxy and info["type"] == "video":
        make_proxy(src, ws.proxy_path(mid))
        summary["proxy"] = ws.rel(ws.proxy_path(mid))
    return summary
