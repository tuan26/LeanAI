# NGÀY 34 — Metadata & filtering

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Thiết kế schema metadata **một lần cho cả dự án**, và hiểu tại sao filter quan trọng hơn embedding trong nhiều trường hợp.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Embedding không làm được gì — metadata làm

| Câu hỏi | Embedding | Metadata filter |
|---|---|---|
| "chính sách hoàn tiền" | ✅ tìm được | — |
| "bảng giá **của chi nhánh Quận 7**" | ❌ trộn lẫn các chi nhánh | ✅ `branch = "Q7"` |
| "quy định **mới nhất**" | ❌ không hiểu thời gian | ✅ `effective_date` sort |
| "tài liệu **của clinic A**" | ❌ **RÒ RỈ DỮ LIỆU** | ✅ `tenant_id` |
| "chỉ tài liệu **đã duyệt**" | ❌ | ✅ `status = approved` |

> Dòng thứ 4 không phải vấn đề chất lượng — đó là **sự cố bảo mật**. Trong SaaS đa khách hàng, thiếu filter tenant nghĩa là bạn để lộ dữ liệu khách hàng này cho khách hàng khác.

### 1.2 Pre-filter vs post-filter

```
POST-FILTER: tìm top-100 → lọc → còn 3 kết quả   ❌ có thể trả về quá ít
PRE-FILTER : lọc trước → tìm top-5 trong tập đã lọc  ✅ luôn đủ k
```

Qdrant làm pre-filter khi bạn truyền `query_filter` **và** có payload index. Không có index → nó phải quét, rất chậm.

### 1.3 Schema metadata chuẩn — dùng cho cả CareDesk-AI

```python
{
  # --- BẮT BUỘC: an ninh & định danh ---
  "tenant_id":    "clinic_001",        # cách ly dữ liệu, KHÔNG BAO GIỜ thiếu
  "doc_id":       "chinh-sach-2026.pdf",
  "chunk_index":  3,
  "chunk_hash":   "sha256...",         # phát hiện trùng khi re-index

  # --- Trích dẫn ---
  "title":        "Chính sách hoàn tiền 2026",
  "page":         5,
  "section":      "3.2 Điều kiện hoàn tiền",
  "source_uri":   "s3://docs/clinic_001/chinh-sach-2026.pdf",

  # --- Lọc nghiệp vụ ---
  "doc_type":     "policy",            # policy|price|procedure|faq|contract
  "branch":       "Q7",
  "language":     "vi",
  "status":       "approved",          # draft|approved|archived
  "effective_from": "2026-01-01",
  "effective_to":   null,

  # --- Vận hành ---
  "ingested_at":  "2026-09-18T10:00:00Z",
  "version":      2,
  "token_count":  312
}
```

### 1.4 Ba quy tắc thiết kế metadata

1. **Trường nào sẽ lọc → phải tạo payload index.** Không index = quét toàn bộ.
2. **Trường nào cần cho trích dẫn → phải lưu trong payload.** Đừng bắt hệ thống truy vấn DB khác giữa lúc trả lời.
3. **Luôn có `tenant_id` ngay cả khi hiện tại chỉ có 1 khách hàng.** Thêm sau rất đau; bạn sẽ phải re-index toàn bộ.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Qdrant — Filtering | https://qdrant.tech/documentation/concepts/filtering/ |
| Qdrant — Payload indexing | https://qdrant.tech/documentation/concepts/indexing/#payload-index |
| Qdrant — Multitenancy | https://qdrant.tech/documentation/guides/multiple-partitions/ |

---

## 3. Thực hành (80 phút)

Mở rộng `leanai_core/vectorstore.py` để hỗ trợ filter phức tạp:

```python
    def build_filter(self, where: dict | None) -> "models.Filter | None":
        """where hỗ trợ: {"k": v} | {"k": {"$in": [...]}} |
        {"k": {"$gte": x, "$lte": y}} | {"$not": {...}}"""
        if not where:
            return None
        must, must_not = [], []
        for key, val in where.items():
            if key == "$not":
                for k2, v2 in val.items():
                    must_not.append(models.FieldCondition(
                        key=k2, match=models.MatchValue(value=v2)))
            elif isinstance(val, dict) and "$in" in val:
                must.append(models.FieldCondition(
                    key=key, match=models.MatchAny(any=val["$in"])))
            elif isinstance(val, dict) and ("$gte" in val or "$lte" in val):
                must.append(models.FieldCondition(
                    key=key, range=models.Range(gte=val.get("$gte"),
                                                lte=val.get("$lte"))))
            else:
                must.append(models.FieldCondition(
                    key=key, match=models.MatchValue(value=val)))
        return models.Filter(must=must or None, must_not=must_not or None)
```

`leanai_core/metadata.py` — schema có validation:

