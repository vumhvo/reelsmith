# Reelsmith

**English** | [Tiếng Việt](README.vi.md)

A video editing toolkit for Claude Code. **Edit any video just by talking to Claude**: vlogs, travel, interviews, talking heads, TikTok/Reels/Shorts, YouTube, photo slideshows, highlight reels, and more.

Claude can't watch video, so this repo gives it:

- **Eyes**: `cstudio ingest` turns footage into things Claude can read: contact sheets (frame grids with timestamps), scene cuts, loudness, silences, and word-level transcripts.
- **Hands**: the whole edit is **one JSON file (EDL)**. Claude writes and edits the EDL; `cstudio render` compiles it into a single ffmpeg command.
- **A check step**: `cstudio review` measures loudness, black frames and silences, and makes a contact sheet of the render so Claude can catch its own mistakes.
- **An editor in the browser**: `cstudio ui` opens the workspace on localhost. Import video, audio and images (drag and drop, or use files in place), browse or remove them in a media library (unused files only; workspace copies can go to the Trash), mark in/out points and add them to the timeline, watch the timeline (thumbnails, waveforms, frame-by-frame stepping), edit on the timeline (drag edges to trim frame by frame, drag to reorder, split at the playhead, delete, undo/redo), change any clip, text, image or audio property in the inspector (in/out, speed, crop with an aspect-locked crop box, fit, zoom, focus, color, fades, transitions, volume, text style and position) with an instant live view, use right-click menus on media, clips and the viewer (split here, duplicate, mute, crop, show in Finder, save the current frame as PNG…), and export video (9:16, 16:9, 1:1, 4:5, 4K), audio (MP3/M4A/WAV) or captions (.srt). It redraws within a second whenever Claude edits the EDL and re-renders the preview in the background. Plain HTML/CSS/JS served by Python's standard library: no Node, no npm.
- **Skills**: the skills in `skills/` teach Claude an editor's workflow.

## Install

Requirements: `ffmpeg` and `uv` (macOS: `brew install ffmpeg uv`).

```bash
git clone https://github.com/vumhvo/reelsmith.git && cd reelsmith && ./scripts/install.sh
```

This installs the `cstudio` command (editable, so code changes apply immediately) and prints how to add the skills to Claude Code.

Add the skills as a plugin (inside Claude Code):

```
/plugin marketplace add vumhvo/reelsmith
/plugin install reelsmith@reelsmith
```

## Usage

Open Claude Code in **any folder** with your videos and describe what you want, for example:

> Cut these 4 clips into a 30-second TikTok with `song.mp3` as music, Vietnamese captions, and the best shot first.

Claude follows the `video-studio` skill: `init` → `ingest` → read contact sheets and transcripts → propose a plan → write `edits/main.edl.json` → preview render → review → final render.

You can also run it by hand:

```bash
cstudio init                     # turn the current folder into a workspace
cstudio ingest footage/ music/   # analyze (add --transcribe --lang en for transcripts)
cstudio media                    # list media ids
cstudio sheet <id> --start 10 --end 20   # zoom in on a section
cstudio roto <id> --start 12 --end 15 --pos 0.5,0.4   # track a person (SAM 2) -> masks for EDL effects
cstudio validate edits/main.edl.json
cstudio ui edits/main.edl.json               # timeline in the browser (http://localhost:8765)
cstudio render edits/main.edl.json --preview
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json
cstudio render edits/main.edl.json
```

## What the EDL can do

Cuts and joins, speed changes, ~35 transition types (xfade), reframing between 16:9 and 9:16 (cover with a focus point, contain, blur), static zoom and Ken Burns, color grading (eq/LUT), fades, still images, color title cards, text and titles, logos, automatic karaoke-style captions (from transcripts, re-timed through every cut), background music with ducking under speech, voice-over, and loudness normalization (−14 LUFS). For anything the EDL doesn't cover, use per-clip raw ffmpeg filters (`vf`/`af`) or the `ffmpeg-recipes` skill.

Full schema: [skills/edl/reference.md](skills/edl/reference.md).

## Skills

| Skill | Purpose |
|---|---|
| `video-studio` | The end-to-end editing workflow (entry point) |
| `edl` | EDL schema, patterns and examples |
| `captions` | Transcription, subtitles, caption styling, SRT export |
| `rough-cut` | Speech-led edits: interviews, podcasts, talking heads |
| `short-form` | TikTok/Reels/Shorts: hooks, pacing, safe zones, beat sync |
| `rotoscoping` | Track people/objects with SAM 2 (local): background removal/replacement/blur, colour pop, outline, text behind the subject, censoring, alpha cutouts |
| `ffmpeg-recipes` | One-off operations outside the EDL |

## Layout

```
src/studio/        the `cstudio` CLI (Python; depends only on ffmpeg + Pillow)
skills/            Claude skills (packaged as a plugin via .claude-plugin/)
examples/          sample EDLs
scripts/install.sh
```

A user workspace (created by `cstudio init`) is separate from this repo:

```
<your video folder>/
  studio.json  .studio/(media.json, analysis/, proxy/)  edits/*.edl.json  renders/
```

## Notes

- Homebrew's ffmpeg has no `drawtext`/`libass`, so text and captions are drawn with Pillow and overlaid. Nothing extra to install.
- Transcription uses `mlx-whisper` (run through `uvx`; the first run downloads a ~1.6 GB model). Default fonts cover Vietnamese diacritics.
- HDR footage (HLG/PQ) is not tone-mapped yet; `cstudio media` flags it as `hdr`.

## License

[MIT](LICENSE)
