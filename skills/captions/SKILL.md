---
name: captions
description: Transcribe speech and add subtitles/captions to a video with reelsmith: word-level karaoke captions, Vietnamese and other languages, fixing misheard words, caption styling, SRT export for YouTube. Use when the user asks for subtitles, captions, phụ đề, a transcript, or text that follows what is said.
---

# Captions

## 1. Transcribe the sources (once per file, cached)

```bash
cstudio transcribe --lang vi                 # all media with audio; or list ids
cstudio transcribe clip-a --lang en --prompt "Claude, Anthropic, Đà Lạt"   # spelling hints
```
- Always pass `--lang` when you know the language. Auto-detect on short or noisy clips is unreliable.
- Default model `mlx-community/whisper-large-v3-turbo` (first run downloads ~1.6 GB). For quick drafts: `--model mlx-community/whisper-small-mlx`.
- Read `.studio/analysis/<id>/transcript.txt` to check it.

**Whisper hallucinates on non-speech** (wind, music, silence): it invents short, repeated, generic sentences ("Thank you for watching", the same line again and again). If a clip has no real speech, set `"captions": false` on that clip or skip captions. Compare against `audio.json` silences and the contact sheet (is anyone talking?).

## 2. Turn them on in the EDL

```json
"captions": {
  "replace": { "da lat": "Đà Lạt", "claude code": "Claude Code" },
  "style": { "y": 0.72, "size": 0.075, "highlight_color": "#FFD400" }
}
```
Captions follow the edit automatically: cuts, reordering, speed changes and transitions are all accounted for. Check them with:

```bash
cstudio captions edits/main.edl.json --show 40     # prints timeline captions, writes renders/main.srt
```

## 3. Fixing text

- Single words consistently wrong → `replace`.
- Many fixes or rephrasing → export editable JSON, edit the `text` (and `words[].w` if karaoke), then point the EDL at it:
  ```bash
  cstudio captions edits/main.edl.json --json edits/main.captions.json
  ```
  `"captions": { "file": "edits/main.captions.json" }`. Note: this file is in timeline time, so re-export after changing the cut.
- Have an existing `.srt` (timeline-timed)? `"captions": { "file": "subs.srt" }`.

## Style guide

- Vertical (TikTok/Reels/Shorts): 2–4 words per caption, big (size 0.07–0.09), y ≈ 0.65–0.75 (above the caption/UI area, below faces), active-word highlight. `case: "upper"` for energy.
- Horizontal (YouTube): 1 line, 5–8 words, size ≈ 0.05, y ≈ 0.86; karaoke optional (`"karaoke": false`).
- Keep a strong outline (`stroke_width` ≥ 0.08) or a `box` so text reads on any background.
- For YouTube/accessibility also deliver the `.srt` (sidecar subtitles) next to the video.
- Vietnamese: default fonts cover all diacritics. If you set a custom `font`, check a frame for missing glyphs (boxes instead of ơ ư ạ ế …).
