"""`cstudio`: command line entry point. Every command prints JSON or a compact table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analyze, captions, edl as edlmod, ff, render as rendermod, review as reviewmod, transcribe
from .workspace import Workspace, collect_media


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _edl_name(p: Path) -> str:
    name = p.name
    for suf in (".edl.json", ".json"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return p.stem


# -- commands -------------------------------------------------------------------
def cmd_init(a):
    ws = Workspace.init(Path(a.dir), a.name)
    print(f"workspace ready: {ws.root}")
    print("next: cstudio ingest <files or folders>")


def cmd_ingest(a):
    ws = Workspace.find()
    paths = [Path(p) for p in a.paths] or [ws.root]
    files = collect_media(paths)
    if not files:
        raise SystemExit("no media files found")
    media = ws.media()
    results = []
    for f in files:
        mid = ws.media_id_for(f, media)
        try:
            info = ff.probe(f)
        except ff.FFError as e:
            print(f"skip {f}: {e}", file=sys.stderr)
            continue
        info["path"] = ws.rel(f)
        is_new = mid not in media
        media[mid] = info
        ws.save_media(media)
        done = (ws.state / "analysis" / mid).exists() and any((ws.state / "analysis" / mid).iterdir())
        if a.no_analysis or info["type"] == "unknown" or (done and not a.force):
            results.append({"id": mid, "type": info["type"], "status": "indexed" if is_new else "cached"})
            continue
        print(f"analyzing {mid} ...", file=sys.stderr)
        summary = analyze.ingest_one(ws, mid, info, proxy=a.proxy)
        if a.transcribe and info.get("has_audio") and info["type"] in ("video", "audio"):
            tr = transcribe.transcribe(ws, mid, model=a.model, language=a.lang)
            summary["transcript_words"] = len(tr["words"])
        results.append(summary)
    _print(results)
    print(f"\nindex: {ws.rel(ws.media_file)}   analysis: .studio/analysis/<id>/", file=sys.stderr)


def cmd_media(a):
    ws = Workspace.find()
    media = ws.media()
    if a.json:
        return _print(media)
    print(f"{'id':<28} {'type':<6} {'dur':>8} {'size':>11} {'fps':>6} audio  path")
    for mid, m in media.items():
        dur = f"{m['duration']:.1f}s" if m.get("duration") else "-"
        size = f"{m.get('width', '-')}x{m.get('height', '-')}" if m.get("width") else "-"
        tr = " T" if (ws.state / "analysis" / mid / "transcript.json").exists() else ""
        print(f"{mid:<28} {m['type']:<6} {dur:>8} {size:>11} {str(m.get('fps') or '-'):>6} "
              f"{'yes' if m.get('has_audio') else 'no':<5}{tr:<2} {m['path']}")


def cmd_probe(a):
    _print(ff.probe(Path(a.file)))


def _src_path(src: str) -> tuple[Path, Path]:
    """Return (media path, folder for outputs) for a media id or a path."""
    try:
        ws = Workspace.find()
        mid, p = ws.resolve_src(src)
        return p, ws.analysis_dir(mid) if mid else ws.state / "scratch"
    except SystemExit:
        p = Path(src)
        return p, p.parent


def cmd_sheet(a):
    p, outdir = _src_path(a.src)
    end = a.end
    tag = f"{a.start:g}-{end:g}" if end is not None else f"{a.start:g}-end"
    out = Path(a.out) if a.out else outdir / f"sheet_{tag}.jpg"
    r = analyze.contact_sheet(p, out, start=a.start, end=end, count=a.count, cols=a.cols,
                              thumb_w=a.width, label=f"{p.name}  {tag}")
    _print(r)


def cmd_frame(a):
    p, outdir = _src_path(a.src)
    out = Path(a.out) if a.out else outdir / f"frame_{a.t:.2f}.jpg"
    analyze.extract_frame(p, a.t, out, width=a.width)
    print(out)


def cmd_transcribe(a):
    ws = Workspace.find()
    media = ws.media()
    ids = list(a.ids)
    if a.all or not ids:
        ids = [m for m, i in media.items() if i.get("has_audio") and i["type"] in ("video", "audio")]
    out = []
    for mid in ids:
        if mid not in media:
            mid2, _ = ws.resolve_src(mid)
            if not mid2:
                raise SystemExit(f"unknown media '{mid}' (ingest it first)")
            mid = mid2
        if transcribe.load(ws, mid) and not a.force:
            out.append({"id": mid, "status": "cached"})
            continue
        tr = transcribe.transcribe(ws, mid, model=a.model, language=a.lang, prompt=a.prompt)
        out.append({"id": mid, "language": tr["language"], "words": len(tr["words"]),
                    "text": f".studio/analysis/{mid}/transcript.txt"})
    _print(out)


def _plan(path: str):
    p = Path(path)
    ws = Workspace.find(p.resolve().parent)
    return ws, edlmod.plan(ws, edlmod.load(p)), p


def cmd_validate(a):
    ws, plan, _ = _plan(a.edl)
    print(edlmod.timeline_table(plan))
    for w in plan.warnings:
        print(f"warning: {w}")
    for e in plan.errors:
        print(f"ERROR: {e}")
    if plan.edl.get("captions"):
        _, missing = captions.build_chunks(ws, plan)
        for m in missing:
            print(f"warning: captions requested but no transcript for {m}")
    sys.exit(1 if plan.errors else 0)


def cmd_captions(a):
    ws, plan, p = _plan(a.edl)
    chunks, missing = captions.build_chunks(ws, plan)
    for m in missing:
        print(f"warning: no transcript for {m}", file=sys.stderr)
    name = _edl_name(p)
    if a.srt or not a.json:
        out = Path(a.srt) if a.srt else ws.root / "renders" / f"{name}.srt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(captions.to_srt(chunks))
        print(f"srt: {out}")
    if a.json:
        out = Path(a.json)
        captions.write_json(chunks, out)
        print(f"json: {out}  (edit, then set captions.file in the EDL)")
    for c in chunks[: a.show]:
        print(f"  {c['start']:7.2f}-{c['end']:7.2f}  {c['text']}")


def cmd_render(a):
    ws, plan, p = _plan(a.edl)
    for w in plan.warnings:
        print(f"warning: {w}", file=sys.stderr)
    name = _edl_name(p) + ("-preview" if a.preview else "")
    out = Path(a.out) if a.out else ws.root / "renders" / f"{name}.mp4"
    rng = None
    if a.range:
        s, e = a.range.split(":")
        rng = (float(s), float(e))
    print(edlmod.timeline_table(plan), file=sys.stderr)
    _print(rendermod.render(ws, plan, out, preview=a.preview, dry_run=a.dry_run, range_=rng))


def cmd_review(a):
    path = Path(a.video)
    expected, target, dark = None, -14, None
    if a.edl:
        _, plan, _ = _plan(a.edl)
        expected, target, dark = plan.duration, plan.output.get("loudness"), reviewmod.intended_dark(plan)
    sheet = path.with_name(path.stem + "_review.jpg")
    _print(reviewmod.review(path, sheet, expected_duration=expected, target_lufs=target, dark_ok=dark))


# -- parser -----------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="cstudio", description="Reelsmith video toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="make the current (or given) folder a workspace")
    s.add_argument("dir", nargs="?", default=".")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("ingest", help="index + analyze media (scenes, sheets, loudness, silence)")
    s.add_argument("paths", nargs="*", help="files or folders (default: whole workspace)")
    s.add_argument("--proxy", action="store_true", help="also make 720p proxies for fast previews")
    s.add_argument("--transcribe", action="store_true", help="also transcribe speech")
    s.add_argument("--lang", help="speech language, e.g. vi, en (default: auto)")
    s.add_argument("--model", default=transcribe.DEFAULT_MODEL)
    s.add_argument("--no-analysis", action="store_true", help="only probe and index")
    s.add_argument("--force", action="store_true", help="re-analyze even if cached")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("media", help="list indexed media")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_media)

    s = sub.add_parser("probe", help="describe one media file")
    s.add_argument("file")
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("sheet", help="contact sheet of a time range (zoom in on a section)")
    s.add_argument("src", help="media id or path")
    s.add_argument("--start", type=float, default=0.0)
    s.add_argument("--end", type=float)
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--cols", type=int, default=4)
    s.add_argument("--width", type=int, default=360, help="thumbnail width")
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_sheet)

    s = sub.add_parser("frame", help="extract one frame")
    s.add_argument("src")
    s.add_argument("t", type=float)
    s.add_argument("--width", type=int, default=960)
    s.add_argument("-o", "--out")
    s.set_defaults(fn=cmd_frame)

    s = sub.add_parser("transcribe", help="speech to text with word timestamps")
    s.add_argument("ids", nargs="*", help="media ids (default: all with audio)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--lang")
    s.add_argument("--model", default=transcribe.DEFAULT_MODEL)
    s.add_argument("--prompt", help="spelling hints: names, places, jargon")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_transcribe)

    s = sub.add_parser("validate", help="check an EDL and print its timeline")
    s.add_argument("edl")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("timeline", help="alias of validate")
    s.add_argument("edl")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("captions", help="build captions for an EDL (export .srt / editable .json)")
    s.add_argument("edl")
    s.add_argument("--srt")
    s.add_argument("--json")
    s.add_argument("--show", type=int, default=20)
    s.set_defaults(fn=cmd_captions)

    s = sub.add_parser("render", help="render an EDL to video")
    s.add_argument("edl")
    s.add_argument("-o", "--out")
    s.add_argument("--preview", action="store_true", help="half resolution, fast encode, uses proxies")
    s.add_argument("--range", help="only render START:END seconds of the timeline")
    s.add_argument("--dry-run", action="store_true", help="write the ffmpeg command without running it")
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("review", help="QA a rendered video: loudness, black frames, silence, contact sheet")
    s.add_argument("video")
    s.add_argument("--edl", help="compare against this EDL's expected duration/loudness")
    s.set_defaults(fn=cmd_review)

    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except ff.FFError as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
