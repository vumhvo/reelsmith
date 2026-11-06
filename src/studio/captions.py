"""Captions that follow the edit.

Transcripts are made once per SOURCE file. When the EDL cuts, reorders or speeds up
clips, words are remapped onto the timeline here, so captions never drift.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import transcribe

CAPTION_DEFAULTS = {
    "max_words": None,      # auto: 3 for vertical, 7 for horizontal
    "max_chars": None,      # auto: 22 for vertical, 42 for horizontal
    "gap": 0.6,             # a pause longer than this starts a new caption
    "linger": 0.25,         # keep a caption up this long after its last word
    "karaoke": True,        # highlight the active word (needs word timestamps)
    "replace": {},          # {"wrong": "right"} word fixes, case-insensitive
    "file": None,           # use an .srt or captions .json (timeline times) instead of transcripts
}

STYLE_VERTICAL = {
    "y": 0.70, "size": 0.075, "font": None, "color": "#FFFFFF", "stroke": "#000000",
    "stroke_width": 0.11, "highlight_color": "#FFD400", "max_width": 0.84, "shadow": "#00000080",
}
STYLE_HORIZONTAL = {
    "y": 0.86, "size": 0.055, "font": None, "color": "#FFFFFF", "stroke": "#000000",
    "stroke_width": 0.09, "highlight_color": "#FFD400", "max_width": 0.8, "shadow": "#00000080",
}

_PUNCT = re.compile(r"^([\W_]*)(.*?)([\W_]*)$", re.UNICODE)


def _fix(word: str, table: dict) -> str:
    if not table:
        return word
    m = _PUNCT.match(word)
    pre, core, post = m.groups() if m else ("", word, "")
    rep = table.get(core.lower())
    return f"{pre}{rep}{post}" if rep is not None else word


def timeline_words(ws, plan) -> tuple[list[dict], list[str]]:
    cfg = {**CAPTION_DEFAULTS, **(plan.edl.get("captions") or {})}
    table = {k.lower(): v for k, v in (cfg.get("replace") or {}).items()}
    words, missing = [], []
    clips = plan.clips
    for n, c in enumerate(clips):
        if c.kind != "video" or c.clip.get("mute") or c.clip.get("captions") is False:
            continue
        if not c.info.get("has_audio"):
            continue
        tr = transcribe.load(ws, c.media_id) if c.media_id else None
        if not tr:
            missing.append(c.clip.get("src"))
            continue
        cin = c.src_in
        cout = cin + c.duration * c.speed
        nxt = clips[n + 1].transition if n + 1 < len(clips) else 0.0
        lo, hi = c.start + c.transition / 2, c.end - nxt / 2
        for w in tr["words"]:
            if w["end"] <= cin or w["start"] >= cout:
                continue
            ts = c.start + (max(w["start"], cin) - cin) / c.speed
            te = c.start + (min(w["end"], cout) - cin) / c.speed
            ts, te = max(ts, lo), min(te, hi)
            if te - ts < 0.02:
                continue
            words.append({"w": _fix(w["w"], table), "start": round(ts, 3), "end": round(te, 3), "clip": c.index})
    words.sort(key=lambda w: w["start"])
    return words, sorted(set(m for m in missing if m))


def chunk(words: list[dict], *, max_words: int, max_chars: int, gap: float, linger: float, total: float) -> list[dict]:
    chunks, cur = [], []
    for w in words:
        if cur:
            text_len = len(" ".join(x["w"] for x in cur + [w]))
            if (len(cur) >= max_words or text_len > max_chars or w["start"] - cur[-1]["end"] > gap
                    or w["clip"] != cur[-1]["clip"]):
                chunks.append(cur)
                cur = []
        cur.append(w)
        if w["w"][-1:] in ".?!…。":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, ws_ in enumerate(chunks):
        start = ws_[0]["start"]
        end = ws_[-1]["end"] + linger
        if i + 1 < len(chunks):
            end = min(end, chunks[i + 1][0]["start"])
        end = min(max(end, start + 0.4), total)
        out.append({"start": round(start, 3), "end": round(end, 3),
                    "text": " ".join(x["w"] for x in ws_), "words": ws_})
    return out


def _parse_srt(text: str) -> list[dict]:
    def t(s):
        h, m, rest = s.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest)
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        for k, l in enumerate(lines):
            if "-->" in l:
                a, b = [x.strip().split(" ")[0] for x in l.split("-->")]
                out.append({"start": t(a), "end": t(b), "text": "\n".join(lines[k + 1:])})
                break
    return out


def build_chunks(ws, plan) -> tuple[list[dict], list[str]]:
    cfg = {**CAPTION_DEFAULTS, **(plan.edl.get("captions") or {})}
    if cfg.get("file"):
        f = ws.abs(cfg["file"])
        if f.suffix.lower() == ".srt":
            return _parse_srt(f.read_text()), []
        return json.loads(f.read_text()), []
    vertical = plan.output["height"] > plan.output["width"]
    words, missing = timeline_words(ws, plan)
    chunks = chunk(
        words,
        max_words=cfg["max_words"] or (3 if vertical else 7),
        max_chars=cfg["max_chars"] or (22 if vertical else 42),
        gap=cfg["gap"], linger=cfg["linger"], total=plan.duration,
    )
    return chunks, missing


def overlay_items(ws, plan) -> tuple[list[dict], list[str]]:
    cfg = {**CAPTION_DEFAULTS, **(plan.edl.get("captions") or {})}
    vertical = plan.output["height"] > plan.output["width"]
    style = {**(STYLE_VERTICAL if vertical else STYLE_HORIZONTAL), **(cfg.get("style") or {})}
    if not cfg.get("karaoke"):
        style["highlight_color"] = None
        style["highlight_box"] = None
    chunks, missing = build_chunks(ws, plan)
    items = []
    for ch in chunks:
        ws_ = ch.get("words")
        if ws_ and (style.get("highlight_color") or style.get("highlight_box")):
            for k, w in enumerate(ws_):
                a = ch["start"] if k == 0 else w["start"]
                b = ws_[k + 1]["start"] if k + 1 < len(ws_) else ch["end"]
                if b > a:
                    items.append({**style, "text": ch["text"], "start": a, "end": b, "highlight_index": k})
        else:
            items.append({**style, "text": ch["text"], "start": ch["start"], "end": ch["end"]})
    return items, missing


def to_srt(chunks: list[dict]) -> str:
    def ts(t):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return "\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n"
                     for i, c in enumerate(chunks, 1))


def write_json(chunks: list[dict], path: Path) -> None:
    path.write_text(json.dumps(chunks, indent=1, ensure_ascii=False) + "\n")
