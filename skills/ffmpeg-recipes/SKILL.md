---
name: ffmpeg-recipes
description: One-off ffmpeg operations that the reelsmith EDL does not cover: beat detection, stabilization, denoise, voice cleanup, reverse, freeze frame, GIF export, extracting audio, picture-in-picture, green screen, compression for messaging apps, converting HDR, splitting long files. Use when a video task needs a direct ffmpeg command or an intermediate file.
---

# ffmpeg recipes

Pattern: produce an **intermediate file** in the workspace (e.g. `.studio/work/`), then use it as a `src` in the EDL. Never overwrite sources. Check the ffmpeg build first if a filter may be missing: `ffmpeg -hide_banner -filters | grep <name>` (Homebrew's build lacks `drawtext`, `subtitles`, `vidstab`, `zscale`, `rubberband`).

## Audio
```bash
# extract audio / a range of it
ffmpeg -i in.mp4 -vn -c:a aac -b:a 192k out.m4a
ffmpeg -ss 12.3 -to 45.0 -i in.mp4 -vn -c:a aac part.m4a
# voice cleanup: high-pass, denoise, gentle compression (also usable as a clip "af")
highpass=f=90,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=10:release=200
# remove a constant hum (50 Hz mains in VN/EU, 60 Hz in US)
bandreject=f=50:width_type=h:w=4,bandreject=f=100:width_type=h:w=4
```

## Beat times (for cut-on-beat)
Onset/energy peaks with ffmpeg only (good enough for clear beats):
```bash
ffmpeg -i song.mp3 -af "lowpass=f=150,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=rms.txt" -f null -
```
then pick local RMS maxima spaced ≥ 60/BPM_max s apart. Better (if allowed to install): `uvx --from librosa python -c "import librosa,sys;y,sr=librosa.load(sys.argv[1]);t,b=librosa.beat.beat_track(y=y,sr=sr,units='time');print(round(float(t)),list(map(lambda x:round(float(x),3),b)))" song.mp3` → tempo and beat times.

## Video fixes
```bash
# stabilize (needs vidstab: brew tap homebrew-ffmpeg/ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libvidstab)
# fallback with stock build: deshake (lighter)
ffmpeg -i in.mp4 -vf deshake -c:a copy stable.mp4
# denoise video (low light)
-vf "hqdn3d=3:3:6:6"
# reverse a short clip (loads into RAM: keep it < ~20 s)
ffmpeg -i in.mp4 -vf reverse -af areverse rev.mp4
# freeze frame: grab a still, then use it as an image clip with duration
ffmpeg -ss 7.5 -i in.mp4 -frames:v 1 freeze.png
# HDR (HLG/PQ) → SDR without zscale: approximate
-vf "colorspace=all=bt709:iall=bt2020:fast=1,eq=saturation=1.1"
```

## Compositing
```bash
# picture-in-picture: small webcam bottom-right
ffmpeg -i main.mp4 -i cam.mp4 -filter_complex "[1:v]scale=iw*0.28:-2[pip];[0:v][pip]overlay=W-w-40:H-h-40" -c:a copy pip.mp4
# green screen
ffmpeg -i bg.mp4 -i fg_green.mp4 -filter_complex "[1:v]chromakey=0x00FF00:0.15:0.05[k];[0:v][k]overlay" out.mp4
```

## Export variants
```bash
# GIF (good palette)
ffmpeg -i in.mp4 -vf "fps=12,scale=480:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" out.gif
# small file for Zalo/Messenger/email (~8 MB for 30 s)
ffmpeg -i in.mp4 -vf "scale=-2:720" -c:v libx264 -crf 28 -preset slow -c:a aac -b:a 96k small.mp4
# hardware encode (fast, bigger files) on macOS
-c:v h264_videotoolbox -b:v 8M
# split a long recording into 10-minute parts without re-encoding
ffmpeg -i long.mp4 -c copy -f segment -segment_time 600 -reset_timestamps 1 part_%02d.mp4
```

## Text without drawtext
The stock Homebrew ffmpeg has no `drawtext`; use EDL `text` items (rendered with Pillow), or make a transparent PNG and `overlay` it.
