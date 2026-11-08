"""Rotoscoping: segment and track people/objects with SAM 2, producing per-frame masks.

SAM 2 (torch) runs through `uvx` in its own environment (see roto_worker.py), locally: Apple GPU (MPS),
CUDA or CPU. The model downloads from Hugging Face on first use and is cached afterwards.

Output, per roto job `<name>`:  .studio/roto/<name>/
  masks/00000.png ...   one mask per frame (white = object(s)); frame 0 = source time `from`
  obj<id>/...           per-object masks when more than one object was tracked
  roto.json             source, range, fps, prompts, warnings, and a ready EDL `object` snippet
  prompt.jpg            prompt frame with the clicks and the resulting mask (check the right thing was picked)
  review.jpg            mask overlay on frames across the range (check the tracking held)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import ff, fonts

MODELS = {"tiny": "facebook/sam2.1-hiera-tiny", "small": "facebook/sam2.1-hiera-small",
          "base": "facebook/sam2.1-hiera-base-plus", "large": "facebook/sam2.1-hiera-large"}
WORKER = Path(__file__).with_name("roto_worker.py")
EMPTY = 0.0005      # mask area (fraction of frame) below which a frame counts as "object lost"
JUMP = 0.6          # relative area change between frames that is flagged as a possible tracking jump


def roto_dir(ws, name: str) -> Path:
    return ws.state / "roto" / name


def load(ws, name: str) -> dict:
    f = roto_dir(ws, name) / "roto.json"
    if not f.exists():
        known = sorted(p.name for p in (ws.state / "roto").glob("*") if (p / "roto.json").exists())
        raise SystemExit(f"no roto job '{name}'" + (f" (known: {', '.join(known)})" if known else ""))
    return json.loads(f.read_text())


def list_jobs(ws) -> list[dict]:
    out = []
    for f in sorted((ws.state / "roto").glob("*/roto.json")):
        m = json.loads(f.read_text())
        out.append({k: m.get(k) for k in ("name", "src", "from", "to", "frames", "objects", "warnings")})
    return out


# -- prompts ---------------------------------------------------------------------
def xy(v) -> list[float]:
    """'0.5,0.4' or [0.5, 0.4] -> [0.5, 0.4]."""
    if isinstance(v, str):
        v = [t for t in re.split(r"[,\s]+", v.strip()) if t]
    return [float(t) for t in v]


def normalize_prompts(raw: list[dict]) -> list[dict]:
    """Prompts as given by the user/CLI -> [{id, at, pos, neg, box}] with float lists."""
    out = []
    for i, p in enumerate(raw):
        q = {"id": int(p.get("id", i + 1)), "at": p.get("at"),
             "pos": [xy(v) for v in p.get("pos") or []], "neg": [xy(v) for v in p.get("neg") or []],
             "box": xy(p["box"]) if p.get("box") else None}
        if not q["pos"] and not q["box"]:
            raise SystemExit(f"prompt {i + 1}: needs at least one positive point (`pos`) or a `box`")
        out.append(q)
    if not out:
        raise SystemExit("nothing to track: give --pos x,y (on the object) or --box x0,y0,x1,y1, or --prompts")
    return out


def _px(v: list[float], sw: int, sh: int, fw: int, fh: int) -> list[float]:
    """Point/box coordinates: fractions of the frame (all <= 1) or source pixels -> extracted-frame pixels."""
    frac = all(0 <= c <= 1 for c in v)
    return [round(c * (fw if i % 2 == 0 else fh) if frac else c * (fw / sw if i % 2 == 0 else fh / sh), 1)
            for i, c in enumerate(v)]


# -- tracking --------------------------------------------------------------------
def _worker_cmd() -> list[str]:
    if not shutil.which("uvx"):
        raise ff.FFError("SAM 2 needs `uv` (brew install uv): it runs torch + sam2 through uvx")
    return ["uvx", "--python", "3.12", "--with", "sam2", "--with", "huggingface_hub", "--with", "pillow",
            "python", "-I", str(WORKER)]


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s).strip("-").lower() or "roto"


def track(ws, src: str, *, start: float = 0.0, end: float | None = None, name: str | None = None,
          prompts: list[dict], model: str = "small", max_size: int = 1280, force: bool = False) -> dict:
    mid, path = ws.resolve_src(src)
    if not path.exists():
        raise SystemExit(f"source not found: {src}")
    info = ws.info_for(src)
    kind = info.get("type")
    if kind not in ("video", "image"):
        raise SystemExit(f"{src} is {kind}: rotoscoping needs a video or an image")
    sw, sh = int(info["width"]), int(info["height"])
    prompts = normalize_prompts(prompts)
    if kind == "video":
        dur = float(info.get("duration") or 0)
        end = dur if end is None else min(float(end), dur)
        start = max(0.0, float(start))
        if end - start < 0.04:
            raise SystemExit(f"empty range {start}-{end} (source is {dur:.2f}s)")
        fps = float(info.get("fps") or 30)
        if end - start > 30:
            print(f"warning: {end - start:.0f}s is long for SAM 2 (memory grows with frames); "
                  "prefer one job per shot", file=sys.stderr)
        name = _slug(name or f"{mid or path.stem}-{start:g}-{end:g}")
    else:
        start, end, fps = 0.0, None, None
        name = _slug(name or f"{mid or path.stem}")
    model_id = MODELS.get(model, model)
    key = {"src": src, "from": start, "to": end, "prompts": prompts, "model": model_id, "max_size": max_size}
    d = roto_dir(ws, name)
    if (d / "roto.json").exists() and not force:
        meta = json.loads((d / "roto.json").read_text())
        if meta.get("key") == key:
            return {**meta, "status": "cached"}

    s = min(1.0, max_size / max(sw, sh))
    fw, fh = max(2, int(sw * s) // 2 * 2), max(2, int(sh * s) // 2 * 2)
    ws.state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ws.state, prefix="roto-") as td:
        frames, tmp_out = Path(td) / "frames", Path(td) / "out"
        frames.mkdir()
        if kind == "video":
            print(f"extracting frames {start:.2f}-{end:.2f}s at {fps:g} fps, {fw}x{fh} ...", file=sys.stderr)
            ff.ffmpeg(["-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", path,
                       "-vf", f"fps={fps},scale={fw}:{fh}", "-q:v", "2", "-start_number", "0",
                       frames / "%05d.jpg"])
        else:
            ImageOps.exif_transpose(Image.open(path)).convert("RGB").resize((fw, fh)).save(
                frames / "00000.jpg", quality=95)
        n = len(list(frames.glob("*.jpg")))
        if not n:
            raise SystemExit("no frames extracted")

        wp = []
        for p in prompts:
            at = start if p["at"] is None or kind == "image" else float(p["at"])
            fi = 0 if kind == "image" else min(n - 1, max(0, round((at - start) * fps)))
            wp.append({"id": p["id"], "frame": fi, "pos": [_px(v, sw, sh, fw, fh) for v in p["pos"]],
                       "neg": [_px(v, sw, sh, fw, fh) for v in p["neg"]],
                       "box": _px(p["box"], sw, sh, fw, fh) if p["box"] else None})
        cfg = Path(td) / "config.json"
        cfg.write_text(json.dumps({"frames": str(frames), "out": str(tmp_out), "model": model_id, "prompts": wp}))
        print(f"tracking with SAM 2 ({model_id}); first run installs torch + sam2 and downloads the model ...",
              file=sys.stderr)
        proc = subprocess.run([*_worker_cmd(), str(cfg)], stdout=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise ff.FFError(f"SAM 2 worker failed (exit {proc.returncode}); see the messages above")
        res = json.loads(proc.stdout.strip().splitlines()[-1])

        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        ids = res["objects"]
        if len(ids) == 1:
            shutil.move(str(tmp_out / f"obj{ids[0]}"), str(d / "masks"))
        else:
            for i in ids:
                shutil.move(str(tmp_out / f"obj{i}"), str(d / f"obj{i}"))
            (d / "masks").mkdir()
            for k in range(n):
                acc = None
                for i in ids:
                    m = Image.open(d / f"obj{i}" / f"{k:05d}.png").convert("L")
                    acc = m if acc is None else ImageChops.lighter(acc, m)
                acc.save(d / "masks" / f"{k:05d}.png")

        def t_of(k: int) -> float:
            return round(start + k / fps, 3) if fps else 0.0

        areas = [_area(d / "masks" / f"{k:05d}.png") for k in range(n)]
        warnings = _check(areas, t_of)
        _prompt_sheet(frames, d, wp, t_of)
        _review_sheet(frames, d, n, areas, t_of)

    mask_ref = ws.rel(d / "masks") if kind == "video" else ws.rel(d / "masks" / "00000.png")
    obj = {"mask": mask_ref, "from": start, "fps": fps} if kind == "video" else {"mask": mask_ref}
    meta = {
        "name": name, "src": src, "media_id": mid, "kind": kind, "from": start, "to": end, "fps": fps,
        "frames": n, "size": [fw, fh], "source_size": [sw, sh], "objects": ids, "model": model_id,
        "device": res.get("device"), "prompts": prompts,
        "area": {"min": round(min(areas), 4), "max": round(max(areas), 4), "mean": round(sum(areas) / n, 4)},
        "warnings": warnings,
        "masks": mask_ref, "per_object": {str(i): ws.rel(d / f"obj{i}") for i in ids} if len(ids) > 1 else None,
        "prompt_sheet": ws.rel(d / "prompt.jpg"), "review_sheet": ws.rel(d / "review.jpg"),
        "object": obj, "key": key,
    }
    (d / "roto.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    return {**meta, "status": "tracked"}


def _area(p: Path) -> float:
    m = Image.open(p).convert("L")
    m.thumbnail((256, 256))
    h = m.histogram()
    return sum(h[128:]) / max(1, m.width * m.height)


def _ranges(idx: list[int], t_of) -> list[list[float]]:
    out, run = [], []
    for k in idx:
        if run and k != run[-1] + 1:
            out.append([t_of(run[0]), t_of(run[-1])])
            run = []
        run.append(k)
    if run:
        out.append([t_of(run[0]), t_of(run[-1])])
    return out


def _check(areas: list[float], t_of) -> list[str]:
    w = []
    lost = [k for k, a in enumerate(areas) if a < EMPTY]
    if lost:
        w.append("object lost (empty mask) at " + ", ".join(f"{a:.2f}-{b:.2f}s" for a, b in _ranges(lost, t_of))
                 + ": add a correction prompt there (`at`) or split the range")
    jumps = [k for k in range(1, len(areas))
             if areas[k - 1] > EMPTY * 4 and abs(areas[k] - areas[k - 1]) / areas[k - 1] > JUMP]
    if jumps:
        w.append("mask size jumps at " + ", ".join(f"{t_of(k):.2f}s" for k in jumps[:12])
                 + ": the mask may switch to another object or drop a part; check review.jpg")
    if areas and max(areas) > 0.85:
        w.append("mask covers >85% of the frame somewhere: probably the background got selected")
    return w


# -- QA sheets -------------------------------------------------------------------
def overlay(frame: Image.Image, mask: Image.Image) -> Image.Image:
    """Object tinted, background darkened, yellow edge: how the mask sits on the picture."""
    m = mask.convert("L").resize(frame.size)
    dark = ImageEnhance.Brightness(frame).enhance(0.4)
    tint = Image.blend(frame, Image.new("RGB", frame.size, (255, 0, 160)), 0.22)
    out = Image.composite(tint, dark, m)
    edge = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(5)), m)
    out.paste((255, 212, 0), mask=edge)
    return out


def _prompt_sheet(frames: Path, d: Path, wp: list[dict], t_of) -> None:
    tiles = []
    multi = len({q["id"] for q in wp}) > 1
    for fi in sorted({p["frame"] for p in wp}):
        im = overlay(Image.open(frames / f"{fi:05d}.jpg").convert("RGB"), Image.open(d / "masks" / f"{fi:05d}.png"))
        dr = ImageDraw.Draw(im)
        r = max(5, im.width // 120)
        for p in (p for p in wp if p["frame"] == fi):
            if p["box"]:
                dr.rectangle(p["box"], outline=(0, 200, 255), width=max(2, r // 2))
            for x, y in p["pos"]:
                dr.ellipse([x - r, y - r, x + r, y + r], fill=(0, 230, 90), outline="white", width=2)
            for x, y in p["neg"]:
                dr.ellipse([x - r, y - r, x + r, y + r], fill=(240, 40, 40), outline="white", width=2)
            if multi:
                x, y = (p["pos"] or [p["box"][:2]])[0]
                dr.text((x + r + 2, y - r), f"obj{p['id']}", font=fonts.load(None, max(14, r * 3)), fill="white")
        im.thumbnail((960, 960))
        dr = ImageDraw.Draw(im)
        dr.text((8, 6), f"prompt frame {fi}  t={t_of(fi):.2f}s   green=object  red=not object",
                font=fonts.load(None, 18), fill="#ffd400")
        tiles.append(im)
    w = max(t.width for t in tiles)
    sheet = Image.new("RGB", (w, sum(t.height for t in tiles)), "#111")
    y = 0
    for t in tiles:
        sheet.paste(t, (0, y))
        y += t.height
    sheet.save(d / "prompt.jpg", quality=85)


def _review_sheet(frames: Path, d: Path, n: int, areas: list[float], t_of, count: int = 12, cols: int = 4) -> None:
    count = min(count, n)
    idx = {min(n - 1, round(i * (n - 1) / max(1, count - 1))) for i in range(count)}
    # always show the worst frames too (lost object)
    idx = sorted(idx | {k for k in sorted(range(n), key=lambda k: areas[k])[:2] if areas[k] < EMPTY})
    tw = 360
    tiles = []
    for k in idx:
        im = overlay(Image.open(frames / f"{k:05d}.jpg").convert("RGB"), Image.open(d / "masks" / f"{k:05d}.png"))
        im.thumbnail((tw, tw * 2))
        tiles.append((k, im))
    th = max(im.height for _, im in tiles)
    cols = min(cols, len(tiles))
    rows = -(-len(tiles) // cols)
    bar = 24
    sheet = Image.new("RGB", (cols * tw, rows * (th + bar)), "#111")
    dr = ImageDraw.Draw(sheet)
    f = fonts.load(None, 16)
    for i, (k, im) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + bar)
        sheet.paste(im, (x, y + bar))
        lost = areas[k] < EMPTY
        dr.text((x + 6, y + 3), f"f{k}  {t_of(k):.2f}s  area {areas[k] * 100:.1f}%" + ("  LOST" if lost else ""),
                font=f, fill="#ff5050" if lost else "#ffd400")
    sheet.save(d / "review.jpg", quality=85)


# -- export ----------------------------------------------------------------------
def matte_chain(grow: int = 0, feather: float = 0, invert: bool = False) -> list[str]:
    """ffmpeg filters that refine a gray mask: grow (+) / shrink (-) in pixels, soften edges, swap sides."""
    ch = ["format=gray"]
    if grow:
        ch += ["dilation" if grow > 0 else "erosion"] * abs(int(grow))
    if feather:
        ch.append(f"gblur=sigma={float(feather):g}")
    if invert:
        ch.append("negate")
    return ch


def export(ws, name: str, *, fmt: str = "mov", out: str | None = None, grow: int = 0, feather: float = 1.0,
           invert: bool = False, matte: bool = False) -> dict:
    """Cutout with transparency (subject only), or the black/white matte itself, for other editors."""
    meta = load(ws, name)
    d = roto_dir(ws, name)
    _, src = ws.resolve_src(meta["src"])
    sw, sh = meta["source_size"]
    image = meta["kind"] == "image"
    if image:
        fmt = "png"
    if fmt == "mp4" and not matte:
        raise SystemExit("mp4 has no transparency: use --format mov (ProRes 4444), webm (VP9 alpha) or png")
    tag = "matte" if matte else "cutout"
    ext = {"mov": ".mov", "webm": ".webm", "mp4": ".mp4", "png": ".png" if image else ""}[fmt]
    dest = Path(out) if out else ws.root / "renders" / f"{name}-{tag}{ext}"
    mchain = ",".join([f"scale={sw}:{sh}", *matte_chain(grow, feather, invert)])
    if image:
        ins = ["-i", src, "-i", d / "masks" / "00000.png"]
    else:
        ins = ["-ss", f"{meta['from']:.3f}", "-t", f"{meta['to'] - meta['from']:.3f}", "-i", src,
               "-framerate", f"{meta['fps']:g}", "-start_number", "0", "-i", d / "masks" / "%05d.png"]
    if matte:
        fc = f"[1:v]{mchain}[o]"
    else:
        rate = f"fps={meta['fps']:g}," if not image else ""
        fc = f"[0:v]{rate}scale={sw}:{sh},format=yuva444p[v];[1:v]{mchain}[m];[v][m]alphamerge[o]"
    enc = {
        "mov": ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuv444p10le" if matte else "yuva444p10le"],
        "webm": ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p" if matte else "yuva420p", "-b:v", "0", "-crf", "28",
                 "-auto-alt-ref", "0"],
        "mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18"],
        "png": [],
    }[fmt]
    if fmt == "png" and not image:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / "%05d.png"
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = dest
    ff.ffmpeg([*ins, "-filter_complex", fc, "-map", "[o]", *enc, "-an",
               *(["-frames:v", "1", "-update", "1"] if image else []), target])
    return {"output": str(dest), "format": fmt, "kind": tag, "frames": meta["frames"]}


# -- helper for picking prompt points ------------------------------------------------
def draw_grid(path: Path, step: float = 0.1) -> Path:
    """Draw a labelled 0-1 coordinate grid on an image so point fractions can be read off it."""
    im = Image.open(path).convert("RGB")
    dr = ImageDraw.Draw(im, "RGBA")
    w, h = im.size
    f = fonts.load(None, max(12, w // 70))
    k = 1
    while k * step < 1 - 1e-6:
        v = round(k * step, 3)
        col = (255, 212, 0, 200) if abs(v - 0.5) < 1e-6 else (255, 255, 255, 110)
        x, y = int(v * w), int(v * h)
        dr.line([(x, 0), (x, h)], fill=col, width=1)
        dr.line([(0, y), (w, y)], fill=col, width=1)
        for pos in ((x + 3, 2), (3, y + 2)):
            dr.text(pos, f"{v:g}", font=f, fill=(255, 212, 0, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        k += 1
    im.save(path, quality=90)
    return path
