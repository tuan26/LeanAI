# NGÀY 46 — Top-k & context budget

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Tìm **k tối ưu** bằng thực nghiệm, và xây bộ chọn context thông minh hơn "lấy top-k".

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 k lớn hơn không phải lúc nào cũng tốt hơn

```
recall            chất lượng câu trả lời
  ▲ ────────          ▲      ╭──╮
  │╱                  │    ╭─╯  ╰──╮
  │                   │  ╭─╯       ╰────
  └──────────► k      └──────────────► k
  recall luôn tăng    nhưng chất lượng ĐỈNH rồi GIẢM
```

Vì sao giảm: nhiễu nhiều → model bị phân tán → lost in the middle (Ngày 8) → và tốn tiền, chậm hơn.

### 1.2 Ba chiến lược chọn context

| Chiến lược | Cách làm |
|---|---|
| **Top-k cố định** | luôn lấy k chunk đầu — đơn giản, không thích nghi |
| **Ngưỡng điểm** | chỉ lấy chunk có điểm > τ — thích nghi nhưng τ khó chọn |
| **Ngân sách token + điểm giảm dần** ⭐ | lấy đến khi hết ngân sách HOẶC điểm tụt quá xa so với chunk đầu |

Chiến lược 3:
```python
if score < best_score * 0.6:   # tụt quá 40% so với kết quả tốt nhất
    dừng
```

### 1.3 Khử trùng lặp

Nhiều chunk gần như giống nhau (do overlap, hoặc tài liệu lặp nội dung) sẽ chiếm chỗ vô ích. Khử bằng: so cosine giữa các chunk đã chọn, bỏ chunk có similarity > 0.95 với chunk đã có.

### 1.4 Sắp xếp lại vị trí trong prompt

Nhớ "lost in the middle": đặt chunk **quan trọng nhất ở đầu và cuối**, chunk kém hơn ở giữa.

```
[1 - tốt nhất] [3] [5] [4] [2 - tốt nhì]
```

Kỹ thuật này miễn phí và thường cải thiện nhẹ.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Lost in the Middle | https://arxiv.org/abs/2307.03172 |
| Anthropic — Long context tips | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips |

---

## 3. Thực hành (80 phút)

`leanai_core/context_builder.py`:

```python
"""Chọn và sắp xếp context đưa vào prompt."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import tiktoken

from .vectorstore import Hit

ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class ContextResult:
    hits: list[Hit]
    tokens: int
    dropped_budget: int = 0
    dropped_score: int = 0
    dropped_dup: int = 0

    def summary(self) -> str:
        return (f"{len(self.hits)} chunk, {self.tokens} token "
                f"(bỏ: {self.dropped_budget} vượt ngân sách, "
                f"{self.dropped_score} điểm thấp, {self.dropped_dup} trùng)")


class ContextBuilder:
    def __init__(self, budget: int = 3000, relative_threshold: float = 0.6,
                 dedup_threshold: float = 0.95, reorder: bool = True,
                 embedder=None):
        self.budget = budget
        self.rel = relative_threshold
        self.dedup = dedup_threshold
        self.reorder = reorder
        self.embedder = embedder

    def build(self, hits: list[Hit]) -> ContextResult:
        if not hits:
            return ContextResult([], 0)

        best = hits[0].score
        selected: list[Hit] = []
        vectors: list[np.ndarray] = []
        total = 0
        d_budget = d_score = d_dup = 0

        for h in hits:
            if h.score < best * self.rel:
                d_score += 1
                continue
            n = len(ENC.encode(h.text))
            if total + n > self.budget:
                d_budget += 1
                continue
            if self.embedder and selected:
                v = self.embedder.embed(h.text)
                if any(float(v @ pv) > self.dedup for pv in vectors):
                    d_dup += 1
                    continue
                vectors.append(v)
            selected.append(h)
            total += n

        if self.reorder and len(selected) > 2:
            selected = self._reorder(selected)

        return ContextResult(selected, total, d_budget, d_score, d_dup)

    @staticmethod
    def _reorder(hits: list[Hit]) -> list[Hit]:
        """Tốt nhất ở đầu và cuối, kém hơn ở giữa (chống lost-in-the-middle)."""
        head, tail = [], []
        for i, h in enumerate(hits):
            (head if i % 2 == 0 else tail).append(h)
        return head + tail[::-1]
```