```python
"""Schema metadata chuẩn cho mọi chunk."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class DocType(str, Enum):
    POLICY = "policy"; PRICE = "price"; PROCEDURE = "procedure"
    FAQ = "faq"; CONTRACT = "contract"; OTHER = "other"


class DocStatus(str, Enum):
    DRAFT = "draft"; APPROVED = "approved"; ARCHIVED = "archived"


class ChunkMeta(BaseModel):
    tenant_id: str = Field(min_length=1)       # bắt buộc — an ninh
    doc_id: str
    chunk_index: int = 0
    chunk_hash: str = ""
    title: str = ""
    page: int | None = None
    section: str = ""
    source_uri: str = ""
    doc_type: DocType = DocType.OTHER
    branch: str = ""
    language: str = "vi"
    status: DocStatus = DocStatus.APPROVED
    effective_from: str | None = None
    effective_to: str | None = None
    ingested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1
    token_count: int = 0

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def to_payload(self) -> dict:
        return {k: v for k, v in self.model_dump(mode="json").items() if v is not None}


INDEXED_FIELDS = ["tenant_id", "doc_id", "doc_type", "branch", "status", "language"]
```

`exercises/day34/filtering.py`:

```python
"""Ngày 34: chứng minh filter quan trọng ngang embedding."""
from leanai_core.vectorstore import VectorStore, Chunk
from leanai_core.metadata import ChunkMeta, DocType

vs = VectorStore("kb_meta")

RAW = [
 ("Bảng giá 2025: massage 400.000đ/buổi.", "clinic_001", "Q1", "price", "archived", "2025-01-01"),
 ("Bảng giá 2026: massage 500.000đ/buổi.", "clinic_001", "Q1", "price", "approved", "2026-01-01"),
 ("Bảng giá Quận 7 2026: massage 550.000đ/buổi.", "clinic_001", "Q7", "price", "approved", "2026-01-01"),
 ("Bảng giá đối thủ: massage 450.000đ.", "clinic_002", "Q1", "price", "approved", "2026-01-01"),
 ("Quy trình xử lý khiếu nại: tiếp nhận trong 24h.", "clinic_001", "Q1", "procedure", "approved", "2026-01-01"),
 ("Chính sách hoàn tiền: hoàn 80% buổi chưa dùng.", "clinic_001", "Q1", "policy", "approved", "2026-01-01"),
]

chunks = []
for i, (text, tenant, branch, dtype, status, eff) in enumerate(RAW):
    m = ChunkMeta(tenant_id=tenant, doc_id=f"doc_{i}", chunk_index=0,
                  chunk_hash=ChunkMeta.hash_text(text), branch=branch,
                  doc_type=DocType(dtype), status=status, effective_from=eff,
                  title=text[:30])
    chunks.append(Chunk(text=text, meta=m.to_payload()))
vs.upsert(chunks)

Q = "giá massage bao nhiêu"

print("=== 1. KHÔNG FILTER (nguy hiểm) ===")
for h in vs.search(Q, k=4):
    m = h.meta
    print(f"  {h.score:.3f} [{m['tenant_id']}/{m['branch']}/{m['status']}] {h.text[:45]}")
print("  ⚠ Có cả clinic_002 và bảng giá đã archived!")

print("\n=== 2. LỌC ĐÚNG ===")
where = {"tenant_id": "clinic_001", "branch": "Q7", "status": "approved"}
for h in vs.search(Q, k=4, where=where):
    m = h.meta
    print(f"  {h.score:.3f} [{m['tenant_id']}/{m['branch']}/{m['status']}] {h.text[:45]}")

print("\n=== 3. Lọc nhiều giá trị ($in) ===")
where = {"tenant_id": "clinic_001", "doc_type": {"$in": ["policy", "procedure"]}}
for h in vs.search("khách khiếu nại thì làm gì", k=3, where=where):
    print(f"  {h.score:.3f} [{h.meta['doc_type']}] {h.text[:50]}")

print("\n=== 4. Kiểm tra rò rỉ tenant trên 20 truy vấn ===")
QUERIES = ["giá", "chính sách", "quy trình", "massage", "hoàn tiền"] * 4
leaks = sum(1 for q in QUERIES
            for h in vs.search(q, k=5, where={"tenant_id": "clinic_001"})
            if h.meta.get("tenant_id") != "clinic_001")
print(f"  Số lần rò rỉ: {leaks} (BẮT BUỘC = 0)")
```

---

## 4. Bài tập

**Bài 1 — Schema cho CareDesk-AI.** Hoàn thiện `templates/schemas/chunk-metadata.md`: mọi trường, kiểu, bắt buộc hay không, có index hay không, dùng để lọc gì. Đây là tài liệu bạn sẽ đưa cho lập trình viên khác.

**Bài 2 — Hàm bảo vệ tenant.** Viết `safe_search(vs, query, tenant_id, **kw)` **luôn** chèn `tenant_id` vào filter và **ném exception** nếu ai đó cố gọi search không có tenant. Thay toàn bộ lời gọi `vs.search` trực tiếp bằng hàm này.
*Đây là cách bạn biến quy tắc an ninh thành thứ không thể quên.*

**Bài 3 — Lọc theo thời gian hiệu lực.** Thêm filter `effective_from <= hôm nay <= effective_to (hoặc null)`. Test: bảng giá 2025 không bao giờ được trả về khi hỏi giá hiện tại.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 34 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `ChunkMeta` validate được, có đủ 3 nhóm trường
- [ ] Filter hỗ trợ `$in`, `$gte/$lte`, `$not`
- [ ] `safe_search` không cho phép truy vấn thiếu tenant
- [ ] Test 20 truy vấn: rò rỉ tenant = 0
- [ ] Lọc theo thời gian hiệu lực hoạt động
- [ ] Quiz ≥ 80%
