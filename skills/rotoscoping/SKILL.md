---
name: rotoscoping
description: Rotoscope people and objects in video with reelsmith (SAM 2, runs locally): track a subject through a shot and use the masks for background removal or replacement, green screen, portrait background blur, colour pop, spotlight, glowing outline, text behind the subject, blurring or pixelating a face, logo or person (censor), subject-only colour, beat flicker, and transparent cutout export (ProRes 4444 / WebM alpha / PNG) for other editors. Use when the user asks to cut out, mask, isolate, select or track a person or object, remove or change the background, or for roto, matte, Magic Mask, Roto Brush, Object Mask, "xóa phông", "tách nền", "tách người", "chữ sau người".
---

# Rotoscoping (masks with SAM 2)

`cstudio roto` segments one or more people/objects on a frame you prompt, tracks them through a source range, and writes one mask per frame. An EDL clip then uses the masks through its `object` key; `cstudio cutout` exports a transparent cutout.

SAM 2 runs **locally** (Apple GPU via MPS, CUDA, or CPU) through `uvx`, so core reelsmith stays free of torch. First run installs torch + sam2 (a few minutes) and downloads the model (~180 MB for `small`); later runs on a 2 s shot take ~10–30 s.

## Workflow

### 1. Find the shot and look at it
Masks are per source range, so pick the exact source seconds the edit will use (plus a little margin). One job per shot: a hard cut inside the range breaks tracking. Keep jobs short (≤ ~20 s); memory grows with frames.

```bash
cstudio frame <id> 129.7 --grid      # frame with a 0–1 coordinate grid: read point positions off it
```
Read the image. Choose prompts on the **frame where the subject is clearest** (big, unoccluded), not necessarily the first frame.

### 2. Prompt and track
Coordinates are fractions of the frame (0–1, x then y), read from the grid. Values > 1 are treated as source pixels.

```bash
# one subject: 1–3 points on it (torso + head/legs), optional negative points on things that must stay out
cstudio roto <id> --start 129.7 --end 131.7 --name fighter --pos 0.44,0.2 --pos 0.37,0.4 --neg 0.4,0.65
# prompt on a later frame (tracking runs forwards and backwards from it)
cstudio roto <id> --start 12 --end 18 --name guest --at 14.5 --pos 0.6,0.35
# a box is good for objects (car, product, logo); points are better for people
cstudio roto <id> --start 3 --end 9 --name car --box 0.2,0.4,0.7,0.85
```
Several objects, or correction clicks at other times, use `--prompts` (inline JSON or a file). Entries with the same `id` refine the same object:
```bash
cstudio roto <id> --start 10 --end 16 --name duo --prompts '[
  {"id": 1, "pos": ["0.3,0.4"]},
  {"id": 2, "pos": ["0.7,0.45"], "neg": ["0.5,0.5"]},
  {"id": 1, "at": 14.2, "pos": ["0.42,0.38"]}]'
```
Output in `.studio/roto/<name>/`: `masks/` (union of all objects), `obj<id>/` (each object, when several), `roto.json` (includes the ready EDL `object` snippet and `warnings`), `prompt.jpg`, `review.jpg`. Same arguments again = cached; `--force` re-runs. `cstudio roto` with no source lists jobs.

Options: `--model tiny|small|base|large` (default `small`; `large` for hair, thin limbs, fast motion; `tiny` for quick tests), `--max-size` (default 1280, the longest side SAM 2 works on; masks are scaled to the source when used).

### 3. Check the masks (always)
1. **Read `prompt.jpg`**: the tinted area with the yellow edge must be exactly the intended subject. Wrong pick → move points, add `neg` points on what leaked in, or use a box.
2. **Read `review.jpg`**: 12+ frames across the range. Look for the mask drifting to another person, dropping limbs, or swallowing background.
3. **Read `warnings`** in the output: `object lost` (empty mask) and `mask size jumps` give times. Fix them by adding a correction prompt with `"at"` at that time (same `id`), or split into two jobs at the problem.

Two people in contact (fighting, hugging, dancing) are the hard case: give each one its own `id`, use several points per person, and put `neg` points on the other person's nearby limbs.

