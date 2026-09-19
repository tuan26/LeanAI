# NGÀY 33 — Vector database (Qdrant)

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Chạy Qdrant bằng Docker, tạo collection, insert/search/delete — và hiểu các tham số ảnh hưởng chất lượng.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vector DB làm gì mà numpy không làm được

| | numpy brute force | Vector DB |
|---|---|---|
| Tốc độ ở 1M vector | ~2 giây | ~5 ms (ANN) |
| Lọc theo metadata | tự code, chậm | tích hợp, có index |
| Thêm/xoá từng phần | phải build lại | cập nhật tại chỗ |
| Bền vững sau restart | mất | lưu đĩa |
| Nhiều tenant | tự quản lý | payload index + filter |

### 1.2 HNSW — thuật toán bạn sẽ dùng

Đồ thị nhiều tầng: tầng trên thưa để nhảy xa, tầng dưới dày để tìm chính xác.

| Tham số | Ảnh hưởng | Mặc định hợp lý |
|---|---|---|
| `m` | số liên kết mỗi node — cao = chính xác hơn, tốn RAM hơn | 16 |
| `ef_construct` | độ kỹ khi build index — cao = build chậm, chất lượng tốt | 100 |
| `ef` (lúc search) | độ kỹ khi tìm — cao = chính xác hơn, chậm hơn | 64–128 |

> ANN là **xấp xỉ**. Bạn sẽ mất 1–3% recall để đổi lấy tốc độ gấp trăm lần. Ngày 35 sẽ đo con số thật.

### 1.3 Cấu trúc một điểm trong Qdrant

```python
{
  "id": "uuid hoặc int",
  "vector": [0.1, -0.3, ...],
  "payload": {                    # ← metadata, cực kỳ quan trọng
      "tenant_id": "clinic_001",  # bắt buộc cho multi-tenant (Ngày 80)
      "doc_id": "hop-dong-2026.pdf",
      "chunk_index": 3,
      "text": "nội dung gốc",     # lưu text để không phải tra DB khác
      "source_page": 5,
      "updated_at": "2026-09-18"
  }
}
```

**Nguyên tắc:** payload phải đủ để **tái tạo trích dẫn** mà không cần truy vấn thêm.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Qdrant quickstart | https://qdrant.tech/documentation/quickstart/ |
| Qdrant Python client | https://python-client.qdrant.tech/ |
| Qdrant filtering | https://qdrant.tech/documentation/concepts/filtering/ |

---

## 3. Thực hành (80 phút)

### Bước 1 — Chạy Qdrant

```powershell
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 `
  -v ${PWD}/data/qdrant:/qdrant/storage qdrant/qdrant
