"""Graphics layer: text, captions and image overlays rasterized with Pillow.

Every moment where the set of visible items changes becomes one transparent PNG.
The PNGs are stitched with ffmpeg's concat demuxer into a single overlay stream,
so any number of titles/captions costs one extra ffmpeg input.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps

from . import fonts

TEXT_DEFAULTS = {
    "x": 0.5, "y": 0.5,          # anchor point, fractions of the frame
    "anchor": "center",          # center | top | bottom | left | right | top-left | ... | bottom-right
    "align": "center",           # line alignment inside the block: left | center | right
    "size": 0.06,                # <= 1: fraction of the frame's shorter side; > 1: pixels
    "font": None,                # path, file stem, or substring ("Arial Bold", "BeVietnamPro-Bold")
    "color": "#FFFFFF",
    "stroke": "#000000",         # outline colour, null for none
    "stroke_width": 0.08,        # fraction of font size
    "box": None,                 # background colour behind the block, e.g. "#000000AA"
    "box_padding": 0.35,         # fraction of font size
    "box_radius": 0.3,           # fraction of font size
    "shadow": None,              # shadow colour, e.g. "#00000099"
    "max_width": 0.86,           # wrap width, fraction of frame width
    "line_spacing": 1.15,
    "case": None,                # upper | lower | null
    "highlight_color": None,     # karaoke: colour of the active word
    "highlight_box": None,       # karaoke: pill colour behind the active word
}

_ANCHORS = {
    "center": (0.5, 0.5), "top": (0.5, 0.0), "bottom": (0.5, 1.0), "left": (0.0, 0.5), "right": (1.0, 0.5),
    "top-left": (0.0, 0.0), "top-right": (1.0, 0.0), "bottom-left": (0.0, 1.0), "bottom-right": (1.0, 1.0),
}


def _rgba(c) -> tuple[int, int, int, int]:
    rgb = ImageColor.getrgb(c)
    return rgb if len(rgb) == 4 else (*rgb, 255)


def _px(v: float, ref: float, scale: float) -> float:
    v = float(v)
    return v * ref if v <= 1 else v * scale


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    for li, line in enumerate(str(text).split("\n")):
        if li:
            out.append("\n")
        out.extend(w for w in line.split(" ") if w)
    return out


def draw_text(canvas: Image.Image, item: dict, scale: float) -> None:
    st = {**TEXT_DEFAULTS, **item}
    W, H = canvas.size
    size = int(round(_px(st["size"], min(W, H), scale)))
    font = fonts.load(st["font"], size)
    text = str(st["text"])
    if st["case"] == "upper":
        text = text.upper()
    elif st["case"] == "lower":
        text = text.lower()

    toks = _tokens(text)
    space = font.getlength(" ")
    max_w = st["max_width"] * W if st["max_width"] <= 1 else st["max_width"] * scale
    lines: list[list[tuple[int, str, float]]] = [[]]
    widths = [0.0]
    wi = 0
    for t in toks:
        if t == "\n":
            lines.append([])
            widths.append(0.0)
            continue
        tw = font.getlength(t)
        new_w = tw if not lines[-1] else widths[-1] + space + tw
        if lines[-1] and new_w > max_w:
            lines.append([(wi, t, tw)])
            widths.append(tw)
        else:
            lines[-1].append((wi, t, tw))
            widths[-1] = new_w
        wi += 1

    asc, desc = font.getmetrics()
    line_h = (asc + desc) * st["line_spacing"]
    bw = max(widths) if widths else 0
    bh = line_h * (len(lines) - 1) + asc + desc
    ax, ay = _ANCHORS.get(st["anchor"], (0.5, 0.5))
    bx = st["x"] * W - bw * ax
    by = st["y"] * H - bh * ay
    margin = size * 0.4
    bx = min(max(bx, margin), max(margin, W - bw - margin))
    by = min(max(by, margin), max(margin, H - bh - margin))

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if st["box"]:
        pad = size * st["box_padding"]
        d.rounded_rectangle((bx - pad, by - pad * 0.8, bx + bw + pad, by + bh + pad * 0.8),
                            radius=size * st["box_radius"], fill=_rgba(st["box"]))

    stroke_w = int(round(size * st["stroke_width"])) if st["stroke"] else 0
    hi = item.get("highlight_index")
    positions = []
    for li, line in enumerate(lines):
        lw = widths[li]
        if st["align"] == "left":
            x = bx
        elif st["align"] == "right":
            x = bx + bw - lw
        else:
            x = bx + (bw - lw) / 2
        base = by + li * line_h + asc
        for (idx, word, tw) in line:
            positions.append((idx, word, tw, x, base))
            x += tw + space

    if hi is not None and st["highlight_box"]:
        for idx, word, tw, x, base in positions:
            if idx == hi:
                p = size * 0.18
                d.rounded_rectangle((x - p, base - asc * 0.95 - p * 0.4, x + tw + p, base + desc + p * 0.4),
                                    radius=size * 0.2, fill=_rgba(st["highlight_box"]))

    if st["shadow"]:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        off = max(2, size * 0.06)
        for idx, word, tw, x, base in positions:
            sd.text((x + off, base + off), word, font=font, anchor="ls", fill=_rgba(st["shadow"]),
                    stroke_width=stroke_w, stroke_fill=_rgba(st["shadow"]))
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, size * 0.05)))
        layer = Image.alpha_composite(sh, layer)
        d = ImageDraw.Draw(layer)

    for idx, word, tw, x, base in positions:
        color = st["color"]
        if hi is not None and idx == hi and st["highlight_color"]:
            color = st["highlight_color"]
        d.text((x, base), word, font=font, anchor="ls", fill=_rgba(color),
               stroke_width=stroke_w, stroke_fill=_rgba(st["stroke"]) if st["stroke"] else None)
    canvas.alpha_composite(layer)


_img_cache: dict = {}


def draw_image(canvas: Image.Image, item: dict, scale: float) -> None:
    W, H = canvas.size
    key = (item["_path"], item.get("width", 0.2), W)
    if key not in _img_cache:
        im = ImageOps.exif_transpose(Image.open(item["_path"])).convert("RGBA")
        tw = _px(item.get("width", 0.2), W, scale)
        im = im.resize((max(1, int(tw)), max(1, int(im.height * tw / im.width))), Image.LANCZOS)
        _img_cache[key] = im
    im = _img_cache[key]
    op = float(item.get("opacity", 1.0))
    if op < 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda a: int(a * op)))
    ax, ay = _ANCHORS.get(item.get("anchor", "center"), (0.5, 0.5))
    x = int(float(item.get("x", 0.5)) * W - im.width * ax)
    y = int(float(item.get("y", 0.5)) * H - im.height * ay)
    canvas.alpha_composite(im, (max(0, x), max(0, y)))


def build(items: list[dict], size: tuple[int, int], total: float, workdir: Path, scale: float = 1.0) -> Path | None:
    """Rasterize items into PNG segments and return an ffconcat list path (None if no items)."""
    items = [it for it in items if float(it.get("end", total)) > float(it.get("start", 0))]
    if not items:
        return None
    workdir.mkdir(parents=True, exist_ok=True)
    for k, it in enumerate(items):
        it["_k"] = k
        it["start"] = max(0.0, float(it.get("start", 0.0)))
        it["end"] = min(total, float(it.get("end", total)))

    cuts = sorted({0.0, total, *(it["start"] for it in items), *(it["end"] for it in items)})
    cuts = [c for c in cuts if 0 <= c <= total]
    segments = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 1e-3:
            continue
        active = [it for it in items if it["start"] <= a + 1e-4 and it["end"] >= b - 1e-4]
        segments.append((a, b, active))

    rendered: dict[str, Path] = {}
    entries = []
    for a, b, active in segments:
        sig = hashlib.md5(json.dumps(
            [{k: v for k, v in it.items() if k not in ("start", "end", "_k")} for it in active],
            sort_keys=True, default=str).encode()).hexdigest()[:16] if active else "blank"
        if sig not in rendered:
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            for it in active:
                if it.get("_kind") == "image":
                    draw_image(canvas, it, scale)
                else:
                    draw_text(canvas, it, scale)
            f = workdir / f"{sig}.png"
            canvas.save(f, compress_level=1)
            rendered[sig] = f
        entries.append((rendered[sig], b - a))

    lst = workdir / "layer.ffconcat"
    lines = ["ffconcat version 1.0"]
    for f, dur in entries:
        lines += [f"file '{f.as_posix()}'", f"duration {dur:.4f}"]
    lines.append(f"file '{entries[-1][0].as_posix()}'")
    lst.write_text("\n".join(lines) + "\n")
    return lst
