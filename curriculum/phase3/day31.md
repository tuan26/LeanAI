# NGÀY 31 — Embedding thực chiến

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Xây `EmbeddingService` có cache, batch, và **đo được chất lượng trên dữ liệu tiếng Việt** trước khi chọn model.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Chọn model embedding — 5 tiêu chí

| Tiêu chí | Vì sao quan trọng |
|---|---|
| **Hỗ trợ tiếng Việt** | phần lớn model tối ưu tiếng Anh — phải tự test |
| Số chiều | nhiều chiều = chính xác hơn nhưng tốn RAM/đĩa hơn |
| Độ dài tối đa | chunk dài hơn giới hạn sẽ bị cắt âm thầm |
| Giá | tính trên 1 triệu token, rẻ hơn LLM nhiều nhưng không miễn phí |
| Self-host được không | dữ liệu y tế/tài chính có thể không được ra ngoài |

> **Không bao giờ chọn model embedding theo bảng xếp hạng tiếng Anh.** Phải chạy bộ test tiếng Việt của chính bạn (bài tập hôm nay).

### 1.2 Ba nguyên tắc bắt buộc

```
1. CACHE   : cùng text + cùng model → cùng vector. Cache theo hash.
2. BATCH   : gửi 50-100 text/lần thay vì từng cái → nhanh hơn 10-50×
3. CHUẨN HOÁ: lưu vector đã normalize → cosine trở thành phép nhân vô hướng
```

### 1.3 Chuẩn hoá text trước khi embed

```python
"  Chính  sách HOÀN TIỀN \n\n" → "chính sách hoàn tiền"
```

Nhưng **cẩn thận**: bỏ dấu tiếng Việt sẽ làm giảm chất lượng đáng kể. Chỉ chuẩn hoá khoảng trắng và ký tự vô hình, **giữ nguyên dấu và chữ hoa nếu model phân biệt**.

### 1.4 Cấm dùng embedding cho việc gì

| ❌ Không dùng để | Vì |
|---|---|
| So sánh số ("5 buổi" vs "50 buổi") | embedding không hiểu lượng |
| Kiểm tra phủ định | "có" và "không có" rất gần nhau |
| Lọc theo thời gian, tenant, trạng thái | dùng metadata filter (Ngày 34) |
| Tìm chính xác mã số, SĐT | dùng BM25/keyword (Ngày 36) |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| OpenAI Embeddings guide | https://platform.openai.com/docs/guides/embeddings |
| MTEB leaderboard (tham khảo, đừng tin mù) | https://huggingface.co/spaces/mteb/leaderboard |
| Sentence-Transformers (self-host) | https://www.sbert.net/ |

---

## 3. Thực hành (80 phút)

`leanai_core/embedding.py`:

```python
"""Embedding service: cache + batch + chuẩn hoá."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import numpy as np
from openai import OpenAI

from .config import cfg

CACHE_DB = Path("data/embed_cache.db")


class EmbeddingService:
    def __init__(self, model: str | None = None, cache: bool = True):
        self.model = model or cfg.EMBED_MODEL
        self.client = OpenAI(api_key=cfg.OPENAI_API_KEY)
        self.cache = cache
        self.hits = self.misses = 0
        if cache:
            CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(CACHE_DB)
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS emb (k TEXT PRIMARY KEY, v TEXT)")

    @staticmethod
    def normalize_text(t: str) -> str:
        t = t.replace(" ", " ").replace("​", "")
        return re.sub(r"\s+", " ", t).strip()

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}::{text}".encode()).hexdigest()

    def _get_cached(self, key: str):
        row = self.db.execute("SELECT v FROM emb WHERE k=?", (key,)).fetchone()
        return np.array(json.loads(row[0])) if row else None

    def _put_cached(self, key: str, vec: np.ndarray) -> None:
        self.db.execute("INSERT OR REPLACE INTO emb VALUES (?,?)",
                        (key, json.dumps(vec.tolist())))
        self.db.commit()

    def embed(self, texts: list[str] | str, batch_size: int = 64) -> np.ndarray:
        single = isinstance(texts, str)
        items = [self.normalize_text(t) for t in ([texts] if single else texts)]
        out: list[np.ndarray | None] = [None] * len(items)
        todo: list[int] = []

        if self.cache:
            for i, t in enumerate(items):
                v = self._get_cached(self._key(t))
                if v is not None:
                    out[i] = v; self.hits += 1
                else:
                    todo.append(i)
        else:
            todo = list(range(len(items)))

        for s in range(0, len(todo), batch_size):
            idxs = todo[s:s + batch_size]
            resp = self.client.embeddings.create(
                model=self.model, input=[items[i] for i in idxs])
            for i, d in zip(idxs, resp.data):
                v = np.array(d.embedding, dtype=np.float32)
                v = v / (np.linalg.norm(v) + 1e-12)      # chuẩn hoá
                out[i] = v
                self.misses += 1
                if self.cache:
                    self._put_cached(self._key(items[i]), v)

        arr = np.vstack(out)
        return arr[0] if single else arr

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed([a, b])
        return float(va @ vb)             # đã chuẩn hoá -> dot = cosine

    def stats(self) -> str:
        tot = self.hits + self.misses
        return (f"cache hit {self.hits}/{tot} ({self.hits/max(tot,1):.0%}) | "
                f"gọi API {self.misses} text")
```

