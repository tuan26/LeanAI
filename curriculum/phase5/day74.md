# NGÀY 74 — Reliability

> Phase 5 · 15' lý thuyết — 10' tài liệu — 85' code — 10' note

## 🎯 Mục tiêu

Hệ thống sống sót khi: provider down, DB chậm, job chết giữa chừng, người dùng bấm hai lần.

---

## 1. Lý thuyết cốt lõi (15 phút)

### 1.1 Năm cơ chế bắt buộc

```
1. TIMEOUT       : mọi lời gọi ra ngoài đều có giới hạn
2. RETRY         : backoff + jitter, không retry hành động ghi (Ngày 56)
3. FALLBACK      : model phụ → câu trả lời mặc định → chuyển người
4. IDEMPOTENCY   : thao tác lặp không gây tác dụng lặp
5. CIRCUIT BREAKER: ngừng gọi dịch vụ đang chết (Ngày 20)
```

### 1.2 Suy giảm có kiểm soát

Khi một phần hỏng, đừng sập cả hệ thống:

| Hỏng | Suy giảm |
|---|---|
| Rerank lỗi | dùng thẳng kết quả truy hồi |
| Vector DB lỗi | dùng BM25 (keyword) |
| LLM lớn lỗi | dùng model nhỏ, ghi rõ "chất lượng giảm" |
| Toàn bộ LLM lỗi | hiện dữ liệu thô + template, không AI |

> Nguyên tắc: **luôn có một đường đi không cần AI**. Sản phẩm vẫn dùng được, chỉ kém tiện hơn.

### 1.3 Job có thể tiếp tục

Job quét 3.000 khách chết ở khách thứ 1.847. Phải:
- lưu checkpoint sau mỗi lô,
- chạy lại chỉ xử lý phần chưa xong,
- không gửi trùng (idempotency),
- báo cáo rõ: đã xử lý bao nhiêu, lỗi bao nhiêu, còn lại bao nhiêu.

### 1.4 Chỉ số độ tin cậy

```
Tỉ lệ thành công  : request thành công / tổng
Tỉ lệ suy giảm    : request chạy ở chế độ dự phòng / tổng
MTTR              : thời gian trung bình phục hồi
Tỉ lệ gửi trùng   : PHẢI bằng 0
```

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Google SRE — Handling overload | https://sre.google/sre-book/handling-overload/ |
| Stripe — Idempotent requests | https://docs.stripe.com/api/idempotent_requests |
| Release It! — Circuit breaker pattern | https://martinfowler.com/bliki/CircuitBreaker.html |

---

## 3. Thực hành (85 phút)

`leanai_core/reliability.py`:

```python
"""Suy giảm có kiểm soát + job có checkpoint."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

JOB_DB = Path("data/jobs.db")


class Quality(str, Enum):
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    UNAVAILABLE = "unavailable"


@dataclass
class DegradedResult:
    value: object
    quality: Quality = Quality.FULL
    note: str = ""


def with_degradation(*stages: tuple[str, Callable, Quality]) -> DegradedResult:
    """Thử lần lượt các phương án, trả về phương án đầu tiên thành công."""
    errors = []
    for name, fn, quality in stages:
        try:
            return DegradedResult(fn(), quality,
                                  "" if quality == Quality.FULL
                                  else f"chạy ở chế độ dự phòng ({name})")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}")
    return DegradedResult(None, Quality.UNAVAILABLE, "; ".join(errors))


@dataclass
class JobRunner:
    """Job xử lý lô, có checkpoint, tiếp tục được."""
    job_id: str
    tenant_id: str = ""
    batch_size: int = 50
    processed: set = field(default_factory=set)
    failed: dict = field(default_factory=dict)

    def __post_init__(self):
        JOB_DB.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(JOB_DB)
        self.db.execute("""CREATE TABLE IF NOT EXISTS job_items(
            job_id TEXT, item_id TEXT, status TEXT, error TEXT, ts TEXT,
            PRIMARY KEY (job_id, item_id))""")
        self.db.commit()
        for item_id, status, err in self.db.execute(
                "SELECT item_id, status, error FROM job_items WHERE job_id=?",
                (self.job_id,)).fetchall():
            if status == "ok":
                self.processed.add(item_id)
            else:
                self.failed[item_id] = err

    def _mark(self, item_id: str, status: str, error: str = "") -> None:
        self.db.execute("INSERT OR REPLACE INTO job_items VALUES (?,?,?,?,?)",
                        (self.job_id, item_id, status, error,
                         datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def run(self, items: list[dict], handler: Callable[[dict], None],
            id_key: str = "id", retry_failed: bool = True) -> dict:
        todo = [i for i in items
                if i[id_key] not in self.processed
                and (retry_failed or i[id_key] not in self.failed)]
        print(f"[{self.job_id}] tổng {len(items)}, đã xong {len(self.processed)}, "
              f"cần xử lý {len(todo)}")

        ok = err = 0
        t0 = time.time()
        for n, item in enumerate(todo, 1):
            iid = item[id_key]
            try:
                handler(item)
                self._mark(iid, "ok")
                self.processed.add(iid)
                self.failed.pop(iid, None)
                ok += 1
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                self._mark(iid, "error", msg)
                self.failed[iid] = msg
                err += 1
            if n % self.batch_size == 0:
                print(f"  ...{n}/{len(todo)} (ok={ok} lỗi={err}) "
                      f"{(time.time()-t0)/n*1000:.0f}ms/item")

        return {"tổng": len(items), "xử lý lần này": len(todo),
                "thành công": ok, "lỗi": err,
                "còn lại": len(items) - len(self.processed),
                "giây": round(time.time() - t0, 1)}

    def report_failures(self, top: int = 10) -> None:
        print(f"\n{len(self.failed)} mục lỗi:")
        for iid, err in list(self.failed.items())[:top]:
            print(f"  {iid}: {err[:80]}")
```

