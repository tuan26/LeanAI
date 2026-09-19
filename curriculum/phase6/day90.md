# NGÀY 90 — DEMO DAY 🚀

> Phase 6 · 60' chuẩn bị — 30' tập — 8' demo — 60' tổng kết 90 ngày

## 🎯 Mục tiêu

Demo 8 phút chạy được từ đầu đến cuối, **có số liệu**, và một portfolio hoàn chỉnh.

---

## 1. Kịch bản demo (8 phút)

```
0:00  BÀI TOÁN (60 giây)
      "Phòng khám X có 3.000 khách. ___% mua gói không dùng hết.
       Giá trị tồn đọng ___đ. Không ai theo dõi vì ___."
      → dùng trích dẫn thật từ Ngày 76

1:00  ĐĂNG NHẬP (20 giây)
      Vào bằng tài khoản clinic_001

1:20  DASHBOARD (40 giây)
      5 chỉ số. Nhấn mạnh con số cuối: doanh thu thu hồi.

2:00  DANH SÁCH CƠ HỘI (60 giây)
      Xếp theo giá trị kỳ vọng. Chỉ ra 2 ca: giá trị cao nhưng xác suất thấp
      vs giá trị vừa nhưng xác suất cao → hệ thống ưu tiên cái thứ hai.

3:00  MỞ MỘT CƠ HỘI (90 giây)
      - Số liệu: còn 4/10 buổi, vắng 112 ngày, hết hạn sau 25 ngày
      - AI giải thích: 3 gạch đầu dòng, mỗi gạch có số
      - Cảnh báo: khách từng phàn nàn chờ lâu
      → nói rõ: "phần phát hiện này KHÔNG dùng AI, dùng SQL, nên chính xác 100%"

4:30  TIN NHẮN NHÁP (60 giây)
      Đọc to tin nhắn. Chỉ ra: mọi con số do hệ thống chèn, AI chỉ viết câu chữ.
      Mở bản template gốc có {biến} → đây là cách chống AI bịa số.

5:30  DUYỆT (60 giây)
      Bấm Edit, sửa một chữ, gửi. Hiện trạng thái sent.
      Bấm Approve lần hai trên cùng tin → hệ thống chặn gửi trùng.

6:30  GUARDRAIL (40 giây)
      Chọn một khách có khiếu nại mở → hệ thống từ chối, nêu lý do.
      Nói: "guardrail chạy bằng code, không phải bằng lời dặn AI."

7:10  SỐ LIỆU (50 giây)
      Mở RESULTS.md:
        100 kịch bản
        Precision  __%    Recall __%
        Số liệu sai trong tin nhắn: 0
        Chi phí AI: ___đ/phòng khám/tháng
        Latency p95: __s
      Kết: "Chi phí AI bằng __% doanh thu gói sản phẩm."

8:00  KẾT THÚC
```

### Ba quy tắc demo

1. **Dùng dữ liệu thật đã seed**, không phải slide.
2. **Thừa nhận giới hạn** — nói trước 2 điều hệ thống chưa làm được. Người nghe tin bạn hơn.
3. **Không sửa code trong lúc demo.** Nếu hỏng, mở sẵn bản ghi màn hình dự phòng.

---

## 2. Chuẩn bị (60 phút)

```powershell
# 1. Reset dữ liệu sạch
python backend/scripts/seed.py --reset --tenants 2 --customers 200

# 2. Chạy job đêm để có cơ hội và nháp
python -m app.worker.nightly --tenant clinic_001

# 3. Kiểm tra toàn hệ thống
python scripts/preflight.py

# 4. Chạy thử demo đầu-cuối 2 lần, bấm giờ

# 5. Quay màn hình bản dự phòng
```

### Checklist trước demo

- [ ] `SEND_SANDBOX=true` (không gửi tin thật)
- [ ] Dữ liệu seed có ít nhất 1 ca: giá trị cao/xác suất thấp, 1 ca có khiếu nại, 1 ca opt-out
- [ ] Dashboard có số liệu, không trống
- [ ] Hàng chờ duyệt có ≥ 10 tin
- [ ] `RESULTS.md` mở sẵn ở tab khác
- [ ] Bản ghi màn hình dự phòng đã quay
- [ ] Đã chạy thử toàn bộ 2 lần