`exercises/day46/k_sweep.py`:

```python
"""Ngày 46: quét k và đo CHẤT LƯỢNG CÂU TRẢ LỜI, không chỉ recall."""
import json
from pathlib import Path

from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.rag import RagPipeline
from leanai_core.context_builder import ContextBuilder
from leanai_core.embedding import EmbeddingService

llm, emb = LLMClient(), EmbeddingService()
vs = VectorStore("company_kb", embedder=emb)
hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": "clinic_001"})

QA = json.loads(Path("templates/eval-dataset.json").read_text(encoding="utf-8"))
W = {"tenant_id": "clinic_001"}

JUDGE = """<câu_hỏi>{q}</câu_hỏi>
<đáp_án_chuẩn>{gold}</đáp_án_chuẩn>
<câu_trả_lời>{a}</câu_trả_lời>

Câu trả lời có khớp đáp án chuẩn về mặt NỘI DUNG không (bỏ qua khác biệt diễn đạt)?
Trả về CHỈ một từ: ĐÚNG, SAI, hoặc THIẾU (trả lời không đủ thông tin trong khi đáng lẽ trả lời được)."""

print(f"{'k':>4} {'ngân sách':>10} {'đúng':>7} {'sai':>5} {'thiếu':>6} "
      f"{'token ctx':>10} {'$/câu':>9} {'giây':>6}")

for k, budget in [(2, 1200), (3, 2000), (5, 3000), (8, 4500), (12, 7000), (20, 12000)]:
    rag = RagPipeline(hs, llm, context_budget=budget, top_k=k)
    cb = ContextBuilder(budget=budget, embedder=emb)
    ok = bad = miss = 0
    toks = costs = secs = 0.0

    for case in QA:
        ans = rag.ask(case["question"], where=W)
        toks += ans.tokens_context; costs += ans.cost; secs += ans.latency
        v = llm.complete(JUDGE.format(q=case["question"], gold=case["expected"],
                                      a=ans.answer),
                         temperature=0, max_tokens=10, tag="judge").text.strip().upper()
        if "ĐÚNG" in v: ok += 1
        elif "THIẾU" in v: miss += 1
        else: bad += 1

    n = len(QA)
    print(f"{k:>4} {budget:>10} {ok/n:>7.0%} {bad:>5} {miss:>6} "
          f"{toks/n:>10.0f} {costs/n:>9.5f} {secs/n:>6.1f}")

print("\nTìm k mà độ chính xác đạt đỉnh — tăng thêm chỉ tốn tiền.")
print(llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Đường cong k.** Chạy `k_sweep.py`. Vẽ bảng k vs độ chính xác vs chi phí. Xác định k tối ưu. **Ghi vào `progress/notes/day46-topk.md` — đây là cấu hình sản phẩm.**

**Bài 2 — Ngưỡng tương đối.** Thử `relative_threshold` = 0.4, 0.6, 0.8. Cái nào cân bằng tốt nhất giữa "đủ thông tin" và "ít nhiễu"?

**Bài 3 — Reorder có tác dụng không.** Chạy 30 câu hỏi với `reorder=True` và `False`. Có chênh lệch không? Nếu chênh lệch nhỏ hơn nhiễu thống kê, kết luận thế nào? (Bài này dạy bạn cách **không tự lừa mình** bằng cải tiến ảo.)

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 46 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `ContextBuilder` có đủ: ngân sách, ngưỡng tương đối, khử trùng, sắp xếp lại
- [ ] Có bảng k vs chất lượng vs chi phí, xác định được k tối ưu
- [ ] Chứng minh được k lớn hơn không luôn tốt hơn
- [ ] Đánh giá trung thực tác dụng của reorder (kể cả khi kết quả là "không rõ rệt")
- [ ] Quiz ≥ 80%
