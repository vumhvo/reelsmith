---
name: edl
description: Schema and patterns for reelsmith edit decision lists (edits/*.edl.json): clips, transitions, speed, reframing/fit, zoom/Ken Burns, color grade, text titles, image overlays, captions, music and ducking, output presets. Use when writing or changing an EDL for `cstudio render`.
---

# Writing EDLs

An EDL is the entire edit as JSON. `cstudio validate` checks it and prints the timeline; `cstudio render` compiles it to one ffmpeg command (saved to `.studio/render/<name>/command.sh` for debugging).

**Read [reference.md](reference.md) for every field.** Minimal example:

```json
{
  "output": { "preset": "tiktok" },
  "clips": [
    { "src": "clip-a", "in": 3.2, "out": 7.0 },
    { "src": "clip-b", "in": 0, "out": 4.5, "transition": { "type": "fade", "duration": 0.4 } },
    { "src": "photos/sunset.jpg", "duration": 2.5, "zoom": { "from": 1.0, "to": 1.15 } }
  ],
  "audio": [ { "src": "music/song.mp3", "volume": 0.35, "fade_out": 2, "duck": true } ],
  "text": [ { "text": "Đà Lạt 2026", "start": 0.3, "end": 2.5, "y": 0.2, "size": 0.09 } ],
  "captions": { "style": { "y": 0.72 } }
}
```

## Mental model

- `clips` play back to back on one video track. A clip's `transition` overlaps it with the previous clip, which shortens the timeline by the transition duration. `cstudio validate` shows each clip's real start/end.
- Clip `in`/`out` = seconds in the **source**. `speed` 2 = twice as fast (audio pitch preserved).
- `text`, `images`, `audio[].at` and captions use **timeline** seconds.
- Positions are fractions of the frame (x 0 = left, y 0 = top). Sizes ≤ 1 are fractions of the frame's shorter side; values > 1 are pixels.
- `src` is a media id from `cstudio media` or a path (relative to the workspace or absolute).

## Patterns

- **Horizontal footage → vertical:** `fit: "cover"` (default) crops; set `focus: [x, y]` to keep the subject (e.g. `[0.3, 0.5]` when the person is left of center). Use `fit: "blur"` to show the whole frame over a blurred fill, or `"contain"` for bars.
- **Punch-in** on a talking head to hide a jump cut: alternate `zoom: 1.0` and `zoom: 1.12` on consecutive clips.
- **Photo slideshow:** image clips with `duration` 2–4 s and alternating `zoom: {from: 1, to: 1.12}` / `{from: 1.12, to: 1}`; `focus` sets where the zoom heads.
- **Title card:** `{ "color": "#101010", "duration": 2 }` plus a `text` item in that window.
- **Music under speech:** `duck: true` on the music track lowers it whenever the clips' own audio is active. B-roll with ugly wind noise: `mute: true` on that clip.
- **Cut on the beat:** get beat times (see `ffmpeg-recipes` or ask the user for BPM; beat = 60/BPM s) and make clip timeline boundaries land on them; verify with `cstudio validate`.
- **Fixes beyond the schema:** per-clip `vf` / `af` take raw ffmpeg filter chains (e.g. `"vf": "hflip"`, `"af": "highpass=f=120"`).

## Checklist before rendering
1. `cstudio validate` has no errors; total duration is what the user asked for.
2. Text sits inside safe zones (vertical: y between ~0.12 and ~0.78) and is on screen ≥ 1.2 s per short line.
3. Every `src` exists in `cstudio media` or as a path.
4. Preview first (`--preview`), then `cstudio review`.
