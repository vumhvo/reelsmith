"""Compile an EDL plan into a single ffmpeg filter_complex command and run it."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from PIL import Image

from . import captions, ff, layer
from .edl import Plan


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _hex(c: str) -> str:
    c = c.strip()
    return "0x" + c[1:7] if c.startswith("#") else c


def _atempo(speed: float) -> list[str]:
    out = []
    while speed > 2.0:
        out.append("atempo=2.0")
        speed /= 2.0
    while speed < 0.5:
        out.append("atempo=0.5")
        speed /= 0.5
    if abs(speed - 1.0) > 1e-6:
        out.append(f"atempo={speed:.6f}")
    return out


def _look(name: str, w0: int, h0: int) -> str:
    """Named look for the subject or the background of a masked object; anything else = raw ffmpeg filters."""
    b = max(8, w0 // 48)
    return {
        "bw": "hue=s=0,eq=contrast=1.12",
        "dim": "eq=brightness=-0.2:saturation=0.55",
        "dark": "eq=brightness=-0.4:saturation=0.3",
        "blur": f"gblur=sigma={max(6, w0 / 64):.0f}",
        "pixelate": f"scale=iw/{b}:ih/{b}:flags=area,scale={w0}:{h0}:flags=neighbor",
        "negate": "negate",
        "pop": "eq=saturation=1.45:contrast=1.08",
        "bright": "eq=brightness=0.08:contrast=1.06",
    }.get(name, name)


def _object_chain(fl: list, add_input, ws, n: int, k: int, c, obj: dict, fps, D: float) -> str:
    """Effects on one object (e.g. a fighter) from per-frame masks, applied in source space.

    Runs before crop/fit/zoom/speed so the effect follows every later transform. Returns the
    filter label to use as the clip's source. Order: background (look / colour / replacement),
    subject look, outline, flicker.
    """
    w0, h0 = int(c.info.get("width") or 1280), int(c.info.get("height") or 720)
    span = D * c.speed if c.kind == "video" else D
    out = obj.get("outline")
    bg = obj.get("background")
    bgsrc = obj.get("background_src")
    subj = obj.get("subject")
    flick = obj.get("flicker") or []
    need = (1 if bg or bgsrc else 0) + (1 if subj else 0) + (2 if out else 0) + (1 if flick else 0)
    if not need:
        return f"{k}:v"
    mk = _mask_input(add_input, ws, c, obj, fps, span)
    fl.append(f"[{k}:v]scale={w0}:{h0},setpts=PTS-STARTPTS,format=yuv420p[ov{n}]")
    masks = [f"om{n}_{i}" for i in range(need)]
    from .roto import matte_chain
    prep = [f"scale={w0}:{h0}", "setpts=PTS-STARTPTS",
            *matte_chain(int(obj.get("grow", 0)), float(obj.get("feather", 0)), bool(obj.get("invert")))]
    fl.append(f"[{mk}:v]{','.join(prep)},"
              + (f"split={need}" + "".join(f"[{m}]" for m in masks) if need > 1 else f"null[{masks[0]}]"))
    cur = f"ov{n}"

    if bg or bgsrc:  # new background behind the untouched object
        m = masks.pop()
        fl.append(f"[{cur}]split[obs{n}][ofs{n}]")
        if bgsrc:  # replacement picture/video, scaled to cover the source frame
            _, bpath = ws.resolve_src(bgsrc)
            binfo = ws.info_for(bgsrc)
            if binfo.get("type") == "image":
                kb = add_input(["-loop", "1", "-framerate", fps, "-t", f"{span:.3f}", "-i", _upright_image(bpath, ws.state)])
            else:
                kb = add_input(["-stream_loop", "-1", "-ss", f"{float(obj.get('background_in', 0)):.3f}",
                                "-t", f"{span:.3f}", "-i", bpath])
            look = f",{_look(bg, w0, h0)}" if bg and not str(bg).startswith("#") else ""
            fl.append(f"[{kb}:v]scale={w0}:{h0}:force_original_aspect_ratio=increase,crop={w0}:{h0},setsar=1,"
                      f"fps={fps},setpts=PTS-STARTPTS{look},format=yuv420p[obd{n}]")
            fl.append(f"[obs{n}]nullsink")
        elif str(bg).startswith("#"):  # solid colour (e.g. #00FF00 green screen, #000000 black)
            fl.append(f"color=c={_hex(bg)}:s={w0}x{h0}:r={fps}:d={span:.3f},format=yuv420p[obd{n}]")
            fl.append(f"[obs{n}]nullsink")
        else:  # bw = colour pop, dim = spotlight, blur = portrait blur, ...
            fl.append(f"[obs{n}]{_look(bg, w0, h0)}[obd{n}]")
        fl.append(f"[ofs{n}][{m}]alphamerge[ofm{n}]")
        fl.append(f"[obd{n}][ofm{n}]overlay=format=auto:shortest=1[obg{n}]")
        cur = f"obg{n}"

    if subj:  # look on the object only: blur / pixelate (censor), bw, pop, negate, raw filters
        m = masks.pop()
        fl.append(f"[{cur}]split[oss{n}][osf{n}]")
        fl.append(f"[osf{n}]{_look(subj, w0, h0)}[osl{n}]")
        fl.append(f"[osl{n}][{m}]alphamerge[osm{n}]")
        fl.append(f"[oss{n}][osm{n}]overlay=format=auto[osb{n}]")
        cur = f"osb{n}"

    if out:  # glowing outline: dilated mask minus mask, blurred, filled with colour
        out = out if isinstance(out, dict) else {}
        width, glow = int(out.get("width", 6)), float(out.get("glow", 6))
        m1, m2 = masks.pop(), masks.pop()
        fl.append(f"[{m1}]" + ",".join(["dilation"] * width) + f"[odl{n}]")
        fl.append(f"[odl{n}][{m2}]blend=all_mode=subtract,gblur=sigma={glow},lut=y='min(val*3,255)'[oed{n}]")
        fl.append(f"color=c={_hex(out.get('color', '#FFD400'))}:s={w0}x{h0}:r={fps}:d={span:.3f}[ocl{n}]")
        fl.append(f"[ocl{n}][oed{n}]alphamerge[ogl{n}]")
        fl.append(f"[{cur}][ogl{n}]overlay=format=auto[oo{n}]")
        cur = f"oo{n}"

    if flick:  # whole object flashes a solid colour on the given TIMELINE times (e.g. beats)
        rate = c.speed if c.kind == "video" else 1.0
        length = float(obj.get("flicker_len", 0.07))
        wins = []
        for T in flick:
            a, b = (float(T) - c.start) * rate, (float(T) + length - c.start) * rate
            if b > 0 and a < span:
                wins.append(f"between(t,{max(a, 0):.3f},{b:.3f})")
        m = masks.pop()
        if wins:
            op = float(obj.get("flicker_opacity", 0.7))
            fl.append(f"color=c={_hex(obj.get('flicker_color', '#FFD400'))}:s={w0}x{h0}:r={fps}:d={span:.3f}[ofc{n}]")
            fl.append(f"[ofc{n}][{m}]alphamerge,colorchannelmixer=aa={op}[off{n}]")
            fl.append(f"[{cur}][off{n}]overlay=format=auto:enable='{'+'.join(wins)}'[ofl{n}]")
            cur = f"ofl{n}"
        else:
            fl.append(f"[{m}]nullsink")
    return cur


def _zoom_filters(clip: dict, c, D: float, W: int, H: int, fps) -> list[str]:
    """One zoompan: Ken Burns ramp x punch (decaying zoom-in) x beat bounce + decaying camera shake."""
    zm = clip.get("zoom")
    fxs = set(clip.get("fx") or [])
    bounce = [float(T) - c.start for T in clip.get("bounce") or []]
    bounce = [b for b in bounce if 0 <= b < D and not ("punch" in fxs and b < 0.05)]
    if not (isinstance(zm, dict) or fxs & {"punch", "shake"} or bounce):
        return []
    z0, z1 = (float(zm.get("from", 1.0)), float(zm.get("to", 1.15))) if isinstance(zm, dict) else (1.0, 1.0)
    fx, fy = clip.get("focus") or [0.5, 0.5]
    frames = max(1, int(D * fps))
    sec = f"(on/{fps})"
    z = f"({z0}+({z1}-{z0})*min(on/{frames},1))"
    if "punch" in fxs:
        z += f"*(1+0.14*exp(-9*{sec}))"
    if bounce:  # small zoom kick on every beat, settling in ~0.2 s
        amt = float(clip.get("bounce_amount", 0.05))
        z += f"*(1+{amt}*(" + "+".join(f"gte({sec},{b:.3f})*exp(-14*({sec}-{b:.3f}))" for b in bounce) + "))"
    x, y = f"(iw-iw/zoom)*{fx}", f"(ih-ih/zoom)*{fy}"
    if "shake" in fxs:
        z += "*1.05"  # margin so the shake never reveals an edge
        amp = 0.012 * W * 2
        x += f"+{amp:.1f}*sin(on*2.3)*exp(-5*{sec})"
        y += f"+{amp:.1f}*cos(on*1.7)*exp(-5*{sec})"
    return [f"scale={W * 2}:{H * 2}", f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps}"]


# Transitions built on an xfade base plus an effect on the frames of the transition window.
XFADE_BASE = {"whip": "slideleft", "whipleft": "slideleft", "whipright": "slideright",
              "whipup": "slideup", "whipdown": "slidedown", "spin": "fade"}


def _window_chain(kind: str, N: int, W: int, H: int, fps) -> str:
    """Filters for the N frames of a whip / spin transition (frame index n restarts at 0)."""
    s = W / 1080
    if kind.startswith("whip"):  # directional motion blur, strongest mid-swipe
        ang = 90 if kind in ("whipup", "whipdown") else 0
        return (f"dblur=angle={ang}:radius={40 * s:.0f}:enable='between(n,1,{N - 2})',"
                f"dblur=angle={ang}:radius={70 * s:.0f}:enable='between(n,2,{N - 3})'")
    # spin: one full eased turn; zoom just enough that the rotated frame always covers the canvas
    p = f"(n/{max(N - 1, 1)})"
    th = f"(2*PI*(3*pow({p},2)-2*pow({p},3)))"
    thz = th.replace("n/", "on/")
    z = f"max(abs(cos({thz}))+{H / W:.4f}*abs(sin({thz})),{W / H:.4f}*abs(sin({thz}))+abs(cos({thz})))"
    return (f"rotate=a='{th}':c=black,scale={W * 2}:{H * 2},"
            f"zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={fps},"
            f"gblur=sigma={7 * s:.1f}:enable='between(n,1,{N - 2})'")


def _apply_windows(fl: list, cv: str, wins: list, fps) -> str:
    """Run per-window filter chains on frame ranges [a, b) of the joined video; returns the new label."""
    if not wins:
        return cv
    wins = sorted(wins)
    pieces, at = [], 0
    for a, b, chain in wins:
        if a > at:
            pieces.append((at, a, None))
        pieces.append((a, b, chain))
        at = b
    pieces.append((at, None, None))
    fl.append(f"[{cv}]split={len(pieces)}" + "".join(f"[wp{i}]" for i in range(len(pieces))))
    for i, (a, b, chain) in enumerate(pieces):
        trim = f"trim=start_frame={a}" + (f":end_frame={b}" if b is not None else "")
        fl.append(f"[wp{i}]{trim},setpts=PTS-STARTPTS" + (f",{chain}" if chain else "")
                  + f",format=yuv420p,setsar=1[wq{i}]")
    fl.append("".join(f"[wq{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0,"
              f"setpts=N/({fps}*TB)[vwin]")
    return "vwin"


def _join(fl: list, plan: Plan, fps, prefix: str, out: str, W: int, H: int, wins: list | None = None) -> None:
    """Join per-clip video streams [{prefix}N]: concat for cuts, xfade for transitions."""
    cv = f"{prefix}0"
    fr = float(fps)
    for n, c in enumerate(plan.clips[1:], start=1):
        if c.transition > 0:
            t = c.clip["transition"].get("type", "fade")
            # frame-aligned, matching the per-clip frame counts
            off, tdur = round(c.start * fr) / fr, (round((c.start + c.transition) * fr) - round(c.start * fr)) / fr
            fl.append(f"[{cv}][{prefix}{n}]xfade=transition={XFADE_BASE.get(t, t)}:duration={tdur:.4f}:"
                      f"offset={off:.4f},settb=AVTB,setpts=N/({fps}*TB)[{prefix}j{n}]")
            if wins is not None and t in XFADE_BASE:
                a = round(c.start * fr)
                N = max(3, round(tdur * fr))
                wins.append((a, a + N, _window_chain(t, N, W, H, fps)))
        else:
            fl.append(f"[{cv}][{prefix}{n}]concat=n=2:v=1:a=0,setpts=N/({fps}*TB)[{prefix}j{n}]")
        cv = f"{prefix}j{n}"
    # Every clip already has an exact frame count; renumber timestamps so joins leave no gaps that
    # the constant-rate encoder would fill with duplicate frames (picture slowly lagging the music).
    fl.append(f"[{cv}]setpts=N/({fps}*TB)[{out}]")


def _mask_input(add_input, ws, c, obj: dict, fps, span: float) -> int:
    mpath = Path(obj["mask"])
    mpath = mpath if mpath.is_absolute() else ws.root / mpath
    if mpath.is_dir():  # 00000.png, 00001.png ... ; frame 0 = source time `from`
        mfps = float(obj.get("fps", 30))
        first = max(0, round((c.src_in - float(obj.get("from", 0))) * mfps))
        return add_input(["-framerate", f"{mfps:g}", "-start_number", str(first), "-t", f"{span:.3f}",
                          "-i", str(mpath / "%05d.png")])
    # one still mask (e.g. for a freeze-frame image clip)
    return add_input(["-loop", "1", "-framerate", str(fps), "-t", f"{span:.3f}", "-i", str(mpath)])


def _matte(fl: list, add_input, ws, n: int, c, clip: dict, fit: str, pre: list, W: int, H: int, fps,
           D: float, nframes: int) -> None:
    """Object mask through the clip's own crop/speed/fit/zoom -> gray matte [mt{n}] (black if no object)."""
    obj = clip.get("object")
    tail = ["tpad=stop_mode=clone:stop_duration=0.5", f"trim=end_frame={nframes}", f"setpts=N/({fps}*TB)",
            "format=gray", "setsar=1", "settb=AVTB"]
    if not obj or c.kind not in ("video", "image"):
        fl.append(f"color=c=black:s={W}x{H}:r={fps}:d={D + 0.5:.3f}," + ",".join(tail) + f"[mt{n}]")
        return
    w0, h0 = int(c.info.get("width") or 1280), int(c.info.get("height") or 720)
    span = D * c.speed if c.kind == "video" else D
    mk = _mask_input(add_input, ws, c, obj, fps, span)
    out = obj.get("outline")
    grow = int(obj.get("front_grow", (out.get("width", 6) if isinstance(out, dict) else 6) if out else 2))
    chain = [f"scale={w0}:{h0}", "format=gray", "setpts=PTS-STARTPTS", *["dilation"] * grow, "gblur=sigma=1.2"]
    fl.append(f"[{mk}:v]{','.join(chain + pre)}[mpre{n}]")
    # `blur` = sharp picture contained over a blurred copy: the object only lives in the contained part
    fl += _fit_chain("contain" if fit in ("blur", "contain") else fit, W, H, clip, "#000000",
                     f"mpre{n}", f"mfit{n}", f"m{n}")
    fl.append(f"[mfit{n}]" + ",".join([f"fps={fps}", *_zoom_filters(clip, c, D, W, H, fps), *tail]) + f"[mt{n}]")


