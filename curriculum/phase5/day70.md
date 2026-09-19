# NGÀY 70 — Cost optimization

> Phase 5 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Biết chính xác **cost/request, cost/user, cost/month** — và giảm ≥ 40% mà không mất chất lượng.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba đơn vị chi phí phải biết

```
cost/request  : để tối ưu kỹ thuật
cost/user/tháng: để định giá sản phẩm
cost/tenant/tháng: để biết khách nào có lãi
```

Không biết con số thứ 2 → bạn không thể định giá, chỉ đoán.

### 1.2 Bảy đòn bẩy giảm chi phí (xếp theo hiệu quả)

| # | Đòn bẩy | Mức giảm điển hình |
|---|---|---|
| 1 | **Lọc bằng code trước khi gọi LLM** | 50–90% |
| 2 | **Cache** (embedding, câu hỏi lặp, prompt caching) | 30–70% |
| 3 | **Model rẻ cho tác vụ đơn giản** (định tuyến) | 40–80% |
| 4 | **Cắt context** (k nhỏ hơn, chunk gọn hơn) | 20–40% |
| 5 | **Giới hạn output** (max_tokens, yêu cầu ngắn gọn) | 10–30% |
| 6 | **Gộp lô** (batch nhiều mục trong 1 request) | 20–50% |
| 7 | **Bỏ bước không tạo giá trị** (rerank/critic nếu eval không chứng minh lợi ích) | 20–40% |

> Đòn bẩy 1 là lớn nhất và hay bị bỏ qua nhất. Trong CareDesk-AI: SQL lọc 3.000 khách xuống 80 khách có cơ hội → chỉ gọi LLM cho 80. Giảm 97%.

### 1.3 Định tuyến model

```
Tác vụ đơn giản (phân loại, trích xuất)  → model nhỏ
Tác vụ cần chất lượng (soạn tin, giải thích) → model lớn
```

Đo trên eval set: nếu model nhỏ đạt ≥ 95% chất lượng model lớn cho tác vụ đó → dùng model nhỏ.

### 1.4 Đơn vị kinh tế

```
Doanh thu/phòng khám/tháng:   2.000.000đ
Chi phí AI/phòng khám/tháng:  ?
Biên lợi nhuận gộp:           ?
```

Nếu chi phí AI > 20% doanh thu, mô hình kinh doanh có vấn đề. Tính con số này **trước khi** bán.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Prompt caching | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching |
| Anthropic — Batch processing | https://docs.anthropic.com/en/docs/build-with-claude/batch-processing |
| Anthropic — Pricing | https://www.anthropic.com/pricing |

---

## 3. Thực hành (80 phút)

`leanai_core/cost.py`:

```python
"""Theo dõi và phân tích chi phí."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB = Path("data/costs.db")

# USD / 1 triệu token — cập nhật theo bảng giá hiện hành
PRICING = {
    "small":  {"in": 0.80, "out": 4.00},
    "medium": {"in": 3.00, "out": 15.00},
    "large":  {"in": 15.00, "out": 75.00},
    "embed":  {"in": 0.02, "out": 0.0},
}
USD_VND = 25_000


def price(tier: str, in_tok: int, out_tok: int = 0) -> float:
    p = PRICING.get(tier, PRICING["medium"])
    return (in_tok * p["in"] + out_tok * p["out"]) / 1e6


class CostTracker:
    def __init__(self, path: Path = DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS costs(
            ts TEXT, tenant_id TEXT, user_id TEXT, feature TEXT, tier TEXT,
            in_tokens INT, out_tokens INT, cost REAL, cached INT DEFAULT 0)""")
        self.db.commit()

    def record(self, *, tenant_id: str, feature: str, tier: str,
               in_tokens: int, out_tokens: int, user_id: str = "",
               cached: bool = False) -> float:
        c = 0.0 if cached else price(tier, in_tokens, out_tokens)
        self.db.execute("INSERT INTO costs VALUES (?,?,?,?,?,?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), tenant_id, user_id,
                         feature, tier, in_tokens, out_tokens, c, int(cached)))
        self.db.commit()
        return c

    def by_feature(self, tenant_id: str = "") -> list[tuple]:
        q = ("SELECT feature, COUNT(*), SUM(in_tokens), SUM(out_tokens), SUM(cost), "
             "SUM(cached) FROM costs")
        args = []
        if tenant_id:
            q += " WHERE tenant_id=?"; args.append(tenant_id)
        return self.db.execute(q + " GROUP BY feature ORDER BY SUM(cost) DESC",
                               args).fetchall()

    def monthly_projection(self, tenant_id: str, days_observed: int = 1) -> dict:
        row = self.db.execute(
            "SELECT SUM(cost), COUNT(*) FROM costs WHERE tenant_id=?",
            (tenant_id,)).fetchone()
        total, n = row[0] or 0.0, row[1] or 0
        monthly = total / max(days_observed, 1) * 30
        return {"đã ghi nhận": round(total, 4), "số request": n,
                "cost/request": round(total / max(n, 1), 6),
                "dự phóng/tháng USD": round(monthly, 2),
                "dự phóng/tháng VNĐ": int(monthly * USD_VND)}

    def report(self, tenant_id: str = "") -> None:
        rows = self.by_feature(tenant_id)
        total = sum(r[4] for r in rows) or 1
        print(f"\n{'tính năng':<24}{'n':>6}{'in':>10}{'out':>9}{'$':>10}{'%':>7}{'cache':>7}")
        print("-" * 74)
        for feat, n, i, o, c, cached in rows:
            print(f"{feat:<24}{n:>6}{i:>10,}{o:>9,}{c:>10.4f}{c/total*100:>6.1f}%"
                  f"{cached or 0:>7}")
        print("-" * 74)
        print(f"{'TỔNG':<24}{'':<6}{'':<10}{'':<9}{total:>10.4f}")
```

