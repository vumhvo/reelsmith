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

from PIL import Image, ImageOps

from . import captions as captionsmod, edl as edlmod, ff, render as rendermod
from .workspace import Workspace

STATIC = Path(__file__).parent / "ui_static"
PEAKS_PER_SEC = 50


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
            "errors": plan.errors,
            "warnings": list(plan.warnings),
            "clips": [], "audio": [], "text": [], "images": [], "captions": [],
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

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path in ("/", "/index.html"):
                    return self._file(STATIC / "index.html", "text/html; charset=utf-8")
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
            try:
                if u.path == "/api/render":
                    p = app.edl_path(q.get("edl"))
                    plan = edlmod.plan(app.ws, edlmod.load(p))
                    if plan.errors:
                        return self._json({"error": "EDL has errors", "errors": plan.errors}, 400)
                    app.renderer.start(p, app.preview_path(p))
                    return self._json(app.renderer.status(p))
                return self._json({"error": "not found"}, 404)
            except LookupError as e:
                self._json({"error": str(e)}, 404)
            except Exception as e:
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
