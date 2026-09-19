# NGÀY 47 — Reranking

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Thêm tầng xếp hạng lại và đo nDCG trước/sau. Đây thường là **cải tiến chất lượng lớn nhất còn lại** của RAG.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao cần rerank

Embedding nén cả đoạn văn thành **một vector** → mất chi tiết. Reranker đọc **cặp (truy vấn, tài liệu) cùng lúc** nên hiểu quan hệ sâu hơn nhiều.

```
Bi-encoder (embedding)          Cross-encoder (reranker)
query ──► vector ┐               ┌─ query ─┐
                 ├─ so sánh      │         ├──► model ──► điểm
doc   ──► vector ┘               └─ doc ───┘
nhanh, tìm trong triệu bản ghi   chậm, chỉ xếp lại vài chục bản ghi
```

### 1.2 Kiến trúc hai tầng

```
Truy hồi (hybrid, k=30-50)  →  Rerank (top 30 → top 5)  →  LLM
   nhanh, recall cao            chậm, precision cao
```

**Quy tắc:** truy hồi rộng (k lớn) rồi rerank hẹp. Nếu truy hồi đã bỏ sót tài liệu đúng thì rerank không cứu được.

### 1.3 Ba cách rerank

| Cách | Chất lượng | Chi phí | Latency |
|---|---|---|---|
| **Cross-encoder API** (Cohere/Voyage rerank) | cao | rẻ | ~100–300ms |
| **LLM-as-reranker** | cao | đắt hơn | ~1–2s |
| **Cross-encoder self-host** | khá–cao | máy chủ | ~50–200ms |

Hôm nay cài **LLM-as-reranker** vì bạn đã có sẵn LLM client — và nó dạy bạn nguyên lý. Trong sản phẩm thật, cân nhắc API rerank chuyên dụng.

### 1.4 Mẹo giảm chi phí LLM rerank

- Cắt mỗi chunk còn ~200 token đầu khi đưa vào chấm điểm.
- Chấm **theo lô** (10 chunk/lần) thay vì từng cái.
- Yêu cầu output cực ngắn: chỉ danh sách id + điểm.
- Dùng model rẻ cho tầng rerank — nó chỉ cần so sánh, không cần sinh văn.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Cohere Rerank | https://docs.cohere.com/docs/rerank-overview |
| Sentence-Transformers Cross-Encoders | https://www.sbert.net/examples/applications/cross-encoder/README.html |

---

## 3. Thực hành (80 phút)

`leanai_core/rerank.py`:

```python
"""Rerank bằng LLM theo lô."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .jsonutil import safe_json_loads
from .llm import LLMClient
from .vectorstore import Hit

RERANK_PROMPT = """Bạn chấm mức liên quan giữa CÂU HỎI và từng ĐOẠN TÀI LIỆU.

CÂU HỎI: {query}

{docs}

Chấm mỗi đoạn theo thang:
3 = trả lời TRỰC TIẾP và ĐẦY ĐỦ câu hỏi
2 = chứa một phần thông tin cần thiết
1 = cùng chủ đề nhưng không trả lời được câu hỏi
0 = không liên quan

Trả về CHỈ JSON: {{"scores": [{{"id": 1, "score": 3}}, ...]}}
Chấm nghiêm khắc. Phần lớn đoạn thường chỉ đạt 0-1."""


@dataclass
class Reranker:
    llm: LLMClient
    batch_size: int = 10
    snippet_chars: int = 800

    def score_batch(self, query: str, hits: list[Hit]) -> dict[int, float]:
        docs = "\n\n".join(
            f"[{i+1}] {h.text[:self.snippet_chars]}" for i, h in enumerate(hits))
        r = self.llm.complete(
            RERANK_PROMPT.format(query=query, docs=docs),
            temperature=0, max_tokens=400, tag="rerank")
        d = safe_json_loads(r.text, {"scores": []})
        out = {}
        for item in d.get("scores", []):
            try:
                out[int(item["id"]) - 1] = float(item["score"])
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def rerank(self, query: str, hits: list[Hit], top_k: int = 5,
               min_score: float = 1.0) -> list[Hit]:
        scored: list[tuple[Hit, float]] = []
        for s in range(0, len(hits), self.batch_size):
            batch = hits[s:s + self.batch_size]
            scores = self.score_batch(query, batch)
            for i, h in enumerate(batch):
                scored.append((h, scores.get(i, 0.0)))

        scored.sort(key=lambda x: -x[1])
        out = []
        for h, s in scored[:top_k]:
            if s < min_score:
                break
            out.append(Hit(id=h.id, text=h.text, score=s, meta=h.meta))
        return out
```

`exercises/day47/rerank_eval.py`:

```python
"""Ngày 47: đo nDCG trước và sau rerank."""
from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.rerank import Reranker
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

llm = LLMClient()
vs = VectorStore("company_kb")
hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": "clinic_001"})
rr = Reranker(llm)
cases = load_cases("templates/retrieval-testset.json")
W = {"tenant_id": "clinic_001"}

def ids(hits): return [f"{h.meta['doc_id']}#chunk{h.meta.get('chunk_index',0)}" for h in hits]

def baseline(q, k): return ids(hs.search(q, k=k, where=W))

def with_rerank(q, k):
    wide = hs.search(q, k=30, where=W)          # truy hồi RỘNG
    return ids(rr.rerank(q, wide, top_k=k))     # rerank HẸP

r1 = evaluate(baseline, cases); print_report("KHÔNG RERANK (k=30 -> k)", r1)
r2 = evaluate(with_rerank, cases); print_report("CÓ RERANK", r2)

print("\n=== SO SÁNH ===")
for m in ("recall@1", "recall@3", "recall@5", "mrr", "ndcg@5"):
    delta = r2[m] - r1[m]
    print(f"  {m:<10} {r1[m]:.3f} -> {r2[m]:.3f}  ({delta:+.3f})")
print(f"  latency   {r1['latency_ms']:.0f}ms -> {r2['latency_ms']:.0f}ms")
print("\n" + llm.usage.report())
print("\nLưu ý: rerank cải thiện MRR/nDCG (thứ hạng) nhiều hơn recall@5.")
```

---

## 4. Bài tập

**Bài 1 — Chọn k truy hồi.** Thử rerank từ k = 10, 20, 30, 50. Chất lượng tăng đến đâu thì bão hoà? Chi phí tăng thế nào? Chọn cấu hình.

**Bài 2 — Model rẻ cho rerank.** Chạy rerank bằng model nhỏ nhất bạn có và model lớn. So sánh nDCG và chi phí. Model rẻ có đủ dùng không?

**Bài 3 — Ảnh hưởng tới câu trả lời cuối.** Rerank cải thiện thứ hạng, nhưng **câu trả lời cuối** có tốt lên không? Chạy 30 câu hỏi qua RAG đầy đủ, chấm bằng LLM-judge (như Ngày 46). Nếu không cải thiện rõ → ghi lại kết luận trung thực và cân nhắc bỏ rerank để tiết kiệm.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 47 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Rerank chạy theo lô, không gọi 30 lần API cho 30 chunk
- [ ] Có bảng nDCG/MRR trước và sau rerank
- [ ] Đo được chi phí và latency tăng thêm
- [ ] Trả lời được: rerank có cải thiện **câu trả lời cuối** không
- [ ] Quyết định dùng/không dùng dựa trên số liệu
- [ ] Quiz ≥ 80%
