# Reelsmith

[English](README.md) | **Tiếng Việt**

Bộ công cụ edit video cho Claude Code. **Edit bất kỳ video nào chỉ bằng cách nói chuyện với Claude**: vlog, du lịch, phỏng vấn, talking-head, TikTok/Reels/Shorts, YouTube, slideshow ảnh, video highlight, ...

Claude không "xem" video được, nên repo này cho Claude:

- **Mắt**: `cstudio ingest` biến footage thành thứ Claude đọc được: contact sheet (ảnh lưới các khung hình, có timestamp), danh sách cắt cảnh, loudness, các đoạn im lặng, transcript từng chữ.
- **Tay**: toàn bộ bản edit là **một file JSON (EDL)**. Claude viết và sửa EDL, rồi `cstudio render` biên dịch nó thành một lệnh ffmpeg.
- **Trình dựng trên trình duyệt**: `cstudio ui` mở workspace trên localhost. Import video, âm thanh, ảnh (kéo thả, hoặc dùng file có sẵn tại chỗ), xem trong thư viện media, đặt điểm vào/ra rồi thêm vào timeline, xem timeline (thumbnail, sóng âm, từng frame), và xuất video (9:16, 16:9, 1:1, 4:5, 4K), âm thanh (MP3/M4A/WAV) hoặc phụ đề (.srt). Timeline tự vẽ lại trong khoảng 1 giây mỗi khi Claude sửa EDL, và bản xem trước được render lại ở chế độ nền. Viết bằng HTML/CSS/JS thuần, server Python thư viện chuẩn: không cần Node hay npm.
- **Bước kiểm tra**: `cstudio review` đo loudness, khung đen, đoạn im lặng và xuất contact sheet của bản render để Claude tự soát lỗi.
- **Kỹ năng**: các skill trong `skills/` dạy Claude quy trình làm việc của một editor.

## Cài đặt

Cần có: `ffmpeg` và `uv` (macOS: `brew install ffmpeg uv`).

```bash
git clone https://github.com/vumhvo/reelsmith.git && cd reelsmith && ./scripts/install.sh
```

Script này cài lệnh `cstudio` (bản editable, sửa code là có hiệu lực ngay) và in hướng dẫn thêm skills vào Claude Code.

Thêm skills dưới dạng plugin (chạy trong Claude Code):

```
/plugin marketplace add vumhvo/reelsmith
/plugin install reelsmith@reelsmith
```

## Cách dùng

Mở Claude Code ở **bất kỳ thư mục nào** chứa video của bạn và nói điều bạn muốn, ví dụ:

> Cắt 4 clip này thành video TikTok 30 giây, có nhạc `song.mp3`, phụ đề tiếng Việt, mở đầu bằng cảnh đẹp nhất.

Claude làm theo skill `video-studio`: `init` → `ingest` → đọc contact sheet và transcript → đề xuất kế hoạch → viết `edits/main.edl.json` → render preview → review → render bản cuối.

Bạn cũng có thể tự chạy từng lệnh:

```bash
cstudio init                     # biến thư mục hiện tại thành workspace
cstudio ingest footage/ music/   # phân tích (thêm --transcribe --lang vi để có transcript)
cstudio media                    # liệt kê media id
cstudio sheet <id> --start 10 --end 20   # zoom vào một đoạn
cstudio validate edits/main.edl.json
cstudio ui edits/main.edl.json               # xem timeline trên trình duyệt (http://localhost:8765)
cstudio render edits/main.edl.json --preview
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json
cstudio render edits/main.edl.json
```

## EDL làm được gì

Cắt/ghép, đổi tốc độ, khoảng 35 kiểu transition (xfade), chuyển khung 16:9 ↔ 9:16 (cover có điểm focus, contain, blur), zoom tĩnh và Ken Burns, chỉnh màu (eq/LUT), fade, ảnh tĩnh, màn tiêu đề màu, chữ và tiêu đề, logo, phụ đề tự động kiểu karaoke (lấy từ transcript, tự khớp lại sau mỗi lần cắt), nhạc nền tự hạ âm lượng khi có lời nói, voice-over, chuẩn hoá loudness (−14 LUFS). Việc gì EDL chưa làm được thì dùng filter ffmpeg thô cho từng clip (`vf`/`af`) hoặc skill `ffmpeg-recipes`.

Schema đầy đủ: [skills/edl/reference.md](skills/edl/reference.md).

## Các skill

| Skill | Dùng để |
|---|---|
| `video-studio` | Quy trình edit từ đầu đến cuối (điểm bắt đầu) |
| `edl` | Schema EDL, các mẫu và ví dụ |
| `captions` | Transcript, phụ đề, kiểu chữ phụ đề, xuất SRT |
| `rough-cut` | Edit theo lời nói: phỏng vấn, podcast, talking-head |
| `short-form` | TikTok/Reels/Shorts: hook, nhịp dựng, vùng an toàn, cắt theo beat |
| `ffmpeg-recipes` | Các thao tác lẻ ngoài EDL |

## Cấu trúc

```
src/studio/        lệnh `cstudio` (Python, chỉ phụ thuộc ffmpeg + Pillow)
skills/            skill cho Claude (đóng gói thành plugin qua .claude-plugin/)
examples/          EDL mẫu
scripts/install.sh
```

Workspace của người dùng (tạo bởi `cstudio init`) tách biệt với repo này:

```
<thư mục video của bạn>/
  studio.json  .studio/(media.json, analysis/, proxy/)  edits/*.edl.json  renders/
```

## Ghi chú

- ffmpeg của Homebrew không có `drawtext`/`libass`, nên chữ và phụ đề được vẽ bằng Pillow rồi overlay. Không cần cài thêm gì.
- Transcript dùng `mlx-whisper` (chạy qua `uvx`, lần đầu tải model khoảng 1.6 GB). Font mặc định hỗ trợ đầy đủ dấu tiếng Việt.
- Video HDR (HLG/PQ) chưa được chuyển màu; `cstudio media` sẽ đánh dấu `hdr`.

## Giấy phép

[MIT](LICENSE)
