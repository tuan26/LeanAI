# NGÀY 36 — Hybrid search (BM25 + vector)

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Kết hợp tìm kiếm từ khoá và ngữ nghĩa, đo mức cải thiện trên chính bộ test hôm qua.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Hai loại tìm kiếm bù trừ cho nhau

| | BM25 (từ khoá) | Vector (ngữ nghĩa) |
|---|---|---|
| Mã sản phẩm, SĐT, tên riêng | ✅ xuất sắc | ❌ kém |
| Diễn đạt khác từ ngữ | ❌ trượt hoàn toàn | ✅ xuất sắc |
| Từ hiếm, thuật ngữ chuyên ngành | ✅ | ❌ nếu không có trong train |
| Phủ định | ⚠️ tìm được từ "không" | ❌ rất kém |
| Đa ngôn ngữ | ❌ | ✅ |

> Truy vấn "gói VIP-7788 còn hạn không" — vector sẽ trượt mã `VIP-7788`, BM25 bắt ngay. Truy vấn "tôi huỷ có mất tiền không" — BM25 trượt vì tài liệu viết "hoàn tiền khi huỷ lịch", vector bắt được.

### 1.2 BM25 tóm tắt

Cải tiến của TF-IDF: từ xuất hiện nhiều trong tài liệu → điểm cao, nhưng **bão hoà** (xuất hiện 20 lần không gấp 20 lần 1 lần); tài liệu dài bị phạt.

Với tiếng Việt: cần tách từ. Cách đơn giản là tách theo khoảng trắng + n-gram; cách tốt hơn dùng thư viện tách từ tiếng Việt.

### 1.3 Reciprocal Rank Fusion (RRF) — cách gộp tốt nhất

```
score(d) = Σ  1 / (k + rank_i(d))        k thường = 60
         i∈{bm25, vector}
```

Ưu điểm lớn: **không cần chuẩn hoá điểm** giữa hai hệ (điểm BM25 và cosine không cùng thang). Chỉ dùng thứ hạng.

Cách khác — weighted sum — cần chuẩn hoá và cần chỉnh trọng số, dễ sai. **Dùng RRF trước.**

### 1.4 Chi phí

Hybrid ≈ 2× công tìm kiếm nhưng **latency tăng ít** nếu chạy song song. Chi phí LLM không đổi. Đây là một trong những cải tiến **rẻ nhất** của RAG.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Qdrant — Hybrid queries | https://qdrant.tech/documentation/concepts/hybrid-queries/ |
| RRF paper | https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf |
| rank-bm25 | https://github.com/dorianbrown/rank_bm25 |

---

## 3. Thực hành (80 phút)

`leanai_core/hybrid.py`:

