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

        pre = []
        if clip.get("crop"):
            x, y, w, h = clip["crop"]
            pre.append(f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}")
        pre.append(f"setpts=(PTS-STARTPTS)/{c.speed}" if c.kind == "video" else "setpts=PTS-STARTPTS")
        fl.append(f"[{k}:v]{','.join(pre)}[pre{n}]")
        if c.kind == "color":
            fl.append(f"[pre{n}]null[fit{n}]")
        else:
            fl += _fit_chain(clip.get("fit", o["fit"]), W, H, clip, o["bg"], f"pre{n}", f"fit{n}", n)

        post = [f"fps={fps}"]
        zm = clip.get("zoom")
        if isinstance(zm, dict):  # animated push-in / pull-out (Ken Burns)
            z0, z1 = float(zm.get("from", 1.0)), float(zm.get("to", 1.15))
            fx, fy = clip.get("focus") or [0.5, 0.5]
            frames = max(1, int(D * fps))
            post += [f"scale={W * 2}:{H * 2}",
                     f"zoompan=z='{z0}+({z1}-{z0})*min(on/{frames},1)':x='(iw-iw/zoom)*{fx}':"
                     f"y='(ih-ih/zoom)*{fy}':d=1:s={W}x{H}:fps={fps}"]
        post += _grade(clip.get("grade"))
        fade = clip.get("fade") or {}
        if fade.get("in"):
            post.append(f"fade=t=in:st=0:d={fade['in']}")
        if fade.get("out"):
            post.append(f"fade=t=out:st={max(0, D - fade['out']):.3f}:d={fade['out']}")
        if clip.get("vf"):
            post.append(clip["vf"])
        post += ["format=yuv420p", "setsar=1", "settb=AVTB"]
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
    cv, ca = "v0", "a0"
    for n, c in enumerate(plan.clips[1:], start=1):
        if c.transition > 0:
            t = c.clip["transition"].get("type", "fade")
            off = c.start
            fl.append(f"[{cv}][v{n}]xfade=transition={t}:duration={c.transition:.3f}:offset={off:.3f},settb=AVTB[vj{n}]")
            fl.append(f"[{ca}][a{n}]acrossfade=d={c.transition:.3f}[aj{n}]")
        else:
            fl.append(f"[{cv}][{ca}][v{n}][a{n}]concat=n=2:v=1:a=1[vj{n}][aj{n}]")
        cv, ca = f"vj{n}", f"aj{n}"

    # -- graphics layer: text, images, captions --------------------------------
    items = [dict(t) for t in plan.edl.get("text") or []]
    for im in plan.edl.get("images") or []:
        items.append({**im, "_kind": "image", "_path": str(ws.resolve_src(im["src"])[1])})
    if plan.edl.get("captions"):
        cap_items, missing = captions.overlay_items(ws, plan)
        if missing:
            notes.append("no transcript for: " + ", ".join(missing) + " (run `cstudio transcribe`)")
        items += cap_items
    lst = layer.build(items, (W, H), total, workdir / "layer", scale=scale)
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
