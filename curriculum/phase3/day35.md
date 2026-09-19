# NGÀY 35 — Semantic search & đo recall

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Xây **bộ test truy hồi** và đo recall@k, MRR. Từ hôm nay bạn không được nói "search có vẻ tốt" nữa — chỉ được nói con số.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Bốn chỉ số phải biết

| Chỉ số | Nghĩa | Khi nào quan trọng nhất |
|---|---|---|
| **Recall@k** | % truy vấn có tài liệu đúng nằm trong top-k | **quan trọng nhất cho RAG** |
| **Precision@k** | % kết quả trả về là đúng | khi context window hẹp |
| **MRR** | trung bình 1/thứ hạng của kết quả đúng đầu tiên | đo "đúng có nằm trên đầu không" |
| **nDCG@k** | có tính đến thứ tự + mức độ liên quan | khi có nhiều mức liên quan |

> **Với RAG, recall@k quan trọng hơn precision.** Nếu tài liệu đúng không có trong top-k, LLM **không thể** trả lời đúng — mọi kỹ thuật prompt sau đó đều vô nghĩa. Nhiễu thừa thì LLM còn lọc được.

### 1.2 Bộ test truy hồi — cách xây

```jsonc
{
  "query": "tôi huỷ lịch có mất tiền không",
  "relevant_doc_ids": ["chinh-sach.pdf#chunk2"],   // do BẠN gán, không do AI
  "difficulty": "medium",
  "type": "paraphrase"   // exact | paraphrase | multi_hop | negation | numeric
}
```

**Tối thiểu 30 truy vấn**, phân bố:
- 40% diễn đạt lại (khách hỏi khác cách viết trong tài liệu)
- 20% cần ghép nhiều tài liệu (multi-hop)
- 15% có phủ định
- 15% có con số/ngày tháng
- 10% **không có đáp án** (để đo tỉ lệ từ chối đúng)

### 1.3 Quy trình cải thiện

```
đo baseline → thay ĐÚNG MỘT thứ → đo lại → giữ nếu tốt hơn
```

Thay nhiều thứ cùng lúc = không biết cái nào có tác dụng. Đây là kỷ luật quan trọng nhất của Phase 3.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Pinecone — Evaluation measures for IR | https://www.pinecone.io/learn/offline-evaluation/ |
| RAGAS — metrics | https://docs.ragas.io/en/stable/concepts/metrics/ |

---

## 3. Thực hành (80 phút)

`leanai_core/retrieval_eval.py`:

```python
"""Đo chất lượng truy hồi: recall@k, precision@k, MRR, nDCG."""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalCase:
    query: str
    relevant_ids: list[str]
    difficulty: str = "medium"
    qtype: str = "paraphrase"


def load_cases(path: str) -> list[EvalCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(c["query"], c["relevant_doc_ids"],
                     c.get("difficulty", "medium"), c.get("type", "paraphrase"))
            for c in raw]


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 1.0 if not retrieved else 0.0        # ca "không có đáp án"
    top = set(retrieved[:k])
    return len(top & set(relevant)) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not retrieved[:k]:
        return 0.0
    return len(set(retrieved[:k]) & set(relevant)) / min(k, len(retrieved))


def mrr(retrieved: list[str], relevant: list[str]) -> float:
    for i, r in enumerate(retrieved, 1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 1) for i, r in enumerate(retrieved[:k], 1) if r in relevant)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / idcg if idcg else 0.0


def evaluate(search_fn, cases: list[EvalCase], ks=(1, 3, 5, 10)) -> dict:
    """search_fn(query, k) -> list[chunk_id]"""
    res = {f"recall@{k}": [] for k in ks}
    res.update({f"precision@{k}": [] for k in ks})
    res["mrr"] = []; res["ndcg@5"] = []; res["latency_ms"] = []
    by_type: dict[str, list[float]] = {}
    failures = []

    for c in cases:
        t0 = time.perf_counter()
        got = search_fn(c.query, max(ks))
        res["latency_ms"].append((time.perf_counter() - t0) * 1000)
        for k in ks:
            res[f"recall@{k}"].append(recall_at_k(got, c.relevant_ids, k))
            res[f"precision@{k}"].append(precision_at_k(got, c.relevant_ids, k))
        res["mrr"].append(mrr(got, c.relevant_ids))
        res["ndcg@5"].append(ndcg_at_k(got, c.relevant_ids, 5))
        by_type.setdefault(c.qtype, []).append(recall_at_k(got, c.relevant_ids, 5))
        if recall_at_k(got, c.relevant_ids, 5) == 0:
            failures.append({"query": c.query, "expected": c.relevant_ids, "got": got[:5]})

    out = {k: sum(v) / len(v) for k, v in res.items()}
    out["recall@5_by_type"] = {t: sum(v) / len(v) for t, v in by_type.items()}
    out["failures"] = failures
    return out


def print_report(name: str, r: dict) -> None:
    print(f"\n=== {name} ===")
    for k in ("recall@1", "recall@3", "recall@5", "recall@10",
              "precision@5", "mrr", "ndcg@5"):
        print(f"  {k:<14} {r[k]:.3f}")
    print(f"  {'latency':<14} {r['latency_ms']:.0f} ms")
    print("  Recall@5 theo loại truy vấn:")
    for t, v in sorted(r["recall@5_by_type"].items(), key=lambda x: x[1]):
        flag = " ⚠" if v < 0.7 else ""
        print(f"    {t:<12} {v:.2f}{flag}")
    if r["failures"]:
        print(f"  {len(r['failures'])} truy vấn THẤT BẠI hoàn toàn:")
        for f in r["failures"][:5]:
            print(f"    - {f['query'][:55]}")
```

`exercises/day35/run_eval.py`:

```python
from leanai_core.vectorstore import VectorStore
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

vs = VectorStore("kb_meta")
cases = load_cases("templates/retrieval-testset.json")

def search(q: str, k: int) -> list[str]:
    return [f"{h.meta['doc_id']}#chunk{h.meta.get('chunk_index',0)}"
            for h in vs.search(q, k=k, where={"tenant_id": "clinic_001"})]

print_report("BASELINE — semantic thuần", evaluate(search, cases))
```

---

## 4. Bài tập

**Bài 1 — Bộ test 30 truy vấn.** Tạo `templates/retrieval-testset.json` đúng phân bố ở mục 1.2, gán nhãn bằng tay. **Đây là tài sản quan trọng nhất của Phase 3** — bạn sẽ dùng nó ở ngày 36, 41, 45, 46, 47, 50.

**Bài 2 — Baseline.** Chạy `run_eval.py`, ghi kết quả vào `progress/notes/day35-baseline.md`. Ghi rõ: cấu hình embedding model, chunk size, k. Mọi cải tiến sau này đều so với con số này.

**Bài 3 — Phân tích thất bại.** Lấy 5 truy vấn recall@5 = 0. Với mỗi cái, tìm nguyên nhân: (a) chunk sai cỡ, (b) từ khoá không có trong text, (c) phủ định/số lượng, (d) cần nhiều tài liệu. Ghi lại — mỗi nguyên nhân sẽ được xử lý ở một ngày cụ thể phía trước.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 35 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Có 30 truy vấn test có nhãn, đúng phân bố loại
- [ ] Đo được recall@1/3/5/10, precision, MRR, nDCG
- [ ] Có báo cáo baseline ghi rõ cấu hình
- [ ] Phân tích được nguyên nhân của ≥ 5 ca thất bại
- [ ] Recall@5 baseline ≥ 0.6 (nếu thấp hơn, ghi lại để so sau)
- [ ] Quiz ≥ 80%
