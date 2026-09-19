# NGÀY 45 — Query rewriting

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Sửa **câu hỏi** thay vì sửa index — thường là cách rẻ nhất để tăng recall.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao câu hỏi của người dùng khó truy hồi

| Vấn đề | Ví dụ |
|---|---|
| Quá ngắn | "hoàn tiền?" |
| Thiếu ngữ cảnh hội thoại | "còn cái kia thì sao?" |
| Dùng từ khác tài liệu | khách: "trả lại tiền" — tài liệu: "hoàn phí dịch vụ" |
| Nhiều câu hỏi trong một | "giá bao nhiêu và có trả góp không?" |
| Sai chính tả / không dấu | "hoan tien the nao" |

### 1.2 Năm kỹ thuật viết lại truy vấn

| Kỹ thuật | Cách làm | Chi phí |
|---|---|---|
| **Chuẩn hoá** | sửa chính tả, thêm dấu, mở rộng viết tắt | code, ~0 |
| **Giải tham chiếu** | "cái kia" → "gói trị liệu da mặt" (từ lịch sử) | 1 lần gọi LLM |
| **Mở rộng đa truy vấn** ⭐ | sinh 3 cách hỏi khác nhau, gộp kết quả bằng RRF | 1 lần gọi LLM |
| **Tách câu hỏi** | "giá và trả góp" → 2 truy vấn riêng | 1 lần gọi LLM |
| **HyDE** | sinh câu trả lời giả định rồi embed **nó** thay vì câu hỏi | 1 lần gọi LLM |

### 1.3 HyDE — vì sao hiệu quả

Câu hỏi và câu trả lời có "hình dạng ngôn ngữ" khác nhau. Embedding của một **câu trả lời giả định** gần với tài liệu thật hơn là embedding của câu hỏi.

```
Hỏi:  "tôi huỷ lịch có mất tiền không"
HyDE: "Khi khách huỷ lịch hẹn, chính sách quy định mức phí áp dụng tuỳ theo
       thời điểm huỷ. Nếu huỷ trước 24 giờ thì không mất phí..."
              ↑ embed câu này để tìm
```

Rủi ro: nếu model bịa sai hướng, truy hồi càng lệch. **Phải đo, đừng mặc định bật.**

### 1.4 Đánh đổi

Mỗi kỹ thuật thêm 1 lần gọi LLM → **+300–800ms latency** và thêm chi phí. Với truy vấn đơn giản, đây là lãng phí.

> **Giải pháp: router.** Chỉ viết lại khi cần (truy vấn quá ngắn, có đại từ tham chiếu, hoặc lần tìm đầu cho recall thấp).

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| HyDE paper | https://arxiv.org/abs/2212.10496 |
| Query expansion overview | https://www.pinecone.io/learn/query-expansion/ |

---

## 3. Thực hành (80 phút)

`leanai_core/query_rewrite.py`:

