# NGÀY 75 — Production AI checklist

> Phase 5 · Cả buổi. Tổng kết Phase 5 thành **tài liệu bạn dùng cho mọi dự án sau này**.

## 🎯 Mục tiêu

Viết checklist production của riêng bạn — không copy của người khác, mà đúc kết từ 10 ngày vừa qua, mỗi mục kèm cách kiểm chứng.

---

## 1. Khung checklist

`templates/production-ai-checklist.md` — bạn điền và giữ mãi:

```markdown
# Production AI Checklist — <tên bạn>, phiên bản 1.0

Quy ước: mỗi mục phải có CÁCH KIỂM CHỨNG cụ thể, không chỉ "đã làm".

## 1. CHẤT LƯỢNG
- [ ] Có eval set ≥ 50 case, nhãn do người gán, có ca âm ≥ 25%
      → kiểm chứng: `python -m eval.run --set data/eval-test-FROZEN.json`
- [ ] Biết chính xác precision / recall / F1 hiện tại
- [ ] Có dev set và test set tách biệt, test set đóng băng
- [ ] LLM-judge đã hiệu chuẩn, đồng ý với người ≥ 85%
- [ ] Chạy lại eval sau MỌI thay đổi prompt/model/tham số
- [ ] Có ngưỡng chặn phát hành: không deploy nếu chỉ số tụt > __%

## 2. CHỐNG BỊA
- [ ] Mọi câu trả lời từ tài liệu đều có trích dẫn verify được
- [ ] Số liệu trong output được đối chiếu với nguồn bằng CODE
- [ ] Có chế độ "KHÔNG ĐỦ THÔNG TIN" và tỉ lệ từ chối nhầm < 15%
- [ ] Tỉ lệ bịa đo được và < 5%
- [ ] Mọi phép tính do code làm, không do LLM

## 3. AN NINH
- [ ] Không có bí mật trong mã nguồn (audit tự động trong CI)
- [ ] Test cách ly tenant chạy tự động mỗi commit
- [ ] Dữ liệu định danh được che trước khi gửi ra LLM khi không cần thiết
- [ ] Log không chứa SĐT, email, khoá
- [ ] Phòng thủ injection nhiều lớp, đã test ≥ 30 payload
- [ ] Phân quyền theo vai trò, lập trình viên không truy cập dữ liệu thật

## 4. KIỂM SOÁT HÀNH ĐỘNG
- [ ] Mọi hành động ghi ra ngoài đều qua người duyệt
- [ ] Guardrail nghiệp vụ chạy bằng CODE (tần suất, giờ gửi, danh sách chặn)
- [ ] Có hạn mức tổng giới hạn thiệt hại khi lỗi hàng loạt
- [ ] Idempotency: tỉ lệ gửi trùng = 0
- [ ] Guardrail fail closed khi không kiểm tra được

## 5. QUAN SÁT ĐƯỢC
- [ ] Trace đầy đủ ≥ 6 tầng, sampling giữ 100% ca lỗi/chậm
- [ ] Log có cấu trúc JSONL, truy vấn được
- [ ] Biết p50/p95 từng tầng
- [ ] Debug được một request cũ chỉ bằng log
- [ ] Có dashboard vận hành cơ bản

## 6. CHI PHÍ
- [ ] Biết cost/request, cost/tenant/tháng
- [ ] Có cảnh báo khi vượt ngân sách
- [ ] Đơn vị kinh tế dương: chi phí AI < 20% doanh thu
- [ ] Có ít nhất 3 đòn bẩy giảm chi phí đã áp dụng

## 7. ĐỘ TIN CẬY
- [ ] Timeout cho mọi lời gọi ra ngoài
- [ ] Retry có backoff + jitter, KHÔNG retry hành động ghi
- [ ] Có đường đi dự phòng không cần AI
- [ ] Job dài có checkpoint, tiếp tục được
- [ ] Circuit breaker cho dịch vụ ngoài

## 8. VẬN HÀNH
- [ ] Sổ tay sự cố ≥ 5 kịch bản
- [ ] Biết cách rollback prompt/model trong < 5 phút
- [ ] Có người chịu trách nhiệm khi sự cố
- [ ] Khách hàng biết trước giới hạn của hệ thống

## 9. NGƯỜI DÙNG
- [ ] Người dùng biết đang nói chuyện với AI
- [ ] Nguồn thông tin hiển thị được, bấm xem được
- [ ] Có cách báo lỗi/phản hồi ngay trong sản phẩm
- [ ] Phản hồi tiêu cực được thu thập thành dữ liệu cải tiến
```

