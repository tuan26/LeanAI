# LeanAI — Chương trình 90 ngày: từ 0 đến AI SaaS production

> Triết lý: **30% học — 70% build**. Mỗi ngày kết thúc bằng một thứ chạy được, không phải một ghi chú đẹp.

## Kết quả sau 90 ngày

Bạn có 4 sản phẩm demo được:

```
① AI Business Analyst  →  ② Company Knowledge RAG  →  ③ Research Agent  →  ★ CareDesk-AI (capstone)
```

Và 6 năng lực: hiểu LLM · LLM API engineering · RAG production · AI Agent · AI Engineering (eval/trace/cost/guardrail) · AI SaaS (multi-tenant/deploy).

## Cấu trúc thư mục

| Thư mục | Nội dung |
|---|---|
| `curriculum/phase1..6/` | 90 file ngày: lý thuyết, tài liệu, thực hành, bài tập, tiêu chí PASS/FAIL |
| `quiz/` | Engine quiz spaced-repetition + ngân hàng câu hỏi theo ngày |
| `exercises/` | Starter code + test tự chấm cho các bài tập chính |
| `projects/` | Spec + rubric chấm điểm của 3 project + capstone |
| `resources/` | Danh sách tài liệu đọc/xem đã lọc, không lan man |
| `progress/` | Nhật ký học, bảng theo dõi, lab notebook |
| `templates/` | Mẫu note, mẫu eval dataset, mẫu prompt |

## Bắt đầu

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # rồi điền API key
python quiz/quiz.py --doctor    # kiểm tra môi trường
```

Chi tiết: [SETUP.md](SETUP.md)

## Nhịp một ngày thường (2 giờ)

```
00:00–00:05   Quiz ôn bài   →  python quiz/quiz.py --review
00:05–00:35   Lý thuyết     →  đọc phần "Lý thuyết cốt lõi" của ngày
00:35–00:55   Tài liệu      →  đọc/xem link trong "Tài liệu"
00:55–01:55   Code          →  phần "Thực hành" + "Bài tập"
01:55–02:00   Note + quiz   →  ghi progress/journal.md, chạy quiz ngày mới
```

Cuối tuần (6–8 giờ): 20% theory / 80% project.

## Giao diện web (khuyên dùng)

```bash
pip install -r requirements.txt
python -m webapp.server          # mở http://127.0.0.1:8080
```

Một app chạy local, không cần internet:

| Màn hình | Có gì |
|---|---|
| **Tiến trình** | 6 thanh giai đoạn, lưới 90 ngày, phân bố hộp Leitner, mốc sản phẩm, cảnh báo nợ |
| **Bài học** | Đúng 90 bài markdown được render: bảng, code có tô màu, nút copy, phần đáp án gấp lại |
| **Quiz** | Làm ngay trong bài, chấm phía server (không lộ đáp án trong HTML), tự lên/xuống hộp Leitner |
| **Đánh dấu xong** | Hiện checklist PASS của đúng ngày đó, nhập phút + chi phí + ghi chú |
| **Tìm kiếm** | Tìm xuyên 90 bài, phím tắt `/` |

Phím tắt: `/` tìm kiếm · `←` `→` chuyển ngày · `A–F` chọn đáp án · `Enter` câu tiếp · `Esc` đóng.

Web app, `quiz/quiz.py` và `track.py` **dùng chung một kho dữ liệu** — học trên web rồi
xem bằng CLI vẫn ra đúng số liệu đó.

## Theo dõi tiến trình

```bash
python track.py                  # thanh tiến trình + chỉ số
python track.py --done 5 --cost 0.12 --minutes 135 --note "khó phần embedding"
python track.py --fail 6 --note "chưa xong bài tập 2"
python track.py --week           # báo cáo 7 ngày + nhịp học dự phóng
python track.py --html           # xuất progress/dashboard.html để xem bằng trình duyệt
```

Công cụ tự đọc dữ liệu thật: quiz đã thuộc (từ Leitner box), số commit git, chi phí API,
chuỗi ngày học liên tiếp, và **nợ** — ngày đã đi qua nhưng chưa PASS. Nợ > 2 ngày thì nó
báo dừng học mới.

## Cách dùng quiz nhớ bài

```bash
python quiz/quiz.py --day 1        # học quiz của ngày 1 lần đầu
python quiz/quiz.py --review       # ôn tất cả câu đến hạn (Leitner SRS)
python quiz/quiz.py --stats        # xem tỉ lệ nhớ, câu yếu nhất
python quiz/quiz.py --exam 1 14    # thi tổng kết phase 1
```

Cơ chế: hộp Leitner 5 mức — đúng thì lên hộp (ôn lại sau 1/2/4/8/16 ngày), sai thì rớt về hộp 1.
**Quy tắc:** không sang ngày mới nếu `--review` hôm đó chưa xong.

## Luật PASS/FAIL

Mỗi ngày có tiêu chí PASS rõ ràng. Nếu FAIL:
- Được phép nợ **tối đa 2 ngày**, trả nợ vào cuối tuần.
- Nợ quá 2 ngày → dừng, làm lại ngày đang nợ. Không học tiếp kiến thức mới trên nền hổng.

## Roadmap tổng

Xem [ROADMAP.md](ROADMAP.md) — bảng 90 ngày đầy đủ với output từng ngày.

## 5 thứ KHÔNG học trong 90 ngày này

Training LLM từ đầu · CUDA optimization · Distributed training · PyTorch research nâng cao · Fine-tuning model lớn.

Lý do: không tạo ra sản phẩm trong 90 ngày, và 99% bài toán B2B không cần. Quay lại sau nếu thật sự cần.