```

Mở http://localhost:6333/dashboard để xem giao diện.

### Bước 2 — Kho vector dùng chung

`leanai_core/vectorstore.py`:

```python
"""Bọc Qdrant — dùng suốt Phase 3 đến Phase 6."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from qdrant_client import QdrantClient, models

from .config import cfg
from .embedding import EmbeddingService


@dataclass
class Chunk:
    text: str
    meta: dict = field(default_factory=dict)
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Hit:
    id: str
    text: str
    score: float
    meta: dict

    def citation(self) -> str:
        m = self.meta
        return f"[{m.get('doc_id','?')}" + (f" tr.{m['page']}" if m.get("page") else "") + "]"


class VectorStore:
    def __init__(self, collection: str, embedder: EmbeddingService | None = None,
                 url: str | None = None, dim: int | None = None):
        self.client = QdrantClient(url=url or cfg.QDRANT_URL)
        self.name = collection
        self.embedder = embedder or EmbeddingService()
        self.dim = dim or len(self.embedder.embed("test"))
        self._ensure()

    def _ensure(self) -> None:
        names = [c.name for c in self.client.get_collections().collections]
        if self.name in names:
            return
        self.client.create_collection(
            collection_name=self.name,
            vectors_config=models.VectorParams(
                size=self.dim, distance=models.Distance.COSINE),
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
        )
        # Index cho các trường sẽ lọc — BẮT BUỘC, nếu không filter sẽ rất chậm
        for f in ("tenant_id", "doc_id", "doc_type"):
            self.client.create_payload_index(
                collection_name=self.name, field_name=f,
                field_schema=models.PayloadSchemaType.KEYWORD)
        print(f"[vectorstore] đã tạo collection '{self.name}' dim={self.dim}")

    def upsert(self, chunks: list[Chunk], batch: int = 100) -> int:
        vecs = self.embedder.embed([c.text for c in chunks])
        points = [
            models.PointStruct(id=c.id, vector=v.tolist(),
                               payload={**c.meta, "text": c.text})
            for c, v in zip(chunks, vecs)
        ]
        for i in range(0, len(points), batch):
            self.client.upsert(self.name, points=points[i:i + batch], wait=True)
        return len(points)

    def search(self, query: str, k: int = 5, where: dict | None = None,
               score_threshold: float | None = None) -> list[Hit]:
        qv = self.embedder.embed(query)
        flt = None
        if where:
            flt = models.Filter(must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=val))
                for key, val in where.items()])
        res = self.client.query_points(
            self.name, query=qv.tolist(), limit=k, query_filter=flt,
            score_threshold=score_threshold, with_payload=True).points
        return [Hit(id=str(p.id), text=p.payload.get("text", ""),
                    score=p.score,
                    meta={k2: v for k2, v in p.payload.items() if k2 != "text"})
                for p in res]

    def delete_doc(self, doc_id: str, tenant_id: str | None = None) -> None:
        must = [models.FieldCondition(key="doc_id",
                                      match=models.MatchValue(value=doc_id))]
        if tenant_id:
            must.append(models.FieldCondition(key="tenant_id",
                                              match=models.MatchValue(value=tenant_id)))
        self.client.delete(self.name,
                           points_selector=models.FilterSelector(
                               filter=models.Filter(must=must)))

    def count(self, where: dict | None = None) -> int:
        flt = models.Filter(must=[
            models.FieldCondition(key=k, match=models.MatchValue(value=v))
            for k, v in where.items()]) if where else None
        return self.client.count(self.name, count_filter=flt, exact=True).count
```

Thêm vào `leanai_core/config.py`: `QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")`

### Bước 3 — Test

`exercises/day33/qdrant_test.py`:

```python
from leanai_core.vectorstore import VectorStore, Chunk

vs = VectorStore("kb_test")

DOCS = [
 ("Chính sách hoàn tiền: hoàn 80% giá trị buổi chưa dùng, trừ phí xử lý 200.000đ.",
  {"doc_id": "chinh-sach.pdf", "page": 2, "tenant_id": "clinic_001", "doc_type": "policy"}),
 ("Gói Trị liệu da mặt: 10 buổi, giá 12.000.000đ, hạn dùng 6 tháng.",
  {"doc_id": "bang-gia.xlsx", "page": 1, "tenant_id": "clinic_001", "doc_type": "price"}),
 ("Giờ mở cửa: 9h-20h thứ 2 đến thứ 7. Chủ nhật nghỉ.",
  {"doc_id": "noi-quy.docx", "page": 1, "tenant_id": "clinic_001", "doc_type": "policy"}),
 ("Khách được chuyển nhượng gói cho người thân, báo trước 3 ngày làm việc.",
  {"doc_id": "chinh-sach.pdf", "page": 3, "tenant_id": "clinic_001", "doc_type": "policy"}),
 ("Bảng giá chi nhánh Quận 7: massage 500.000đ/buổi.",
  {"doc_id": "bang-gia-q7.xlsx", "page": 1, "tenant_id": "clinic_002", "doc_type": "price"}),
]

n = vs.upsert([Chunk(text=t, meta=m) for t, m in DOCS])
print(f"Đã nạp {n} chunk. Tổng trong collection: {vs.count()}")

print("\n=== Tìm không lọc ===")
for h in vs.search("tôi huỷ lịch có mất tiền không", k=3):
    print(f"  {h.score:.3f} {h.citation()} {h.text[:60]}")

print("\n=== Lọc theo tenant (QUAN TRỌNG) ===")
for h in vs.search("bảng giá", k=3, where={"tenant_id": "clinic_001"}):
    print(f"  {h.score:.3f} {h.meta['tenant_id']} {h.text[:60]}")

print("\n=== Kiểm tra cách ly tenant ===")
hits = vs.search("bảng giá quận 7", k=5, where={"tenant_id": "clinic_001"})
leak = [h for h in hits if h.meta.get("tenant_id") != "clinic_001"]
print(f"  Rò rỉ tenant: {len(leak)} (phải = 0)")

print(f"\nclinic_001 có {vs.count({'tenant_id': 'clinic_001'})} chunk")
vs.delete_doc("bang-gia.xlsx", tenant_id="clinic_001")
print(f"Sau khi xoá bang-gia.xlsx: {vs.count({'tenant_id': 'clinic_001'})} chunk")
```

---

## 4. Bài tập

**Bài 1 — Ảnh hưởng của HNSW.** Nạp 5.000 chunk giả. Tạo 3 collection với `m` = 4, 16, 64. Đo: thời gian build, thời gian search, recall@5 so với brute force. Lập bảng.

**Bài 2 — Filter có index vs không index.** Nạp 20.000 chunk với 10 tenant. Đo thời gian search có filter khi **có** payload index và khi **xoá** index. Chênh lệch bao nhiêu lần?

**Bài 3 — Kịch bản cập nhật.** Viết `reindex_doc(vs, doc_id, new_chunks)`: xoá hết chunk cũ của doc rồi nạp mới, đảm bảo không còn chunk mồ côi. Test: nạp 5 chunk → reindex thành 3 chunk → count phải đúng 3.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 33 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Qdrant chạy qua Docker, dashboard mở được
- [ ] `VectorStore` insert/search/delete/count hoạt động
- [ ] Payload index được tạo cho tenant_id, doc_id
- [ ] Test cách ly tenant cho kết quả rò rỉ = 0
- [ ] Có bảng đo ảnh hưởng tham số HNSW
- [ ] Quiz ≥ 80%
