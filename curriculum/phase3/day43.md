# NGÀY 43 — Indexing & incremental update

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Re-index **không trùng, không mồ côi, không tốn tiền embed lại** những gì không đổi.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vấn đề: tài liệu thay đổi liên tục

```
Ngày 1:  chinh-sach.docx (v1) → 20 chunk
Ngày 30: chinh-sach.docx (v2) → sửa 2 mục, thêm 1 mục
```

Xử lý sai:
- Nạp lại toàn bộ → **trùng lặp** 20 chunk cũ vẫn còn → AI trả lời theo bản cũ
- Xoá sạch rồi nạp lại → tốn tiền embed lại 18 chunk **không đổi**, và có khoảng thời gian tài liệu biến mất

### 1.2 Giải pháp: content hash

```
Với mỗi chunk:  hash = sha256(text)

Chunk mới:  hash không có trong index  → embed + upsert
Chunk cũ:   hash vẫn còn trong tài liệu mới → GIỮ NGUYÊN, không embed lại
Chunk xoá:  hash có trong index nhưng không còn trong tài liệu → xoá
```

Đây là **diff 3 chiều**, giống git. Tiết kiệm phần lớn chi phí embedding khi tài liệu chỉ sửa nhỏ.

### 1.3 Ba bất biến của index

```
1. KHÔNG TRÙNG   : một (doc_id, chunk_hash) chỉ tồn tại 1 lần
2. KHÔNG MỒ CÔI  : không còn chunk của tài liệu đã bị xoá
3. NHẤT QUÁN     : trong lúc re-index, truy vấn vẫn trả về kết quả hợp lệ
```

Bất biến 3 đạt được bằng cách **upsert trước, xoá sau** (không xoá trước rồi nạp).

### 1.4 ID ổn định

```python
point_id = uuid5(NAMESPACE, f"{tenant_id}:{doc_id}:{chunk_hash}")
```

Cùng nội dung → cùng ID → upsert tự động ghi đè, không tạo bản trùng. Đừng dùng `uuid4()` ngẫu nhiên.

### 1.5 Theo dõi trạng thái ingest

Cần một bảng nhỏ (SQLite/Postgres) ghi: `doc_id, file_hash, n_chunks, ingested_at, status, error`. Không có nó, bạn không biết tài liệu nào đã xử lý, cái nào lỗi.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Qdrant — Points & upsert | https://qdrant.tech/documentation/concepts/points/ |
| Qdrant — Snapshots (backup) | https://qdrant.tech/documentation/concepts/snapshots/ |

---

## 3. Thực hành (80 phút)

`leanai_core/indexer.py`:

```python
"""Index tăng dần: chỉ embed lại phần thay đổi."""
from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import models

from .vectorstore import VectorStore, Chunk

NS = uuid.UUID("6f1e2c00-0000-4000-8000-000000000000")
STATE_DB = Path("data/ingest_state.db")


def stable_id(tenant_id: str, doc_id: str, chunk_hash: str) -> str:
    return str(uuid.uuid5(NS, f"{tenant_id}:{doc_id}:{chunk_hash}"))


def text_hash(t: str) -> str:
    return hashlib.sha256(t.strip().encode()).hexdigest()[:16]


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()[:16]


@dataclass
class IndexResult:
    doc_id: str
    added: int = 0
    kept: int = 0
    removed: int = 0
    skipped: bool = False

    def __str__(self):
        if self.skipped:
            return f"{self.doc_id}: bỏ qua (không đổi)"
        return (f"{self.doc_id}: +{self.added} thêm, ={self.kept} giữ, "
                f"-{self.removed} xoá")


class IngestState:
    def __init__(self, path: Path = STATE_DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS docs(
            tenant_id TEXT, doc_id TEXT, file_hash TEXT, n_chunks INT,
            ingested_at TEXT, status TEXT, error TEXT,
            PRIMARY KEY (tenant_id, doc_id))""")
        self.db.commit()

    def get_hash(self, tenant_id: str, doc_id: str) -> str | None:
        row = self.db.execute(
            "SELECT file_hash FROM docs WHERE tenant_id=? AND doc_id=?",
            (tenant_id, doc_id)).fetchone()
        return row[0] if row else None

    def record(self, tenant_id: str, doc_id: str, fhash: str, n: int,
               status: str = "ok", error: str = "") -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?)",
            (tenant_id, doc_id, fhash, n,
             datetime.now(timezone.utc).isoformat(), status, error))
        self.db.commit()

    def report(self) -> list[tuple]:
        return self.db.execute(
            "SELECT doc_id, n_chunks, status, ingested_at FROM docs "
            "ORDER BY ingested_at DESC").fetchall()


class Indexer:
    def __init__(self, vs: VectorStore, state: IngestState | None = None):
        self.vs = vs
        self.state = state or IngestState()

    def existing_hashes(self, tenant_id: str, doc_id: str) -> dict[str, str]:
        """{chunk_hash: point_id} của tài liệu hiện có trong index."""
        flt = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])
        out, offset = {}, None
        while True:
            batch, offset = self.vs.client.scroll(
                self.vs.name, scroll_filter=flt, limit=500, offset=offset,
                with_payload=["chunk_hash"], with_vectors=False)
            for p in batch:
                out[p.payload.get("chunk_hash", "")] = str(p.id)
            if offset is None:
                break
        return out

    def index_doc(self, tenant_id: str, doc_id: str, chunks: list[Chunk],
                  source_path: Path | None = None) -> IndexResult:
        res = IndexResult(doc_id=doc_id)

        # 1. Bỏ qua nếu file không đổi
        if source_path and source_path.exists():
            fh = file_hash(source_path)
            if self.state.get_hash(tenant_id, doc_id) == fh:
                res.skipped = True
                return res
        else:
            fh = ""

        # 2. Diff theo chunk_hash
        old = self.existing_hashes(tenant_id, doc_id)
        new_hashes = set()
        to_add: list[Chunk] = []
        for c in chunks:
            h = text_hash(c.text)
            new_hashes.add(h)
            c.meta = {**c.meta, "tenant_id": tenant_id, "doc_id": doc_id,
                      "chunk_hash": h}
            c.id = stable_id(tenant_id, doc_id, h)
            if h in old:
                res.kept += 1
            else:
                to_add.append(c)

        # 3. Upsert TRƯỚC (giữ tính nhất quán khi đang truy vấn)
        if to_add:
            self.vs.upsert(to_add)
            res.added = len(to_add)

        # 4. Xoá chunk không còn
        gone = [pid for h, pid in old.items() if h not in new_hashes]
        if gone:
            self.vs.client.delete(
                self.vs.name,
                points_selector=models.PointIdsList(points=gone))
            res.removed = len(gone)

        self.state.record(tenant_id, doc_id, fh, len(chunks))
        return res

    def verify(self, tenant_id: str) -> dict:
        """Kiểm tra 3 bất biến."""
        flt = models.Filter(must=[models.FieldCondition(
            key="tenant_id", match=models.MatchValue(value=tenant_id))])
        seen, dupes, offset = set(), 0, None
        docs: dict[str, int] = {}
        while True:
            batch, offset = self.vs.client.scroll(
                self.vs.name, scroll_filter=flt, limit=500, offset=offset,
                with_payload=["doc_id", "chunk_hash"], with_vectors=False)
            for p in batch:
                key = (p.payload.get("doc_id"), p.payload.get("chunk_hash"))
                if key in seen:
                    dupes += 1
                seen.add(key)
                docs[p.payload.get("doc_id", "?")] = docs.get(p.payload.get("doc_id", "?"), 0) + 1
            if offset is None:
                break
        known = {d[0] for d in self.state.report()}
        orphans = [d for d in docs if d not in known]
        return {"tổng chunk": sum(docs.values()), "số tài liệu": len(docs),
                "trùng lặp": dupes, "mồ côi": orphans}
```