`exercises/day31/vi_embedding_test.py` — **bộ test tiếng Việt của bạn**:

```python
"""Ngày 31: đánh giá model embedding trên tiếng Việt spa/phòng khám."""
from leanai_core.embedding import EmbeddingService

svc = EmbeddingService()

SHOULD_BE_CLOSE = [
 ("đặt lịch hẹn", "book an appointment"),
 ("giá bao nhiêu tiền", "chi phí là bao nhiêu"),
 ("gói liệu trình", "gói trị liệu"),
 ("chăm sóc da mặt", "dịch vụ facial"),
 ("khách không quay lại", "khách hàng rời bỏ"),
 ("hoàn tiền", "trả lại tiền"),
]

SHOULD_BE_FAR = [
 ("đặt lịch hẹn", "huỷ lịch hẹn"),
 ("gói còn hiệu lực", "gói đã hết hạn"),
 ("khách hài lòng", "khách khiếu nại"),
 ("thanh toán thành công", "thanh toán thất bại"),
]

TRAPS = [        # embedding thường THẤT BẠI ở đây
 ("có bảo hành", "không có bảo hành"),
 ("gói 5 buổi", "gói 50 buổi"),
 ("giảm 10%", "giảm 90%"),
 ("đã thanh toán", "chưa thanh toán"),
]

def report(name, pairs):
    print(f"\n=== {name} ===")
    scores = []
    for a, b in pairs:
        s = svc.similarity(a, b)
        scores.append(s)
        print(f"  {s:.3f}  {a!r} <-> {b!r}")
    print(f"  Trung bình: {sum(scores)/len(scores):.3f}")
    return sum(scores) / len(scores)

close = report("PHẢI GẦN NHAU", SHOULD_BE_CLOSE)
far = report("PHẢI XA NHAU", SHOULD_BE_FAR)
trap = report("BẪY (phủ định / số lượng)", TRAPS)

print(f"\n{'='*60}")
print(f"Khoảng cách phân tách: {close - far:.3f}  (càng lớn càng tốt, > 0.15 là ổn)")
print(f"Điểm bẫy: {trap:.3f}  (CAO = model KHÔNG phân biệt được -> nguy hiểm)")
print(f"\n{svc.stats()}")
print("\nKẾT LUẬN: mọi cặp bẫy có điểm > 0.85 đều là lỗ hổng bạn phải")
print("chữa bằng hybrid search (Ngày 36) hoặc metadata filter (Ngày 34).")
```

---

## 4. Bài tập

**Bài 1 — So sánh 2 model.** Chạy bộ test trên ít nhất 2 model embedding khác nhau. Lập bảng: khoảng cách phân tách, điểm bẫy, số chiều, giá, latency. Chọn một và **ghi lý do** vào `progress/notes/day31-embedding-choice.md`.

**Bài 2 — Hiệu quả cache và batch.** Embed 500 đoạn text. Đo: (a) không cache không batch, (b) có batch, (c) chạy lại lần 2 với cache. Lập bảng thời gian + chi phí. Tính: cache tiết kiệm bao nhiêu % trong 20 ngày Phase 3?

**Bài 3 — Mở rộng bộ bẫy.** Thêm 10 cặp bẫy đặc thù ngành của bạn (y tế/thẩm mỹ). Đây là bộ test bạn sẽ chạy lại mỗi khi đổi model embedding.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 31 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `EmbeddingService` có cache SQLite, batch, chuẩn hoá vector
- [ ] Bộ test tiếng Việt chạy được, có 3 nhóm (gần / xa / bẫy)
- [ ] Có số liệu so sánh ≥ 2 model, chọn được một có lý do
- [ ] Chỉ ra được ít nhất 2 cặp bẫy mà model thất bại
- [ ] Cache hit ≥ 90% khi chạy lại
- [ ] Quiz ≥ 80%