---

## 3. Portfolio (60 phút)

`README.md` gốc của repo — viết lại cho **người tuyển dụng / khách hàng** đọc:

```markdown
# LeanAI — 90 ngày từ 0 đến AI SaaS production

## Sản phẩm
| # | Dự án | Mô tả | Số liệu |
|---|---|---|---|
| 1 | AI Business Analyst | Yêu cầu thô → tài liệu phân tích có cấu trúc | __ use case/phút, 0 trích dẫn bịa |
| 2 | Company Knowledge RAG | Hỏi đáp tài liệu doanh nghiệp có trích nguồn | recall@5 __, bịa __%, __s |
| 3 | Research Agent | Agent tự nghiên cứu và lập báo cáo | __ bản ghi, __% chính xác |
| ★ | **CareDesk-AI** | AI SaaS phát hiện và thu hồi doanh thu cho phòng khám | precision __, chi phí ___đ/tháng |

## Năng lực chứng minh được
- LLM API engineering: streaming, structured output, retry, cost tracking
- RAG production: hybrid search, rerank, citation verify, eval 100 câu
- AI Agent: tool use, state, human-in-the-loop, guardrail bằng code
- AI Engineering: eval dataset, tracing, cost/latency optimization, security audit
- AI SaaS: multi-tenant với RLS, RBAC, job có checkpoint, dashboard

## Điều tôi học được quan trọng nhất
<viết thật, 3-5 câu>

## Cách chạy
<hướng dẫn để người khác chạy lại được>
```

### Tổng kết 90 ngày

`progress/notes/final-review.md`:

```markdown
## Số liệu 90 ngày
- Số commit: ___
- Tổng chi phí API: $___
- Số dòng code: ___
- Số quiz đã thuộc (box 5-6): ___/___
- Số ngày FAIL phải làm lại: ___

## 5 điều tôi hiểu sâu nhất
## 5 điều tôi vẫn chưa chắc
## 3 sai lầm tốn thời gian nhất
## Nếu làm lại, tôi sẽ làm khác thế nào
## 3 tháng tới tôi sẽ làm gì
```

---

## 4. PASS/FAIL cuối cùng

### Demo
- [ ] Chạy đủ 8 bước, không crash
- [ ] Mọi số liệu trên màn hình khớp database
- [ ] Trình bày trong 8 phút (± 1 phút)
- [ ] Nói rõ được phần nào dùng AI, phần nào không, **và vì sao**
- [ ] Thừa nhận ≥ 2 giới hạn

### Portfolio
- [ ] 4 dự án có README chạy lại được
- [ ] Mỗi dự án có số liệu đánh giá thật
- [ ] 90 commit trong git
- [ ] `RESULTS.md` dành cho người không kỹ thuật

### Kiến thức
```powershell
python quiz\quiz.py --exam 1 90
python quiz\quiz.py --stats
```
- [ ] Bài thi tổng kết ≥ 85%
- [ ] ≥ 80% câu hỏi ở box 5–6 (đã thuộc)

---

## 5. Sau ngày 90

Bạn đã đủ nền để chọn một trong ba hướng:

| Hướng | Việc tiếp theo |
|---|---|
| **Thương mại hoá CareDesk-AI** | 3 khách hàng thử nghiệm trả phí, đo doanh thu thu hồi thật, hiệu chuẩn scoring bằng dữ liệu thật |
| **Đi sâu kỹ thuật** | Fine-tuning (LoRA), self-host model, đánh giá nâng cao, multi-agent |
| **Làm dịch vụ** | Đóng gói quy trình 90 ngày này thành dịch vụ tư vấn AI cho doanh nghiệp Việt |

Với nền BA/BrSE của bạn, hướng 1 và 3 có lợi thế rõ rệt: bạn hiểu nghiệp vụ, biết hỏi đúng câu, và giờ bạn build được.

```powershell
git add . ; git commit -m "day 90: DEMO DAY - 90 days complete 🚀"
git tag v1.0-90days
```

**Chúc mừng. Bạn không còn là người "biết về AI" — bạn là người xây được hệ thống AI production.**