def _grade(g: dict | None) -> list[str]:
    if not g:
        return []
    out = []
    eq = {k: g[k] for k in ("brightness", "contrast", "saturation", "gamma") if k in g}
    if eq:
        out.append("eq=" + ":".join(f"{k}={v}" for k, v in eq.items()))
    if g.get("lut"):
        out.append(f"lut3d=file='{g['lut']}'")
    return out


def _upright_image(path: Path, workdir: Path) -> Path:
    """ffmpeg ignores EXIF orientation on stills; bake it in when needed."""
    try:
        im = Image.open(path)
        if im.getexif().get(274, 1) in (1, None):
            return path
        from PIL import ImageOps
        out = workdir / f"upright_{path.stem}.jpg"
        ImageOps.exif_transpose(im).convert("RGB").save(out, quality=95)
        return out
    except Exception:
        return path


def _fit_chain(fit: str, W: int, H: int, clip: dict, bg: str, label_in: str, label_out: str, i: int) -> list[str]:
    fx, fy = (clip.get("focus") or [0.5, 0.5])
    z = float(clip.get("zoom", 1.0)) if not isinstance(clip.get("zoom"), dict) else 1.0
    if fit == "contain":
        return [f"[{label_in}]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={_hex(bg)}[{label_out}]"]
    if fit == "fill":
        return [f"[{label_in}]scale={W}:{H}[{label_out}]"]
    if fit == "blur":
        w8, h8 = _even(W / 8), _even(H / 8)
        return [
            f"[{label_in}]split[bgs{i}][fgs{i}]",
            f"[bgs{i}]scale={w8}:{h8}:force_original_aspect_ratio=increase,crop={w8}:{h8},"
            f"boxblur=8:2,eq=brightness=-0.06,scale={W}:{H}[bg{i}]",
            f"[fgs{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{i}]",
            f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2[{label_out}]",
        ]
    Wz, Hz = _even(W * z), _even(H * z)
    return [f"[{label_in}]scale={Wz}:{Hz}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}[{label_out}]"]