### 4. Use the masks in the EDL
Paste `roto.json`'s `object` snippet into the clip and add effects. The clip's `in`/`out` must lie inside the roto range (`cstudio validate` warns when they don't). Effects follow every crop, speed, zoom and fit, because they are applied in source space first.

```json
{ "src": "<id>", "in": 129.7, "out": 131.7,
  "object": { "mask": ".studio/roto/fighter/masks", "from": 129.7, "fps": 29.992,
              "background": "blur", "outline": { "color": "#FFD400", "width": 6, "glow": 5 } } }
```
For a still image clip (or a freeze frame), use one PNG: `"mask": ".studio/roto/<name>/masks/00000.png"` (or the matching frame `000NN.png` of a video job).

### 5. Render and review
`cstudio render ... --preview`, then pull frames with `cstudio frame renders/x-preview.mp4 <t>` and check edges, especially on fast motion. Soft or haloed edges: `feather` 1–3; background showing around the subject: `grow` −1 to −3; subject edges cut off: `grow` 2–4.

## Request → recipe

| User asks for | EDL `object` keys / command |
|---|---|
| Remove background, green screen | `"background": "#00FF00"` (any colour, e.g. `#000000`, `#FFFFFF`) |
| Replace background with a photo/video | `"background_src": "beach.jpg"` (media id or path; video loops; `background_in` = start second). Add `"background": "blur"` or `"dim"` to treat the new background too |
| Transparent cutout for Premiere/Final Cut/CapCut/DaVinci | `cstudio cutout <name>` → `renders/<name>-cutout.mov` (ProRes 4444). `--format webm` (VP9 alpha, web/CapCut), `--format png` (sequence), `--matte` (B/W matte as a track matte), `--invert` (background only) |
| Portrait / bokeh background blur | `"background": "blur"` |
| Colour pop (subject in colour, world B&W) | `"background": "bw"` (don't also use `fx: ["bw"]`) |
| Spotlight on the subject | `"background": "dim"` (or `"dark"`) |
| Glowing outline / stroke around a person | `"outline": { "color": "#FFD400", "width": 6, "glow": 6 }` |
| Text behind the person | clip `object` + `text[]` item with `"behind": true` (big word placed over the subject; see the `edl` skill) |
| Blur / pixelate a face, person, plate, logo | roto that thing, then `"subject": "blur"` or `"pixelate"` with `"grow": 4` so edges are covered |
| Grade only the subject | `"subject": "pop"` (saturation), `"bright"`, `"bw"`, `"negate"`, or a raw ffmpeg chain such as `"eq=gamma=1.2,hue=h=20"` |
| Grade only the background | `"background": "<filters>"` (raw chain, e.g. `"eq=saturation=0.3,colorbalance=bs=0.2"`) |
| Effect on everything except the subject | `"invert": true` swaps object and background for every effect |
| Subject flashes on the beat | `"flicker": [timeline beat times]`, `flicker_color`, `flicker_opacity`, `flicker_len` |
| Freeze frame with the subject highlighted | still image clip of that frame + still mask + `outline` / `background: "dim"` |
| Sticker cutout of a person on another clip | `cstudio cutout <name> --format png` on a still job → `renders/<name>-cutout.png`, then `images[]` |

Named looks for `background` and `subject`: `bw`, `dim`, `dark`, `blur`, `pixelate`, `negate`, `pop`, `bright`; anything else is used as raw ffmpeg filters. Matte refinement on any clip: `grow` (px, negative shrinks), `feather` (edge blur sigma, px), `invert`.

## Limits (say so instead of faking it)
- **Object removal** (erase a person and fill the hole) needs video inpainting (e.g. ProPainter), which reelsmith does not have. Offer blur/pixelate, a crop, or a replacement background instead.
- **Fine hair and motion blur**: SAM 2 masks are hard-edged. Use `--model large`, `feather`, and avoid flat bright backgrounds that show halos.
- **Hard cuts and long occlusions** lose the subject: split jobs at cuts and add correction prompts after the subject reappears.
- Chroma key of real green screen footage is cheaper and cleaner with ffmpeg `colorkey`/`chromakey` (`ffmpeg-recipes` skill) than with SAM 2.
