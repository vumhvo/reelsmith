#!/usr/bin/env bash
# Install the `cstudio` CLI (editable: code changes apply immediately) and show how to add the skills.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for bin in ffmpeg ffprobe uv; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "missing: $bin  (macOS: brew install ffmpeg uv)" >&2
    exit 1
  fi
done

uv tool install --force --editable "$ROOT"
echo
echo "cstudio installed: $(command -v cstudio || echo "~/.local/bin/cstudio (add ~/.local/bin to PATH)")"
echo
echo "Add the skills to Claude Code (run inside Claude Code):"
echo "  /plugin marketplace add \"$ROOT\""
echo "  /plugin install reelsmith@reelsmith"
echo
echo "Optional: put Be Vietnam Pro (or any .ttf) in $ROOT/assets/fonts/ to use it as the default caption font."
