---
name: short-form
description: Craft short vertical videos (TikTok, Instagram Reels, YouTube Shorts, Facebook Reels) with reelsmith: hooks in the first seconds, fast pacing, reframing horizontal footage to 9:16, on-screen text in safe zones, captions, music and beat-synced cuts, photo carousels as video. Use when the target is a short social video.
---

# Short-form vertical video

## Defaults
- `"output": { "preset": "tiktok" }` (1080x1920, 30 fps, −14 LUFS). Length: 15–35 s unless the user says otherwise.
- Shots 0.8–2.5 s for montage; up to 4 s for a payoff shot. Talking content: cut every ~2–4 s (punch-ins).

## Structure
1. **Hook (0–2 s)**: the most striking shot or line *first*, plus a big text hook ("POV: …", "3 điều …", a question). No logos or slow intros.
2. **Build**: progression (journey, steps, before → after). Vary shot size and motion.
3. **Payoff (last 3–5 s)**: best view/result; optionally loop back visually to the first shot so replays feel seamless.

## Choosing shots
Read every contact sheet. Prefer moments with motion toward camera, faces/expressions, reveals, and clean light. Skip shaky starts and ends (first/last ~0.5 s of phone clips). Use `scenes.json` to find natural cut points inside long clips.

## Reframing to 9:16
- Vertical sources: `fit: "cover"` and done.
- Horizontal sources: `cover` with `focus` on the subject (check the frame: e.g. `[0.35, 0.5]`), `zoom` 1.0–1.2 for tighter framing; or `fit: "blur"` for wide scenery that must be seen whole.
- Verify with `cstudio frame renders/x-preview.mp4 <t>` that heads and key action stay in frame.

## Text and safe zones (1080x1920)
- Keep important text and faces between y ≈ 0.12 and y ≈ 0.78, x ≈ 0.06–0.86: the top has the platform header, the bottom ~22% has caption/username, the right edge has the like/share buttons.
- Hook text: size 0.08–0.1, y ≈ 0.2–0.3, `box` or strong stroke. Max ~6 words per line; on screen ≥ 1.5 s.
- Captions (`captions` skill): y ≈ 0.68–0.74.

## Music and beat
- `audio: [{ "src": "song", "volume": 0.8, "fade_out": 1.5, "duck": true }]`. With speech, lower volume (0.2–0.35) and keep `duck`.
- Beat sync: estimate beats (see `ffmpeg-recipes` → beat times, or the user gives BPM: beat interval = 60/BPM). Make clip boundaries land on beats (every 1, 2 or 4 beats). Check with `cstudio validate` timeline starts.
- Only use music the user provides or confirms they may use; platforms mute copyrighted audio.

## Photo carousel → video
Image clips 1.5–2.5 s with alternating Ken Burns (`zoom: {from: 1, to: 1.12}` then `{from: 1.12, to: 1}`), `focus` on the subject, quick `fade`/`slideleft` transitions (0.25–0.35 s) or straight cuts on the beat.

## Before final
`cstudio review` must show: loudness ≈ −14 LUFS, no unintended black frames, total length as requested. Read the review sheet: is the hook frame strong? Is every text readable at phone size?
