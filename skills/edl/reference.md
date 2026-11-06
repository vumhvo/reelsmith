# EDL reference (reelsmith, version 1)

All times in seconds. Colors: `#RRGGBB` or `#RRGGBBAA`. Unknown keys are ignored.

## `output`

| key | default | notes |
|---|---|---|
| `preset` | – | `tiktok` `reels` `shorts` `vertical` (1080x1920) · `youtube` `1080p` (1920x1080) · `720p` · `4k` · `square` (1080x1080) · `portrait` (1080x1350). All 30 fps. |
| `width`, `height`, `fps` | from preset, else first visual source (max 1080p, max 60 fps) | override any preset value |
| `fit` | `cover` | default fit for clips: `cover` (fill + crop), `contain` (letterbox), `blur` (contain over blurred fill), `fill` (stretch) |
| `bg` | `#000000` | bar color for `contain` |
| `loudness` | `-14` | integrated LUFS target (streaming standard). `null` = no normalization |
| `fade_in`, `fade_out` | – | whole-video fade from/to black (+ audio) |
| `grade` | – | global color, same keys as clip `grade` |
| `crf`, `encoder_preset`, `audio_bitrate`, `sample_rate` | 20, medium, 192k, 48000 | encoding |

## `clips[]` (sequential video track)

One of:
- **video**: `{ "src", "in", "out" }`. `in` defaults to 0, `out` to the source end.
- **image**: `{ "src", "duration" }` (default 3 s). EXIF rotation is respected.
- **color card**: `{ "color": "#101010", "duration": 2 }`.

Optional on any clip:

| key | meaning |
|---|---|
| `speed` | playback rate (video only), e.g. `0.5` slow-mo, `2` fast; audio pitch kept |
| `transition` | `{ "type": "fade", "duration": 0.5 }` into this clip from the previous one. Types: fade, fadeblack, fadewhite, dissolve, wipeleft/right/up/down, slideleft/right/up/down, smoothleft/right/up/down, circleopen, circleclose, radial, pixelize, zoomin, hblur, diagtl/tr/bl/br, … (ffmpeg xfade names) |
| `fit` | per-clip override of `output.fit` |
| `focus` | `[x, y]` 0–1: which part of the frame to keep when cropping (`cover`) or to zoom towards. Default `[0.5, 0.5]` |
| `zoom` | number ≥ 1 = static punch-in (cover only); `{ "from": 1.0, "to": 1.2 }` = animated Ken Burns over the clip |
| `crop` | `[x, y, w, h]` fractions of the source frame, applied before fit (manual reframe) |
| `grade` | `{ "brightness": 0.03, "contrast": 1.08, "saturation": 1.15, "gamma": 1.0, "lut": "/path/look.cube" }` |
| `fade` | `{ "in": 0.3, "out": 0.5 }` video + audio fade within the clip |
| `volume` | clip audio gain (1 = unchanged, 0.5 = −6 dB) |
| `mute` | `true` drops the clip's own audio |
| `captions` | `false` excludes this clip from auto captions |
| `vf`, `af` | raw ffmpeg filter chain appended to the clip's video / audio |

## `audio[]` (music, voice-over, sound effects)

| key | default | meaning |
|---|---|---|
| `src` | – | media id or path |
| `at` | 0 | timeline time where it starts |
| `in`, `out` | 0, end | range within the audio file |
| `volume` | 1 | gain; music under speech ≈ 0.15–0.3, music-only ≈ 0.6–1.0 |
| `fade_in`, `fade_out` | – | seconds |
| `loop` | false | repeat to fill the rest of the video |
| `duck` | – | `true` (or a ratio like `10`): automatically lower this track while the clips' own audio is loud (speech) |

Tracks are mixed with the clips' audio, then the whole mix is normalized to `output.loudness`. The video length always wins; audio past the end is cut.

## `text[]`

`{ "text": "Hello\nworld", "start": 1.0, "end": 3.5, ...style }`. `end` defaults to the end of the video.

| style key | default | notes |
|---|---|---|
| `x`, `y` | 0.5, 0.5 | anchor point, fraction of frame |
| `anchor` | `center` | `center` `top` `bottom` `left` `right` `top-left` `top-right` `bottom-left` `bottom-right` |
| `align` | `center` | line alignment |
| `size` | 0.06 | ≤ 1: fraction of the frame's shorter side; > 1: pixels at full resolution |
| `font` | Vietnamese-capable bold (Be Vietnam Pro if in `assets/fonts/`, else Arial Bold) | path, file name stem, or substring |
| `color` | `#FFFFFF` | |
| `stroke`, `stroke_width` | `#000000`, 0.08 | outline; width as fraction of font size; `stroke: null` disables |
| `box`, `box_padding`, `box_radius` | –, 0.35, 0.3 | background pill behind the block, e.g. `#000000A0` |
| `shadow` | – | soft drop shadow color, e.g. `#00000099` |
| `max_width` | 0.86 | wrap width (fraction of frame width) |
| `line_spacing` | 1.15 | |
| `case` | – | `upper` / `lower` |

## `images[]` (logos, stickers, picture-in-picture stills)

`{ "src": "logo.png", "start": 0, "end": 5, "x": 0.95, "y": 0.05, "anchor": "top-right", "width": 0.2, "opacity": 0.9 }`. `width` ≤ 1 = fraction of frame width. PNG transparency is kept.

## `captions` (auto subtitles from transcripts)

Present (even `{}`) = burn captions in. Needs `cstudio transcribe` for the source clips. Words are remapped through cuts, speed and transitions automatically.

| key | default | notes |
|---|---|---|
| `style` | vertical: y 0.70, size 0.075, yellow active word · horizontal: y 0.86, size 0.055 | any text style key, plus `highlight_color`, `highlight_box` (pill behind active word) |
| `karaoke` | true | highlight the active word |
| `max_words`, `max_chars` | 3 / 22 vertical, 7 / 42 horizontal | words per caption |
| `gap` | 0.6 | pause that forces a new caption |
| `linger` | 0.25 | keep caption after last word |
| `replace` | {} | word fixes: `{ "dalat": "Đà Lạt" }` (case-insensitive, punctuation kept) |
| `file` | – | use an `.srt` or an edited captions `.json` (timeline times) instead of transcripts |

## Full example

See `examples/vertical-travel.edl.json` and `examples/talking-head.edl.json` in the reelsmith repo.
