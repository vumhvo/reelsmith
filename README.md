# Reelsmith

Video editing toolkit for Claude Code. Bộ công cụ để **edit bất kỳ video nào bằng cách nói chuyện với Claude**: vlog, du lịch, phỏng vấn, talking-head, TikTok/Reels/Shorts, YouTube, slideshow ảnh, highlight, ...

Claude không "xem" video được, nên repo này cho Claude:

- **Mắt** – `cstudio ingest` biến footage thành thứ Claude đọc được: contact sheet (ảnh lưới có timestamp), danh sách cắt cảnh, loudness, đoạn im lặng, transcript từng chữ.
- **Tay** – toàn bộ bản edit là **một file JSON (EDL)**. Claude viết/sửa EDL, `cstudio render` biên dịch thành một lệnh ffmpeg.
- **Kiểm tra** – `cstudio review` đo loudness, khung đen, im lặng và xuất contact sheet của bản render để Claude tự soát lỗi.
- **Kỹ năng** – các skill trong `skills/` dạy Claude quy trình làm việc của một editor.

## Cài đặt

Cần: `ffmpeg`, `uv` (macOS: `brew install ffmpeg uv`).

```bash
git clone https://github.com/vumhvo/reelsmith.git && cd reelsmith && ./scripts/install.sh
```

Script này cài lệnh `cstudio` (bản editable, sửa code là có hiệu lực ngay) và in hướng dẫn cài skills vào Claude Code.

Cài skills dưới dạng plugin (trong Claude Code):

```
/plugin marketplace add vumhvo/reelsmith
/plugin install reelsmith@reelsmith
```

## Dùng

Mở Claude Code ở **bất kỳ thư mục nào** chứa video của bạn và nói điều bạn muốn, ví dụ:

> Cắt 4 clip này thành video TikTok 30 giây, có nhạc `song.mp3`, phụ đề tiếng Việt, mở đầu bằng cảnh đẹp nhất.

Claude sẽ dùng skill `video-studio`: `init` → `ingest` → xem contact sheet / transcript → đề xuất kế hoạch → viết `edits/main.edl.json` → render preview → review → render final.

Tự chạy bằng tay cũng được:

```bash
cstudio init                     # biến thư mục hiện tại thành workspace
cstudio ingest footage/ music/   # phân tích (thêm --transcribe --lang vi để có transcript)
cstudio media                    # liệt kê media id
cstudio sheet <id> --start 10 --end 20   # zoom vào 1 đoạn
cstudio validate edits/main.edl.json
cstudio render edits/main.edl.json --preview
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json
cstudio render edits/main.edl.json
```

## EDL làm được gì

Cắt/ghép, đổi tốc độ, transition (xfade), chuyển khung 16:9 ↔ 9:16 (cover/contain/blur, điểm focus, crop), zoom tĩnh và Ken Burns, chỉnh màu (eq/LUT), fade, ảnh tĩnh, màn màu, chữ/tiêu đề, logo, phụ đề tự động kiểu karaoke (theo transcript, tự khớp sau khi cắt), nhạc nền với ducking, voice-over, chuẩn hoá loudness. Thứ gì EDL chưa có: dùng `vf`/`af` (filter ffmpeg thô) hoặc skill `ffmpeg-recipes`.

Schema đầy đủ: [skills/edl/reference.md](skills/edl/reference.md).

## Cấu trúc

```
src/studio/        CLI `cstudio` (Python, chỉ phụ thuộc ffmpeg + Pillow)
skills/            skill cho Claude (đóng gói thành plugin qua .claude-plugin/)
examples/          EDL mẫu
scripts/install.sh
```

Workspace của người dùng (tạo bởi `cstudio init`) độc lập với repo này:

```
<thư mục video>/
  studio.json  .studio/(media.json, analysis/, proxy/)  edits/*.edl.json  renders/
```

## Ghi chú

- ffmpeg của Homebrew không có `drawtext`/`libass`, nên chữ và phụ đề được vẽ bằng Pillow rồi overlay. Không cần cài thêm gì.
- Transcript dùng `mlx-whisper` (chạy qua `uvx`, lần đầu tải model khoảng 1.6 GB). Font mặc định hỗ trợ tiếng Việt.
- Video HDR (HLG/PQ) chưa được tone-map; `cstudio media` sẽ đánh dấu `hdr`.
