# Hướng dẫn sử dụng Reelsmith

> Edit video bằng cách nói chuyện với Claude. Không cần biết dựng phim, không cần mở phần mềm edit nặng nề.

Tài liệu này viết cho **hai kiểu người đọc**:

- **Bạn chưa từng edit video**: đọc theo thứ tự từ trên xuống. Mục [Thuật ngữ](#thuat-ngu) giải thích mọi từ chuyên môn bằng lời thường. Đọc tới mục [Bắt đầu nhanh](#bat-dau-nhanh) là bạn đã làm được video đầu tiên.
- **Bạn đã quen Premiere, CapCut, DaVinci…**: nhảy thẳng tới [Cách Reelsmith hoạt động](#cach-hoat-dong), [Trình dựng trên trình duyệt](#trinh-dung) và [EDL](#edl).

Read in English: [guide.md](guide.md).

---

<a id="muc-luc"></a>
## Mục lục

1. [Reelsmith là gì?](#gioi-thieu)
2. [Cách Reelsmith hoạt động](#cach-hoat-dong)
3. [Thuật ngữ cần biết](#thuat-ngu)
4. [Cài đặt](#cai-dat)
5. [Bắt đầu nhanh: video đầu tiên trong 10 phút](#bat-dau-nhanh)
6. [Cách nhờ Claude để có video ưng ý](#nho-claude)
   - [Những thông tin nên nói ngay từ đầu](#thong-tin-nen-noi)
   - [Câu mẫu theo từng loại video](#cau-mau)
   - [Yêu cầu sửa sau khi xem bản nháp](#yeu-cau-sua)
7. [Trình dựng trên trình duyệt (`cstudio ui`)](#trinh-dung)
   - [Mở trình dựng](#mo-trinh-dung)
   - [Các vùng trên màn hình](#cac-vung)
   - [Thêm media và đưa lên timeline](#them-media)
   - [Chỉnh sửa trên timeline](#chinh-timeline)
   - [Chỉnh thuộc tính và crop](#thuoc-tinh)
   - [Xuất file](#xuat-file)
   - [Phím tắt](#phim-tat)
8. [Tự chạy bằng dòng lệnh](#dong-lenh)
9. [EDL: "công thức" của video](#edl)
10. [Làm gì, nói gì: các việc hay gặp](#cong-thuc)
11. [Tách người khỏi nền (rotoscoping)](#rotoscoping)
12. [Thư mục làm việc trông như thế nào](#thu-muc)
13. [Câu hỏi thường gặp và xử lý sự cố](#faq)
14. [Giới hạn hiện tại](#gioi-han)
15. [Tài liệu tham khảo thêm](#tham-khao)

---

<a id="gioi-thieu"></a>
## 1. Reelsmith là gì?

Reelsmith là bộ công cụ giúp **Claude** (trợ lý AI chạy trong Claude Code) edit video thay bạn. Bạn bỏ video, ảnh, nhạc vào một thư mục, rồi nói kiểu:

> Ghép mấy clip này thành video TikTok 30 giây, dùng nhạc `song.mp3`, thêm phụ đề tiếng Việt, mở đầu bằng cảnh đẹp nhất.

Claude sẽ xem nội dung các clip, đề xuất cách dựng, dựng thử, tự kiểm tra lỗi và xuất ra file `.mp4` hoàn chỉnh.

**Làm được những loại video nào?** Vlog, video du lịch, phỏng vấn, người nói trước camera (talking-head), hướng dẫn, TikTok/Reels/Shorts, video YouTube, slideshow ảnh, video highlight, quảng cáo ngắn…

**Có gì đặc biệt?**

- **Không động vào file gốc.** Video của bạn chỉ được đọc, không bao giờ bị sửa hay xoá. Kết quả luôn ra file mới.
- **Sửa bao nhiêu lần cũng được.** Toàn bộ bản dựng được lưu thành một file "công thức" nhỏ. Muốn đổi nhạc, bỏ một cảnh, đổi chữ… chỉ cần nói, Claude sửa công thức rồi xuất lại.
- **Có giao diện để xem và chỉnh tay.** Nếu thích tự kéo thả, bạn mở trình dựng trên trình duyệt, vừa xem vừa chỉnh. Claude và bạn cùng sửa một bản dựng.
- **Xử lý video ngay trên máy bạn.** Phân tích, nhận dạng giọng nói, tách người khỏi nền và xuất video đều chạy local; file video không bị tải lên đâu cả.

---

<a id="cach-hoat-dong"></a>
## 2. Cách Reelsmith hoạt động

Claude không "xem" video được như người. Reelsmith cho Claude ba thứ:

| Bộ phận | Làm gì | Lệnh |
|---|---|---|
| **Mắt** | Biến video thành thứ Claude đọc được: ảnh lưới các khung hình có ghi thời gian, các điểm chuyển cảnh, độ lớn âm thanh, các đoạn im lặng, lời nói chép lại từng chữ | `cstudio ingest` |
| **Tay** | Claude viết bản dựng vào một file JSON (gọi là **EDL**), rồi lệnh render biến file đó thành video | `cstudio render` |
| **Bước tự kiểm tra** | Đo âm lượng, tìm khung hình đen, đoạn im lặng bất thường, chụp lại các khung hình của video đã xuất để Claude soát lỗi | `cstudio review` |

Quy trình đầy đủ trông như sau:

```
 Thư mục video của bạn
        │
        ▼
 ① init      biến thư mục thành "workspace" (chỗ làm việc)
        │
        ▼
 ② ingest    phân tích: ảnh lưới khung hình, cảnh, âm thanh, lời nói
        │
        ▼
 ③ Claude đọc kết quả phân tích → đề xuất kế hoạch → bạn đồng ý
        │
        ▼
 ④ Claude viết EDL (công thức dựng)  edits/main.edl.json
        │
        ▼
 ⑤ render --preview   xuất bản nháp nhanh, độ phân giải thấp
        │
        ▼
 ⑥ review             tự kiểm tra lỗi → sửa EDL → lặp lại ⑤
        │
        ▼
 ⑦ render             bản cuối  renders/main.mp4
```

Bạn **không phải gõ những lệnh này**. Khi bạn nhờ Claude, nó tự chạy. Bảng lệnh ở [mục 8](#dong-lenh) dành cho ai muốn tự làm.

---

<a id="thuat-ngu"></a>
## 3. Thuật ngữ cần biết

Nếu bạn chưa từng edit video, đây là tất cả những từ bạn sẽ gặp. Đọc một lần là đủ.

### Về video nói chung

| Thuật ngữ | Nghĩa là | Ví dụ dễ hình dung |
|---|---|---|
| **Footage** | Video gốc bạn quay được, chưa cắt | Nguyên liệu chưa sơ chế |
| **Clip** | Một đoạn video lấy ra từ footage | Một lát cắt từ ổ bánh mì |
| **Timeline** | Dải thời gian của video thành phẩm, các clip xếp nối nhau trên đó | Cuộn phim đã nối |
| **Cắt / trim** | Bỏ bớt phần đầu hoặc phần cuối của clip | Cắt bỏ 2 giây rung tay đầu clip |
| **Điểm vào / điểm ra (in / out)** | Giây bắt đầu và giây kết thúc của phần clip được dùng | Lấy từ giây 12 đến giây 18 |
| **Chuyển cảnh (transition)** | Hiệu ứng nối hai clip, thay vì nhảy cảnh đột ngột | Mờ dần, trượt ngang, xoay |
| **Tỉ lệ khung hình** | Hình chữ nhật nằm hay đứng | **9:16** dọc (TikTok, Reels, Shorts) · **16:9** ngang (YouTube) · **1:1** vuông · **4:5** dọc hơi ngắn (bài đăng Instagram) |
| **Reframe** | Đổi video ngang thành dọc (hoặc ngược lại) mà vẫn giữ người/vật chính trong khung | Quay ngang, đăng TikTok dọc |
| **Render / xuất** | Máy tính "nấu" bản dựng thành file video thật | Bấm "Export" trong CapCut |
| **Preview / bản xem** | Bản render nhanh, chất lượng thấp, để xem thử | Nếm thử trước khi dọn ra |
| **B-roll** | Cảnh minh hoạ chèn lên khi ai đó đang nói | Người kể về phố cổ, màn hình chiếu cảnh phố cổ |
| **Ken Burns** | Ảnh tĩnh được phóng to/thu nhỏ từ từ cho có chuyển động | Slideshow ảnh kiểu phim tài liệu |
| **Color grading / chỉnh màu** | Chỉnh sáng, tương phản, độ rực màu | Bộ lọc màu trên Instagram |
| **LUT** | File "bộ lọc màu" có sẵn (đuôi `.cube`) | Preset màu mua trên mạng |

### Về âm thanh và chữ

| Thuật ngữ | Nghĩa là |
|---|---|
| **Nhạc nền** | Nhạc chạy phía dưới video |
| **Ducking** | Tự hạ nhỏ nhạc nền khi có người nói, để nghe rõ lời |
| **Voice-over** | Giọng đọc thu riêng, đặt lên video |
| **Loudness / LUFS** | Đơn vị đo độ to "cảm nhận được". YouTube, TikTok… chuẩn khoảng **−14 LUFS**. Reelsmith tự chỉnh về mức này để video không quá nhỏ hay quá to |
| **Transcript** | Lời nói trong video được chép thành chữ, kèm thời gian của từng chữ |
| **Phụ đề (captions)** | Chữ hiện trên video theo lời nói. **Kiểu karaoke**: chữ đang được nói sáng màu lên |
| **SRT** | File phụ đề rời (`.srt`) để tải kèm lên YouTube |
| **Safe zone / vùng an toàn** | Phần màn hình không bị nút like, tên tài khoản, mô tả… của TikTok/Reels che mất |

### Về Reelsmith

| Thuật ngữ | Nghĩa là |
|---|---|
| **Workspace** | Thư mục chứa video của bạn, đã được `cstudio init` đánh dấu (có file `studio.json`) |
| **Media id** | Tên ngắn Reelsmith đặt cho mỗi file, ví dụ `walking`, `interview`. Dùng thay cho đường dẫn dài |
| **Contact sheet** | Một ảnh ghép lưới nhiều khung hình của video, mỗi ô ghi thời gian. Đây là "đôi mắt" của Claude |
| **EDL** (Edit Decision List) | File JSON ghi lại toàn bộ bản dựng: dùng clip nào, đoạn nào, chữ gì, nhạc gì. Xem [mục 9](#edl) |
| **Proxy** | Bản sao nhẹ 720p của video 4K, giúp xem thử nhanh hơn |
| **Skill** | Bộ hướng dẫn dạy Claude cách làm việc như một editor (ví dụ: cách làm video TikTok, cách làm phụ đề) |
| **Rotoscoping / mask** | Tách riêng một người hay vật ra khỏi nền, khung hình nào cũng theo đúng người đó. Dùng để xoá phông, làm mờ nền, đặt chữ sau lưng người… |

---

<a id="cai-dat"></a>
## 4. Cài đặt

### Cần có

| Thứ cần | Để làm gì | Cài thế nào (macOS) |
|---|---|---|
| **Claude Code** | Trợ lý AI sẽ edit video cho bạn | Ứng dụng Claude (tab Code) hoặc Claude Code trong Terminal |
| **ffmpeg** | "Động cơ" xử lý video | `brew install ffmpeg` |
| **uv** | Cài và chạy công cụ Python | `brew install uv` |
| **git** | Tải mã nguồn Reelsmith | Có sẵn trên macOS (hoặc `xcode-select --install`) |

> Chưa có Homebrew (`brew`)? Xem hướng dẫn cài ở [brew.sh](https://brew.sh).
>
> Nên dùng máy Mac chip Apple (M1 trở lên): phần nhận dạng giọng nói (làm phụ đề) dùng `mlx-whisper`, chỉ chạy trên chip này. Các phần khác chạy được ở mọi nơi có ffmpeg và uv.

### Các bước

**Bước 1.** Cài ffmpeg và uv (bỏ qua nếu đã có):

```bash
brew install ffmpeg uv
```

**Bước 2.** Tải Reelsmith và cài lệnh `cstudio`:

```bash
git clone https://github.com/vumhvo/reelsmith.git && cd reelsmith && ./scripts/install.sh
```

Script sẽ báo nơi cài `cstudio`. Nếu nó nhắc thêm `~/.local/bin` vào PATH, làm theo hướng dẫn nó in ra.

**Bước 3.** Thêm các skill vào Claude Code. Mở Claude Code rồi gõ hai dòng sau vào khung chat:

```
/plugin marketplace add vumhvo/reelsmith
/plugin install reelsmith@reelsmith
```

**Bước 4 (tuỳ chọn).** Muốn chữ và phụ đề dùng font Be Vietnam Pro (đẹp với tiếng Việt), đặt file `.ttf` vào thư mục `assets/fonts/` trong repo Reelsmith. Không có cũng không sao: font mặc định vẫn hiển thị đủ dấu tiếng Việt.

### Kiểm tra cài đặt

```bash
cstudio --help
```

Nếu thấy danh sách lệnh (`init`, `ingest`, `render`…) là đã xong.

---

<a id="bat-dau-nhanh"></a>
## 5. Bắt đầu nhanh: video đầu tiên trong 10 phút

**1. Gom nguyên liệu vào một thư mục.** Ví dụ `~/Videos/da-lat/` chứa vài clip quay bằng điện thoại, vài tấm ảnh, một file nhạc.

```
da-lat/
  IMG_0012.MOV
  IMG_0015.MOV
  IMG_0021.MOV
  hoang-hon.jpg
  nhac.mp3
```

**2. Mở Claude Code trong thư mục đó.** Trong ứng dụng Claude, chọn thư mục `da-lat` làm thư mục làm việc. (Nếu dùng Terminal: `cd ~/Videos/da-lat && claude`.)

**3. Nói điều bạn muốn.** Ví dụ:

> Làm cho mình một video TikTok khoảng 30 giây từ các clip trong thư mục này, dùng `nhac.mp3` làm nhạc nền, có tiêu đề "48 giờ ở Đà Lạt" ở đầu. Mở đầu bằng cảnh đẹp nhất.

**4. Trả lời vài câu hỏi của Claude (nếu có).** Claude sẽ phân tích video, rồi tóm tắt cho bạn những gì nó thấy trong từng clip và đề xuất thứ tự cảnh. Đọc qua, đồng ý hoặc góp ý ("bỏ clip quay đường phố", "cho cảnh hồ lên đầu").

**5. Xem bản nháp.** Claude xuất bản xem thử vào `renders/main-preview.mp4`. Nếu muốn xem trực quan, nói:

> Mở trình dựng cho mình xem.

Trình duyệt sẽ mở timeline, bạn bấm phát để xem.

**6. Góp ý và chốt.** Ví dụ: "chữ tiêu đề to hơn", "cắt ngắn cảnh thứ ba", "nhạc nhỏ lại một chút". Khi ưng, nói "xuất bản cuối". File hoàn chỉnh nằm ở `renders/main.mp4`.

Xong. Bạn vừa làm video mà không cần biết dựng phim.

> **Mẹo:** Lần đầu bật phụ đề, máy sẽ tải mô hình nhận dạng giọng nói khoảng 1,6 GB. Lần sau thì nhanh.

---

<a id="nho-claude"></a>
## 6. Cách nhờ Claude để có video ưng ý

Claude làm tốt nhất khi biết rõ bạn muốn gì. Bạn không cần dùng từ chuyên môn, cứ nói như đang dặn một người bạn biết edit.

<a id="thong-tin-nen-noi"></a>
### Những thông tin nên nói ngay từ đầu

| Thông tin | Tại sao quan trọng | Ví dụ |
|---|---|---|
| **Đăng ở đâu** | Quyết định khung dọc hay ngang, độ dài, nhịp | "đăng TikTok", "lên YouTube", "đăng bài Instagram" |
| **Dài bao lâu** | Claude chọn bao nhiêu cảnh | "khoảng 30 giây", "dưới 1 phút" |
| **Cảm giác / nhịp** | Cắt nhanh hay chậm, chuyển cảnh kiểu gì | "sôi động", "nhẹ nhàng, chill", "điện ảnh" |
| **Nhạc** | File nào, to hay nhỏ | "dùng `song.mp3`", "không nhạc, giữ tiếng gốc" |
| **Phụ đề** | Có hay không, ngôn ngữ gì | "phụ đề tiếng Việt kiểu karaoke" |
| **Cảnh bắt buộc** | Để Claude không bỏ sót | "phải có cảnh thổi nến", "kết bằng cảnh cả nhóm" |
| **Chữ trên màn hình** | Tiêu đề, tên người, lời kêu gọi | "ghi tên 'Nguyễn Văn A, Founder' khi anh ấy xuất hiện" |

Thiếu thông tin nào, Claude sẽ hỏi hoặc chọn mặc định hợp lý (ví dụ: TikTok thì 15 đến 35 giây).

<a id="cau-mau"></a>
### Câu mẫu theo từng loại video

**Video ngắn dọc (TikTok / Reels / Shorts)**

> Dựng video Reels 20 giây từ các clip này, nhịp nhanh theo nhạc `beat.mp3`, mở đầu bằng chữ to "POV: lần đầu đi Hà Giang", phụ đề nếu có người nói.

**Vlog du lịch dài (YouTube)**

> Làm video YouTube 16:9 khoảng 5 phút từ chuyến đi này, giữ tiếng gốc, nhạc nền nhẹ tự nhỏ đi khi mình nói, chuyển cảnh mờ giữa các ngày, có tiêu đề "Ngày 1", "Ngày 2"…

**Phỏng vấn / podcast / người nói trước camera**

> Đây là buổi phỏng vấn 40 phút. Chọn những câu trả lời hay nhất thành video 3 phút, bỏ các đoạn "ờ", "ừm" và khoảng lặng, thêm phụ đề tiếng Việt và tên khách mời ở góc dưới.

Claude sẽ gửi trước một "bản dựng trên giấy" (danh sách câu nói được giữ, kèm thời gian) để bạn duyệt trước khi dựng.

**Slideshow ảnh**

> Biến 15 tấm ảnh cưới này thành video 45 giây, mỗi ảnh chuyển động nhẹ, chuyển cảnh mờ, nhạc `wedding.mp3`, kết bằng chữ "Cảm ơn mọi người".

**Chỉ thêm phụ đề cho video có sẵn**

> Thêm phụ đề tiếng Việt cho `talk.mp4`, xuất thêm file .srt để mình tải lên YouTube.

**Xoá phông, làm mờ nền, che mặt** (xem thêm [mục 11](#rotoscoping))

> Ở clip `dance.mp4` từ giây 5 đến 12, làm nền đen trắng còn người nhảy giữ màu.

> Làm mờ mặt người đi đường mặc áo đỏ trong clip `street.mp4`.

**Chuyển video ngang thành dọc**

> Đổi video `presentation.mp4` thành khung dọc 9:16 cho TikTok, giữ người nói ở giữa khung.

<a id="yeu-cau-sua"></a>
### Yêu cầu sửa sau khi xem bản nháp

Cứ nói cụ thể điều bạn thấy. Claude chỉ sửa file công thức (EDL) rồi xuất lại, rất nhanh.

| Bạn thấy | Bạn nói |
|---|---|
| Một cảnh quá dài | "Cảnh ở giây 8 đến 12 dài quá, cắt còn 2 giây" |
| Chữ khó đọc | "Tiêu đề to hơn và có nền đen mờ phía sau" |
| Chữ bị nút TikTok che | "Đưa chữ lên cao hơn một chút" |
| Nhạc át tiếng nói | "Nhạc nhỏ lại, tự giảm khi có người nói" |
| Phụ đề sai chính tả | "Phụ đề ghi 'da lat', sửa thành 'Đà Lạt'" |
| Muốn thêm phiên bản | "Giữ bản này, làm thêm bản 15 giây để chạy quảng cáo" |
| Màu hơi nhạt | "Cho màu rực hơn, tương phản hơn một chút" |
| Muốn hiệu ứng | "Thêm hiệu ứng nháy trắng khi chuyển cảnh theo nhịp nhạc" |

> **Mẹo:** Nhờ Claude làm phiên bản mới (`v2-short`, `teaser`) thay vì ghi đè lên bản bạn đã thích. Bản cũ vẫn còn nguyên để quay lại.

---

<a id="trinh-dung"></a>
## 7. Trình dựng trên trình duyệt (`cstudio ui`)

Đây là giao diện edit chạy trong trình duyệt, ngay trên máy bạn (không cần internet). Bạn có thể:

- **chỉ xem** những gì Claude đang dựng (timeline tự cập nhật trong khoảng 1 giây mỗi khi Claude sửa), hoặc
- **tự chỉnh tay** như một phần mềm edit thông thường, hoặc
- **kết hợp cả hai**: bạn kéo thả, Claude tinh chỉnh, và ngược lại.

<a id="mo-trinh-dung"></a>
### Mở trình dựng

Cách dễ nhất: nói với Claude "mở trình dựng cho mình". Hoặc tự chạy trong thư mục workspace:

```bash
cstudio ui
```

Trình duyệt mở tại `http://localhost:8765`. Nếu workspace chưa có bản dựng nào, trang sẽ tạo sẵn một bản trống `edits/main.edl.json` để bạn dựng từ đầu.

Giao diện tự hiện tiếng Việt nếu trình duyệt của bạn đặt tiếng Việt. Muốn ép tiếng Việt, thêm `?lang=vi` vào cuối địa chỉ.

<a id="cac-vung"></a>
### Các vùng trên màn hình

| Vùng | Có gì |
|---|---|
| **Thanh trên cùng** | Chọn bản dựng (EDL) đang mở · nút **Render bản xem** (kèm trạng thái: đã mới nhất / đã cũ / đang render) · nút **Import** · nút **Xuất file** |
| **Thư viện** | Tất cả video, âm thanh, ảnh trong workspace, lọc theo loại. Chuột phải để mở, sao chép đường dẫn, hoặc gỡ khỏi thư viện |
| **Khung xem** | Xem video. Hai chế độ: **Bản xem** (bản đã render, đầy đủ chữ và hiệu ứng) và **Khung nguồn** (xem từng khung hình gốc ngay lập tức). Khi chỉnh thuộc tính, chế độ **Live** cho thấy kết quả gần đúng tức thì |
| **Nút điều khiển** | Về đầu · lùi 1 khung hình · phát/dừng · tới 1 khung hình |
| **Timeline** | Các hàng (track): **Video** (các clip, có ảnh thu nhỏ và chuyển cảnh), **Tiếng clip** (sóng âm, đoạn im lặng), **Âm thanh** (nhạc, voice-over), **Chữ**, **Ảnh** (logo, sticker), **Phụ đề** |
| **Bảng thuộc tính** (bên phải) | Bấm vào một khối trên timeline để xem và chỉnh mọi thông số của nó |
| **Tab Timeline / Nguồn** | Mở một file từ thư viện sẽ thêm tab **Nguồn: tên-file** để xem file gốc và chọn đoạn cần dùng |

<a id="them-media"></a>
### Thêm media và đưa lên timeline

**Nhập file vào:**

- **Kéo thả** file video, âm thanh, ảnh vào trang, hoặc
- Bấm **Import** rồi chọn file. Bạn cũng có thể dán đường dẫn một file hay thư mục có sẵn trên máy: file được **dùng tại chỗ, không chép lại**.
- Tick **Nhận dạng giọng nói** (chọn ngôn ngữ) nếu muốn làm phụ đề cho file đó.

File tải lên được chép vào `footage/` (video, ảnh) hoặc `audio/` (âm thanh) trong workspace rồi tự động được phân tích. Xem tiến độ ở danh sách job.

**Chọn đoạn cần dùng và thêm vào timeline:**

1. Mở file trong thư viện (bấm vào file, hoặc chuột phải → **Mở trong màn xem nguồn**).
2. Tua đến chỗ muốn bắt đầu, bấm **[ Vào** (phím `I`).
3. Tua đến chỗ muốn kết thúc, bấm **Ra ]** (phím `O`).
4. Bấm **Thêm vào timeline** (phím `Enter`) để thêm thành clip video, hoặc **Thêm làm track âm thanh** để dùng làm nhạc/tiếng.

**Gỡ file khỏi thư viện:** chỉ gỡ được file chưa dùng trên timeline. Bạn chọn giữ file trên máy, hoặc chuyển bản chép trong workspace vào Thùng rác.

<a id="chinh-timeline"></a>
### Chỉnh sửa trên timeline

| Muốn | Làm |
|---|---|
| Cắt bớt đầu/cuối clip | Kéo mép trái/phải của khối (khớp theo từng khung hình) |
| Đổi thứ tự clip | Kéo khối sang vị trí mới |
| Cắt đôi một clip | Đặt đầu phát (playhead) vào chỗ cần cắt, bấm `B` |
| Cắt phần đầu tới đầu phát | `Q` |
| Cắt phần cuối từ đầu phát | `W` |
| Xoá | Chọn khối, bấm `Delete` |
| Thêm chữ | `T` (thêm chữ tại đầu phát) |
| Hoàn tác / làm lại | `⌘Z` / `⇧⌘Z` (Windows: `Ctrl+Z` / `Ctrl+Y`) |
| Phóng to/thu nhỏ timeline | `+` / `−`, hoặc giữ `⌘`/`Ctrl` và cuộn chuột |

**Menu chuột phải** có thêm: cắt đôi tại đây, nhân bản, tắt/bật tiếng clip, thêm/bỏ chuyển cảnh, dời điểm bắt đầu, thêm chữ tại đây, sao chép timecode, **lưu frame hiện tại ra ảnh PNG** (đầy đủ chữ và hiệu ứng), hiện file trong Finder.

Mọi thao tác được lưu thẳng vào file EDL. Nếu Claude vừa sửa cùng lúc, trang sẽ báo, tự tải lại bản mới nhất và bạn chỉ cần thao tác lại.

<a id="thuoc-tinh"></a>
### Chỉnh thuộc tính và crop

Bấm một khối trên timeline, bảng bên phải hiện các nhóm:

- **Clip video:** điểm vào/ra trong file gốc, tốc độ, cách lấp khung, phóng to, tâm khung (X, Y), độ sáng, tương phản, độ bão hoà, gamma, hiện dần/mờ dần, kiểu và thời lượng chuyển cảnh, âm lượng, tắt tiếng, bỏ khỏi phụ đề.
- **Chữ:** nội dung, thời gian bắt đầu/kết thúc, vị trí, neo, căn lề, cỡ chữ, màu, viền, nền chữ, bóng, chữ hoa/thường.
- **Ảnh (logo):** thời gian, vị trí, chiều rộng, độ mờ.
- **Âm thanh:** bắt đầu ở đâu, âm lượng, lặp lại, hiện dần/mờ dần, tự giảm khi có tiếng nói.

Nút **Lấy theo playhead** điền thời gian hiện tại vào ô cho nhanh. Mục **Mục EDL** cho xem đoạn JSON gốc của khối đó.

**Crop (cắt khung):** chọn clip → **Sửa crop**, kéo khung trên màn hình. Có thể khoá tỉ lệ (**Theo khung xuất**, hoặc **Tự do**). `Enter` để áp dụng, `Esc` để huỷ. **Bỏ crop** để quay về khung gốc.

<a id="xuat-file"></a>
### Xuất file

Bấm **Xuất file** và chọn:

| Loại | Tuỳ chọn |
|---|---|
| **Video** | Khung hình: Như trong EDL, 9:16, 16:9, 1:1, 4:5, 4K · Chất lượng: Cao / Tiêu chuẩn / File nhẹ · Chỉ xuất một đoạn (từ giây… đến giây…) |
| **Âm thanh** | MP3, M4A hoặc WAV (bản mix đầy đủ: tiếng clip + nhạc + voice-over) |
| **Phụ đề .srt** | File phụ đề rời, dùng cho YouTube |

File được ghi vào thư mục `renders/` của workspace. Khi xong, bấm **Tải về** hoặc **Hiện trong Finder**.

<a id="phim-tat"></a>
### Phím tắt

**Timeline**

| Phím | Tác dụng |
|---|---|
| `Space` | Phát / dừng |
| `←` `→` | Lùi / tới 1 khung hình |
| `Shift` + `←` `→` | Lùi / tới 1 giây |
| `Home` / `End` | Về đầu / tới cuối |
| `+` / `−` | Phóng to / thu nhỏ timeline |
| `S` | Đổi giữa Bản xem và Khung nguồn |
| `B` | Cắt đôi tại đầu phát |
| `Q` / `W` | Cắt đầu / cắt đuôi tới đầu phát |
| `T` | Thêm chữ |
| `Delete` | Xoá khối đang chọn |
| `⌘Z` / `⇧⌘Z` | Hoàn tác / làm lại |

**Màn xem nguồn** (khi đang mở một file từ thư viện)

| Phím | Tác dụng |
|---|---|
| `Space` | Phát / dừng |
| `←` `→` · `Shift` + `←` `→` | Lùi/tới 1 khung hình · 1 giây |
| `I` / `O` | Đặt điểm vào / điểm ra |
| `Enter` | Thêm đoạn đã chọn vào timeline |
| `Esc` | Đóng màn xem nguồn |

---

<a id="dong-lenh"></a>
## 8. Tự chạy bằng dòng lệnh

Phần này cho ai muốn tự điều khiển từng bước. Mọi lệnh chạy **bên trong thư mục workspace**.

### Quy trình tối thiểu

```bash
cstudio init                                   # 1. biến thư mục hiện tại thành workspace
cstudio ingest                                 # 2. phân tích mọi file trong thư mục
cstudio media                                  # 3. xem danh sách file và media id
# 4. viết edits/main.edl.json (xem mục 9), hoặc nhờ Claude viết
cstudio validate edits/main.edl.json           # 5. kiểm tra lỗi, in bảng timeline
cstudio render edits/main.edl.json --preview   # 6. xuất bản nháp nhanh
cstudio review renders/main-preview.mp4 --edl edits/main.edl.json   # 7. tự kiểm tra
cstudio render edits/main.edl.json             # 8. xuất bản cuối → renders/main.mp4
```

### Tất cả các lệnh

| Lệnh | Làm gì | Tuỳ chọn hay dùng |
|---|---|---|
| `cstudio init [thư-mục]` | Tạo workspace | `--name` |
| `cstudio ingest [file/thư-mục…]` | Đăng ký và phân tích media: contact sheet, cảnh, âm lượng, khoảng lặng | `--transcribe --lang vi` (chép lời) · `--proxy` (bản nhẹ cho video 4K dài) · `--force` (phân tích lại) |
| `cstudio media` | Liệt kê media: id, thời lượng, kích thước, có tiếng không, có transcript không (`T`), có phải HDR không | `--json` |
| `cstudio probe <file>` | Thông tin chi tiết một file | |
| `cstudio sheet <id>` | Contact sheet của một đoạn (để xem kỹ) | `--start 10 --end 20 --count 12` |
| `cstudio frame <id> <giây>` | Xuất một khung hình | `--grid` (vẽ lưới toạ độ 0–1, dùng khi tách người) |
| `cstudio transcribe [id…]` | Chép lời nói thành chữ, kèm thời gian từng chữ | `--lang vi` · `--prompt "Đà Lạt, Claude"` (gợi ý chính tả tên riêng) |
| `cstudio validate <edl>` | Kiểm tra EDL, in bảng timeline (mỗi clip bắt đầu/kết thúc ở giây nào) | |
| `cstudio captions <edl>` | Tạo phụ đề theo bản dựng | `--srt out.srt` · `--json file.json` (để sửa tay) · `--show 40` |
| `cstudio render <edl>` | Xuất video | `--preview` (nửa độ phân giải, nhanh) · `--range 10:20` (chỉ xuất đoạn này) · `-o file.mp4` · `--dry-run` |
| `cstudio review <video>` | Kiểm tra video đã xuất: âm lượng, khung đen, khoảng lặng, ảnh tổng quan | `--edl <edl>` (so với độ dài mong đợi) |
| `cstudio ui [edl]` | Mở trình dựng trên trình duyệt | `--port` · `--no-open` · `--no-render` |
| `cstudio roto <id>` | Tách người/vật thể khỏi nền (xem [mục 11](#rotoscoping)) | `--start --end --pos x,y --name` |
| `cstudio cutout <tên>` | Xuất người đã tách ra nền trong suốt cho phần mềm khác | `--format mov\|webm\|png\|mp4` |

Mỗi lệnh có `--help` để xem đầy đủ, ví dụ `cstudio render --help`.

---

<a id="edl"></a>
## 9. EDL: "công thức" của video

### Ý tưởng

Thay vì lưu video đã dựng, Reelsmith lưu **công thức** để dựng nó: một file JSON nhỏ trong thư mục `edits/`. Lệnh `render` đọc công thức và "nấu" ra video.

Lợi ích: sửa một con số trong công thức là xong, không phải dựng lại từ đầu. Claude chỉnh công thức rất chính xác; bạn cũng có thể mở file ra sửa bằng tay, hoặc chỉnh qua trình dựng.

### Một ví dụ nhỏ, đọc từng dòng

```json
{
  "output": { "preset": "tiktok" },
  "clips": [
    { "src": "footage/canh-dep.mp4", "in": 2.0, "out": 4.0 },
    { "src": "footage/di-bo.mp4", "in": 0.5, "out": 6.5, "speed": 1.5 },
    { "src": "photos/hoang-hon.jpg", "duration": 2.5,
      "transition": { "type": "fade", "duration": 0.3 } }
  ],
  "audio": [
    { "src": "nhac.mp3", "volume": 0.7, "fade_out": 1.5, "duck": true }
  ],
  "text": [
    { "text": "48 giờ ở Đà Lạt", "start": 0, "end": 2, "y": 0.25, "size": 0.1 }
  ],
  "captions": {}
}
```

| Dòng | Nghĩa |
|---|---|
| `"preset": "tiktok"` | Video dọc 1080×1920, 30 khung hình/giây |
| Clip 1 | Lấy file `canh-dep.mp4` từ giây 2 đến giây 4 |
| Clip 2 | Lấy `di-bo.mp4` từ giây 0,5 đến 6,5, phát nhanh gấp 1,5 lần |
| Clip 3 | Ảnh `hoang-hon.jpg` hiện 2,5 giây, chuyển vào bằng hiệu ứng mờ 0,3 giây |
| `audio` | Nhạc nền âm lượng 70%, nhỏ dần 1,5 giây cuối, tự hạ khi có người nói |
| `text` | Chữ "48 giờ ở Đà Lạt" từ giây 0 đến 2 của video, đặt ở 1/4 chiều cao từ trên xuống, cỡ lớn |
| `captions: {}` | Bật phụ đề tự động (cần chép lời trước) |

### Quy tắc quan trọng nhất: hai loại thời gian

Đây là chỗ dễ nhầm nhất, kể cả với người đã quen edit:

- **`in` / `out` của clip** là giây **trong file gốc**. `"in": 12` nghĩa là "giây thứ 12 của file `di-bo.mp4`".
- **Mọi thời gian khác** (`start`/`end` của chữ, `at` của âm thanh…) là giây **trên video thành phẩm**. `"start": 5` nghĩa là "giây thứ 5 khi người xem bấm phát".

Muốn biết mỗi clip nằm ở giây nào trên video thành phẩm, chạy `cstudio validate edits/main.edl.json`: nó in bảng timeline.

### Các phần của một EDL

| Phần | Chứa gì |
|---|---|
| `output` | Khung hình (preset), âm lượng chuẩn, fade đầu/cuối toàn video, màu tổng thể, chất lượng nén |
| `clips` | Các clip video, ảnh, hoặc màn màu trơn, **xếp nối nhau theo thứ tự** |
| `audio` | Nhạc nền, voice-over, hiệu ứng âm thanh, đặt ở thời điểm bất kỳ |
| `text` | Chữ, tiêu đề, có thể kèm hiệu ứng xuất hiện |
| `images` | Logo, sticker, ảnh đè lên video |
| `captions` | Phụ đề tự động từ lời nói |

### Preset khung hình

| Preset | Kích thước | Dùng cho |
|---|---|---|
| `tiktok`, `reels`, `shorts`, `vertical` | 1080×1920 (9:16) | TikTok, Instagram Reels, YouTube Shorts |
| `youtube`, `1080p` | 1920×1080 (16:9) | YouTube, video ngang |
| `720p` | 1280×720 | Video ngang nhẹ |
| `4k` | 3840×2160 | Video ngang chất lượng cao |
| `square` | 1080×1080 (1:1) | Bài đăng vuông |
| `portrait` | 1080×1350 (4:5) | Bài đăng Instagram dọc |

Đặc tả đầy đủ mọi trường: [skills/edl/reference.md](../skills/edl/reference.md). Hai EDL mẫu: [examples/vertical-travel.edl.json](../examples/vertical-travel.edl.json) (TikTok du lịch) và [examples/talking-head.edl.json](../examples/talking-head.edl.json) (phỏng vấn YouTube).

---

<a id="cong-thuc"></a>
## 10. Làm gì, nói gì: các việc hay gặp

Cột "Nói với Claude" là đủ. Cột "Trong EDL" dành cho ai muốn tự sửa file.

| Việc | Nói với Claude | Trong EDL |
|---|---|---|
| Đổi video ngang sang dọc, giữ người ở giữa | "Chuyển sang 9:16, giữ người nói trong khung" | `"preset": "tiktok"` + clip `"focus": [0.4, 0.5]` |
| Cảnh rộng không muốn bị cắt mất | "Giữ trọn khung cảnh, nền mờ hai bên" | clip `"fit": "blur"` |
| Phóng to vào mặt người | "Zoom gần vào mặt" | `"zoom": 1.15, "focus": [0.5, 0.35]` |
| Ảnh tĩnh có chuyển động | "Cho ảnh phóng to từ từ" | `"zoom": { "from": 1.0, "to": 1.15 }` |
| Quay chậm / tua nhanh | "Cảnh này chậm lại một nửa" | `"speed": 0.5` (hoặc `2` để nhanh gấp đôi) |
| Phát ngược | "Tua ngược cảnh này" | `"reverse": true` |
| Chuyển cảnh | "Chuyển cảnh mờ giữa các ngày" | `"transition": { "type": "fade", "duration": 0.5 }` |
| Chỉnh màu | "Màu rực và tương phản hơn" | `"grade": { "saturation": 1.15, "contrast": 1.08 }` |
| Nhạc nền tự nhỏ khi nói | "Thêm nhạc nhẹ, nhỏ đi khi có người nói" | audio `"volume": 0.2, "duck": true` |
| Tắt tiếng gốc của clip | "Tắt tiếng cảnh này" | `"mute": true` |
| Tiêu đề có hiệu ứng | "Tiêu đề bật lên kiểu nảy" | text `"enter": "pop"` |
| Chữ hiện từng từ | "Chữ hiện dần từng chữ" | text `"reveal": "words"` |
| Logo ở góc | "Đặt `logo.png` góc trên bên phải" | `images: [{ "src": "logo.png", "x": 0.94, "y": 0.06, "anchor": "top-right", "width": 0.14 }]` |
| Phụ đề | "Thêm phụ đề tiếng Việt kiểu karaoke" | `"captions": {}` (sau khi chép lời) |
| Sửa chữ sai trong phụ đề | "Sửa 'da lat' thành 'Đà Lạt'" | `"captions": { "replace": { "da lat": "Đà Lạt" } }` |
| Hiệu ứng theo nhịp | "Nháy trắng và rung nhẹ ở cú cắt" | clip `"fx": ["flash", "shake"]` |
| Ảnh đen trắng, hạt phim | "Cảnh cuối đen trắng, có hạt" | `"fx": ["bw", "grain"]` |
| Bỏ khoảng lặng, từ thừa | "Bỏ các đoạn im lặng và 'ờ, ừm'" | Claude chia clip theo transcript |
| Mở/đóng video bằng màn đen | "Hiện dần lúc đầu, tối dần lúc cuối" | `"output": { "fade_in": 0.5, "fade_out": 0.8 }` |

**Hiệu ứng có sẵn (`fx`)**: `flash` (nháy trắng), `punch` (giật zoom), `shake` (rung), `rgb` (tách màu), `trail` (vệt mờ chuyển động), `bw` (đen trắng), `grain` (hạt phim), `vignette` (tối viền), `impact` (khung hình "va chạm" kiểu anime), `open` (mở khung từ một khe ngang).

**Kiểu chuyển cảnh**: khoảng 35 kiểu như `fade`, `fadeblack`, `dissolve`, `wipeleft`, `slideleft`, `circleopen`, `pixelize`, `zoomin`, cộng thêm `whipleft`/`whipright`/`whipup`/`whipdown` (lia máy nhanh) và `spin` (xoay 360°).

**Hiệu ứng chữ xuất hiện (`enter`)**: `fade`, `pop`, `stamp`, `zoom`, `slideup`, `slidedown`, `slideleft`, `slideright`, `drop`, `blur`, `spin`.

---

<a id="rotoscoping"></a>
## 11. Tách người khỏi nền (rotoscoping)

### Là gì?

Reelsmith dùng mô hình AI **SAM 2** (chạy ngay trên máy bạn) để "khoanh" một người hay vật thể trong video, rồi bám theo nó qua từng khung hình. Phần mềm khác gọi tính năng này là Magic Mask, Roto Brush, Object Mask, hay "tách nền".

### Làm được gì?

| Muốn | Ví dụ câu nói |
|---|---|
| Xoá phông, thay nền màu (phông xanh) | "Thay nền thành màu xanh lá" |
| Thay nền bằng ảnh/video khác | "Đặt người này lên nền `bai-bien.jpg`" |
| Làm mờ hậu cảnh (giống chụp chân dung) | "Làm mờ nền phía sau người nói" |
| Người giữ màu, nền đen trắng | "Nền đen trắng, người giữ màu" |
| Ánh đèn sân khấu (nền tối đi) | "Làm tối nền, chiếu sáng vào người" |
| Viền phát sáng quanh người | "Viền vàng phát sáng quanh vận động viên" |
| Chữ nằm **sau lưng** người | "Chữ 'ĐÀ LẠT' to phía sau người đang đi" |
| Che mặt, biển số, logo | "Làm mờ mặt người đi đường áo đỏ" |
| Xuất người đã tách cho phần mềm khác | "Xuất người này ra nền trong suốt cho Premiere" |

### Claude làm thế nào?

1. Xuất một khung hình có lưới toạ độ để xác định vị trí người/vật.
2. Chấm vài điểm lên người/vật đó (và điểm "không phải" lên thứ cần loại ra), rồi chạy `cstudio roto`.
3. Kiểm tra ảnh xem lại, sửa chỗ mask bị trôi hoặc mất.
4. Gắn mask vào clip trong EDL kèm hiệu ứng, xuất bản nháp, kiểm tra viền.

Tự chạy tay:

```bash
cstudio frame <id> 12.5 --grid                                   # xem khung hình có lưới
cstudio roto <id> --start 12 --end 15 --name nguoi --pos 0.5,0.4 # tách người ở toạ độ (0.5, 0.4)
cstudio cutout nguoi                                             # → renders/nguoi-cutout.mov (nền trong suốt)
```

> **Lưu ý:** Lần đầu chạy, máy cài thêm thư viện AI và tải mô hình (khoảng 180 MB), mất vài phút. Các lần sau, một cảnh 2 giây tốn khoảng 10 đến 30 giây. Nên tách từng cảnh ngắn (dưới 20 giây) và không vắt qua chỗ chuyển cảnh.

Chi tiết: [skills/rotoscoping/SKILL.md](../skills/rotoscoping/SKILL.md).

---

<a id="thu-muc"></a>
## 12. Thư mục làm việc trông như thế nào

Sau khi dùng, thư mục video của bạn sẽ có thêm vài thứ:

```
da-lat/                        ← thư mục của bạn (workspace)
  IMG_0012.MOV …               ← file gốc: không bao giờ bị sửa
  studio.json                  ← đánh dấu đây là workspace
  .studio/                     ← dữ liệu phân tích (thư mục ẩn)
    media.json                 ←   danh sách media và id
    analysis/<id>/             ←   contact sheet, cảnh, âm thanh, transcript của từng file
    proxy/                     ←   bản nhẹ 720p (nếu dùng --proxy)
    roto/<tên>/                ←   mask tách người (nếu dùng)
  footage/  audio/             ← file import qua trình dựng (nếu có)
  edits/
    main.edl.json              ← công thức dựng: giữ lại để sửa sau
  renders/
    main-preview.mp4           ← bản nháp
    main.mp4                   ← bản cuối
    main.srt                   ← phụ đề rời (nếu xuất)
```

**Muốn sửa video tuần sau?** Mở lại Claude Code trong thư mục này và nói "sửa video main, bỏ cảnh thứ hai". Công thức vẫn còn, không phải làm lại từ đầu.

**File gốc nằm chỗ khác?** Không sao. Reelsmith ghi đường dẫn tới file, không chép, không di chuyển.

---

<a id="faq"></a>
## 13. Câu hỏi thường gặp và xử lý sự cố

**Gõ `cstudio` báo "command not found".**
Lệnh được cài vào `~/.local/bin`. Thêm thư mục này vào PATH (script cài đặt có in hướng dẫn), hoặc chạy `uv tool update-shell` rồi mở lại Terminal.

**Render chậm.**
Dùng bản nháp (`--preview`) khi đang chỉnh. Với video 4K dài, phân tích kèm `--proxy` để bản nháp dùng bản nhẹ. Đang chỉnh một đoạn thì chỉ xuất đoạn đó: `--range 10:20`.

**Phụ đề có câu lạ lặp đi lặp lại ("Cảm ơn các bạn đã xem"…) ở đoạn không ai nói.**
Mô hình nhận dạng giọng nói đôi khi "bịa" chữ khi chỉ có tiếng gió, nhạc hay im lặng. Nói với Claude "bỏ phụ đề ở clip này", hoặc đặt `"captions": false` cho clip đó.

**Phụ đề sai tên riêng.**
Nói với Claude tên đúng ("tên khách mời là Nguyễn Thị Hạnh"). Claude sẽ chép lời lại với gợi ý chính tả, hoặc thêm luật sửa chữ `replace`.

**Chữ bị nút like/tên tài khoản của TikTok che.**
Nói "đưa chữ vào vùng an toàn". Vùng an toàn trên khung dọc là khoảng từ 12% đến 78% chiều cao, chừa mép phải.

**Âm thanh quá nhỏ hoặc quá to so với video khác.**
Reelsmith tự chuẩn hoá về −14 LUFS (chuẩn của nền tảng mạng xã hội). Nếu vẫn thấy lệch, xem số đo trong kết quả `cstudio review`.

**Màu video bị nhạt, xám.**
Có thể là video HDR (iPhone hay quay HDR). `cstudio media` sẽ đánh dấu `hdr`. Reelsmith chưa chuyển màu HDR; tắt HDR khi quay, hoặc nhờ Claude tăng tương phản/độ rực.

**Trình dựng báo "EDL vừa được sửa ở nơi khác".**
Claude vừa sửa bản dựng cùng lúc với bạn. Trang đã tự tải bản mới nhất, bạn thao tác lại là được.

**Bản xem trên trình dựng bị "cũ".**
Trang tự render lại sau mỗi thay đổi. Nếu bạn chạy với `--no-render`, bấm **Render bản xem**.

**Muốn dùng kết quả trong Premiere/Final Cut/CapCut/DaVinci.**
Xuất video `.mp4` bình thường, hoặc với người đã tách nền: `cstudio cutout <tên>` (ProRes 4444 có kênh trong suốt), `--format webm` (cho CapCut/web), `--format png` (chuỗi ảnh).

**Video có bị tải lên mạng không?**
Không. Phân tích, nhận dạng giọng nói, tách nền và render đều chạy trên máy bạn. Claude chỉ đọc các file phân tích (ảnh lưới khung hình, transcript, số liệu) để quyết định cách dựng.

---

<a id="gioi-han"></a>
## 14. Giới hạn hiện tại

- **Một track video.** Clip xếp nối tiếp nhau; chưa đặt hai video chồng lên nhau tuỳ ý (ảnh/logo thì được). B-roll đè lên lời nói được làm bằng cách tắt tiếng clip B-roll và phát tiếng người nói từ track âm thanh: Claude biết cách làm.
- **Không xoá hẳn một người khỏi cảnh** (xoá rồi tự vẽ lại phần nền). Có thể làm mờ, che, crop, hoặc thay nền.
- **Tóc mảnh, chuyển động nhanh** khi tách nền có thể có viền cứng. Dùng mô hình `large` và làm mềm viền (`feather`).
- **HDR** chưa được chuyển màu tự động.
- **Nhận dạng giọng nói** cần Mac chip Apple.
- **Nhạc có bản quyền:** chỉ dùng nhạc bạn có quyền dùng; các nền tảng có thể tắt tiếng video vi phạm.
- Việc EDL chưa hỗ trợ (chống rung, khử nhiễu, xuất GIF, tách phông xanh thật…) Claude làm bằng lệnh ffmpeg riêng (skill `ffmpeg-recipes`) rồi đưa kết quả vào bản dựng.

---

<a id="tham-khao"></a>
## 15. Tài liệu tham khảo thêm

| Tài liệu | Nội dung |
|---|---|
| [README.vi.md](../README.vi.md) | Giới thiệu ngắn về dự án |
| [skills/edl/reference.md](../skills/edl/reference.md) | Đặc tả đầy đủ mọi trường của EDL (tiếng Anh) |
| [examples/](../examples/) | EDL mẫu |

Các skill Claude dùng (đọc để biết Claude làm việc theo quy trình nào):

| Skill | Dùng khi |
|---|---|
| [`video-studio`](../skills/video-studio/SKILL.md) | Quy trình edit từ đầu đến cuối (điểm bắt đầu) |
| [`edl`](../skills/edl/SKILL.md) | Viết và sửa EDL |
| [`captions`](../skills/captions/SKILL.md) | Chép lời, phụ đề, kiểu chữ phụ đề, xuất SRT |
| [`rough-cut`](../skills/rough-cut/SKILL.md) | Dựng theo lời nói: phỏng vấn, podcast, talking-head |
| [`short-form`](../skills/short-form/SKILL.md) | TikTok/Reels/Shorts: câu mở đầu, nhịp, vùng an toàn, cắt theo nhạc |
| [`rotoscoping`](../skills/rotoscoping/SKILL.md) | Tách người/vật thể, hiệu ứng nền |
| [`ffmpeg-recipes`](../skills/ffmpeg-recipes/SKILL.md) | Các thao tác lẻ ngoài EDL |

[↑ Về mục lục](#muc-luc)