def build_command(ws, plan: Plan, out_path: Path, workdir: Path, *, preview: bool = False,
                  range_: tuple[float, float] | None = None) -> tuple[list[str], list[str]]:
    o = plan.output
    scale = 0.5 if preview else 1.0
    W, H, fps = _even(o["width"] * scale), _even(o["height"] * scale), o["fps"]
    sr = int(o["sample_rate"])
    total = plan.duration
    notes: list[str] = []
    inputs: list[list[str]] = []
    fl: list[str] = []
    aformat = f"aformat=sample_fmts=fltp:sample_rates={sr}:channel_layouts=stereo"

    def add_input(args: list) -> int:
        inputs.append([str(a) for a in args])
        return len(inputs) - 1

    # Text marked `behind` goes under the masked object of the clip on screen (text behind subject):
    # every clip then also renders a matte (object mask in output space, same crop/fit/zoom/speed).
    behind_text = any(t.get("behind") for t in plan.edl.get("text") or [])

    # -- clips ----------------------------------------------------------------
    for n, c in enumerate(plan.clips):
        D = c.duration
        clip = c.clip
        if c.kind == "video":
            src = c.path
            if preview and c.media_id and ws.proxy_path(c.media_id).exists():
                src = ws.proxy_path(c.media_id)
            span = D * c.speed
            k = add_input([*ff.hwaccel_args(), "-ss", f"{c.src_in:.3f}", "-t", f"{span:.3f}", "-i", src])
        elif c.kind == "image":
            k = add_input(["-loop", "1", "-framerate", fps, "-t", f"{D:.3f}", "-i", _upright_image(c.path, workdir)])
        else:
            k = add_input(["-f", "lavfi", "-t", f"{D:.3f}", "-i",
                           f"color=c={_hex(clip['color'])}:s={W}x{H}:r={fps}"])

        src_label = f"{k}:v"
        if clip.get("object") and c.kind in ("video", "image"):
            src_label = _object_chain(fl, add_input, ws, n, k, c, clip["object"], fps, D)

        pre = []
        if clip.get("crop"):
            x, y, w, h = clip["crop"]
            pre.append(f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}")
        pre.append(f"setpts=(PTS-STARTPTS)/{c.speed}" if c.kind == "video" else "setpts=PTS-STARTPTS")
        if clip.get("reverse") and c.kind == "video":
            pre += ["reverse", "setpts=PTS-STARTPTS"]  # play backwards (rewind); keep clips short, it buffers
        fl.append(f"[{src_label}]{','.join(pre)}[pre{n}]")
        nframes = max(1, round((c.start + D) * float(fps)) - round(c.start * float(fps)))
        if behind_text:
            _matte(fl, add_input, ws, n, c, clip, clip.get("fit", o["fit"]), pre, W, H, fps, D, nframes)
        if c.kind == "color":
            fl.append(f"[pre{n}]null[fit{n}]")
        else:
            fl += _fit_chain(clip.get("fit", o["fit"]), W, H, clip, o["bg"], f"pre{n}", f"fit{n}", n)

        fxs = set(clip.get("fx") or [])
        post = [f"fps={fps}", *_zoom_filters(clip, c, D, W, H, fps)]
        post += _grade(clip.get("grade"))
        if "bw" in fxs:
            post.append("hue=s=0,eq=contrast=1.15")
        if "trail" in fxs:
            post.append("tmix=frames=4:weights='4 3 2 1'")
        if "rgb" in fxs:
            s = max(2, round(W / 1080 * 9))
            post.append(f"rgbashift=rh=-{s}:bh={s}:edge=smear")
        if "vignette" in fxs:
            post.append("vignette=angle=PI/4.5")
        if "grain" in fxs:
            post.append("noise=alls=9:allf=t")
        if "flash" in fxs:
            post.append("fade=t=in:st=0:d=0.14:color=white")
        if "impact" in fxs:  # anime impact frame: 1 negative frame, then 1 hard black & white frame
            f1, f2 = 0.5 / float(fps), 1.5 / float(fps)
            post.append(f"hue=s=0:enable='lt(t,{f2:.4f})',"
                        f"eq=contrast=2.4:brightness=0.06:enable='lt(t,{f2:.4f})',"
                        f"negate=enable='lt(t,{f1:.4f})'")
        fade = clip.get("fade") or {}
        if fade.get("in"):
            post.append(f"fade=t=in:st=0:d={fade['in']}")
        if fade.get("out"):
            post.append(f"fade=t=out:st={max(0, D - fade['out']):.3f}:d={fade['out']}")
        if clip.get("vf"):
            post.append(clip["vf"])
        # Exact frame count from the clip's timeline position (not its own rounded length), so
        # per-clip rounding never accumulates into picture drifting behind the music over many cuts.
        post += ["tpad=stop_mode=clone:stop_duration=0.5", f"trim=end_frame={nframes}", f"setpts=N/({fps}*TB)"]
        post += ["format=yuv420p", "setsar=1", "settb=AVTB"]
        if "open" in fxs:  # letterbox slit: a thin band of picture opens (ease-in) to the full frame in 0.35 s
            fl.append(f"[fit{n}]{','.join(post)}[vo{n}]")
            bar = f"({H / 2:.0f}*0.94*(1-pow(min(t/0.35,1),2)))"
            fl.append(f"color=c=black:s={W}x{H // 2}:r={fps}:d=0.4,split[obt{n}][obb{n}]")
            fl.append(f"[vo{n}][obt{n}]overlay=x=0:y='{bar}-{H // 2}':eval=frame:eof_action=pass[vo2{n}]")
            fl.append(f"[vo2{n}][obb{n}]overlay=x=0:y='{H}-{bar}':eval=frame:eof_action=pass,"
                      f"format=yuv420p,setsar=1,settb=AVTB[v{n}]")
        else:
            fl.append(f"[fit{n}]{','.join(post)}[v{n}]")

        # audio for this clip, always exactly D seconds long
        if c.kind == "video" and c.info.get("has_audio") and not clip.get("mute"):
            ach = ["asetpts=PTS-STARTPTS", *_atempo(c.speed), f"volume={clip.get('volume', 1.0)}", aformat]
            if D > 0.1:
                ach += ["afade=t=in:d=0.015", f"afade=t=out:st={D - 0.015:.3f}:d=0.015"]
            if fade.get("in"):
                ach.append(f"afade=t=in:d={fade['in']}")
            if fade.get("out"):
                ach.append(f"afade=t=out:st={max(0, D - fade['out']):.3f}:d={fade['out']}")
            if clip.get("af"):
                ach.append(clip["af"])
            ach += [f"apad=whole_dur={D:.4f}", f"atrim=0:{D:.4f}"]
            fl.append(f"[{k}:a]{','.join(ach)}[a{n}]")
        else:
            fl.append(f"aevalsrc=0|0:c=stereo:s={sr}:d={D:.4f},{aformat}[a{n}]")

    # -- join clips: concat for cuts, xfade/acrossfade for transitions ---------
    wins: list = []
    _join(fl, plan, fps, "v", "vjoined", W, H, wins)
    cv = _apply_windows(fl, "vjoined", wins, fps)
    ca = "a0"
    for n, c in enumerate(plan.clips[1:], start=1):
        if c.transition > 0:
            fl.append(f"[{ca}][a{n}]acrossfade=d={c.transition:.3f}[aj{n}]")
        else:
            fl.append(f"[{ca}][a{n}]concat=n=2:v=0:a=1[aj{n}]")
        ca = f"aj{n}"

    # -- graphics layer: text, images, captions --------------------------------
    items = [dict(t) for t in plan.edl.get("text") or []]
    for im in plan.edl.get("images") or []:
        items.append({**im, "_kind": "image", "_path": str(ws.resolve_src(im["src"])[1])})
    if plan.edl.get("captions"):
        cap_items, missing = captions.overlay_items(ws, plan)
        if missing:
            notes.append("no transcript for: " + ", ".join(missing) + " (run `cstudio transcribe`)")
        items += cap_items
    behind = [it for it in items if it.get("behind")]
    items = [it for it in items if not it.get("behind")]
    lb = layer.build(behind, (W, H), total, workdir / "layer_behind", scale=scale, fps=float(fps)) if behind else None
    if lb:  # behind-text over the picture, then the masked object pasted back on top of it
        _join(fl, plan, fps, "mt", "mseq", W, H)
        kb = add_input(["-f", "concat", "-safe", "0", "-i", lb])
        fl.append(f"[{cv}]split[vbk][vfr]")
        fl.append(f"[vbk][{kb}:v]overlay=0:0:format=auto:eof_action=pass[vbt]")
        fl.append("[vfr][mseq]alphamerge[vfa]")
        fl.append("[vbt][vfa]overlay=0:0:format=auto[vbh]")
        cv = "vbh"
    lst = layer.build(items, (W, H), total, workdir / "layer", scale=scale, fps=float(fps))
    if lst:
        k = add_input(["-f", "concat", "-safe", "0", "-i", lst])
        fl.append(f"[{cv}][{k}:v]overlay=0:0:format=auto:eof_action=pass[vov]")
        cv = "vov"

    # -- global video finishing --------------------------------------------------
    fin = _grade(o.get("grade"))
    if o.get("fade_in"):
        fin.append(f"fade=t=in:st=0:d={o['fade_in']}")
    if o.get("fade_out"):
        fin.append(f"fade=t=out:st={max(0, total - o['fade_out']):.3f}:d={o['fade_out']}")
    fin.append("format=yuv420p")
    fl.append(f"[{cv}]{','.join(fin)}[vout]")

    # -- extra audio tracks (music, voice-over, sfx) ---------------------------
    tracks = plan.edl.get("audio") or []
    mix = [ca]
    ducked = [i for i, a in enumerate(tracks) if a.get("duck")]
    if ducked:
        fl.append(f"[{ca}]asplit={len(ducked) + 1}[amain]" + "".join(f"[sc{i}]" for i in ducked))
        mix = ["amain"]
    for i, a in enumerate(tracks):
        _, ap = ws.resolve_src(a["src"])
        at = float(a.get("at", 0))
        a_in = float(a.get("in", 0))
        loop = bool(a.get("loop"))
        info = ff.probe(ap)
        avail = (float(a["out"]) if a.get("out") is not None else info.get("duration", total)) - a_in
        length = max(0.05, min(total - at, avail if not loop else total - at))
        k = add_input([*(["-stream_loop", "-1"] if loop else []), "-i", ap])
        ach = [f"atrim=start={a_in:.3f}" + (f":end={float(a['out']):.3f}" if a.get("out") is not None and not loop else ""),
               "asetpts=PTS-STARTPTS", f"atrim=0:{length:.3f}", f"volume={a.get('volume', 1.0)}", aformat]
        if a.get("fade_in"):
            ach.append(f"afade=t=in:d={a['fade_in']}")
        if a.get("fade_out"):
            ach.append(f"afade=t=out:st={max(0, length - a['fade_out']):.3f}:d={a['fade_out']}")
        if at > 0:
            ach.append(f"adelay={int(at * 1000)}:all=1")
        fl.append(f"[{k}:a]{','.join(ach)}[t{i}]")
        if a.get("duck"):
            amount = a["duck"] if isinstance(a["duck"], (int, float)) and not isinstance(a["duck"], bool) else 8
            fl.append(f"[t{i}][sc{i}]sidechaincompress=threshold=0.02:ratio={amount}:attack=30:release=500[td{i}]")
            mix.append(f"td{i}")
        else:
            mix.append(f"t{i}")
    if len(mix) > 1:
        fl.append("".join(f"[{m}]" for m in mix) +
                  f"amix=inputs={len(mix)}:duration=first:normalize=0:dropout_transition=0[amix]")
        afinal = "amix"
    else:
        afinal = ca
    fin_a = []
    if o.get("fade_in"):
        fin_a.append(f"afade=t=in:d={o['fade_in']}")
    if o.get("fade_out"):
        fin_a.append(f"afade=t=out:st={max(0, total - o['fade_out']):.3f}:d={o['fade_out']}")
    if o.get("loudness") is not None:
        fin_a += [f"loudnorm=I={o['loudness']}:TP=-1.5:LRA=11", f"aresample={sr}"]
    fin_a.append(aformat)
    fl.append(f"[{afinal}]{','.join(fin_a)}[aout]")

    cmd = [ff.require("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-v", "error", "-stats", "-stats_period", "5"]
    for args in inputs:
        cmd += args
    cmd += ["-filter_complex", ";\n".join(fl), "-map", "[vout]", "-map", "[aout]"]
    if range_:
        cmd += ["-ss", f"{range_[0]:.3f}", "-to", f"{range_[1]:.3f}"]
    else:
        cmd += ["-t", f"{total:.3f}"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast" if preview else o["encoder_preset"],
        "-crf", str(28 if preview else o["crf"]), "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", o["audio_bitrate"], "-ar", str(sr),
        "-movflags", "+faststart", str(out_path),
    ]
    return cmd, notes


def render(ws, plan: Plan, out_path: Path, *, preview: bool = False, dry_run: bool = False,
           range_: tuple[float, float] | None = None) -> dict:
    if plan.errors:
        raise SystemExit("EDL has errors:\n  " + "\n  ".join(plan.errors))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = ws.state / "render" / out_path.stem
    workdir.mkdir(parents=True, exist_ok=True)
    cmd, notes = build_command(ws, plan, out_path, workdir, preview=preview, range_=range_)
    (workdir / "command.sh").write_text(" ".join(shlex.quote(c) for c in cmd) + "\n")
    for n in notes:
        print(f"note: {n}", file=sys.stderr)
    if dry_run:
        return {"command": str(workdir / "command.sh"), "notes": notes}
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed; full command in {workdir / 'command.sh'}")
    return {"output": str(out_path), "duration": round(plan.duration, 3), "notes": notes,
            "command": str(workdir / "command.sh")}