`exercises/day74/reliability_test.py`:

```python
"""Ngày 74: test chịu lỗi."""
import random
from leanai_core.reliability import JobRunner, with_degradation, Quality
from leanai_core.idempotency import IdempotencyStore

random.seed(7)

# --- 1. Suy giảm có kiểm soát ---
def broken(): raise RuntimeError("dịch vụ không khả dụng")
def rerank_ok(): return ["kết quả đã rerank"]
def retrieval_only(): return ["kết quả truy hồi thô"]
def keyword_only(): return ["kết quả keyword"]

print("=== 1. Suy giảm có kiểm soát ===")
for label, stages in {
    "tất cả OK": [("rerank", rerank_ok, Quality.FULL)],
    "rerank hỏng": [("rerank", broken, Quality.FULL),
                    ("retrieval", retrieval_only, Quality.DEGRADED)],
    "vector hỏng": [("rerank", broken, Quality.FULL),
                    ("retrieval", broken, Quality.DEGRADED),
                    ("keyword", keyword_only, Quality.MINIMAL)],
    "hỏng hết": [("rerank", broken, Quality.FULL),
                 ("retrieval", broken, Quality.DEGRADED),
                 ("keyword", broken, Quality.MINIMAL)],
}.items():
    r = with_degradation(*stages)
    print(f"  {label:<14} -> {r.quality.value:<12} {r.value} {r.note[:50]}")

# --- 2. Job có checkpoint ---
print("\n=== 2. Job chết giữa chừng rồi chạy lại ===")
CUSTOMERS = [{"id": f"C{i:04d}"} for i in range(200)]
sent = []

def handler(item):
    if random.random() < 0.05:
        raise ConnectionError("API timeout")
    sent.append(item["id"])

job = JobRunner("quet_2026_09_19", tenant_id="clinic_001", batch_size=50)
print(job.run(CUSTOMERS[:120], handler))      # lần 1: chỉ 120 khách

print("\n-- chạy lại (tiếp tục phần còn lại + retry lỗi) --")
job2 = JobRunner("quet_2026_09_19", tenant_id="clinic_001", batch_size=50)
print(job2.run(CUSTOMERS, handler))
job2.report_failures()
print(f"  Tổng đã xử lý: {len(job2.processed)}/200")
print(f"  Số lần handler chạy: {len(sent)} (có thể > số khách nếu retry lỗi)")
print(f"  Số khách DUY NHẤT đã gửi: {len(set(sent))} — phải ≤ 200")
```

---

## 4. Bài tập

**Bài 1 — Suy giảm cho pipeline thật.** Áp dụng `with_degradation` cho: rerank → retrieval → BM25 → template không AI. Tắt từng dịch vụ, xác nhận hệ thống vẫn trả lời được (chất lượng thấp hơn nhưng không sập).

**Bài 2 — Job 3.000 khách.** Chạy job quét với tỉ lệ lỗi nhân tạo 10%. Kill giữa chừng. Chạy lại. Xác nhận: không bỏ sót ai, **không gửi trùng ai**.

**Bài 3 — Sổ tay sự cố.** Viết `progress/notes/day74-runbook.md`: 5 kịch bản sự cố (provider down, DB chậm, quota hết, job treo, dữ liệu bẩn hàng loạt), mỗi kịch bản: dấu hiệu nhận biết, tác động, cách xử lý ngay, cách phòng ngừa.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 74 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Có đường đi dự phòng **không cần AI**
- [ ] Job tiếp tục được sau khi chết, không bỏ sót, không trùng
- [ ] Mọi lời gọi ra ngoài có timeout
- [ ] Tỉ lệ gửi trùng = 0 (chứng minh bằng test)
- [ ] Có sổ tay sự cố 5 kịch bản
- [ ] Quiz ≥ 80%
