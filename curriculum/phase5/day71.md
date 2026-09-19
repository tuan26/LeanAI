# NGÀY 71 — Latency

> Phase 5 · 15' lý thuyết — 10' tài liệu — 85' code — 10' note

## 🎯 Mục tiêu

Đo TTFT và p50/p95 từng tầng, đặt **ngân sách latency**, và đạt được nó.

---

## 1. Lý thuyết cốt lõi (15 phút)

### 1.1 Đo p95, không đo trung bình

```
10 request: 1s × 9 lần + 20s × 1 lần
trung bình = 2.9s  ← nghe ổn
p95        = 20s   ← thực tế người dùng bực
```

Người dùng nhớ lần chậm nhất, không nhớ trung bình.

### 1.2 Ngân sách latency — phân bổ trước, tối ưu sau

```
Mục tiêu: p95 < 5s cho câu hỏi tra cứu

  guardrail       0.05s
  query rewrite   0.60s   (chỉ khi cần — router Ngày 45)
  retrieval       0.40s
  rerank          0.80s
  LLM (TTFT)      0.90s
  LLM (sinh)      1.50s
  verify          0.05s
  ─────────────────────
  tổng            4.30s   ← còn 0.7s dự phòng
```

Vượt ngân sách ở tầng nào → biết ngay phải sửa gì.

### 1.3 Bốn kỹ thuật giảm latency

| Kỹ thuật | Giảm được |
|---|---|
| **Song song hoá** (vector + BM25, nhiều tool) | 30–50% tầng đó |
| **Streaming** | TTFT cảm nhận giảm mạnh (Ngày 19) |
| **Cache** | ~100% cho câu lặp |
| **Cắt bước** (bỏ rerank nếu điểm truy hồi đã cao) | 20–30% |
| **Model nhỏ hơn** | 30–60% thời gian sinh |

### 1.4 Latency khác nhau theo loại tác vụ

| Tác vụ | Ngưỡng chấp nhận |
|---|---|
| Gợi ý trong lúc gõ | < 300ms |
| Tra cứu hỏi–đáp | < 3s (TTFT < 1s) |
| Soạn tin nhắn | < 5s |
| Agent nhiều bước | < 30s, **phải hiện tiến trình** |
| Job quét ban đêm | không giới hạn |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Nielsen — Response time limits | https://www.nngroup.com/articles/response-times-3-important-limits/ |
| Anthropic — Reduce latency | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-latency |

---

## 3. Thực hành (85 phút)

`leanai_core/latency.py`:

```python
"""Đo và kiểm soát latency."""
from __future__ import annotations

import statistics
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class LatencyBudget:
    """Ngân sách latency theo tầng, đơn vị giây."""
    budgets: dict[str, float] = field(default_factory=dict)
    measurements: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    @contextmanager
    def measure(self, stage: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            self.measurements[stage].append(dt)

    def percentile(self, values: list[float], p: float) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        return s[min(int(len(s) * p), len(s) - 1)]

    def report(self) -> None:
        print(f"\n{'tầng':<20}{'n':>5}{'p50':>9}{'p95':>9}{'p99':>9}"
              f"{'ngân sách':>11}{'':>4}")
        print("-" * 70)
        total_p50 = total_p95 = 0.0
        for stage, vals in sorted(self.measurements.items(),
                                  key=lambda x: -self.percentile(x[1], 0.95)):
            p50 = statistics.median(vals)
            p95 = self.percentile(vals, 0.95)
            p99 = self.percentile(vals, 0.99)
            budget = self.budgets.get(stage)
            flag = ""
            if budget:
                flag = "✓" if p95 <= budget else "✗ VƯỢT"
            total_p50 += p50; total_p95 += p95
            print(f"{stage:<20}{len(vals):>5}{p50:>9.3f}{p95:>9.3f}{p99:>9.3f}"
                  f"{(budget or 0):>11.3f}  {flag}")
        print("-" * 70)
        target = self.budgets.get("_total", 0)
        flag = "✓" if (not target or total_p95 <= target) else "✗ VƯỢT"
        print(f"{'TỔNG':<20}{'':<5}{total_p50:>9.3f}{total_p95:>9.3f}"
              f"{'':<9}{target:>11.3f}  {flag}")

    def violations(self) -> list[str]:
        out = []
        for stage, vals in self.measurements.items():
            b = self.budgets.get(stage)
            if b and self.percentile(vals, 0.95) > b:
                out.append(f"{stage}: p95={self.percentile(vals,0.95):.2f}s > {b}s")
        return out
```

