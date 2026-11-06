# Reelsmith: notes for working on this repo

A toolkit that lets Claude edit **any** video: `cstudio` CLI (Python, `src/studio/`) + skills (`skills/`, packaged as a plugin via `.claude-plugin/`). User footage and workspaces never live in this repo (`travel-video/` and `projects/` are gitignored personal projects).

## Layout
- `src/studio/cli.py`: argparse entry point; every command prints JSON or a compact table (Claude reads it).
- `workspace.py`: workspace = any folder with `studio.json`; state in `.studio/`.
- `analyze.py`: scenes, silence/loudness, contact sheets, proxies. `transcribe.py`: mlx-whisper via `uvx`.
- `edl.py`: EDL loading, presets, validation, timeline placement (`Plan`). `render.py`: EDL → one ffmpeg `filter_complex`.
- `layer.py`: text/images/captions rasterized with Pillow into a concat-demuxer overlay stream (Homebrew ffmpeg has no drawtext/libass).
- `captions.py`: remaps source-time transcripts onto the timeline (cuts, speed, transitions). `review.py`: QA of renders.
- `ui.py` + `ui_static/` (`index.html` timeline, `editor.js`/`editor.css` media library, import/export, jobs): `cstudio ui`, a stdlib HTTP server (Range support for seeking) and vanilla JS; polls the EDL mtime and auto-renders the preview. Every POST needs the per-run token embedded in the page plus a local Host/Origin.

## Conventions
- Clip `in`/`out` are source seconds; everything else is timeline seconds.
- Keep the core dependency-free beyond ffmpeg + Pillow; heavier tools run through `uvx` on demand.
- Any new EDL field must be documented in `skills/edl/reference.md` (the skill is the user-facing spec).
- Run commands with `uv run cstudio …` from the repo, or the installed `cstudio`.

## Testing
No unit tests yet. Smoke test: `cstudio init /tmp/ws && cd /tmp/ws && cstudio ingest <some media> && cstudio validate edits/x.edl.json && cstudio render edits/x.edl.json --preview && cstudio review renders/x-preview.mp4 --edl edits/x.edl.json`, then look at the review sheet.
