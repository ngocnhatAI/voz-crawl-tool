# crawl-voz-tool

Lấy toàn bộ comment (người viết, nội dung, comment được trả lời) của một bài trên [voz.vn](https://voz.vn), để lọc ra quán ngon và chỗ đi chơi hay.

## Cài đặt

```
pip install -r requirements.txt
```

Cần Python 3.10 trở lên.

## Cách dùng

```
python voz_crawl.py "https://voz.vn/t/cam-nhan-ve-nha-trang.1142279/" nhatrang
```

Dán link page nào của bài cũng được (`page-2`, `page-12`, hay link có `#post-...`). Tool tự quay về page 1, đọc xem bài có tổng bao nhiêu page rồi lấy lần lượt từng page.

Tùy chọn:

| Tham số | Ý nghĩa |
|---|---|
| `out_dir` (bắt buộc) | Thư mục lưu file JSON, tự tạo nếu chưa có |
| `--delay` | Số giây nghỉ giữa các page. Mặc định: `1.0` |

## Kết quả

Tool lưu kết quả vào `<out_dir>/<slug>.json`, ví dụ `nhatrang/cam-nhan-ve-nha-trang.1142279.json`.

Nếu file của bài đó đã có sẵn (crawl lại), tool giữ nguyên nhãn `is_relevant` cũ theo `post_id`. Comment mới xuất hiện từ lần trước sẽ để `null`.

File JSON có dạng:

```json
{
  "url": "https://voz.vn/t/cam-nhan-ve-nha-trang.1142279/",
  "title": "Cảm nhận về Nha Trang",
  "pages": 3,
  "total": 42,
  "posts": [ ... ]
}
```

Mỗi comment có các trường sau:

| Trường | Ý nghĩa |
|---|---|
| `post_id` | id comment |
| `floor`, `page` | số thứ tự comment trong bài (#1, #2…) và page chứa nó |
| `user`, `time` | người viết, thời gian đăng |
| `content` | nội dung comment, **đã bỏ phần trích dẫn** nên không bị lặp lại chữ của comment khác. Ảnh, video và link được chèn đúng vị trí (xem bên dưới) |
| `reply_to_post_ids`, `reply_to_users` | comment này trả lời comment nào, của ai |
| `is_relevant` | comment có liên quan đến chủ đề đang lọc hay không. Lúc crawl để `null` (chưa đánh giá), sau đó điền `true`/`false` |

Ví dụ một comment:

```json
{
  "post_id": "38506437",
  "floor": 4,
  "page": 1,
  "user": "ShmilyGone",
  "time": "2025-09-03T16:20:17+0700",
  "content": "Chuẩn không cần chỉnh.\nĐều bãi biển đẹp thì họ khen Bãi Dài, Cam Ranh hoặc Bãi Dốc Lết, Ninh Hoà ấy, không phải bãi Nha Trang đâu.",
  "reply_to_post_ids": ["38478002"],
  "reply_to_users": ["Cậu bé vô tư"],
  "is_relevant": true
}
```

Comment này trả lời bài #1 (`post_id` 38478002) của "Cậu bé vô tư".

Cách tool xử lý nội dung đặc biệt trong `content`:

| Trong bài gốc | Trong `content` |
|---|---|
| Ảnh (kể cả tệp đính kèm cuối bài) | `[ảnh: https://...]` |
| Video nhúng | `[video: https://...]` |
| Link có chữ riêng | `chữ (https://...)` |
| Khung xem trước link (Google Maps, báo…) | `tiêu đề (https://...)` |
| Emoji | ký tự emoji hoặc mã như `:beauty:` |
| Dòng chữ ký app (`via theNEXTvoz for iPhone`, `Sent from ... using vozFApp`…) | bị xoá |

## Xuất ra HTML để đọc

Sau khi đã điền `is_relevant`, gộp các file JSON thành 1 file HTML dạng chat nhóm:

```
python json_to_html.py "nhatrang/*.json" --title "Ăn chơi Nha Trang"
```

Mặc định file được ghi thẳng vào thư mục deploy `site/`, tên theo thư mục chứa JSON: `nhatrang/*.json` → `site/nhatrang.html`.

| Tham số | Ý nghĩa |
|---|---|
| `-o`, `--out` | Ghi ra đường dẫn khác. Mặc định: `site/<tên thư mục chứa JSON>.html` |
| `--title` | Tiêu đề trang |
| `--all` | Lấy cả comment không liên quan (bỏ qua `is_relevant`) |

Mỗi bài là một phần riêng, gộp comment của tất cả các page. Đầu trang có mục lục để nhảy tới từng bài. Mỗi tin hiện tên người viết, thời gian đăng và nội dung. Ảnh và video hiện thành nút nhỏ, bấm để mở. Nếu tin đó trả lời comment khác thì có khung trích tên người được trả lời và vài dòng đầu tin gốc, bấm vào để nhảy tới tin gốc (nếu tin gốc cũng có trong trang). Bài không có comment liên quan nào sẽ bị bỏ qua. File HTML không cần thư viện ngoài, tự đổi sáng/tối theo máy.

## Cách hoạt động

- voz chỉ trả về trang HTML bình thường, không cần chạy trình duyệt, nên tool dùng `requests` + `BeautifulSoup`.
- Nếu gửi yêu cầu kiểu mặc định thì voz chặn (lỗi 403). Tool giả làm trình duyệt Chrome nên vào được, không cần đăng nhập.
- Giữa các page tool nghỉ 1 giây. Nếu bị lỗi mạng hoặc bị voz hạn chế tốc độ (429, 5xx) thì tool tự thử lại tối đa 4 lần.
- Comment nào bị lấy trùng (do có người đăng thêm trong lúc đang crawl) sẽ được bỏ bớt.

## Giới hạn

- Chỉ dùng cho domain voz.vn.
- Khi một comment trích lại comment đã có trích dẫn bên trong, tool chỉ ghi nhận comment được trích trực tiếp. Lớp trích dẫn sâu hơn bị bỏ qua.

## Deploy lên GitHub Pages

Workflow [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml) đưa **toàn bộ file trong thư mục `site/`** lên GitHub Pages.

- Mỗi file là một trang: `site/nhatrang.html` → `https://<user>.github.io/<repo>/nhatrang.html`.
- Nếu `site/` không có `index.html`, workflow tự tạo trang mục lục liệt kê các trang (tên lấy từ `<title>` của từng file). Có sẵn `index.html` thì giữ nguyên.
- Tự chạy khi push lên `main` có thay đổi trong `site/`, hoặc bấm chạy tay ở tab **Actions**.
- Thêm chủ đề mới: crawl vào thư mục mới (ví dụ `duhoc/`), đánh nhãn, chạy `python json_to_html.py "duhoc/*.json" --title "..."` → có `site/duhoc.html`, commit và push. Không cần sửa workflow.
- Cài đặt một lần: repo **Settings → Pages → Source: GitHub Actions**.
