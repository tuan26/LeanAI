# NGÀY 77 — Architecture

> Phase 6 · 40' thiết kế — 50' ADR — 30' dựng khung dự án

## 🎯 Mục tiêu

Sơ đồ kiến trúc + 5 quyết định kiến trúc (ADR) + khung thư mục chạy được.

---

## 1. Kiến trúc mục tiêu

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js (App Router)                                        │
│  /login  /dashboard  /opportunities  /approvals  /settings   │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + session cookie
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI                                                     │
│  ├─ auth        (session, role)                              │
│  ├─ tenants     (mọi request BẮT BUỘC có tenant_id)          │
│  ├─ customers   (CRUD, import CSV)                           │
│  ├─ opportunities (detect, score, explain)                   │
│  ├─ messages    (draft, approve, send)                       │
│  └─ metrics     (dashboard)                                  │
└───┬─────────────────┬──────────────────┬────────────────────┘
    │                 │                  │
┌───▼──────┐   ┌──────▼───────┐   ┌──────▼──────────┐
│PostgreSQL│   │  Qdrant      │   │  LLM provider   │
│+ RLS     │   │  (per-tenant │   │  (Anthropic)    │
│          │   │   filter)    │   │                 │
└──────────┘   └──────────────┘   └─────────────────┘
       ▲
       │  job hàng đêm: quét khách → tạo cơ hội → soạn nháp
┌──────┴──────────┐
│  Worker (cron)  │
└─────────────────┘
```

### Luồng chính

```
[Job đêm]  SQL lọc 3.000 khách ──► ~80 cơ hội ──► LLM giải thích + soạn nháp
                                                        │
                                                        ▼
                                              hàng chờ duyệt
                                                        │
[Ban ngày] Nhân viên mở /approvals ──► Approve/Edit/Reject ──► gửi Zalo/SMS
                                                        │
                                                        ▼
                                              ghi nhận kết quả → dashboard
```

**Điểm mấu chốt:** LLM chỉ chạy trên ~80 khách đã lọc, không phải 3.000. Đây là quyết định Ngày 70.

---

## 2. Năm ADR bắt buộc

`projects/capstone-caredesk-ai/docs/adr/`:

| ADR | Quyết định | Phải trả lời |
|---|---|---|
| 001 | Cách ly multi-tenant | shared DB + RLS, hay DB riêng mỗi tenant? |
| 002 | Phát hiện cơ hội bằng rule hay LLM | (gợi ý: rule — nhưng phải viết rõ vì sao) |
| 003 | Khi nào gọi LLM | job đêm hay realtime? |
| 004 | Human-in-the-loop | mức tự động nào cho v1? |
| 005 | Lưu trữ tin nhắn đã gửi | giữ bao lâu, ai xem được? |

Mẫu ADR:

```markdown
# ADR-001: Cách ly dữ liệu multi-tenant

## Bối cảnh
Nhiều phòng khám dùng chung hệ thống. Dữ liệu khách hàng là tài sản nhạy cảm.
Rò rỉ giữa tenant là sự cố nghiêm trọng nhất có thể xảy ra.

## Các phương án
1. Shared DB + cột tenant_id (chỉ tầng ứng dụng)
2. Shared DB + tenant_id + Row Level Security  ← CHỌN
3. Database riêng mỗi tenant
4. Hạ tầng riêng mỗi tenant

## Quyết định
Phương án 2.

## Lý do
- Phương án 1 phụ thuộc lập trình viên không quên WHERE — không chấp nhận được
- RLS ép cách ly ở tầng DB, quên cũng không rò rỉ
- Phương án 3/4 quá tốn vận hành cho giai đoạn đầu (< 20 tenant)

## Hệ quả
- Mọi bảng phải có tenant_id NOT NULL
- Mọi kết nối phải SET app.tenant_id
- Bắt buộc có test tự động chứng minh cách ly
- Khi > 50 tenant hoặc có khách yêu cầu, xem xét lại phương án 3

## Kiểm chứng
`pytest tests/test_tenant_isolation.py`
```

---

## 3. Khung dự án

```
projects/capstone-caredesk-ai/
├── PRD.md
├── README.md
├── docs/
│   ├── architecture.md
│   └── adr/001-*.md ... 005-*.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── deps.py            # tenant context, auth
│   │   ├── db.py
│   │   ├── models.py          # SQLAlchemy
│   │   ├── schemas.py         # Pydantic
│   │   ├── routers/
│   │   │   ├── auth.py  customers.py  opportunities.py
│   │   │   ├── messages.py   metrics.py
│   │   ├── services/
│   │   │   ├── detector.py    # Ngày 82 — RULE, không LLM
│   │   │   ├── scoring.py     # Ngày 83 — CODE
│   │   │   ├── explainer.py   # Ngày 84 — LLM
│   │   │   ├── drafter.py     # Ngày 86 — LLM
│   │   │   └── sender.py      # Ngày 87
│   │   └── worker/
│   │       └── nightly.py     # job quét
│   ├── alembic/
│   └── tests/
└── frontend/                   # Next.js, Ngày 88
```

Tạo khung + `main.py` tối thiểu chạy được hôm nay:

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="CareDesk-AI", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
```

```powershell
cd projects/capstone-caredesk-ai/backend
uvicorn app.main:app --reload
# mở http://localhost:8000/docs
```

---

## 4. PASS/FAIL

- [ ] Sơ đồ kiến trúc vẽ được, có trong `docs/architecture.md`
- [ ] 5 ADR viết đầy đủ, mỗi cái có phương án bị loại + lý do
- [ ] ADR-002 giải thích rõ vì sao phát hiện cơ hội **không** dùng LLM
- [ ] Khung thư mục tạo xong
- [ ] `/health` chạy được, `/docs` mở được

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 77 ; python quiz\quiz.py --review
git add . ; git commit -m "day 77: architecture + ADR"
```
