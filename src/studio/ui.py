"""`cstudio ui`: a local web page that shows an EDL as a timeline.

Stdlib only (http.server). The page polls the server, so when Claude (or you) edits the
EDL the timeline redraws within a second, and a fresh half-resolution preview is rendered
in the background.

Routes (all GET unless noted, `edl` = file name inside `edits/`):
    /                       the page (studio/ui_static/index.html)
    /api/edls               EDL files in the workspace
    /api/timeline?edl=      the resolved timeline: clips, audio, overlays, captions, status
    /api/version?edl=       cheap change detector (EDL + preview mtimes, render state)
    /api/thumb?src=&t=&h=   one frame of a source as JPEG (cached in .studio/ui/thumbs)
    /api/peaks?src=         audio peaks of a source, 50 per second (cached)
    /media/preview?edl=     the preview render, with HTTP Range support (seeking)
    POST /api/render?edl=   start a preview render now
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from array import array
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import copy
import secrets

from PIL import Image, ImageOps

from . import captions as captionsmod, edl as edlmod, ff, render as rendermod
from .workspace import MEDIA_EXT, Workspace, collect_media

STATIC = Path(__file__).parent / "ui_static"
PEAKS_PER_SEC = 50
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
QUALITY = {"high": (18, "slow"), "standard": (20, "medium"), "small": (26, "medium")}
AUDIO_CODECS = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "256k"],
    "m4a": ["-c:a", "aac", "-b:a", "256k"],
    "wav": ["-c:a", "pcm_s16le"],
}


class Jobs:
    """Background work (imports, exports) with progress the page can poll."""

    def __init__(self):
        self.lock = threading.Lock()
        self.items: dict[str, dict] = {}
        self.n = 0

    def add(self, kind: str, label: str, fn) -> str:
        with self.lock:
            self.n += 1
            jid = f"j{self.n}"
            self.items[jid] = {"id": jid, "kind": kind, "label": label, "state": "running", "progress": None,
                               "message": "", "result": None, "started": time.time()}

        def report(progress=None, message=None):
            with self.lock:
                j = self.items[jid]
                j["progress"] = progress
                if message is not None:
                    j["message"] = message

        def run():
            try:
                res = fn(report)
                with self.lock:
                    self.items[jid].update(state="done", progress=1.0, result=res, message="", finished=time.time())
            except BaseException as e:  # SystemExit from the toolkit carries the readable message
                readable = isinstance(e, (SystemExit, ff.FFError, ValueError, LookupError))
                if not readable:
                    traceback.print_exc()
                msg = str(e) if readable else f"{type(e).__name__}: {e}"
                with self.lock:
                    self.items[jid].update(state="error", message=msg[-2000:], finished=time.time())

        threading.Thread(target=run, daemon=True).start()
        return jid

    def list(self) -> list[dict]:
        with self.lock:
            return sorted((dict(j) for j in self.items.values()), key=lambda j: -j["started"])[:40]


def edl_name(p: Path) -> str:
    for suf in (".edl.json", ".json"):
        if p.name.endswith(suf):
            return p.name[: -len(suf)]
    return p.stem


class Renderer:
    """Background preview renders, one at a time per EDL, re-run when the EDL changed meanwhile."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.lock = threading.Lock()
        self.state: dict[str, dict] = {}   # edl path -> {state, message, started, finished}

    def status(self, edl_path: Path) -> dict:
        with self.lock:
            return dict(self.state.get(str(edl_path), {"state": "idle"}))

    def start(self, edl_path: Path, out: Path) -> bool:
        key = str(edl_path)
        with self.lock:
            st = self.state.get(key, {})
            if st.get("state") == "running":
                st["again"] = True
                return False
            self.state[key] = {"state": "running", "started": time.time()}
        threading.Thread(target=self._run, args=(edl_path, out), daemon=True).start()
        return True

    def _run(self, edl_path: Path, out: Path) -> None:
        key = str(edl_path)
        msg, ok = "", False
        try:
            plan = edlmod.plan(self.ws, edlmod.load(edl_path))
            tmp = out.with_name(out.stem + ".rendering.mp4")
            rendermod.render(self.ws, plan, tmp, preview=True)
            tmp.replace(out)  # swap atomically so the page never streams a half-written file
            ok = True
        except SystemExit as e:
            msg = str(e)
        except Exception as e:  # keep the server alive whatever happens
            msg = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        with self.lock:
            again = self.state.get(key, {}).get("again")
            self.state[key] = {"state": "done" if ok else "error", "message": msg[-2000:],
                               "finished": time.time()}
        if again:
            self.start(edl_path, out)