```python
"""Viết lại truy vấn: chuẩn hoá, đa truy vấn, HyDE, giải tham chiếu."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .jsonutil import safe_json_loads
from .llm import LLMClient

ABBREV = {
    r"\bkh\b": "khách hàng", r"\bdv\b": "dịch vụ", r"\blt\b": "liệu trình",
    r"\bcs\b": "chính sách", r"\bsp\b": "sản phẩm", r"\btt\b": "thanh toán",
    r"\bkm\b": "khuyến mãi", r"\bnv\b": "nhân viên",
}


def normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", q.strip())
    low = q.lower()
    for pat, full in ABBREV.items():
        low = re.sub(pat, full, low)
    return low if low != q.lower() else q


@dataclass
class RewriteResult:
    original: str
    queries: list[str]
    method: str
    cost: float = 0.0


class QueryRewriter:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def multi_query(self, q: str, n: int = 3) -> RewriteResult:
        r = self.llm.complete(
            f'Câu hỏi của khách: "{q}"\n\n'
            f"Viết {n} cách diễn đạt KHÁC NHAU cho câu hỏi này, dùng từ ngữ mà một "
            f"tài liệu chính sách/quy định nội bộ của doanh nghiệp sẽ dùng. "
            f"Mỗi cách một dòng, không đánh số, không giải thích.",
            temperature=0.3, max_tokens=200, tag="rewrite-multi")
        qs = [l.strip(" -•") for l in r.text.splitlines() if l.strip()][:n]
        return RewriteResult(q, [q] + qs, "multi_query", r.cost)

    def hyde(self, q: str) -> RewriteResult:
        r = self.llm.complete(
            f'Câu hỏi: "{q}"\n\n'
            "Viết một đoạn văn 2-3 câu giống như trích từ tài liệu chính sách nội bộ "
            "TRẢ LỜI câu hỏi trên. Không cần đúng sự thật — chỉ cần đúng văn phong và "
            "thuật ngữ của loại tài liệu đó. Chỉ trả về đoạn văn.",
            temperature=0.3, max_tokens=200, tag="rewrite-hyde")
        return RewriteResult(q, [r.text.strip()], "hyde", r.cost)

    def decompose(self, q: str) -> RewriteResult:
        r = self.llm.complete(
            f'Câu hỏi: "{q}"\n\n'
            'Nếu câu hỏi chứa NHIỀU câu hỏi con độc lập, tách ra. Nếu chỉ có một, '
            'giữ nguyên. Trả về JSON: {"queries": ["..."]}',
            temperature=0, max_tokens=200, tag="rewrite-decompose")
        d = safe_json_loads(r.text, {"queries": [q]})
        return RewriteResult(q, d.get("queries", [q]) or [q], "decompose", r.cost)

    def resolve_refs(self, q: str, history: list[dict]) -> RewriteResult:
        if not history or not re.search(r"\b(nó|cái đó|cái kia|vậy|thế|đó)\b", q.lower()):
            return RewriteResult(q, [q], "no_rewrite_needed")
        ctx = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in history[-4:])
        r = self.llm.complete(
            f"<hội_thoại>\n{ctx}\n</hội_thoại>\n\n"
            f'Câu hỏi mới: "{q}"\n\n'
            "Viết lại câu hỏi mới thành câu ĐỘC LẬP, thay mọi đại từ tham chiếu bằng "
            "đối tượng cụ thể từ hội thoại. Chỉ trả về câu đã viết lại.",
            temperature=0, max_tokens=120, tag="rewrite-refs")
        return RewriteResult(q, [r.text.strip()], "resolve_refs", r.cost)

    def route(self, q: str, history: list[dict] | None = None) -> RewriteResult:
        """Chỉ viết lại khi CẦN — tiết kiệm latency và tiền."""
        q = normalize_query(q)
        if history and re.search(r"\b(nó|cái đó|cái kia|vậy|thế)\b", q.lower()):
            return self.resolve_refs(q, history)
        if re.search(r"\bvà\b.*\?|\?.*\?", q) or q.count(",") >= 2:
            return self.decompose(q)
        if len(q.split()) <= 4:
            return self.multi_query(q)
        return RewriteResult(q, [q], "no_rewrite_needed")


def rrf_merge(result_lists: list[list], k: int = 5, rrf_k: int = 60) -> list:
    """Gộp kết quả của nhiều truy vấn bằng RRF (Ngày 36)."""
    fused, store = {}, {}
    for hits in result_lists:
        for rank, h in enumerate(hits, 1):
            fused[h.id] = fused.get(h.id, 0.0) + 1.0 / (rrf_k + rank)
            store[h.id] = h
    return [store[i] for i, _ in sorted(fused.items(), key=lambda x: -x[1])[:k]]
```

`exercises/day45/rewrite_eval.py`:

```python
from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.query_rewrite import QueryRewriter, rrf_merge
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

llm = LLMClient()
vs = VectorStore("company_kb")
hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": "clinic_001"})
qr = QueryRewriter(llm)
cases = load_cases("templates/retrieval-testset.json")
W = {"tenant_id": "clinic_001"}

def ids(hits): return [f"{h.meta['doc_id']}#chunk{h.meta.get('chunk_index',0)}" for h in hits]

STRATS = {
 "baseline":   lambda q, k: ids(hs.search(q, k=k, where=W)),
 "multi":      lambda q, k: ids(rrf_merge([hs.search(x, k=k, where=W)
                                           for x in qr.multi_query(q).queries], k)),
 "hyde":       lambda q, k: ids(hs.search(qr.hyde(q).queries[0], k=k, where=W)),
 "router":     lambda q, k: ids(rrf_merge([hs.search(x, k=k, where=W)
                                           for x in qr.route(q).queries], k)),
}

res = {}
for name, fn in STRATS.items():
    r = evaluate(fn, cases); res[name] = r
    print_report(name, r)

print("\n=== SO SÁNH ===")
print(f"{'chiến lược':<12} {'recall@5':>9} {'MRR':>7} {'latency':>10}")
for n, r in res.items():
    print(f"{n:<12} {r['recall@5']:>9.3f} {r['mrr']:>7.3f} {r['latency_ms']:>9.0f}ms")
print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Chọn chiến lược.** Chạy so sánh trên 30 truy vấn. Lập bảng recall / latency / chi phí mỗi truy vấn. Chiến lược nào đáng dùng cho sản phẩm? Ghi quyết định + lý do.

**Bài 2 — Router thông minh hơn.** Cải tiến `route()`: thêm quy tắc "nếu điểm cao nhất của lần tìm đầu < ngưỡng thì mới viết lại". Đo: bao nhiêu % truy vấn cần viết lại? Latency trung bình giảm bao nhiêu?

**Bài 3 — Truy vấn hội thoại.** Tạo 10 cặp (lịch sử, câu hỏi có đại từ). Đo tỉ lệ `resolve_refs` viết lại đúng. Ví dụ: sau khi hỏi về gói trị liệu da, hỏi "cái đó dùng được bao lâu?".

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 45 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Cài được ≥ 4 kỹ thuật viết lại
- [ ] Có bảng so sánh recall/latency/chi phí trên 30 truy vấn
- [ ] Router chỉ viết lại khi cần, có số liệu chứng minh tiết kiệm
- [ ] Giải tham chiếu hoạt động đúng ≥ 8/10 ca
- [ ] Quyết định được chiến lược cho sản phẩm, có lý do bằng số
- [ ] Quiz ≥ 80%
