# CareDesk-AI — Capstone (Ngày 76–90)

> AI SaaS giúp chuỗi spa/phòng khám **phát hiện và thu hồi doanh thu tồn đọng** từ khách hàng đã mua gói nhưng chưa dùng hết.

---

## Bài toán

Một phòng khám 3.000 khách thường có 15–25% khách mua gói liệu trình rồi không dùng hết. Giá trị tồn đọng hàng trăm triệu đồng. Không ai theo dõi vì:
- dữ liệu nằm rải rác trong phần mềm quản lý, không ai lọc,
- nhân viên bận phục vụ khách đến, không có thời gian gọi khách cũ,
- không biết nên liên hệ ai trước.

## Giải pháp

```
Job đêm:  SQL lọc 3.000 khách ──► ~80 cơ hội ──► chấm điểm ──► LLM giải thích
                                                                    │
                                                            LLM soạn nháp tin
                                                                    │
                                                            guardrail (code)
                                                                    │
Ban ngày: nhân viên duyệt ──► Approve / Edit / Reject ──► gửi Zalo/SMS
                                                                    │
                                                            ghi nhận doanh thu
```

### Phần nào dùng AI, phần nào không

| Chức năng | Công nghệ | Vì sao |
|---|---|---|
| Phát hiện cơ hội | **SQL + rule** | luật rõ ràng, cần chính xác 100%, chạy 3.000 khách/đêm |
| Ước tính giá trị | **Code** | công thức cố định, kiểm toán được |
| Chấm điểm xác suất | **Code** (ML sau) | minh bạch, giải thích được cho khách hàng |
| Giải thích cơ hội | **LLM** | cần diễn đạt tự nhiên cho nhân viên đọc nhanh |
| Soạn tin nhắn | **LLM** (biến + code thay số) | cần ngôn ngữ tự nhiên, số liệu phải tuyệt đối đúng |
| Guardrail nghiệp vụ | **Code** | prompt không phải biện pháp an ninh |
| Quyết định gửi | **Con người** | rủi ro thương hiệu |

Chỉ **2/7** thành phần dùng LLM. Đây là lý do chi phí thấp và hệ thống đoán trước được.

---

## Chạy dự án

### Yêu cầu
```
Python 3.11+ · Node.js 20+ · Docker (Postgres + Qdrant)
```

### Cài đặt
```powershell
# 1. Hạ tầng
docker compose up -d           # postgres + qdrant

# 2. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py --tenants 2 --customers 200
uvicorn app.main:app --reload

# 3. Frontend
cd ../frontend
npm install && npm run dev

# 4. Job quét cơ hội
cd ../backend
python -m app.worker.nightly --tenant clinic_001 --dry-run   # thử trước
python -m app.worker.nightly --tenant clinic_001
```

Mở http://localhost:3000 — đăng nhập bằng tài khoản seed.

> **Quan trọng:** giữ `SEND_SANDBOX=true` trong `.env` cho đến khi bạn thật sự muốn gửi tin cho khách hàng thật.

---

## Cấu trúc

```
backend/app/
  services/
    detector.py    # Ngày 82 — RULE, không LLM
    scoring.py     # Ngày 83 — CODE
    explainer.py   # Ngày 84 — LLM, có chống bịa
    drafter.py     # Ngày 86 — LLM sinh biến, code thay số
    guards.py      # Ngày 62 — guardrail nghiệp vụ bằng code
    sender.py      # Ngày 87 — idempotent, có sandbox
    kb.py          # Ngày 81 — RAG theo tenant
  worker/nightly.py  # Ngày 85 — job quét
  routers/           # auth, customers, opportunities, messages, metrics
docs/adr/            # 5 quyết định kiến trúc
tests/               # test_tenant_isolation.py là bắt buộc
```

---

## Chỉ số (điền sau Ngày 89)

| Chỉ số | Kết quả | Mục tiêu |
|---|---|---|
| Precision phát hiện cơ hội | | ≥ 0.85 |
| Recall | | ≥ 0.75 |
| Độ chính xác số liệu trong tin nhắn | | **100%** |
| Tỉ lệ nhân viên duyệt thẳng | | ≥ 70% |
| Latency p95 | | < 8s |
| Chi phí AI / phòng khám / tháng | | < 400.000đ |
| Rò rỉ dữ liệu giữa phòng khám | | **0** |

Chi tiết: [EVAL.json](EVAL.json) · [RESULTS.md](RESULTS.md) (bản cho khách hàng)

---

## Bảo mật

- Cách ly tenant 4 tầng: ứng dụng + Postgres RLS + vector filter + test tự động
- Phân quyền theo vai trò: lễ tân không duyệt được tin
- Dữ liệu định danh được che trước khi gửi ra LLM khi không cần thiết
- Mọi hành động ghi vào `audit_logs`
- Kiểm tra: `pytest tests/test_tenant_isolation.py`

---

## Giới hạn đã biết

- Không tự gửi tin — mọi tin đều cần người duyệt (đây là **chủ ý**, không phải thiếu sót)
- Không dự đoán được khách có quay lại hay không, chỉ xếp hạng khả năng
- Cần dữ liệu tối thiểu: ngày mua gói, số buổi, lần đến cuối
- Độ chính xác giảm với khách vắng > 300 ngày
- Chưa tích hợp phần mềm đặt lịch — doanh thu thu hồi cần đánh dấu tay
- Tích hợp Zalo OA / SMS chưa hoàn thiện (hiện chạy sandbox)

---

## Lộ trình tiếp theo

1. 3 khách hàng thử nghiệm trả phí, đo doanh thu thu hồi **thật**
2. Hiệu chuẩn scoring bằng kết quả thật (Ngày 83 mục 1.4)
3. Tích hợp phần mềm đặt lịch phổ biến để đo chuyển đổi tự động
4. Duyệt lô cho phòng khám lớn (mức tự động 2)
