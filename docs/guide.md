# Reelsmith user guide

> Edit video by talking to Claude. No editing experience needed, no heavy editing software to learn.

This guide is written for **two kinds of readers**:

- **You have never edited a video**: read from top to bottom. [Key terms](#key-terms) explains every bit of jargon in plain words. By the end of [Quick start](#quick-start) you will have made your first video.
- **You already know Premiere, CapCut, DaVinci…**: jump straight to [How Reelsmith works](#how-it-works), [The browser editor](#editor) and [The EDL](#edl).

Đọc bằng tiếng Việt: [huong-dan-su-dung.md](huong-dan-su-dung.md).

---

<a id="contents"></a>
## Contents

1. [What is Reelsmith?](#what-is-reelsmith)
2. [How Reelsmith works](#how-it-works)
3. [Key terms](#key-terms)
4. [Install](#install)
5. [Quick start: your first video in 10 minutes](#quick-start)
6. [Asking Claude for the video you want](#asking-claude)
   - [What to say up front](#what-to-say)
   - [Example requests by type of video](#example-requests)
   - [Asking for changes after the draft](#asking-for-changes)
7. [The browser editor (`cstudio ui`)](#editor)
   - [Opening the editor](#open-editor)
   - [What is on the screen](#screen-areas)
   - [Adding media and putting it on the timeline](#adding-media)
   - [Editing on the timeline](#timeline-editing)
   - [Properties and crop](#properties)
   - [Exporting](#exporting)
   - [Keyboard shortcuts](#shortcuts)
8. [Running it yourself from the command line](#command-line)
9. [The EDL: your video's recipe](#edl)
10. [Common tasks: what to say, what it writes](#recipes)
11. [Cutting people out of the background (rotoscoping)](#rotoscoping)
12. [What your workspace folder looks like](#workspace)
13. [FAQ and troubleshooting](#faq)
14. [Current limits](#limits)
15. [Further reading](#further-reading)

---

<a id="what-is-reelsmith"></a>
## 1. What is Reelsmith?

Reelsmith is a toolkit that lets **Claude** (the AI assistant running in Claude Code) edit video for you. You put your videos, photos and music in a folder, then say something like:

> Cut these clips into a 30-second TikTok, use `song.mp3` as the music, add Vietnamese captions, and open with the best shot.

Claude looks at what is in each clip, proposes an edit, makes a draft, checks it for mistakes, and renders a finished `.mp4`.

**What kinds of video?** Vlogs, travel videos, interviews, people talking to camera (talking heads), tutorials, TikTok/Reels/Shorts, YouTube videos, photo slideshows, highlight reels, short ads…

**What makes it different?**

- **Your originals are never touched.** Source files are only read, never changed or deleted. Results always go to new files.
- **Change it as often as you like.** The whole edit is saved as a small "recipe" file. Want different music, one shot less, new wording? Just say so: Claude edits the recipe and renders again.
- **A real editor when you want one.** If you like dragging things around, open the editor in your browser and edit by hand. You and Claude work on the same edit.
- **Your video stays on your machine.** Analysis, speech recognition, background removal and rendering all run locally; no video is uploaded anywhere.

---

<a id="how-it-works"></a>
## 2. How Reelsmith works

Claude can't watch video the way people do. Reelsmith gives it three things:

| Part | What it does | Command |
|---|---|---|
| **Eyes** | Turns footage into things Claude can read: grids of frames with timestamps, scene cuts, loudness, silences, and word-by-word transcripts of speech | `cstudio ingest` |
| **Hands** | Claude writes the edit as one JSON file (the **EDL**); render turns that file into a video | `cstudio render` |
| **A check step** | Measures loudness, finds black frames and unexpected silences, and grabs frames from the render so Claude can catch its own mistakes | `cstudio review` |

The full workflow:

```
 Your video folder
        │
        ▼
 ① init      make the folder a "workspace"
        │
        ▼
 ② ingest    analyze: frame grids, scenes, audio, speech
        │
        ▼
 ③ Claude reads the analysis → proposes a plan → you say OK
        │
        ▼
 ④ Claude writes the EDL (the recipe)   edits/main.edl.json
        │
        ▼
 ⑤ render --preview   quick low-resolution draft
        │
        ▼
 ⑥ review             automatic checks → fix the EDL → back to ⑤
        │
        ▼
 ⑦ render             final video   renders/main.mp4
```

You **don't have to type any of these commands**. When you ask Claude, it runs them. The command table in [section 8](#command-line) is for people who want to drive it themselves.

---

<a id="key-terms"></a>
## 3. Key terms

If you have never edited video, these are all the words you will run into. One read is enough.

### Video basics

| Term | Meaning | Think of it as |
|---|---|---|
| **Footage** | The raw video you shot, uncut | Ingredients before prep |
| **Clip** | One piece taken out of the footage | A slice of the loaf |
| **Timeline** | The running time of the finished video, with clips laid end to end | The finished reel |
| **Trim / cut** | Remove part of the start or end of a clip | Cutting the shaky first 2 seconds |
| **In / out points** | The second where the used part of a clip starts and ends | "From 0:12 to 0:18" |
| **Transition** | An effect between two clips instead of a hard jump | Fade, slide, spin |
| **Aspect ratio** | The shape of the frame | **9:16** vertical (TikTok, Reels, Shorts) · **16:9** horizontal (YouTube) · **1:1** square · **4:5** tall-ish (Instagram posts) |
| **Reframe** | Turn horizontal video into vertical (or the reverse) while keeping the subject in frame | Shot it wide, posting it on TikTok |
| **Render / export** | The computer "cooks" the edit into a real video file | Pressing "Export" in CapCut |
| **Preview** | A fast, low-quality render to check the edit | Tasting before serving |
| **B-roll** | Footage shown over someone talking, to illustrate what they say | They talk about the old town, you see the old town |
| **Ken Burns** | A slow zoom or pan over a still photo so it moves | Documentary-style photo slideshow |
| **Color grading** | Adjusting brightness, contrast, how vivid colors are | An Instagram filter |
| **LUT** | A ready-made color look stored in a file (`.cube`) | A color preset you download |

### Audio and text

| Term | Meaning |
|---|---|
| **Background music** | Music playing under the video |
| **Ducking** | Automatically lowering the music while someone speaks, so you hear the words |
| **Voice-over** | Narration recorded separately and laid over the video |
| **Loudness / LUFS** | A measure of how loud audio *feels*. YouTube, TikTok and others aim for about **−14 LUFS**. Reelsmith adjusts to this so your video isn't too quiet or too loud |
| **Transcript** | Speech written out as text, with the time of every word |
| **Captions / subtitles** | Text on screen following what is said. **Karaoke style**: the word being spoken lights up |
| **SRT** | A separate subtitle file (`.srt`) you upload alongside a YouTube video |
| **Safe zone** | The part of the screen not covered by TikTok/Reels buttons, usernames and descriptions |

### Reelsmith words

| Term | Meaning |
|---|---|
| **Workspace** | Your video folder, marked by `cstudio init` (it gets a `studio.json` file) |
| **Media id** | A short name Reelsmith gives each file, such as `walking` or `interview`, used instead of a long path |
| **Contact sheet** | One image with a grid of frames from a video, each labelled with its time. These are Claude's "eyes" |
| **EDL** (Edit Decision List) | The JSON file describing the whole edit: which clips, which parts, what text, what music. See [section 9](#edl) |
| **Proxy** | A lightweight 720p copy of 4K footage, for faster previews |
| **Skill** | A set of instructions that teaches Claude how to work like an editor (for example, how to make a TikTok, how to do captions) |
| **Rotoscoping / mask** | Separating one person or object from the background, following it frame by frame. Used to remove or blur backgrounds, put text behind someone… |

---

<a id="install"></a>
## 4. Install

### What you need

| You need | For | How to get it (macOS) |
|---|---|---|
| **Claude Code** | The AI assistant that edits for you | The Claude app (Code tab) or Claude Code in a terminal |
| **ffmpeg** | The video engine | `brew install ffmpeg` |
| **uv** | Installs and runs Python tools | `brew install uv` |
| **git** | Downloads the Reelsmith source | Comes with macOS (or `xcode-select --install`) |

> No Homebrew (`brew`) yet? See [brew.sh](https://brew.sh).
>
> An Apple Silicon Mac (M1 or later) is recommended: speech recognition (for captions) uses `mlx-whisper`, which only runs on those chips. Everything else works anywhere ffmpeg and uv do.

### Steps

**Step 1.** Install ffmpeg and uv (skip if you have them):

```bash
brew install ffmpeg uv
```

**Step 2.** Download Reelsmith and install the `cstudio` command:

```bash
git clone https://github.com/vumhvo/reelsmith.git && cd reelsmith && ./scripts/install.sh
```

The script tells you where `cstudio` was installed. If it asks you to add `~/.local/bin` to your PATH, follow what it prints.

**Step 3.** Add the skills to Claude Code. Open Claude Code and type these two lines into the chat:

```
/plugin marketplace add vumhvo/reelsmith
/plugin install reelsmith@reelsmith
```

**Step 4 (optional).** To use a nicer default font for titles and captions (Be Vietnam Pro, or any `.ttf`), put the font file in `assets/fonts/` inside the Reelsmith folder. Without it, the default font still covers Vietnamese diacritics.

### Check it worked

```bash
cstudio --help
```

If you see a list of commands (`init`, `ingest`, `render`…), you're done.

---

<a id="quick-start"></a>
## 5. Quick start: your first video in 10 minutes

**1. Put your material in one folder.** For example `~/Videos/dalat/` with a few phone clips, some photos and a music file.

```
dalat/
  IMG_0012.MOV
  IMG_0015.MOV
  IMG_0021.MOV
  sunset.jpg
  music.mp3
```

**2. Open Claude Code in that folder.** In the Claude app, pick `dalat` as the working folder. (In a terminal: `cd ~/Videos/dalat && claude`.)

**3. Say what you want.** For example:

> Make me a TikTok of about 30 seconds from the clips in this folder, with `music.mp3` as the music and the title "48 hours in Da Lat" at the start. Open with the best shot.

**4. Answer Claude's questions (if any).** Claude analyzes the footage, sums up what it saw in each clip, and proposes an order. Read it, then agree or steer ("drop the street clip", "put the lake first").

**5. Watch the draft.** Claude renders a preview to `renders/main-preview.mp4`. To watch it in a proper viewer, say:

> Open the editor so I can see it.

Your browser opens the timeline; press play.

**6. Give feedback and finish.** For example: "bigger title", "shorten the third shot", "music a bit quieter". When you're happy, say "render the final". The finished file is `renders/main.mp4`.

That's it. You made a video without knowing how to edit.

> **Tip:** The first time you turn on captions, your machine downloads a speech-recognition model of about 1.6 GB. After that it's quick.

---

<a id="asking-claude"></a>
## 6. Asking Claude for the video you want

Claude does its best work when it knows what you want. No jargon needed: talk as you would to a friend who edits.

<a id="what-to-say"></a>
### What to say up front

| Tell it | Why it matters | Example |
|---|---|---|
| **Where it will be posted** | Decides vertical vs horizontal, length, pacing | "for TikTok", "for YouTube", "an Instagram post" |
| **How long** | How many shots Claude picks | "about 30 seconds", "under a minute" |
| **Mood / pace** | Fast or slow cuts, which transitions | "energetic", "calm and chill", "cinematic" |
| **Music** | Which file, loud or soft | "use `song.mp3`", "no music, keep the original sound" |
| **Captions** | Yes or no, which language | "Vietnamese captions, karaoke style" |
| **Must-have moments** | So nothing important is cut | "include blowing out the candles", "end on the group shot" |
| **On-screen text** | Titles, names, calls to action | "show 'Jane Doe, Founder' when she first appears" |

Anything you leave out, Claude either asks about or picks a sensible default (a TikTok is 15 to 35 seconds, for example).

<a id="example-requests"></a>
### Example requests by type of video

**Short vertical video (TikTok / Reels / Shorts)**

> Make a 20-second Reel from these clips, fast cuts on the beat of `beat.mp3`, open with big text "POV: first time in Ha Giang", captions if anyone talks.

**Long travel vlog (YouTube)**

> Make a 16:9 YouTube video of about 5 minutes from this trip, keep the original sound, soft music that dips when I talk, fades between days, titles "Day 1", "Day 2"…

**Interview / podcast / talking head**

> This is a 40-minute interview. Pick the best answers into a 3-minute video, cut the "um"s, "uh"s and pauses, add English captions and the guest's name in the lower corner.

Claude first sends a "paper edit" (the list of quotes it will keep, with timestamps) for you to approve before it cuts.

**Photo slideshow**

> Turn these 15 wedding photos into a 45-second video, each photo moving gently, fade transitions, music `wedding.mp3`, end with "Thank you all".

**Just add captions to an existing video**

> Add English captions to `talk.mp4` and also give me an .srt file for YouTube.

**Background removal, background blur, face blur** (more in [section 11](#rotoscoping))

> In `dance.mp4` from 0:05 to 0:12, make the background black and white and keep the dancer in color.

> Blur the face of the passer-by in the red shirt in `street.mp4`.

**Horizontal to vertical**

> Turn `presentation.mp4` into a 9:16 TikTok and keep the speaker centered.

<a id="asking-for-changes"></a>
### Asking for changes after the draft

Just describe what you see. Claude only edits the recipe file (the EDL) and renders again, which is fast.

| You notice | You say |
|---|---|
| A shot is too long | "The shot at 0:08–0:12 drags, cut it to 2 seconds" |
| Text is hard to read | "Make the title bigger with a dark box behind it" |
| TikTok buttons cover the text | "Move the text up a bit" |
| Music drowns out speech | "Music quieter, and dip it when someone talks" |
| A caption is misspelled | "Captions say 'da lat', it should be 'Da Lat'" |
| You want another version | "Keep this one, and make a 15-second cut for ads" |
| Colors look flat | "A bit more color and contrast" |
| You want effects | "Add a white flash on the cuts that land on the beat" |

> **Tip:** Ask for a new version (`v2-short`, `teaser`) instead of overwriting one you liked. The old one stays there to go back to.

---

<a id="editor"></a>
## 7. The browser editor (`cstudio ui`)

An editing interface that runs in your browser, on your own machine (no internet needed). You can:

- **just watch** what Claude is building (the timeline refreshes within about a second whenever Claude edits), or
- **edit by hand** like in any editing app, or
- **do both**: you drag things around, Claude fine-tunes, and the other way round.

<a id="open-editor"></a>
### Opening the editor

Easiest: tell Claude "open the editor". Or run this inside the workspace folder:

```bash
cstudio ui
```

Your browser opens `http://localhost:8765`. If the workspace has no edit yet, the page starts an empty `edits/main.edl.json` so you can build one from scratch.

The interface follows your browser's language (English or Vietnamese). Add `?lang=en` or `?lang=vi` to the address to force one.

<a id="screen-areas"></a>
### What is on the screen

| Area | What's there |
|---|---|
| **Top bar** | Which edit (EDL) is open · **Render preview** button (with its status: up to date / out of date / rendering) · **Import** · **Export** |
| **Media** | Every video, audio file and image in the workspace, filterable by type. Right-click to open, copy the path, or remove from the library |
| **Viewer** | Watch the video. Two modes: **Preview** (the rendered edit, with all text and effects) and **Source frame** (original frames, instantly). While you change properties, **Live** shows an instant approximation |
| **Transport** | Go to start · back 1 frame · play/pause · forward 1 frame |
| **Timeline** | Tracks: **Video** (clips with thumbnails and transitions), **Clip audio** (waveforms, silences), **Audio** (music, voice-over), **Text**, **Images** (logos, stickers), **Captions** |
| **Inspector** (right) | Click any block on the timeline to see and change all its settings |
| **Timeline / Source tabs** | Opening a file from the library adds a **Source: file-id** tab where you watch the original and choose the part to use |

<a id="adding-media"></a>
### Adding media and putting it on the timeline

**Bring files in:**

- **Drag and drop** video, audio or images anywhere on the page, or
- Press **Import** and choose files. You can also paste the path of a file or folder already on your Mac: it is **used in place, not copied**.
- Tick **Transcribe speech** (and pick the language) if you want captions for it.

Uploaded files are copied into `footage/` (video, images) or `audio/` in the workspace, then analyzed automatically. Progress shows in the jobs list.

**Pick the part you want and add it:**

1. Open the file from the library (click it, or right-click → **Open in source viewer**).
2. Move to where it should start and press **[ In** (key `I`).
3. Move to where it should end and press **Out ]** (key `O`).
4. Press **Add to timeline** (key `Enter`) to add it as a video clip, or **Add as audio track** to use it as music or sound.

**Removing from the library:** only files not used on the timeline can be removed. You choose whether to keep the file on disk or move the workspace copy to the Trash.

<a id="timeline-editing"></a>
### Editing on the timeline

| To | Do |
|---|---|
| Trim the start or end of a clip | Drag its left or right edge (snaps to frames) |
| Reorder clips | Drag the block to a new place |
| Split a clip | Put the playhead where you want the cut, press `B` |
| Trim the start up to the playhead | `Q` |
| Trim the end from the playhead | `W` |
| Delete | Select the block, press `Delete` |
| Add text | `T` (adds text at the playhead) |
| Undo / redo | `⌘Z` / `⇧⌘Z` (Windows: `Ctrl+Z` / `Ctrl+Y`) |
| Zoom the timeline | `+` / `−`, or hold `⌘`/`Ctrl` and scroll |

**Right-click menus** add: split here, duplicate, mute/unmute the clip, add/remove a transition, move the start, add text here, copy timecode, **save the current frame as a PNG** (with all text and effects), show the file in Finder.

Everything you do is written straight into the EDL file. If Claude edited at the same moment, the page tells you, reloads the latest version, and you just redo your last action.

<a id="properties"></a>
### Properties and crop

Click a block on the timeline; the inspector on the right shows:

- **Video clip:** in/out in the source file, speed, fit, zoom, focus (X, Y), brightness, contrast, saturation, gamma, fade in/out, transition type and duration, volume, mute, exclude from captions.
- **Text:** the text, start/end time, position, anchor, alignment, size, color, outline, box, shadow, upper/lower case.
- **Images (logos):** timing, position, width, opacity.
- **Audio:** where it starts, volume, loop, fade in/out, duck under speech.

**Set to playhead** fills in the current time. **EDL entry** shows the raw JSON for that block.

**Crop:** select a clip → **Edit crop**, then drag the box on the picture. You can lock the aspect (**Output**) or leave it **Free**. `Enter` applies, `Esc` cancels. **Reset** removes the crop.

<a id="exporting"></a>
### Exporting

Press **Export** and choose:

| Type | Options |
|---|---|
| **Video** | Frame: As in the EDL, 9:16, 16:9, 1:1, 4:5, 4K · Quality: High / Standard / Small file · Export only a range (from… to… seconds) |
| **Audio** | MP3, M4A or WAV (the full mix: clip audio + music + voice-over) |
| **Captions .srt** | A separate subtitle file, for YouTube |

Files are written to `renders/` in the workspace. When a job finishes, press **Download** or **Show in Finder**.

<a id="shortcuts"></a>
### Keyboard shortcuts

**Timeline**

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `←` `→` | Back / forward 1 frame |
| `Shift` + `←` `→` | Back / forward 1 second |
| `Home` / `End` | Go to start / end |
| `+` / `−` | Zoom the timeline in / out |
| `S` | Switch between Preview and Source frame |
| `B` | Split at the playhead |
| `Q` / `W` | Trim start / end to the playhead |
| `T` | Add text |
| `Delete` | Delete the selected block |
| `⌘Z` / `⇧⌘Z` | Undo / redo |

**Source viewer** (when a file from the library is open)

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `←` `→` · `Shift` + `←` `→` | Back/forward 1 frame · 1 second |
| `I` / `O` | Set in / out point |
| `Enter` | Add the selected range to the timeline |
| `Esc` | Close the source viewer |

---

<a id="command-line"></a>
## 8. Running it yourself from the command line

For people who want to drive each step. Run every command **inside the workspace folder**.

### Minimal workflow

```bash
cstudio init                                   # 1. make the current folder a workspace
cstudio ingest                                 # 2. analyze every file in it
cstudio media                                  # 3. list files and their media ids
# 4. write edits/main.edl.json (see section 9), or ask Claude to
cstudio validate edits/main.edl.json           # 5. check for errors, print the timeline
cstudio render edits/main.edl.json --preview   # 6. quick draft
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json   # 7. automatic checks
cstudio render edits/main.edl.json             # 8. final → renders/main.mp4
```

### All commands

| Command | What it does | Useful options |
|---|---|---|
| `cstudio init [folder]` | Create a workspace | `--name` |
| `cstudio ingest [files/folders…]` | Index and analyze media: contact sheets, scenes, loudness, silences | `--transcribe --lang en` (transcripts) · `--proxy` (light copies for long 4K) · `--force` (re-analyze) |
| `cstudio media` | List media: id, duration, size, audio, transcript (`T`), HDR | `--json` |
| `cstudio probe <file>` | Details of one file | |
| `cstudio sheet <id>` | Contact sheet of a time range (to look closer) | `--start 10 --end 20 --count 12` |
| `cstudio frame <id> <seconds>` | Extract one frame | `--grid` (draws a 0–1 coordinate grid, for rotoscoping) |
| `cstudio transcribe [ids…]` | Speech to text with per-word times | `--lang en` · `--prompt "Da Lat, Claude"` (spelling hints for names) |
| `cstudio validate <edl>` | Check an EDL and print the timeline (where each clip starts and ends) | |
| `cstudio captions <edl>` | Build captions for the edit | `--srt out.srt` · `--json file.json` (to hand-edit) · `--show 40` |
| `cstudio render <edl>` | Render the video | `--preview` (half resolution, fast) · `--range 10:20` (only that part) · `-o file.mp4` · `--dry-run` |
| `cstudio review <video>` | Check a render: loudness, black frames, silences, overview sheet | `--edl <edl>` (compare with the expected length) |
| `cstudio ui [edl]` | Open the browser editor | `--port` · `--no-open` · `--no-render` |
| `cstudio roto <id>` | Cut a person or object out of the background (see [section 11](#rotoscoping)) | `--start --end --pos x,y --name` |
| `cstudio cutout <name>` | Export a cut-out subject with transparency, for other editors | `--format mov\|webm\|png\|mp4` |

Every command has `--help`, for example `cstudio render --help`.

---

<a id="edl"></a>
## 9. The EDL: your video's recipe

### The idea

Instead of saving the finished video, Reelsmith saves the **recipe** for it: a small JSON file in `edits/`. The `render` command reads the recipe and "cooks" the video.

Why: changing one number in the recipe is enough, nothing has to be rebuilt by hand. Claude edits the recipe precisely; you can also open the file and edit it yourself, or use the browser editor.

### A small example, line by line

```json
{
  "output": { "preset": "tiktok" },
  "clips": [
    { "src": "footage/best-view.mp4", "in": 2.0, "out": 4.0 },
    { "src": "footage/walking.mp4", "in": 0.5, "out": 6.5, "speed": 1.5 },
    { "src": "photos/sunset.jpg", "duration": 2.5,
      "transition": { "type": "fade", "duration": 0.3 } }
  ],
  "audio": [
    { "src": "music.mp3", "volume": 0.7, "fade_out": 1.5, "duck": true }
  ],
  "text": [
    { "text": "48 hours in Da Lat", "start": 0, "end": 2, "y": 0.25, "size": 0.1 }
  ],
  "captions": {}
}
```

| Line | Meaning |
|---|---|
| `"preset": "tiktok"` | Vertical 1080×1920 video at 30 frames per second |
| Clip 1 | Use `best-view.mp4` from second 2 to second 4 |
| Clip 2 | Use `walking.mp4` from 0.5 to 6.5 s, played 1.5× faster |
| Clip 3 | Show `sunset.jpg` for 2.5 s, fading in over 0.3 s |
| `audio` | Music at 70% volume, fading out over the last 1.5 s, dipping when someone talks |
| `text` | "48 hours in Da Lat" from 0 to 2 s of the video, a quarter of the way down, large |
| `captions: {}` | Turn on automatic captions (needs a transcript first) |

### The most important rule: two kinds of time

This is the easiest thing to get wrong, even for experienced editors:

- **A clip's `in` / `out`** are seconds **in the source file**. `"in": 12` means "second 12 of `walking.mp4`".
- **Every other time** (`start`/`end` of text, `at` of audio…) is seconds **in the finished video**. `"start": 5` means "5 seconds after the viewer presses play".

To see where each clip lands in the finished video, run `cstudio validate edits/main.edl.json`: it prints the timeline.

### The parts of an EDL

| Part | Holds |
|---|---|
| `output` | Frame size (preset), loudness target, fade in/out of the whole video, overall color, encoding quality |
| `clips` | Video clips, photos or solid color cards, **played one after another in order** |
| `audio` | Music, voice-over, sound effects, placed at any time |
| `text` | Text and titles, optionally animated |
| `images` | Logos, stickers, images over the video |
| `captions` | Automatic captions from speech |

### Frame presets

| Preset | Size | For |
|---|---|---|
| `tiktok`, `reels`, `shorts`, `vertical` | 1080×1920 (9:16) | TikTok, Instagram Reels, YouTube Shorts |
| `youtube`, `1080p` | 1920×1080 (16:9) | YouTube, horizontal video |
| `720p` | 1280×720 | Lighter horizontal video |
| `4k` | 3840×2160 | High-quality horizontal video |
| `square` | 1080×1080 (1:1) | Square posts |
| `portrait` | 1080×1350 (4:5) | Tall Instagram posts |

Every field in detail: [skills/edl/reference.md](../skills/edl/reference.md). Two sample EDLs: [examples/vertical-travel.edl.json](../examples/vertical-travel.edl.json) (travel TikTok) and [examples/talking-head.edl.json](../examples/talking-head.edl.json) (YouTube interview).

---

<a id="recipes"></a>
## 10. Common tasks: what to say, what it writes

The "Say to Claude" column is all you need. The "In the EDL" column is for editing the file yourself.

| Task | Say to Claude | In the EDL |
|---|---|---|
| Horizontal to vertical, subject centered | "Make it 9:16 and keep the speaker in frame" | `"preset": "tiktok"` + clip `"focus": [0.4, 0.5]` |
| Wide shot that must not be cropped | "Show the whole view, blurred bars around it" | clip `"fit": "blur"` |
| Punch in on a face | "Zoom in closer on her face" | `"zoom": 1.15, "focus": [0.5, 0.35]` |
| Movement on a still photo | "Slowly zoom into the photo" | `"zoom": { "from": 1.0, "to": 1.15 }` |
| Slow motion / speed up | "Half speed for this shot" | `"speed": 0.5` (or `2` for double speed) |
| Play backwards | "Rewind this shot" | `"reverse": true` |
| Transition | "Fade between the days" | `"transition": { "type": "fade", "duration": 0.5 }` |
| Color | "More vivid, a bit more contrast" | `"grade": { "saturation": 1.15, "contrast": 1.08 }` |
| Music that dips under speech | "Soft music that drops when people talk" | audio `"volume": 0.2, "duck": true` |
| Mute a clip's own sound | "Mute this shot" | `"mute": true` |
| Animated title | "Title pops in" | text `"enter": "pop"` |
| Words appearing one by one | "Reveal the text word by word" | text `"reveal": "words"` |
| Logo in a corner | "Put `logo.png` top right" | `images: [{ "src": "logo.png", "x": 0.94, "y": 0.06, "anchor": "top-right", "width": 0.14 }]` |
| Captions | "Add karaoke-style captions" | `"captions": {}` (after transcribing) |
| Fix a word in captions | "Change 'da lat' to 'Da Lat'" | `"captions": { "replace": { "da lat": "Da Lat" } }` |
| Hit effects on the beat | "White flash and a little shake on the cut" | clip `"fx": ["flash", "shake"]` |
| Black and white, film grain | "Last shot black and white with grain" | `"fx": ["bw", "grain"]` |
| Remove pauses and filler words | "Cut the silences and the 'um's" | Claude splits clips using the transcript |
| Fade the whole video in and out | "Fade in at the start, to black at the end" | `"output": { "fade_in": 0.5, "fade_out": 0.8 }` |

**Built-in effects (`fx`)**: `flash` (white flash), `punch` (zoom punch), `shake` (camera shake), `rgb` (RGB split), `trail` (motion echo), `bw` (black and white), `grain` (film grain), `vignette` (dark edges), `impact` (anime-style impact frame), `open` (picture opens from a thin horizontal slit).

**Transitions**: about 35 types such as `fade`, `fadeblack`, `dissolve`, `wipeleft`, `slideleft`, `circleopen`, `pixelize`, `zoomin`, plus `whipleft`/`whipright`/`whipup`/`whipdown` (whip pan) and `spin` (360° roll).

**Text entrances (`enter`)**: `fade`, `pop`, `stamp`, `zoom`, `slideup`, `slidedown`, `slideleft`, `slideright`, `drop`, `blur`, `spin`.

---

<a id="rotoscoping"></a>
## 11. Cutting people out of the background (rotoscoping)

### What it is

Reelsmith uses the **SAM 2** AI model (running on your machine) to outline a person or object in a video and follow it frame by frame. Other apps call this Magic Mask, Roto Brush or Object Mask.

### What you can do with it

| You want | Say something like |
|---|---|
| Remove the background, solid color (green screen) | "Replace the background with green" |
| Put the subject on another photo or video | "Put her on `beach.jpg`" |
| Blur the background (portrait look) | "Blur the background behind the speaker" |
| Subject in color, world in black and white | "Background black and white, keep him in color" |
| Spotlight (darker background) | "Darken the background, spotlight on her" |
| Glowing outline | "Yellow glowing outline around the runner" |
| Text **behind** the person | "Big 'DA LAT' behind the person walking" |
| Hide a face, license plate, logo | "Blur the face of the passer-by in red" |
| Export the cut-out for another app | "Export her with a transparent background for Premiere" |

### How Claude does it

1. Grabs a frame with a coordinate grid to locate the subject.
2. Places a few points on the subject (and "not this" points on things to leave out), then runs `cstudio roto`.
3. Checks the review images and fixes places where the mask drifts or drops out.
4. Attaches the mask to the clip in the EDL with the effect, renders a draft, checks the edges.

By hand:

```bash
cstudio frame <id> 12.5 --grid                                     # frame with a grid
cstudio roto <id> --start 12 --end 15 --name person --pos 0.5,0.4  # track the subject at (0.5, 0.4)
cstudio cutout person                                              # → renders/person-cutout.mov (transparent)
```

> **Note:** The first run installs extra AI libraries and downloads the model (about 180 MB), which takes a few minutes. After that, a 2-second shot takes about 10 to 30 seconds. Keep each job to one shot (under about 20 seconds) and don't span a hard cut.

Details: [skills/rotoscoping/SKILL.md](../skills/rotoscoping/SKILL.md).

---

<a id="workspace"></a>
## 12. What your workspace folder looks like

After using Reelsmith, your video folder has a few extra things:

```
dalat/                         ← your folder (the workspace)
  IMG_0012.MOV …               ← originals: never modified
  studio.json                  ← marks this as a workspace
  .studio/                     ← analysis data (hidden folder)
    media.json                 ←   media list and ids
    analysis/<id>/             ←   contact sheets, scenes, audio, transcript per file
    proxy/                     ←   720p proxies (with --proxy)
    roto/<name>/               ←   rotoscoping masks (if used)
  footage/  audio/             ← files imported through the editor (if any)
  edits/
    main.edl.json              ← the recipe: keep it for later changes
  renders/
    main-preview.mp4           ← draft
    main.mp4                   ← final
    main.srt                   ← separate subtitles (if exported)
```

**Want to change the video next week?** Open Claude Code in this folder again and say "edit the main video, drop the second shot". The recipe is still there; nothing starts over.

**Originals live somewhere else?** That's fine. Reelsmith records the path to each file; it doesn't copy or move them.

---

<a id="faq"></a>
## 13. FAQ and troubleshooting

**`cstudio` says "command not found".**
It is installed in `~/.local/bin`. Add that folder to your PATH (the install script prints how), or run `uv tool update-shell` and open a new terminal.

**Rendering is slow.**
Use drafts (`--preview`) while editing. For long 4K footage, ingest with `--proxy` so drafts use the light copies. Working on one part? Render only that part: `--range 10:20`.

**Captions show odd repeated lines ("Thanks for watching"…) where nobody speaks.**
Speech recognition sometimes invents words over wind, music or silence. Tell Claude "no captions on this clip", or set `"captions": false` on that clip.

**Captions misspell names.**
Tell Claude the right spelling ("the guest's name is Nguyen Thi Hanh"). It re-transcribes with spelling hints, or adds a `replace` rule.

**TikTok buttons or the username cover the text.**
Say "keep the text in the safe zone". On a vertical frame that's roughly 12% to 78% of the height, away from the right edge.

**The audio is quieter or louder than other videos.**
Reelsmith normalizes to −14 LUFS (the social-media standard). If something still sounds off, check the numbers in the `cstudio review` output.

**Colors look washed out and grey.**
The footage may be HDR (iPhones often record HDR). `cstudio media` marks it `hdr`. Reelsmith doesn't convert HDR yet: turn HDR off when shooting, or ask Claude to add contrast and saturation.

**The editor says "The EDL changed elsewhere".**
Claude edited at the same moment as you. The page has already reloaded the latest version; just redo your last action.

**The preview in the editor is "out of date".**
The page re-renders after every change by itself. If you started it with `--no-render`, press **Render preview**.

**I want to use the result in Premiere / Final Cut / CapCut / DaVinci.**
Export a normal `.mp4`, or for a cut-out subject: `cstudio cutout <name>` (ProRes 4444 with transparency), `--format webm` (for CapCut / web), `--format png` (image sequence).

**Is my video uploaded anywhere?**
No. Analysis, speech recognition, background removal and rendering all run on your machine. Claude only reads the analysis files (frame grids, transcripts, numbers) to decide on the edit.

---

<a id="limits"></a>
## 14. Current limits

- **One video track.** Clips play one after another; you can't freely stack two videos (images and logos can go on top). B-roll over speech works by muting the B-roll clip and playing the speaker's audio from an audio track, and Claude knows how to do it.
- **No full object removal** (erasing a person and filling in the background). Blur, cover, crop or replace the background instead.
- **Fine hair and fast motion** can give hard edges when cutting out. Use the `large` model and soften edges (`feather`).
- **HDR** is not converted automatically.
- **Speech recognition** needs an Apple Silicon Mac.
- **Copyrighted music:** only use music you have the rights to; platforms may mute videos that break the rules.
- Things the EDL doesn't cover (stabilization, noise reduction, GIF export, keying real green screen…) Claude does with a separate ffmpeg step (the `ffmpeg-recipes` skill) and then uses the result in the edit.

---

<a id="further-reading"></a>
## 15. Further reading

| Document | About |
|---|---|
| [README.md](../README.md) | Short project overview |
| [skills/edl/reference.md](../skills/edl/reference.md) | Every EDL field in detail |
| [examples/](../examples/) | Sample EDLs |
| [huong-dan-su-dung.md](huong-dan-su-dung.md) | This guide in Vietnamese |

The skills Claude follows (read them to see how Claude works):

| Skill | Used for |
|---|---|
| [`video-studio`](../skills/video-studio/SKILL.md) | The end-to-end editing workflow (entry point) |
| [`edl`](../skills/edl/SKILL.md) | Writing and changing EDLs |
| [`captions`](../skills/captions/SKILL.md) | Transcripts, captions, caption style, SRT export |
| [`rough-cut`](../skills/rough-cut/SKILL.md) | Speech-led edits: interviews, podcasts, talking heads |
| [`short-form`](../skills/short-form/SKILL.md) | TikTok/Reels/Shorts: hooks, pacing, safe zones, beat sync |
| [`rotoscoping`](../skills/rotoscoping/SKILL.md) | Cutting out people/objects, background effects |
| [`ffmpeg-recipes`](../skills/ffmpeg-recipes/SKILL.md) | One-off operations outside the EDL |

[↑ Back to contents](#contents)
