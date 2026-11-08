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
    "rotate": 0,                 # degrees, counter-clockwise
}

# Motion: enter/exit effects, word-by-word reveal and beat pulses. Animated stretches
# are sampled once per output frame; static stretches stay a single PNG.
ENTER_DEFAULT, EXIT_DEFAULT, WORD_IN, PULSE_LEN = 0.3, 0.25, 0.14, 0.22

_ANCHORS = {
    "center": (0.5, 0.5), "top": (0.5, 0.0), "bottom": (0.5, 1.0), "left": (0.0, 0.5), "right": (1.0, 0.5),
    "top-left": (0.0, 0.0), "top-right": (1.0, 0.0), "bottom-left": (0.0, 1.0), "bottom-right": (1.0, 1.0),
}


def _rgba(c) -> tuple[int, int, int, int]:
    rgb = ImageColor.getrgb(c)
    return rgb if len(rgb) == 4 else (*rgb, 255)


def _alpha(c: tuple[int, int, int, int], a: float) -> tuple[int, int, int, int]:
    return (*c[:3], int(c[3] * a))


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


def _out_cubic(x: float) -> float:
    return 1 - (1 - x) ** 3


def _out_back(x: float) -> float:
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _effect(kind: str, p: float) -> dict:
    """Transform for an enter effect at progress p (0 = hidden, 1 = at rest). Exits run it backwards."""
    p = min(max(p, 0.0), 1.0)
    e, a = _out_cubic(p), min(1.0, p * 2.5)
    if kind == "pop":
        return {"scale": 0.35 + 0.65 * _out_back(p), "alpha": min(1.0, p * 4)}
    if kind == "stamp":
        return {"scale": 1 + 1.3 * (1 - e), "alpha": min(1.0, p * 5)}
    if kind == "zoom":
        return {"scale": 1.5 - 0.5 * e, "alpha": a}
    if kind == "slideup":
        return {"dy": 0.05 * (1 - e), "alpha": a}
    if kind == "slidedown":
        return {"dy": -0.05 * (1 - e), "alpha": a}
    if kind == "slideleft":
        return {"dx": 0.18 * (1 - e), "alpha": a}
    if kind == "slideright":
        return {"dx": -0.18 * (1 - e), "alpha": a}
    if kind == "drop":
        return {"dy": -0.12 * (1 - _out_back(p)), "alpha": min(1.0, p * 4)}
    if kind == "blur":
        return {"blur": 0.3 * (1 - e), "scale": 1.12 - 0.12 * e, "alpha": a}
    if kind == "spin":
        return {"rot": -30 * (1 - e), "scale": 0.5 + 0.5 * _out_back(p), "alpha": min(1.0, p * 3)}
    return {"alpha": e}  # fade


def _motion_spec(v, default: float):
    if not v:
        return None
    if isinstance(v, str):
        return v, default
    return v.get("type", "fade"), float(v.get("duration", default))


def _word_times(item: dict) -> list[float]:
    n = sum(1 for t in _tokens(item["text"]) if t != "\n")
    if not n:
        return []
    wt = item.get("word_times")
    if wt:
        return [float(x) for x in wt][:n] + [float(wt[-1])] * max(0, n - len(wt))
    s, e = item["start"], item["end"]
    span = float(item.get("reveal_duration", min(0.6 * (e - s), 0.18 * n)))
    return [s + span * i / n for i in range(n)]


def _state(item: dict, t: float, words: list[float]) -> dict:
    s, e = item["start"], item["end"]
    st = {"scale": 1.0, "dx": 0.0, "dy": 0.0, "alpha": 1.0, "blur": 0.0, "rot": 0.0}

    def apply(fx: dict):
        st["scale"] *= fx.get("scale", 1.0)
        st["alpha"] *= fx.get("alpha", 1.0)
        for k in ("dx", "dy", "blur", "rot"):
            st[k] += fx.get(k, 0.0)

    enter = _motion_spec(item.get("enter"), ENTER_DEFAULT)
    if enter and t < s + enter[1]:
        apply(_effect(enter[0], (t - s) / enter[1]))
    exit_ = _motion_spec(item.get("exit"), EXIT_DEFAULT)
    if exit_ and t > e - exit_[1]:
        apply(_effect(exit_[0], (e - t) / exit_[1]))
    amt = float(item.get("pulse_amount", 0.12))
    for p in item.get("pulse") or []:
        if p <= t < p + PULSE_LEN:
            st["scale"] *= 1 + amt * (1 - (t - p) / PULSE_LEN) ** 2
    out = {f"_{k}": round(v, 3) for k, v in st.items() if v != (1.0 if k in ("scale", "alpha") else 0.0)}
    if words:
        out["_wp"] = [round(min(1.0, max(0.0, (t - w) / WORD_IN)), 2) if t >= w else 0.0 for w in words]
    return out


