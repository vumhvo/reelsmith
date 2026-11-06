"""Speech-to-text with word timestamps.

Default engine: mlx-whisper (fast on Apple Silicon), run through `uvx` so it is not a hard dependency.
Output: .studio/analysis/<id>/transcript.json  (normalized) + transcript.txt (for reading).

transcript.json:
  {"language": "vi", "model": "...",
   "segments": [{"start": 0.0, "end": 2.1, "text": "..."}],
   "words":    [{"w": "xin", "start": 0.12, "end": 0.40}]}
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from . import ff
from .analyze import fmt_time

DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


def _run_mlx(src: Path, outdir: Path, model: str, language: str | None, prompt: str | None) -> dict:
    if shutil.which("mlx_whisper"):
        base = ["mlx_whisper"]
    elif shutil.which("uvx"):
        base = ["uvx", "--from", "mlx-whisper", "mlx_whisper"]
    else:
        raise ff.FFError("mlx-whisper not available: install uv (brew install uv) or `pip install mlx-whisper`")
    args = [*base, str(src), "--model", model, "--word-timestamps", "True",
            "-f", "json", "-o", str(outdir), "--output-name", "raw", "--verbose", "False",
            # reduce Whisper's classic failure: repeated invented sentences over music/wind/silence
            "--condition-on-previous-text", "False", "--hallucination-silence-threshold", "2"]
    if language:
        args += ["--language", language]
    if prompt:
        args += ["--initial-prompt", prompt]
    print(f"transcribing {src.name} with {model} (first run downloads the model)...", file=sys.stderr)
    ff.run(args)
    return json.loads((outdir / "raw.json").read_text())


def normalize(raw: dict, model: str) -> dict:
    segs, words = [], []
    for s in raw.get("segments", []):
        text = s.get("text", "").strip()
        if not text:
            continue
        segs.append({"start": round(s["start"], 3), "end": round(s["end"], 3), "text": text})
        for w in s.get("words", []) or []:
            token = w.get("word", "").strip()
            if token:
                words.append({"w": token, "start": round(w["start"], 3), "end": round(w["end"], 3)})
    return {"language": raw.get("language"), "model": model, "segments": segs, "words": words}


def transcribe(ws, mid: str, *, model: str = DEFAULT_MODEL, language: str | None = None,
               prompt: str | None = None) -> dict:
    media = ws.media()
    info = media[mid]
    if not info.get("has_audio"):
        raise SystemExit(f"{mid} has no audio track")
    src = ws.abs(info["path"])
    adir = ws.analysis_dir(mid)
    with tempfile.TemporaryDirectory() as td:
        # Extract mono 16 kHz audio first: faster and avoids container quirks.
        wav = Path(td) / "audio.wav"
        ff.ffmpeg(["-i", src, "-vn", "-ac", "1", "-ar", "16000", wav])
        raw = _run_mlx(wav, Path(td), model, language, prompt)
    tr = normalize(raw, model)
    (adir / "transcript.json").write_text(json.dumps(tr, indent=1, ensure_ascii=False) + "\n")
    (adir / "transcript.txt").write_text(as_text(tr, mid))
    return tr


def as_text(tr: dict, label: str = "") -> str:
    lines = [f"# transcript {label} (language={tr.get('language')})", ""]
    for s in tr["segments"]:
        lines.append(f"[{s['start']:7.2f} - {s['end']:7.2f}]  ({fmt_time(s['start'])})  {s['text']}")
    return "\n".join(lines) + "\n"


def load(ws, mid: str) -> dict | None:
    f = ws.state / "analysis" / mid / "transcript.json"
    return json.loads(f.read_text()) if f.exists() else None
