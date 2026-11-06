---
name: video-studio
description: Edit any video the user asks for (vlog, travel, interview, talking head, tutorial, TikTok/Reels/Shorts, YouTube, photo slideshow, highlight reel, ad) with the `cstudio` toolkit. Use whenever the user wants to cut, trim, merge, reframe, caption, add music or titles to, speed up, or otherwise edit video or turn photos/clips into a video. Covers the end-to-end workflow; other reelsmith skills cover details.
---

# Video Studio: the editing workflow

You edit video by **looking** (analysis files and contact sheets), **deciding** (writing a JSON edit decision list) and **rendering** (ffmpeg via `cstudio`). You cannot watch video, so never guess what a clip contains: open its contact sheet or transcript first.

## 0. Setup check

```bash
command -v cstudio || bash "<this skill's base directory>/../../scripts/install.sh"
```
`cstudio` needs `ffmpeg` and `uv`. Run every command from inside the workspace (a folder with `studio.json`).

## 1. Workspace + ingest

```bash
cstudio init                      # in the user's video folder (or: cstudio init ~/Videos/my-edit)
cstudio ingest <files/folders>    # default: the whole workspace
cstudio media                     # ids, durations, sizes, audio, T = has transcript
```
Add `--transcribe --lang vi` (or `en`, ...) when speech matters (interviews, vlogs, tutorials, captions). Add `--proxy` for long 4K footage so previews are fast. Sources may live outside the workspace; they are referenced by path, never copied or modified.

Per source, `.studio/analysis/<id>/` holds:
- `sheet_N.jpg`: contact sheets with timestamps. **Read these images** to see the footage.
- `scenes.json`: cut/large-motion points. `audio.json`: loudness and silences.
- `transcript.txt` / `transcript.json`: speech with segment and word timestamps.

To look closer at a moment: `cstudio sheet <id> --start 12 --end 18 --count 12` or `cstudio frame <id> 14.2`.

## 2. Understand the brief, then propose a plan

Ask only what you can't infer: target platform/aspect (→ `output.preset`), target length, mood/music, captions language, must-have moments. Then summarise the footage you saw and propose a short shot list (which clips, in what order, roughly how long, text/music). For anything beyond a trivial edit, get a quick OK before rendering the full thing.

## 3. Write the EDL

Write `edits/<name>.edl.json`. Load the `edl` skill for the schema (it has a full reference). Key rule: clip `in`/`out` are **source** seconds; `text`/`audio`/caption times are **timeline** seconds. Then:

```bash
cstudio validate edits/main.edl.json   # errors, warnings, and the timeline table with each clip's start/end
```
Use the timeline table to place titles and music cues.

## 4. Preview → review → iterate

```bash
cstudio render edits/main.edl.json --preview          # half-res, fast
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json
```
`review` reports loudness, unexpected black frames, long silences, duration mismatch, and writes `<name>_review.jpg`: **read that sheet** and check framing, text legibility and placement (nothing covered by platform UI), and pacing. Fix the EDL and re-render. Use `--range 10:20` to re-render only a section while tweaking.

## 5. Final

```bash
cstudio render edits/main.edl.json      # → renders/main.mp4
```
Report the output path, duration, resolution, and anything you could not do. Keep the EDL: the user can ask for changes later and you only edit JSON.

## Rules

- Never modify or delete source media. Outputs go to `renders/`.
- Prefer multiple EDLs (`main`, `v2-short`, `teaser`) over overwriting one the user liked.
- If a request is beyond the EDL (stabilization, denoise, chroma key, reverse, GIF export, ...), use per-clip `vf`/`af` raw filters or the `ffmpeg-recipes` skill on an intermediate file, then reference that file in the EDL.
- Motion graphics beyond text/images (animated charts, complex templates) can be built in Remotion if the user has a Remotion project; render it to an .mp4/.mov and use it as a clip.
- HDR sources (`hdr` in `cstudio media`) are not tone-mapped; warn the user if colors look washed out.

## Other reelsmith skills
- `edl`: full EDL schema, patterns, examples.
- `captions`: transcription, caption styles, fixing words, SRT export.
- `rough-cut`: speech-led edits (interviews, podcasts, vlogs): select quotes, remove silences/fillers.
- `short-form`: TikTok/Reels/Shorts craft: hook, pacing, reframing, safe zones.
- `ffmpeg-recipes`: one-off operations outside the EDL.