`exercises/day43/incremental_test.py`:

```python
from pathlib import Path
from leanai_core.vectorstore import VectorStore, Chunk
from leanai_core.indexer import Indexer

vs = VectorStore("kb_incremental")
ix = Indexer(vs)
T = "clinic_001"

v1 = ["Chính sách hoàn tiền: hoàn 80%.",
      "Giờ mở cửa 9h-20h.",
      "Chuyển nhượng gói báo trước 3 ngày.",
      "Phí giữ chỗ 200.000đ."]
print(ix.index_doc(T, "cs.docx", [Chunk(text=t) for t in v1]))

# v2: giữ 2 câu, sửa 1, thêm 1, xoá 1
v2 = ["Chính sách hoàn tiền: hoàn 80%.",
      "Giờ mở cửa 9h-20h.",
      "Chuyển nhượng gói báo trước 5 ngày làm việc.",   # sửa
      "Khách VIP được ưu tiên xếp lịch."]               # thêm
print(ix.index_doc(T, "cs.docx", [Chunk(text=t) for t in v2]))
print("Kỳ vọng: +2 thêm, =2 giữ, -2 xoá")

print(ix.index_doc(T, "cs.docx", [Chunk(text=t) for t in v2]))
print("Kỳ vọng: +0, =4, -0 (chạy lại không đổi gì)")

print("\nKiểm tra bất biến:", ix.verify(T))
print("\nTrạng thái ingest:")
for r in ix.state.report():
    print("  ", r)
```

---

## 4. Bài tập

**Bài 1 — Đo tiết kiệm.** Tài liệu 100 chunk, sửa 5 chunk. So sánh: (a) nạp lại toàn bộ, (b) incremental. Đo số lần gọi API embedding và chi phí. Tiết kiệm bao nhiêu %?

**Bài 2 — Xoá tài liệu.** Viết `delete_doc_fully(tenant_id, doc_id)` xoá cả trong vector store và bảng trạng thái. Chạy `verify()` chứng minh không còn mồ côi.

**Bài 3 — Ingest lỗi giữa chừng.** Mô phỏng: đang nạp 50 chunk thì lỗi ở chunk 30. Trạng thái index lúc đó thế nào? Chạy lại có sinh trùng không? Nếu có → sửa. Ghi kết luận vào note.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 43 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Re-index 2 lần liên tiếp không tạo bản trùng
- [ ] Chunk không đổi **không** bị embed lại (chứng minh bằng số lần gọi API)
- [ ] Chunk đã xoá khỏi tài liệu biến mất khỏi index
- [ ] `verify()` báo trùng lặp = 0, mồ côi = 0
- [ ] Bảng trạng thái ingest ghi đủ thông tin
- [ ] Quiz ≥ 80%