`exercises/day70/cost_optimize.py`:

```python
"""Ngày 70: đo 4 cấu hình chi phí trên cùng eval set."""
from leanai_core.cost import CostTracker, price, USD_VND
from leanai_core.eval_dataset import EvalSet

tracker = CostTracker()
ds = EvalSet.load("data/eval-50.json")

SCENARIOS = {
 "A. ngây thơ (LLM cho mọi khách)": dict(
    llm_calls_per_customer=3, in_tok=2500, out_tok=400, tier="large",
    prefilter_ratio=1.0, cache_hit=0.0),
 "B. + lọc SQL trước": dict(
    llm_calls_per_customer=3, in_tok=2500, out_tok=400, tier="large",
    prefilter_ratio=0.03, cache_hit=0.0),
 "C. + model rẻ cho phân loại": dict(
    llm_calls_per_customer=3, in_tok=1200, out_tok=250, tier="medium",
    prefilter_ratio=0.03, cache_hit=0.0),
 "D. + cache + cắt context": dict(
    llm_calls_per_customer=2, in_tok=900, out_tok=200, tier="medium",
    prefilter_ratio=0.03, cache_hit=0.4),
}

N_CUSTOMERS = 3000
N_CLINICS = 10

print(f"Giả định: {N_CUSTOMERS} khách/phòng khám, quét 1 lần/tháng, {N_CLINICS} phòng khám\n")
print(f"{'cấu hình':<34}{'$/clinic/tháng':>16}{'VNĐ':>12}{'$/tất cả':>11}")
print("-" * 74)

base = None
for name, s in SCENARIOS.items():
    n_llm = N_CUSTOMERS * s["prefilter_ratio"] * s["llm_calls_per_customer"]
    n_llm *= (1 - s["cache_hit"])
    cost_clinic = n_llm * price(s["tier"], s["in_tok"], s["out_tok"])
    base = base or cost_clinic
    print(f"{name:<34}{cost_clinic:>16.2f}{int(cost_clinic*USD_VND):>12,}"
          f"{cost_clinic*N_CLINICS:>11.2f}")

best = min(N_CUSTOMERS * s["prefilter_ratio"] * s["llm_calls_per_customer"] *
           (1 - s["cache_hit"]) * price(s["tier"], s["in_tok"], s["out_tok"])
           for s in SCENARIOS.values())
print(f"\nGiảm được: {(1 - best/base):.0%} so với cấu hình ngây thơ")

REVENUE_PER_CLINIC = 2_000_000
print(f"\n=== ĐƠN VỊ KINH TẾ (cấu hình D) ===")
print(f"  Doanh thu/phòng khám/tháng : {REVENUE_PER_CLINIC:,}đ")
print(f"  Chi phí AI                 : {int(best*USD_VND):,}đ")
print(f"  Biên lợi nhuận gộp         : {(1 - best*USD_VND/REVENUE_PER_CLINIC):.1%}")
print(f"  {'✓ Khả thi' if best*USD_VND/REVENUE_PER_CLINIC < 0.2 else '✗ Chi phí quá cao'}")
```

---

## 4. Bài tập

**Bài 1 — Đo thật.** Gắn `CostTracker` vào mọi lời gọi LLM trong pipeline. Chạy 50 eval case. In `report()`. Tính năng nào tốn nhất?

**Bài 2 — Định tuyến model.** Chọn 2 tác vụ đơn giản (phân loại cơ hội, trích xuất). Chạy eval với model nhỏ và model lớn. Nếu chất lượng chênh < 5% → chuyển sang model nhỏ, ghi mức tiết kiệm.

**Bài 3 — Bảng định giá.** Với chi phí đo được, lập bảng định giá 3 gói (nhỏ 500 khách / vừa 3.000 / lớn 10.000): chi phí AI, giá bán đề xuất, biên lợi nhuận. Lưu `progress/notes/day70-pricing.md`.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 70 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Biết chính xác cost/request, cost/tenant/tháng
- [ ] Giảm ≥ 40% chi phí so với baseline
- [ ] Chứng minh chất lượng **không giảm** (chạy lại eval)
- [ ] Có bảng định giá 3 gói với biên lợi nhuận
- [ ] Quiz ≥ 80%