`exercises/day71/latency_bench.py`:

```python
"""Ngày 71: đo latency pipeline, tìm và sửa vi phạm ngân sách."""
from concurrent.futures import ThreadPoolExecutor

from leanai_core.latency import LatencyBudget
from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.rerank import Reranker
from leanai_core.context_builder import ContextBuilder
from leanai_core.citation import CITED_SYSTEM

llm = LLMClient()
vs = VectorStore("company_kb")
hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": "clinic_001"})
rr = Reranker(llm)
cb = ContextBuilder(budget=3000)

QUESTIONS = ["Chính sách hoàn tiền thế nào?", "Giờ mở cửa?",
             "Chuyển nhượng gói cần gì?", "Phí giữ chỗ bao nhiêu?",
             "Gói trị liệu bao nhiêu buổi?"] * 4

budget = LatencyBudget(budgets={
    "retrieval": 0.40, "rerank": 0.80, "llm_ttft": 0.90,
    "llm_total": 2.40, "verify": 0.05, "_total": 5.00})

W = {"tenant_id": "clinic_001"}


def run(q: str, use_rerank: bool = True):
    with budget.measure("retrieval"):
        hits = hs.search(q, k=30, where=W)
    if use_rerank:
        with budget.measure("rerank"):
            hits = rr.rerank(q, hits, top_k=8)
    else:
        hits = hits[:8]
    with budget.measure("context"):
        ctx = cb.build(hits)
    docs = "\n".join(f'<document id="{i+1}">{h.text}</document>'
                     for i, h in enumerate(ctx.hits))
    with budget.measure("llm_total"):
        r = llm.stream(f"<documents>\n{docs}\n</documents>\n\nCÂU HỎI: {q}",
                       system=CITED_SYSTEM, max_tokens=500)
    budget.measurements["llm_ttft"].append(getattr(r, "ttft", 0))
    with budget.measure("verify"):
        pass
    return r


print("=== BASELINE (có rerank, tuần tự) ===")
for q in QUESTIONS:
    run(q, use_rerank=True)
budget.report()
print("Vi phạm:", budget.violations() or "không")

print("\n=== SAU TỐI ƯU (bỏ rerank khi điểm đã cao) ===")
budget.measurements.clear()
for q in QUESTIONS:
    hits = hs.search(q, k=30, where=W)
    high_confidence = hits and hits[0].score > 0.75
    run(q, use_rerank=not high_confidence)
budget.report()
print("Vi phạm:", budget.violations() or "không")

print("\n=== Song song hoá truy hồi ===")
def parallel_retrieval(q):
    with ThreadPoolExecutor(2) as ex:
        f1 = ex.submit(vs.search, q, 30, W)
        f2 = ex.submit(hs.search_bm25, q, 30)
        return f1.result(), f2.result()

budget.measurements.clear()
for q in QUESTIONS:
    with budget.measure("retrieval_parallel"):
        parallel_retrieval(q)
    with budget.measure("retrieval_serial"):
        vs.search(q, 30, W); hs.search_bm25(q, 30)
budget.report()
```

---

## 4. Bài tập

**Bài 1 — Ngân sách của bạn.** Viết ngân sách latency cho 3 luồng của CareDesk-AI (tra cứu, soạn tin, quét đêm). Đo thực tế, đánh dấu tầng vượt ngân sách.

**Bài 2 — Sửa một vi phạm.** Chọn tầng vượt ngân sách nhiều nhất. Áp dụng 1 kỹ thuật ở mục 1.3. Đo lại. **Kiểm tra chất lượng không giảm** (chạy eval Ngày 67).

**Bài 3 — Latency dưới tải.** Chạy 20 request đồng thời bằng `ThreadPoolExecutor`. p95 thay đổi thế nào so với chạy tuần tự? Đây là con số thật khi có nhiều người dùng.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 71 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Đo p50/p95/p99 cho từng tầng, không chỉ trung bình
- [ ] Có ngân sách latency rõ ràng cho mỗi luồng
- [ ] Đạt ngân sách tổng, hoặc ghi rõ tầng nào vượt và vì sao
- [ ] Một tối ưu có số liệu trước/sau + kiểm tra chất lượng
- [ ] Đo được latency dưới tải đồng thời
- [ ] Quiz ≥ 80%
