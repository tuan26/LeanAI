# NGÀY 32 — Cosine similarity & vector math

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Tự cài tìm kiếm vector, hiểu vì sao vector DB tồn tại, và **đo được giới hạn của brute force**.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba phép đo khoảng cách

| Phép đo | Công thức | Dùng khi |
|---|---|---|
| **Cosine** | `A·B / (|A||B|)` | mặc định cho text — chỉ quan tâm hướng |
| **Dot product** | `A·B` | khi vector đã chuẩn hoá → **bằng cosine, nhanh hơn** |
| **Euclidean (L2)** | `√Σ(aᵢ-bᵢ)²` | khi độ lớn có ý nghĩa (hiếm với text) |

> Chuẩn hoá vector khi lưu (Ngày 31) rồi dùng dot product — nhanh nhất mà kết quả y hệt cosine.

### 1.2 Brute force và giới hạn của nó

```
Tìm top-k trong N vector d chiều: O(N × d)
```

| Số chunk | Thời gian brute force (d=1536) |
|---|---|
| 1.000 | ~2 ms — ổn |
| 100.000 | ~200 ms — bắt đầu chậm |
| 10.000.000 | ~20 s — không dùng được |

Vector DB dùng **ANN** (approximate nearest neighbor, vd HNSW): đổi một chút độ chính xác lấy tốc độ gấp hàng trăm lần.

### 1.3 "Lời nguyền số chiều"

Ở số chiều cao, mọi vector ngẫu nhiên gần như trực giao nhau (cosine ≈ 0). Hệ quả thực tế: **điểm số tuyệt đối ít ý nghĩa, thứ hạng tương đối mới quan trọng**. Đừng đặt ngưỡng cứng kiểu "score > 0.8 mới lấy" mà chưa đo.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Pinecone — Vector similarity explained | https://www.pinecone.io/learn/vector-similarity/ |
| HNSW paper (abstract) | https://arxiv.org/abs/1603.09320 |

---

## 3. Thực hành (80 phút)

`exercises/day32/vector_search.py`:

```python
"""Ngày 32: tự cài tìm kiếm vector, đo giới hạn brute force."""
import time
import numpy as np

rng = np.random.default_rng(42)


def normalize(M: np.ndarray) -> np.ndarray:
    return M / (np.linalg.norm(M, axis=-1, keepdims=True) + 1e-12)


def brute_force_topk(query: np.ndarray, matrix: np.ndarray, k: int = 5):
    scores = matrix @ query                       # đã chuẩn hoá -> dot = cosine
    idx = np.argpartition(-scores, k)[:k]         # nhanh hơn argsort toàn bộ
    idx = idx[np.argsort(-scores[idx])]
    return [(int(i), float(scores[i])) for i in idx]


def benchmark(sizes=(1_000, 10_000, 100_000, 500_000), dim=1536, k=5):
    print(f"{'N vector':>10} {'ms/query':>10} {'RAM (MB)':>10}")
    for n in sizes:
        M = normalize(rng.normal(0, 1, (n, dim)).astype(np.float32))
        q = normalize(rng.normal(0, 1, dim).astype(np.float32))
        brute_force_topk(q, M, k)                 # làm nóng
        t0 = time.perf_counter()
        for _ in range(10):
            brute_force_topk(q, M, k)
        ms = (time.perf_counter() - t0) / 10 * 1000
        print(f"{n:>10,} {ms:>10.1f} {M.nbytes/1e6:>10.0f}")


def curse_of_dimensionality():
    print(f"\n{'chiều':>8} {'cosine TB':>12} {'độ lệch chuẩn':>14}")
    for d in (2, 10, 100, 768, 1536, 3072):
        A = normalize(rng.normal(0, 1, (500, d)))
        S = A @ A.T
        off = S[~np.eye(500, dtype=bool)]
        print(f"{d:>8} {off.mean():>12.4f} {off.std():>14.4f}")
    print("  -> chiều càng cao, vector ngẫu nhiên càng trực giao (cosine ~ 0)")
    print("  -> điểm tuyệt đối mất ý nghĩa, phải dùng THỨ HẠNG")


if __name__ == "__main__":
    print("=== Brute force benchmark ===")
    benchmark()
    print("\n=== Lời nguyền số chiều ===")
    curse_of_dimensionality()
```

`exercises/day32/mini_index.py` — index có thể tìm + lọc:

```python
"""Index vector tối giản, có metadata filter — tiền thân của Ngày 33-34."""
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Doc:
    id: str
    text: str
    meta: dict = field(default_factory=dict)


class MiniIndex:
    def __init__(self, embedder):
        self.embedder = embedder
        self.docs: list[Doc] = []
        self.M: np.ndarray | None = None

    def add(self, docs: list[Doc]) -> None:
        self.docs.extend(docs)
        vecs = self.embedder.embed([d.text for d in docs])
        self.M = vecs if self.M is None else np.vstack([self.M, vecs])

    def search(self, query: str, k: int = 5, where: dict | None = None):
        q = self.embedder.embed(query)
        scores = self.M @ q
        order = np.argsort(-scores)
        out = []
        for i in order:
            d = self.docs[i]
            if where and any(d.meta.get(kk) != vv for kk, vv in where.items()):
                continue                     # lọc SAU khi xếp hạng — xem nhược điểm ở Ngày 34
            out.append((d, float(scores[i])))
            if len(out) >= k:
                break
        return out
```

---

## 4. Bài tập

**Bài 1 — Bảng benchmark.** Chạy `benchmark()` với N đến mức máy bạn chịu được. Xác định: ở mức N nào thì brute force vượt 100ms? Đó là ngưỡng bạn **bắt buộc** phải chuyển sang vector DB.

**Bài 2 — Lọc trước hay lọc sau.** `MiniIndex.search` đang lọc **sau** khi xếp hạng. Tìm trường hợp làm nó trả về **ít hơn k kết quả** dù dữ liệu có đủ. Viết phiên bản lọc **trước** rồi so sánh. Ghi nhận xét — đây là bài học cho Ngày 34.

**Bài 3 — Đo tương quan điểm số.** Lấy 20 cặp câu có nhãn "liên quan/không liên quan" từ Ngày 31, tính điểm. Vẽ bảng phân bố. Có ngưỡng nào tách sạch 2 nhóm không? Nếu không → kết luận gì về việc dùng ngưỡng cứng?

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 32 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Tự cài được `brute_force_topk`, kết quả khớp với thư viện
- [ ] Có bảng benchmark, xác định được ngưỡng N cần vector DB
- [ ] Chứng minh được lời nguyền số chiều bằng số liệu
- [ ] Chỉ ra được nhược điểm của lọc-sau-xếp-hạng
- [ ] Quiz ≥ 80%