def expand_motion(item: dict, fps: float) -> list[dict]:
    """Split an animated item into per-frame sub-items (static stretches stay one item)."""
    s, e = item["start"], item["end"]
    words = _word_times(item) if item.get("reveal") == "words" else []
    enter = _motion_spec(item.get("enter"), ENTER_DEFAULT)
    exit_ = _motion_spec(item.get("exit"), EXIT_DEFAULT)
    pulses = [float(p) for p in item.get("pulse") or [] if s <= float(p) < e]
    if not (enter or exit_ or pulses or words):
        return [item]
    item = {**item, "pulse": pulses}
    windows = []
    if enter:
        windows.append((s, s + enter[1]))
    if exit_:
        windows.append((e - exit_[1], e))
    windows += [(p, p + PULSE_LEN) for p in pulses] + [(w, w + WORD_IN) for w in words]
    step = 1.0 / fps
    ts = {s, e}
    for a, b in windows:
        a, b = max(a, s), min(b, e)
        t = a
        while t < b - 1e-6:
            ts.add(round(t, 4))
            t += step
        ts.add(round(b, 4))
    ts = sorted(x for x in ts if s <= x <= e)
    out = []
    for a, b in zip(ts, ts[1:]):
        if b - a < 1e-4:
            continue
        out.append({**item, **_state(item, a, words), "start": a, "end": b})
    return out


def draw_text(canvas: Image.Image, item: dict, scale: float) -> None:
    st = {**TEXT_DEFAULTS, **item}
    W, H = canvas.size
    if st.get("_alpha", 1.0) <= 0.003:
        return
    size = int(round(_px(st["size"], min(W, H), scale) * st.get("_scale", 1.0)))
    size = max(size, 2)
    font = fonts.load(st["font"], size)
    text = str(st["text"])
    if st["case"] == "upper":
        text = text.upper()
    elif st["case"] == "lower":
        text = text.lower()

    toks = _tokens(text)
    space = font.getlength(" ")
    max_w = st["max_width"] * W if st["max_width"] <= 1 else st["max_width"] * scale
    max_w *= st.get("_scale", 1.0)  # wrap as at rest, so animated scaling never re-wraps
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
    bx += st.get("_dx", 0.0) * W
    by += st.get("_dy", 0.0) * H

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if st["box"]:
        pad = size * st["box_padding"]
        d.rounded_rectangle((bx - pad, by - pad * 0.8, bx + bw + pad, by + bh + pad * 0.8),
                            radius=size * st["box_radius"], fill=_rgba(st["box"]))

    stroke_w = int(round(size * st["stroke_width"])) if st["stroke"] else 0
    hi = item.get("highlight_index")
    wp = item.get("_wp")  # word reveal progress, 0..1 per word
    if wp is not None and hi is None:
        shown = [i for i, v in enumerate(wp) if v > 0]
        hi = shown[-1] if shown else None
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
            a = 1.0 if wp is None or idx >= len(wp) else wp[idx]
            if a > 0:
                positions.append((idx, word, tw, x, base + (1 - _out_cubic(a)) * size * 0.4, a))
            x += tw + space

    if hi is not None and st["highlight_box"]:
        for idx, word, tw, x, base, _a in positions:
            if idx == hi:
                p = size * 0.18
                d.rounded_rectangle((x - p, base - asc * 0.95 - p * 0.4, x + tw + p, base + desc + p * 0.4),
                                    radius=size * 0.2, fill=_rgba(st["highlight_box"]))

    if st["shadow"]:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        off = max(2, size * 0.06)
        for idx, word, tw, x, base, a in positions:
            c = _alpha(_rgba(st["shadow"]), a)
            sd.text((x + off, base + off), word, font=font, anchor="ls", fill=c, stroke_width=stroke_w, stroke_fill=c)
        sh = sh.filter(ImageFilter.GaussianBlur(max(1, size * 0.05)))
        layer = Image.alpha_composite(sh, layer)
        d = ImageDraw.Draw(layer)

    for idx, word, tw, x, base, a in positions:
        color = st["color"]
        if hi is not None and idx == hi and st["highlight_color"]:
            color = st["highlight_color"]
        if a >= 1:
            d.text((x, base), word, font=font, anchor="ls", fill=_rgba(color),
                   stroke_width=stroke_w, stroke_fill=_rgba(st["stroke"]) if st["stroke"] else None)
        else:  # fading-in word: draw on its own layer so stroke and fill fade together
            wl = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(wl).text((x, base), word, font=font, anchor="ls", fill=_rgba(color),
                                    stroke_width=stroke_w, stroke_fill=_rgba(st["stroke"]) if st["stroke"] else None)
            wl.putalpha(wl.getchannel("A").point(lambda v: int(v * a)))
            layer.alpha_composite(wl)

    blur = st.get("_blur", 0.0)
    if blur > 0:
        layer = layer.filter(ImageFilter.GaussianBlur(max(0.5, blur * size)))
    rot = float(st.get("rotate") or 0) + st.get("_rot", 0.0)
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, center=(bx + bw / 2, by + bh / 2))
    alpha = st.get("_alpha", 1.0)
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
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


def build(items: list[dict], size: tuple[int, int], total: float, workdir: Path, scale: float = 1.0,
          fps: float = 30) -> Path | None:
    """Rasterize items into PNG segments and return an ffconcat list path (None if no items)."""
    items = [it for it in items if float(it.get("end", total)) > float(it.get("start", 0))]
    if not items:
        return None
    workdir.mkdir(parents=True, exist_ok=True)
    for k, it in enumerate(items):
        it["_k"] = k
        it["start"] = max(0.0, float(it.get("start", 0.0)))
        it["end"] = min(total, float(it.get("end", total)))
    items = [sub for it in items for sub in (expand_motion(it, fps) if it.get("_kind") != "image" else [it])]

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