```python
"""Hybrid search: BM25 + vector, gộp bằng RRF."""
from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi

from .vectorstore import VectorStore, Hit


def tokenize_vi(text: str) -> list[str]:
    """Tách từ tiếng Việt đơn giản: token đơn + bigram (giữ dấu)."""
    text = unicodedata.normalize("NFC", text.lower())
    words = re.findall(r"[0-9a-zà-ỹ]+", text)
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return words + bigrams


class HybridSearch:
    def __init__(self, vs: VectorStore, tenant_id: str | None = None):
        self.vs = vs
        self.tenant_id = tenant_id
        self.corpus: list[Hit] = []
        self.bm25: BM25Okapi | None = None

    def build_bm25(self, where: dict | None = None, limit: int = 50_000) -> int:
        """Nạp toàn bộ chunk (đã lọc) vào chỉ mục BM25 trong bộ nhớ."""
        flt = self.vs.build_filter(where)
        points, offset = [], None
        while True:
            batch, offset = self.vs.client.scroll(
                self.vs.name, scroll_filter=flt, limit=1000,
                offset=offset, with_payload=True, with_vectors=False)
            points.extend(batch)
            if offset is None or len(points) >= limit:
                break
        self.corpus = [Hit(id=str(p.id), text=p.payload.get("text", ""), score=0.0,
                           meta={k: v for k, v in p.payload.items() if k != "text"})
                       for p in points]
        self.bm25 = BM25Okapi([tokenize_vi(h.text) for h in self.corpus])
        return len(self.corpus)

    def search_bm25(self, query: str, k: int = 10) -> list[Hit]:
        scores = self.bm25.get_scores(tokenize_vi(query))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        out = []
        for i in order:
            h = self.corpus[i]
            out.append(Hit(id=h.id, text=h.text, score=float(scores[i]), meta=h.meta))
        return out

    def search(self, query: str, k: int = 5, where: dict | None = None,
               candidates: int = 20, rrf_k: int = 60,
               mode: str = "hybrid") -> list[Hit]:
        if mode == "vector":
            return self.vs.search(query, k=k, where=where)
        if mode == "bm25":
            return self.search_bm25(query, k=k)

        with ThreadPoolExecutor(2) as ex:
            f_vec = ex.submit(self.vs.search, query, candidates, where)
            f_bm = ex.submit(self.search_bm25, query, candidates)
            vec_hits, bm_hits = f_vec.result(), f_bm.result()

        fused: dict[str, float] = {}
        store: dict[str, Hit] = {}
        for hits in (vec_hits, bm_hits):
            for rank, h in enumerate(hits, 1):
                fused[h.id] = fused.get(h.id, 0.0) + 1.0 / (rrf_k + rank)
                store[h.id] = h
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [Hit(id=i, text=store[i].text, score=s, meta=store[i].meta)
                for i, s in top]
```

`exercises/day36/hybrid_eval.py`:

```python
"""Ngày 36: so sánh 3 chiến lược trên cùng bộ test."""
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

vs = VectorStore("kb_meta")
hs = HybridSearch(vs)
n = hs.build_bm25(where={"tenant_id": "clinic_001"})
print(f"BM25 index: {n} chunk")

cases = load_cases("templates/retrieval-testset.json")
WHERE = {"tenant_id": "clinic_001"}

def make(mode):
    def fn(q, k):
        hits = hs.search(q, k=k, where=WHERE, mode=mode)
        return [f"{h.meta['doc_id']}#chunk{h.meta.get('chunk_index',0)}" for h in hits]
    return fn

results = {}
for mode in ("vector", "bm25", "hybrid"):
    r = evaluate(make(mode), cases)
    results[mode] = r
    print_report(mode.upper(), r)

print("\n=== SO SÁNH ===")
print(f"{'mode':<10} {'recall@5':>9} {'MRR':>7} {'latency':>9}")
for m, r in results.items():
    print(f"{m:<10} {r['recall@5']:>9.3f} {r['mrr']:>7.3f} {r['latency_ms']:>8.0f}ms")

base = results["vector"]["recall@5"]
gain = (results["hybrid"]["recall@5"] - base) / max(base, 1e-9)
print(f"\nHybrid cải thiện recall@5: {gain:+.1%} so với vector thuần")
```

---

## 4. Bài tập

**Bài 1 — Chỉnh `rrf_k`.** Thử `rrf_k` = 10, 30, 60, 100. Giá trị nào tốt nhất trên bộ test của bạn? Ghi bảng.

**Bài 2 — Phân tích theo loại truy vấn.** Dùng `recall@5_by_type`. Loại nào BM25 thắng? Loại nào vector thắng? Kết quả có khớp bảng lý thuyết 1.1 không? Nếu không, giải thích.

**Bài 3 — Truy vấn mã số.** Thêm 5 truy vấn chứa mã/số điện thoại/ngày cụ thể vào bộ test. Đo lại 3 chiến lược. Chênh lệch chắc chắn sẽ rất lớn — ghi con số cụ thể để dùng trong báo cáo Ngày 50.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 36 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] BM25 chạy được trên tiếng Việt có dấu
- [ ] RRF gộp đúng, không cần chuẩn hoá điểm
- [ ] Vector và BM25 chạy song song
- [ ] Có bảng so sánh 3 chiến lược trên cùng 30 truy vấn
- [ ] Hybrid ≥ vector thuần về recall@5
- [ ] Quiz ≥ 80%