---

## 2. Việc phải làm (cả buổi)

### Bước 1 — Tự chấm (60 phút)

Chạy qua toàn bộ checklist với hệ thống hiện tại của bạn. Mỗi mục: ✅ / ⚠️ / ❌. **Trung thực.** Checklist đẹp mà sai thì vô dụng.

### Bước 2 — Vá 5 mục quan trọng nhất (90 phút)

Xếp các mục ❌ theo (mức rủi ro × độ dễ sửa). Sửa 5 mục đầu. Ghi lại bằng chứng đã sửa.

### Bước 3 — Tự động hoá kiểm chứng (60 phút)

`scripts/preflight.py` — chạy trước mỗi lần deploy:

```python
"""Preflight: chặn deploy nếu không đạt chuẩn."""
import subprocess
import sys

CHECKS = [
 ("Bí mật trong code", "python exercises/day72/security_audit.py", 0),
 ("Test cách ly tenant", "pytest tests/test_tenant_isolation.py -q", 0),
 ("Eval chất lượng", "python -m eval.run --set data/eval-test-FROZEN.json --min-f1 0.80", 0),
 ("Guardrail", "pytest tests/test_guardrails.py -q", 0),
]

failed = []
for name, cmd, expect in CHECKS:
    print(f"\n{'='*60}\n{name}\n{'='*60}")
    r = subprocess.run(cmd, shell=True)
    if r.returncode != expect:
        failed.append(name)

print("\n" + "=" * 60)
if failed:
    print(f"❌ KHÔNG ĐƯỢC DEPLOY — thất bại: {failed}")
    sys.exit(1)
print("✅ Đạt mọi kiểm tra — có thể deploy")
```

---

## 3. PASS/FAIL

- [ ] Checklist có ≥ 40 mục, mỗi mục có **cách kiểm chứng cụ thể**
- [ ] Đã tự chấm trung thực toàn bộ
- [ ] Vá được ≥ 5 mục ❌, có bằng chứng
- [ ] `preflight.py` chạy được và **chặn được** khi có lỗi thật
- [ ] Checklist lưu ở `templates/production-ai-checklist.md`

---

## 4. Tổng kết Phase 5

```powershell
python quiz\quiz.py --day 75
python quiz\quiz.py --exam 66 75
python quiz\quiz.py --stats
git add . ; git commit -m "day 75: production AI checklist - Phase 5 complete"
```

`progress/notes/phase5-review.md`:

```markdown
## Chỉ số hệ thống của tôi hiện tại
| Chỉ số | Giá trị |
|---|---|
| Precision / Recall / F1 | |
| Tỉ lệ bịa | |
| p50 / p95 latency | |
| Cost/request | |
| Cost/tenant/tháng | |
| Biên lợi nhuận gộp | |
| Tỉ lệ rò rỉ tenant | 0 (bắt buộc) |

## 3 lỗ hổng nghiêm trọng nhất tôi tự tìm được
## Điều tôi sẽ làm khác nếu bắt đầu lại
## Tổng chi phí API Phase 5
```

> **Nhìn trước Phase 6:** 15 ngày cuối — ghép tất cả thành CareDesk-AI. Không học kỹ thuật mới. Chỉ build, đo, và demo.
>
> Chuẩn bị trước ngày 76: Node.js 20+, Docker Desktop đang chạy, và **nói chuyện với ít nhất 1 chủ spa/phòng khám thật** để kiểm chứng bài toán.
