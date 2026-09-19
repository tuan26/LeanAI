# NGÀY 80 — Multi-tenant isolation

> Phase 6 · 20' lý thuyết — 100' code + test
> ⭐ Ngày quan trọng nhất về mặt **rủi ro** trong toàn bộ Phase 6.

## 🎯 Mục tiêu

Chứng minh **bằng test tự động** rằng phòng khám A không bao giờ thấy được dữ liệu phòng khám B.

---

## 1. Lý thuyết (20 phút)

### 1.1 Bốn tầng phòng thủ

```
Tầng 1 — ỨNG DỤNG : mọi query có .filter(tenant_id == principal.tenant_id)
Tầng 2 — DATABASE : Row Level Security — quên filter cũng không rò rỉ
Tầng 3 — VECTOR DB: filter bắt buộc trong mọi search
Tầng 4 — KIỂM THỬ : test tự động chạy mỗi commit
```

Chỉ tầng 1 là **không đủ**: một lần quên = một sự cố. Tầng 2 biến "phải nhớ" thành "không thể quên".

### 1.2 Row Level Security (Postgres)

```sql
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;   -- áp dụng cả với chủ bảng

CREATE POLICY tenant_isolation ON customers
  USING (tenant_id = current_setting('app.tenant_id', true));
```

Mỗi kết nối phải `SET LOCAL app.tenant_id = 'clinic_001'`. Nếu quên set → `current_setting` trả NULL → **không thấy dòng nào** (fail closed, đúng hướng).

### 1.3 Những chỗ hay rò rỉ

| Chỗ | Cách rò |
|---|---|
| Vector DB | quên filter `tenant_id` |
| Cache | key không có tenant → tenant B đọc cache của A |
| Log/trace | tenant A xem được trace của B |
| Job nền | chạy với quyền admin, quên scope |
| Thông báo lỗi | lộ id/tên của tenant khác |
| File upload | đường dẫn đoán được |
| Prompt LLM | nhồi dữ liệu nhiều tenant vào cùng context |

---

## 2. Code (100 phút)

`backend/app/db.py`:

```python
"""Kết nối DB có tenant context bắt buộc."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def tenant_session(tenant_id: str):
    """Mọi truy vấn nghiệp vụ PHẢI đi qua đây."""
    if not tenant_id:
        raise ValueError("tenant_id rỗng — từ chối mở phiên DB")
    db: Session = SessionLocal()
    try:
        db.execute(text("SET LOCAL app.tenant_id = :t"), {"t": tenant_id})
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def admin_session():
    """CHỈ dùng cho migration và job hệ thống. Không dùng trong request."""
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()
```

`backend/alembic/versions/xxx_enable_rls.py`:

```python
"""Bật RLS cho mọi bảng có tenant_id."""
from alembic import op

TABLES = ["users", "customers", "packages", "opportunities", "messages",
          "audit_logs", "documents"]


def upgrade():
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {t}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """)


def downgrade():
    for t in TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
```

### Bọc vector store

```python
# backend/app/services/kb.py
from leanai_core.vectorstore import VectorStore

class TenantKB:
    """Không thể search mà thiếu tenant."""
    def __init__(self, tenant_id: str, collection: str = "caredesk_kb"):
        if not tenant_id:
            raise ValueError("tenant_id bắt buộc")
        self.tenant_id = tenant_id
        self.vs = VectorStore(collection)

    def search(self, query: str, k: int = 5, where: dict | None = None):
        w = {**(where or {}), "tenant_id": self.tenant_id}   # luôn ghi đè
        return self.vs.search(query, k=k, where=w)

    def upsert(self, chunks):
        for c in chunks:
            c.meta = {**c.meta, "tenant_id": self.tenant_id}
        return self.vs.upsert(chunks)
```

### Test cách ly — phần quan trọng nhất

`backend/tests/test_tenant_isolation.py`:

```python
"""Test cách ly tenant — PHẢI chạy mỗi commit."""
import pytest
from sqlalchemy import text

from app.db import tenant_session, admin_session
from app.models import Customer, Message, Opportunity

TENANTS = ["clinic_001", "clinic_002"]


@pytest.fixture(scope="module")
def seeded():
    with admin_session() as db:
        for t in TENANTS:
            for i in range(50):
                db.add(Customer(tenant_id=t, full_name=f"{t}-khach-{i}",
                                phone=f"09{hash((t,i)) % 10**8:08d}"))
        db.commit()
    yield


def test_query_chi_thay_tenant_cua_minh(seeded):
    for t in TENANTS:
        with tenant_session(t) as db:
            rows = db.query(Customer).all()
            assert rows, "phải thấy dữ liệu của chính mình"
            assert all(c.tenant_id == t for c in rows)


def test_quen_filter_van_khong_ro_ri(seeded):
    """Cố tình query KHÔNG filter — RLS phải chặn."""
    with tenant_session("clinic_001") as db:
        rows = db.execute(text("SELECT tenant_id FROM customers")).fetchall()
        assert all(r[0] == "clinic_001" for r in rows), "RLS KHÔNG hoạt động!"


def test_khong_doc_duoc_ban_ghi_cu_the_cua_tenant_khac(seeded):
    with tenant_session("clinic_002") as db:
        other = db.execute(
            text("SELECT id FROM customers WHERE tenant_id='clinic_001' LIMIT 1")
        ).fetchall()
        assert not other


def test_khong_ghi_duoc_sang_tenant_khac(seeded):
    with pytest.raises(Exception):
        with tenant_session("clinic_001") as db:
            db.add(Customer(tenant_id="clinic_002", full_name="lén"))
            db.commit()


def test_thieu_tenant_bi_tu_choi():
    with pytest.raises(ValueError):
        with tenant_session(""):
            pass


def test_vector_kb_khong_ro_ri():
    from app.services.kb import TenantKB
    kb = TenantKB("clinic_001")
    for q in ["giá", "chính sách", "khách hàng", "quy trình", "hoàn tiền"]:
        for h in kb.search(q, k=10):
            assert h.meta.get("tenant_id") == "clinic_001"


def test_cache_key_co_tenant():
    from app.services.cache import make_cache_key
    k1 = make_cache_key("clinic_001", "câu hỏi giống nhau")
    k2 = make_cache_key("clinic_002", "câu hỏi giống nhau")
    assert k1 != k2, "cache key phải chứa tenant_id"


@pytest.mark.parametrize("endpoint", [
    "/customers", "/opportunities", "/messages", "/metrics/summary"])
def test_api_khong_gia_mao_duoc_tenant(client, login_clinic1, endpoint):
    r = client.get(f"{endpoint}?tenant_id=clinic_002")
    assert r.status_code in (200, 404)
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert all(i.get("tenant_id", "clinic_001") == "clinic_001" for i in items)
```

---

## 3. PASS/FAIL

- [ ] RLS bật cho **mọi** bảng có tenant_id
- [ ] Query quên filter vẫn không rò rỉ (test chứng minh)
- [ ] Không ghi được dữ liệu sang tenant khác
- [ ] Vector DB không rò rỉ trên 50 truy vấn
- [ ] Cache key có chứa tenant_id
- [ ] API không thể bị giả mạo tenant qua query param
- [ ] Toàn bộ 8 test pass, chạy được trong CI

> **Nếu một test nào fail, không được sang Ngày 81.** Đây là ranh giới cứng.

---

## 4. Quiz + commit

```powershell
pytest backend/tests/test_tenant_isolation.py -v
python quiz\quiz.py --day 80 ; python quiz\quiz.py --review
git add . ; git commit -m "day 80: multi-tenant isolation + RLS + tests"
```
