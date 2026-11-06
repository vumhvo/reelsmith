---
name: rough-cut
description: Speech-led editing with reelsmith: interviews, podcasts, talking-head videos, tutorials, vlogs, webinars. Pick the best quotes from a transcript, remove silences, filler words and retakes, tighten pacing, build a story order, add B-roll. Use when the edit is driven by what people say rather than by visuals.
---

# Rough cut from the transcript

The transcript is your timeline. You edit text, then convert the chosen text to `in`/`out` ranges.

## Workflow

1. `cstudio ingest <files> --transcribe --lang <xx>`. For long recordings add `--proxy`.
2. Read `transcript.txt` for each source (segment lines have `[start - end]` in source seconds). For precise cut points read `transcript.json` → `words[]` (`start`/`end` per word).
3. Write a **paper edit** to the user first: the ordered list of quotes you'll keep, with timestamps and the resulting total length. Ask for a go-ahead if the content selection is subjective.
4. Convert to EDL clips: one clip per kept passage.
   - `in` = first word's `start` − 0.08 s; `out` = last word's `end` + 0.12 s (don't clip breaths and plosives).
   - Never cut in the middle of a word. Prefer cutting at pauses (gaps in `words[]`, or `audio.json` silences).
5. `cstudio validate`, preview, `cstudio review`, listen-check via the review numbers and contact sheet, iterate.

## Tightening

- **Silences**: `audio.json` lists silences (threshold −35 dB, ≥ 0.5 s). Split clips around long pauses and leave ~0.15–0.25 s of air.
- **Fillers / retakes**: look for "ờ", "ừm", "à", "kiểu", "thì là", "uh", "um", "you know", false starts and repeated sentences. Keep the last clean take.
- **Jump cuts** on a static talking head: alternate `zoom: 1.0` and `zoom: 1.12` (with `focus` on the face) on consecutive clips, or cover the cut with B-roll.
- **B-roll over speech**: the EDL has one video track. Put the B-roll clip in `clips` with `mute: true`, and play the speaker's audio for that stretch from `audio[]`. A video file works as an audio source: `{ "src": "interview", "in": 84.2, "out": 90.6, "at": <timeline start of the B-roll clip> }`. Music `duck` reacts only to clip audio, so lower the music manually there if needed.
- **Pacing**: tutorials keep pauses before key steps; social cuts remove nearly all air.

## Story order

Hook (strongest line or result) → context → body in logical order → payoff → call to action. Interviews: question cards (`text` or a `color` card) between answers if the questions were cut.

## Deliver

Final render + `cstudio captions … --srt` if useful. Tell the user what you removed (e.g. "removed 2:14 of pauses and 3 retakes").