class App:
    def __init__(self, ws: Workspace, default_edl: Path | None, auto_render: bool):
        self.ws = ws
        self.default_edl = default_edl.resolve() if default_edl else None
        self.auto_render = auto_render
        self.renderer = Renderer(ws)
        self.thumb_dir = ws.state / "ui" / "thumbs"
        self.peaks_dir = ws.state / "ui" / "peaks"
        self._seen: dict[str, float] = {}   # edl path -> mtime that auto-render last reacted to
        self._peaks_lock = threading.Lock()
        self._media_lock = threading.Lock()
        self._edl_lock = threading.Lock()
        self.jobs = Jobs()
        self.token = secrets.token_urlsafe(24)   # required on every state-changing request

    # -- EDL selection ---------------------------------------------------------
    def edls(self) -> list[Path]:
        found = sorted((p.resolve() for p in (self.ws.root / "edits").glob("*.json")),
                       key=lambda p: -p.stat().st_mtime)
        if self.default_edl and self.default_edl not in found:
            found.insert(0, self.default_edl)
        return found

    def edl_path(self, name: str | None) -> Path:
        if not name:
            if self.default_edl:
                return self.default_edl
            all_ = self.edls()
            if not all_:
                raise LookupError("no EDL in edits/ yet")
            return all_[0]
        for p in self.edls():
            if p.name == name or edl_name(p) == name:
                return p
        raise LookupError(f"unknown EDL '{name}'")

    def preview_path(self, edl_path: Path) -> Path:
        return self.ws.root / "renders" / f"{edl_name(edl_path)}-preview.mp4"

    # -- status ----------------------------------------------------------------
    def version(self, edl_path: Path) -> dict:
        prev = self.preview_path(edl_path)
        em = edl_path.stat().st_mtime
        pm = prev.stat().st_mtime if prev.exists() else None
        rs = self.renderer.status(edl_path)
        if self.auto_render and self._seen.get(str(edl_path)) != em and (pm is None or pm < em):
            # debounce: wait until the file has been still for a moment (Claude often edits twice)
            if time.time() - em > 1.5:
                self._seen[str(edl_path)] = em
                try:
                    plan = edlmod.plan(self.ws, edlmod.load(edl_path))
                    if not plan.errors:
                        self.renderer.start(edl_path, prev)
                        rs = self.renderer.status(edl_path)
                except Exception:
                    pass  # invalid JSON mid-edit: the timeline endpoint reports it
        return {"edl": edl_path.name, "edl_mtime": em, "preview_mtime": pm,
                "preview_stale": pm is None or pm < em, "render": rs}

    # -- the timeline ----------------------------------------------------------
    def timeline(self, edl_path: Path) -> dict:
        try:
            edl = edlmod.load(edl_path)
        except json.JSONDecodeError as e:
            return {"name": edl_name(edl_path), "errors": [f"invalid JSON: {e}"], "warnings": [],
                    "clips": [], "audio": [], "text": [], "images": [], "captions": [],
                    "duration": 0, "output": {"width": 1920, "height": 1080, "fps": 30},
                    **self.version(edl_path)}
        plan = edlmod.plan(self.ws, edl)
        total = plan.duration
        out: dict = {
            "name": edl_name(edl_path),
            "path": self.ws.rel(edl_path),
            "output": plan.output,
            "duration": round(total, 3),
            # an empty edit is a starting point here, not a problem (render/validate still refuse it)
            "errors": [e for e in plan.errors if e != "EDL has no clips"],
            "warnings": list(plan.warnings) + (
                [] if plan.clips else ["empty timeline: import media, then add clips from the library"]),
            "clips": [], "audio": [], "text": [], "images": [], "captions": [],
            "doc": edl,   # raw document: the page edits this and saves it back whole
        }
        for c in plan.clips:
            item = {
                "index": c.index, "kind": c.kind, "src": c.clip.get("src"), "color": c.clip.get("color"),
                "start": round(c.start, 3), "end": round(c.end, 3), "duration": round(c.duration, 3),
                "transition": round(c.transition, 3),
                "transition_type": (c.clip.get("transition") or {}).get("type", "fade") if c.transition else None,
                "speed": c.speed,
                "label": c.media_id or (Path(c.clip["src"]).name if c.clip.get("src") else c.clip.get("color")),
                "has_audio": bool(c.info.get("has_audio")) and c.kind == "video",
                "mute": bool(c.clip.get("mute")), "volume": c.clip.get("volume", 1),
                "entry": c.clip,
                "width": c.info.get("width"), "height": c.info.get("height"),
                "src_fps": c.info.get("fps"), "src_duration": c.info.get("duration"),
            }
            if c.kind == "video":
                item["in"] = c.src_in
                item["out"] = float(c.clip.get("out", c.info.get("duration", 0)))
                item["silences"] = self._silences_on_timeline(c)
            out["clips"].append(item)

        for k, a in enumerate(edl.get("audio") or []):
            if not a.get("src"):
                continue
            mid, _ = self.ws.resolve_src(a["src"])
            try:
                adur = float(self.ws.info_for(a["src"]).get("duration") or 0)
            except Exception:
                adur = 0.0
            a_in = float(a.get("in", 0))
            a_out = float(a["out"]) if a.get("out") is not None else adur
            at = float(a.get("at", 0))
            loop = bool(a.get("loop"))
            end = total if loop else min(total, at + max(0.0, a_out - a_in))
            out["audio"].append({"index": k, "src": a["src"], "label": mid or Path(a["src"]).name,
                                 "start": round(at, 3), "end": round(max(at, end), 3), "in": a_in,
                                 "out": a_out, "loop": loop, "volume": a.get("volume", 1),
                                 "entry": a})

        for key in ("text", "images"):
            for k, t in enumerate(edl.get(key) or []):
                s = float(t.get("start", 0))
                e = min(total, float(t.get("end", total)))
                label = t.get("text", "") if key == "text" else Path(t.get("src", "?")).name
                if s >= total > 0:
                    out["warnings"].append(f"{key}[{k}] starts at {s:g}s, after the video ends ({total:.2f}s)")
                    e = s
                out[key].append({"index": k, "start": round(s, 3), "end": round(e, 3),
                                 "label": label, "entry": t})

        if edl.get("captions") is not None and plan.clips:
            try:
                chunks, missing = captionsmod.build_chunks(self.ws, plan)
                out["captions"] = [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in chunks]
                for m in missing:
                    out["warnings"].append(f"captions: no transcript for {m} (run cstudio transcribe)")
            except Exception as e:
                out["warnings"].append(f"captions: {e}")

        out.update(self.version(edl_path))
        return out

    def _silences_on_timeline(self, c) -> list[list[float]]:
        if not c.media_id:
            return []
        f = self.ws.state / "analysis" / c.media_id / "audio.json"
        if not f.exists():
            return []
        cin = c.src_in
        cout = cin + c.duration * c.speed
        res = []
        for s in json.loads(f.read_text()).get("silences", []):
            a = max(s["start"], cin)
            b = min(s["end"] if s["end"] is not None else cout, cout)
            if b - a > 0.05:
                res.append([round(c.start + (a - cin) / c.speed, 3), round(c.start + (b - cin) / c.speed, 3)])
        return res

    # -- media helpers -----------------------------------------------------------
    def allowed_src(self, src: str) -> Path:
        """Only sources the workspace knows about (indexed, or referenced by an EDL) are served."""
        media = self.ws.media()
        if src in media:
            return self.ws.abs(media[src]["path"])
        for p in self.edls():
            try:
                e = edlmod.load(p)
            except Exception:
                continue
            refs = {x.get("src") for k in ("clips", "audio", "images") for x in (e.get(k) or [])}
            if src in refs:
                return self.ws.resolve_src(src)[1]
        raise PermissionError(f"not a workspace source: {src}")

    def thumb(self, src: str, t: float, h: int) -> Path:
        path = self.allowed_src(src)
        mid, _ = self.ws.resolve_src(src)
        h = max(24, min(1080, h)) // 2 * 2
        grid = 4 if h < 360 else 100      # timeline thumbs: 0.25 s grid; viewer frames: 0.01 s
        t = round(max(0.0, t) * grid) / grid
        key = hashlib.sha1(f"{path}|{path.stat().st_mtime}|{t}|{h}".encode()).hexdigest()[:16]
        out = self.thumb_dir / f"{key}.jpg"
        if out.exists():
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{key}.{threading.get_ident()}.tmp.jpg")
        if path.suffix.lower() in ff.IMAGE_EXT:
            im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            im.thumbnail((h * 4, h))
            im.save(tmp, quality=82)
        else:
            src_file = path
            if h <= 360 and mid and self.ws.proxy_path(mid).exists():
                src_file = self.ws.proxy_path(mid)
            dur = float(self.ws.info_for(src).get("duration") or 0)
            if dur:
                t = min(t, max(0.0, dur - 0.05))
            ff.ffmpeg(["-ss", f"{t:.3f}", "-i", src_file, "-frames:v", "1",
                       "-vf", f"scale=-2:{h}", "-q:v", "4", tmp])
        tmp.replace(out)
        return out

    def peaks(self, src: str) -> Path:
        path = self.allowed_src(src)
        key = hashlib.sha1(f"{path}|{path.stat().st_mtime}".encode()).hexdigest()[:16]
        out = self.peaks_dir / f"{key}.json"
        with self._peaks_lock:
            if out.exists():
                return out
            rate = 2000
            proc = subprocess.run(
                [ff.require("ffmpeg"), "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
                 "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                capture_output=True)
            samples = array("h")
            samples.frombytes(proc.stdout[: len(proc.stdout) // 2 * 2])
            if sys.byteorder == "big":
                samples.byteswap()
            step = rate // PEAKS_PER_SEC
            vals = []
            for i in range(0, len(samples), step):
                sl = samples[i:i + step]
                vals.append(min(255, max(max(sl), -min(sl)) * 255 // 32767) if sl else 0)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"rate": PEAKS_PER_SEC, "peaks": vals}, separators=(",", ":")))
        return out


class Actions:
    """Import, timeline edits and export, mixed into App."""

    # -- media library -----------------------------------------------------------
    def media_usage(self: App) -> dict[str, list[str]]:
        """media id -> EDL files that reference it (by id or by path)."""
        media = self.ws.media()
        by_path = {self.ws.abs(m["path"]).resolve(): mid for mid, m in media.items()}
        used: dict[str, list[str]] = {}
        for p in self.edls():
            try:
                e = edlmod.load(p)
            except Exception:
                continue
            for x in (x for k in ("clips", "audio", "images") for x in (e.get(k) or [])):
                src = x.get("src")
                if not src:
                    continue
                mid = src if src in media else by_path.get(self.ws.abs(src).resolve())
                if mid and p.name not in used.setdefault(mid, []):
                    used[mid].append(p.name)
        return used

    def media_list(self: App) -> list[dict]:
        res, used = [], self.media_usage()
        for mid, m in self.ws.media().items():
            adir = self.ws.state / "analysis" / mid
            res.append({"id": mid, **{k: m.get(k) for k in ("type", "duration", "width", "height", "fps",
                                                             "has_audio", "path")},
                        "analyzed": adir.exists() and any(adir.iterdir()),
                        "transcript": (adir / "transcript.json").exists(),
                        "used_in": used.get(mid, []),
                        "in_workspace": self.ws.root in self.ws.abs(m["path"]).resolve().parents})
        return res

    def remove_media(self: App, mid: str, trash_file: bool) -> dict:
        """Drop a source from the library; optionally move its file to the Trash (workspace files only).

        Refuses while an EDL still uses it, so no edit is left pointing at a missing source.
        Files outside the workspace (imported "in place") are never touched."""
        import shutil

        with self._media_lock:
            media = self.ws.media()
            if mid not in media:
                raise LookupError(f"unknown media '{mid}'")
            used = self.media_usage().get(mid)
            if used:
                raise ValueError(f"'{mid}' is still used in {', '.join(used)}: remove those clips first")
            path = self.ws.abs(media[mid]["path"]).resolve()
            trashed = None
            if trash_file:
                if self.ws.root not in path.parents:
                    raise PermissionError("only files inside the workspace can be moved to the Trash")
                if path.exists():
                    trash = Path.home() / ".Trash" if sys.platform == "darwin" else self.ws.state / "trash"
                    trash.mkdir(parents=True, exist_ok=True)
                    dest, n = trash / path.name, 2
                    while dest.exists():
                        dest, n = trash / f"{path.stem} {n}{path.suffix}", n + 1
                    shutil.move(str(path), str(dest))
                    trashed = str(dest)
            del media[mid]
            self.ws.save_media(media)
            for d in (self.ws.state / "analysis" / mid,):
                shutil.rmtree(d, ignore_errors=True)   # derived data only; re-created by ingest
            self.ws.proxy_path(mid).unlink(missing_ok=True)
        return {"removed": mid, "trashed": trashed}

    def upload_target(self: App, filename: str) -> Path:
        name = re.sub(r"[^\w.\- ]+", "_", Path(filename).name).strip(" .") or "media"
        ext = Path(name).suffix.lower()
        if ext not in MEDIA_EXT:
            raise ValueError(f"unsupported file type: {ext or name}")
        folder = self.ws.root / ("audio" if ext in ff.AUDIO_EXT else "footage")
        folder.mkdir(exist_ok=True)
        dest, n = folder / name, 2
        while dest.exists():
            dest, n = folder / f"{Path(name).stem}-{n}{ext}", n + 1
        return dest

    def ingest(self: App, paths: list[Path], language: str | None, report) -> dict:
        """Index + analyze (+ transcribe when language is not None; "" = auto-detect)."""
        from . import analyze, transcribe

        if language == "auto":
            language = ""
        files = collect_media(paths)
        if not files:
            raise SystemExit("no media files found")
        done = []
        for k, f in enumerate(files):
            with self._media_lock:
                media = self.ws.media()
                mid = self.ws.media_id_for(f, media)
                info = ff.probe(f)
                info["path"] = self.ws.rel(f)
                media[mid] = info
                self.ws.save_media(media)
            report(k / len(files), f"{mid}: analyzing")
            if info["type"] in ("video", "audio", "image"):
                analyze.ingest_one(self.ws, mid, info)
            if language is not None and info.get("has_audio") and info["type"] in ("video", "audio"):
                report((k + 0.5) / len(files), f"{mid}: transcribing")
                transcribe.transcribe(self.ws, mid, language=language or None)
            done.append(mid)
        return {"media": done}

    # -- timeline edits ----------------------------------------------------------
    def edit_edl(self: App, name: str | None, fn) -> Path:
        with self._edl_lock:
            try:
                p = self.edl_path(name)
            except LookupError:
                if name:
                    raise
                p = self.ws.root / "edits" / "main.edl.json"
            edl = edlmod.load(p) if p.exists() else {"output": {}, "clips": []}
            fn(edl)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(json.dumps(edl, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(p)
            return p

    def append(self: App, body: dict) -> dict:
        src = body["src"]
        mid, path = self.ws.resolve_src(src)
        if not path.exists():
            raise LookupError(f"source not found: {src}")
        ref = mid or src
        info = self.ws.info_for(ref)
        r3 = lambda x: round(float(x), 3)
        as_ = body.get("as", "clip")
        if as_ == "audio":
            entry = {"src": ref, "at": r3(body.get("at", 0))}
        elif info.get("type") == "image":
            entry = {"src": ref, "duration": r3(body.get("duration", 3))}
        else:
            entry = {"src": ref}
        if info.get("type") in ("video", "audio"):
            if body.get("in") is not None and float(body["in"]) > 0:
                entry["in"] = r3(body["in"])
            if body.get("out") is not None and float(body["out"]) < float(info.get("duration") or 0) - 0.01:
                entry["out"] = r3(body["out"])
        if as_ == "audio" and body.get("volume") is not None:
            entry["volume"] = float(body["volume"])
        if as_ == "audio" and body.get("loop"):
            entry["loop"] = True

        def apply(edl):
            edl.setdefault("audio" if as_ == "audio" else "clips", []).append(entry)
            if body.get("preset") and not edl.get("output", {}).get("preset"):
                edl.setdefault("output", {})["preset"] = body["preset"]

        p = self.edit_edl(body.get("edl"), apply)
        return {"edl": p.name, "entry": entry}

    # -- export --------------------------------------------------------------------
    def render_with_progress(self: App, plan, out: Path, rng, report, *, preview: bool = False) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        workdir = self.ws.state / "render" / out.stem
        workdir.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.stem + ".part" + out.suffix)
        cmd, _ = rendermod.build_command(self.ws, plan, tmp, workdir, preview=preview, range_=rng)
        cmd = [str(c) for c in cmd]
        cmd[1:1] = ["-progress", "pipe:1"]
        total = (rng[1] - rng[0]) if rng else plan.duration
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        err: list[str] = []
        drain = threading.Thread(target=lambda: err.extend(proc.stderr), daemon=True)
        drain.start()
        for line in proc.stdout:
            if line.startswith("out_time_us="):
                try:
                    v = int(line.split("=", 1)[1]) / 1e6
                except ValueError:
                    continue
                if total > 0:
                    report(min(0.99, max(0.0, v / total)))
        proc.wait()
        drain.join(timeout=5)
        if proc.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise SystemExit("ffmpeg failed:\n" + "".join(err[-15:]))
        tmp.replace(out)

    def export(self: App, body: dict) -> str:
        p = self.edl_path(body.get("edl"))
        name = edl_name(p)
        kind = body.get("kind", "video")
        fmt = body.get("format") or "edl"
        rng = None
        if body.get("range"):
            a, b = (float(x) for x in body["range"])
            if b <= a:
                raise ValueError("range end must be after its start")
            rng = (a, b)
        tag = f"-{int(rng[0])}-{int(rng[1])}s" if rng else ""

        def load_plan(edl):
            plan = edlmod.plan(self.ws, edl)
            if plan.errors:
                raise SystemExit("EDL has errors:\n" + "\n".join(plan.errors))
            return plan

        if kind == "video":
            def run(report):
                edl = copy.deepcopy(edlmod.load(p))
                o = edl.setdefault("output", {})
                if fmt != "edl":
                    if fmt not in edlmod.PRESETS:
                        raise ValueError(f"unknown format {fmt}")
                    for k in ("width", "height", "preset"):
                        o.pop(k, None)
                    o["preset"] = fmt
                o["crf"], o["encoder_preset"] = QUALITY.get(body.get("quality", "standard"), QUALITY["standard"])
                out = self.ws.root / "renders" / f"{name}{'' if fmt == 'edl' else '-' + fmt}{tag}.mp4"
                self.render_with_progress(load_plan(edl), out, rng, report)
                return {"path": self.ws.rel(out), "size": out.stat().st_size}
            label = f"{name}.mp4" + (f" ({fmt})" if fmt != "edl" else "")
        elif kind == "audio":
            afmt = body.get("audio_format", "mp3")
            if afmt not in AUDIO_CODECS:
                raise ValueError(f"unknown audio format {afmt}")

            def run(report):
                plan = load_plan(edlmod.load(p))
                mix = self.ws.state / "render" / f"{name}-audio-mix.mp4"
                self.render_with_progress(plan, mix, rng, lambda v=None, m=None: report(None if v is None else v * 0.95),
                                          preview=True)
                out = self.ws.root / "renders" / f"{name}{tag}.{afmt}"
                ff.ffmpeg(["-i", mix, "-vn", *AUDIO_CODECS[afmt], out])
                mix.unlink(missing_ok=True)
                return {"path": self.ws.rel(out), "size": out.stat().st_size}
            label = f"{name}.{afmt}"
        elif kind == "frame":
            # one exact frame with every effect (crop, grade, text, captions): render a sliver, keep frame 1
            t = float(body.get("t", 0))

            def run(report):
                plan = load_plan(edlmod.load(p))
                a = max(0.0, min(t, plan.duration - 0.05))
                clip = self.ws.state / "render" / f"{name}-frame.mp4"
                self.render_with_progress(plan, clip, (a, min(plan.duration, a + 0.2)), report)
                out = self.ws.root / "renders" / f"{name}-frame-{a:.2f}s.png"
                ff.ffmpeg(["-i", clip, "-frames:v", "1", out])
                clip.unlink(missing_ok=True)
                return {"path": self.ws.rel(out), "size": out.stat().st_size}
            label = f"{name} frame {t:.2f}s.png"
        elif kind == "srt":
            def run(report):
                plan = load_plan(edlmod.load(p))
                chunks, missing = captionsmod.build_chunks(self.ws, plan)
                if not chunks:
                    raise SystemExit("no captions: transcribe the clips first"
                                     + (f" (missing: {', '.join(missing)})" if missing else ""))
                out = self.ws.root / "renders" / f"{name}.srt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(captionsmod.to_srt(chunks))
                return {"path": self.ws.rel(out), "size": out.stat().st_size}
            label = f"{name}.srt"
        else:
            raise ValueError(f"unknown export kind {kind}")
        return self.jobs.add("export", label, run)

    def render_file(self: App, rel: str) -> Path:
        f = (self.ws.root / rel).resolve()
        renders = (self.ws.root / "renders").resolve()
        if renders not in f.parents or not f.is_file():
            raise PermissionError("only files in renders/ can be downloaded")
        return f


for _name, _fn in vars(Actions).items():
    if callable(_fn) and not _name.startswith("__"):
        setattr(App, _name, _fn)


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "reelsmith-ui"

        def log_message(self, fmt, *args):  # quiet: only log failed requests
            if len(args) > 1 and str(args[1])[:1] in ("4", "5"):
                sys.stderr.write("ui: " + fmt % args + "\n")

        # -- responses ---------------------------------------------------------
        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: Path, ctype: str | None = None, cache: bool = False):
            size = path.stat().st_size
            ctype = ctype or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            start, end = 0, size - 1
            m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                else:  # suffix range: last N bytes
                    start = max(0, size - int(m.group(2)))
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            length = end - start + 1
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-cache")
            for k, v in getattr(self, "headers_extra", {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command == "HEAD":
                return
            with path.open("rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(256 * 1024, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        # -- routing -------------------------------------------------------------
        def do_HEAD(self):
            self.do_GET()

        def _local_host(self) -> bool:
            """Refuse DNS-rebinding: the Host header must name this machine."""
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host in LOCAL_HOSTS

        def _body_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if not self._local_host():
                return self._json({"error": "forbidden host"}, 403)
            try:
                if u.path in ("/", "/index.html"):
                    html = (STATIC / "index.html").read_text().replace("__REELSMITH_TOKEN__", app.token)
                    body = html.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    return self.wfile.write(body)
                if u.path.startswith("/static/"):
                    f = (STATIC / u.path[len("/static/"):]).resolve()
                    if STATIC.resolve() not in f.parents or not f.is_file():
                        return self._json({"error": "not found"}, 404)
                    return self._file(f)
                if u.path == "/api/media":
                    return self._json(app.media_list())
                if u.path == "/api/jobs":
                    return self._json(app.jobs.list())
                if u.path == "/media/source":
                    src = q["src"]
                    path = app.allowed_src(src)
                    mid, _ = app.ws.resolve_src(src)
                    if mid and app.ws.proxy_path(mid).exists():
                        path = app.ws.proxy_path(mid)
                    return self._file(path)
                if u.path == "/api/download":
                    f = app.render_file(q["path"])
                    self.headers_extra = {"Content-Disposition": f'attachment; filename="{f.name}"'}
                    return self._file(f)
                if u.path == "/api/edls":
                    return self._json([{"name": p.name, "path": app.ws.rel(p), "mtime": p.stat().st_mtime}
                                       for p in app.edls()])
                if u.path == "/api/timeline":
                    return self._json(app.timeline(app.edl_path(q.get("edl"))))
                if u.path == "/api/version":
                    return self._json(app.version(app.edl_path(q.get("edl"))))
                if u.path == "/api/thumb":
                    return self._file(app.thumb(q["src"], float(q.get("t", 0)), int(q.get("h", 72))),
                                      "image/jpeg", cache=True)
                if u.path == "/api/peaks":
                    return self._file(app.peaks(q["src"]), "application/json", cache=True)
                if u.path == "/media/preview":
                    p = app.preview_path(app.edl_path(q.get("edl")))
                    if not p.exists():
                        return self._json({"error": "no preview yet"}, 404)
                    return self._file(p, "video/mp4")
                return self._json({"error": "not found"}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except LookupError as e:
                self._json({"error": str(e)}, 404)
            except PermissionError as e:
                self._json({"error": str(e)}, 403)
            except (ff.FFError, ValueError) as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:
                traceback.print_exc()
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            # Writes need the per-run token embedded in the page, and must come from a local origin:
            # another website open in the browser cannot import, edit or export through this server.
            origin = self.headers.get("Origin")
            if (not self._local_host() or self.headers.get("X-Reelsmith-Token") != app.token
                    or (origin and urlparse(origin).hostname not in LOCAL_HOSTS)):
                return self._json({"error": "forbidden"}, 403)
            try:
                if u.path == "/api/render":
                    p = app.edl_path(q.get("edl"))
                    plan = edlmod.plan(app.ws, edlmod.load(p))
                    if plan.errors:
                        return self._json({"error": "EDL has errors", "errors": plan.errors}, 400)
                    app.renderer.start(p, app.preview_path(p))
                    return self._json(app.renderer.status(p))
                if u.path == "/api/import":
                    # raw file body (not multipart), streamed to disk; analysis runs as a job
                    dest = app.upload_target(q["name"])
                    left = int(self.headers.get("Content-Length") or 0)
                    part = dest.with_name(dest.name + ".part")
                    with part.open("wb") as f:
                        while left > 0:
                            chunk = self.rfile.read(min(1 << 20, left))
                            if not chunk:
                                break
                            f.write(chunk)
                            left -= len(chunk)
                    if left:
                        part.unlink(missing_ok=True)
                        return self._json({"error": "upload interrupted"}, 400)
                    part.replace(dest)
                    lang = q.get("transcribe")
                    jid = app.jobs.add("import", dest.name, lambda r: app.ingest([dest], lang, r))
                    return self._json({"job": jid, "path": app.ws.rel(dest)})
                if u.path == "/api/import-path":
                    b = self._body_json()
                    path = Path(b["path"]).expanduser()
                    if not path.exists():
                        return self._json({"error": f"not found: {path}"}, 404)
                    jid = app.jobs.add("import", path.name, lambda r: app.ingest([path], b.get("transcribe"), r))
                    return self._json({"job": jid})
                if u.path == "/api/edl/append":
                    return self._json(app.append(self._body_json()))
                if u.path == "/api/media/remove":
                    b = self._body_json()
                    return self._json(app.remove_media(b["id"], bool(b.get("trash_file"))))
                if u.path == "/api/edl/save":
                    # whole-document save from the page's editor; refuses if the file changed meanwhile
                    b = self._body_json()
                    p = app.edl_path(b.get("edl"))
                    doc = b.get("doc")
                    if not isinstance(doc, dict) or not isinstance(doc.get("clips", []), list):
                        raise ValueError("invalid EDL document")
                    with app._edl_lock:
                        cur = p.stat().st_mtime
                        if b.get("base_mtime") is not None and abs(cur - float(b["base_mtime"])) > 1e-6:
                            return self._json({"error": "conflict", "edl_mtime": cur}, 409)
                        tmp = p.with_name(p.name + ".tmp")
                        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
                        tmp.replace(p)
                    return self._json({"edl_mtime": p.stat().st_mtime})
                if u.path == "/api/export":
                    return self._json({"job": app.export(self._body_json())})
                if u.path == "/api/reveal":
                    b = self._body_json()
                    f = app.allowed_src(b["id"]) if b.get("id") else app.render_file(b["path"])
                    if sys.platform == "darwin":
                        subprocess.run(["open", "-R", str(f)])
                    else:
                        subprocess.run(["xdg-open", str(f.parent)])
                    return self._json({"ok": True})
                return self._json({"error": "not found"}, 404)
            except LookupError as e:
                self._json({"error": str(e)}, 404)
            except PermissionError as e:
                self._json({"error": str(e)}, 403)
            except (ValueError, ff.FFError, json.JSONDecodeError) as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:
                traceback.print_exc()
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    return Handler


def serve(ws: Workspace, edl_path: Path | None, *, port: int = 8765, host: str = "127.0.0.1",
          open_browser: bool = True, auto_render: bool = True) -> None:
    app = App(ws, edl_path, auto_render)
    handler = make_handler(app)
    httpd = None
    for p in range(port, port + 20):
        try:
            httpd = ThreadingHTTPServer((host, p), handler)
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit(f"no free port in {port}-{port + 19}")
    httpd.daemon_threads = True
    url = f"http://localhost:{httpd.server_address[1]}/"
    if edl_path:
        url += f"?edl={edl_path.name}"
    print(json.dumps({"url": url, "workspace": str(ws.root), "auto_render": auto_render},
                     ensure_ascii=False), flush=True)
    print("Ctrl+C to stop", file=sys.stderr, flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
