# NGÀY 56 — Retry & backoff cho agent

> Phase 4 · 15' lý thuyết — 10' tài liệu — 85' code — 10' note

## 🎯 Mục tiêu

Retry đúng chỗ, đúng cách, có giới hạn — và **không bao giờ retry hành động có tác dụng phụ**.

---

## 1. Lý thuyết cốt lõi (15 phút)

### 1.1 Ba tầng retry trong agent

```
Tầng 1: RETRY HTTP      (Ngày 20) — lỗi mạng, 429, 500
Tầng 2: RETRY TOOL      — tool lỗi tạm thời, retryable=true
Tầng 3: RETRY KẾ HOẠCH  — agent đi sai hướng, thử cách tiếp cận khác
```

Ba tầng độc lập. Nhân chúng lại: 3 × 3 × 2 = 18 lần gọi cho một yêu cầu. **Phải có ngân sách tổng.**

### 1.2 Khi nào TUYỆT ĐỐI không retry

| Hành động | Vì sao |
|---|---|
| Gửi tin nhắn cho khách | khách nhận 3 tin giống nhau |
| Trừ tiền / hoàn tiền | mất tiền thật |
| Đặt/huỷ lịch | tạo trùng lịch |
| Gửi email | không rút lại được |

Với nhóm này: **idempotency key** bắt buộc (Ngày 20, làm kỹ ở Ngày 74).

### 1.3 Retry kế hoạch — kỹ thuật đáng giá

Khi agent thất bại sau N bước, đừng bỏ cuộc ngay. Cho nó biết:

```
"Cách tiếp cận vừa rồi thất bại vì: <lý do>.
 Những gì đã thử: <danh sách>.
 Hãy đề xuất một cách tiếp cận KHÁC, hoặc nói rõ bạn không làm được và vì sao."
```

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| AWS — Timeouts, retries, backoff | https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ |
| Stripe — Idempotent requests | https://docs.stripe.com/api/idempotent_requests |

---

## 3. Thực hành (85 phút)

`leanai_core/idempotency.py`:

```python
"""Chống thực thi trùng cho hành động có tác dụng phụ."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/idempotency.db")


class IdempotencyStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS ops(
            key TEXT PRIMARY KEY, tool TEXT, args TEXT,
            result TEXT, created_at TEXT)""")
        self.db.commit()

    @staticmethod
    def make_key(tool: str, args: dict, scope: str = "") -> str:
        raw = f"{scope}:{tool}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT result FROM ops WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, tool: str, args: dict, result: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO ops VALUES (?,?,?,?,?)",
                        (key, tool, json.dumps(args, ensure_ascii=False), result,
                         datetime.now(timezone.utc).isoformat()))
        self.db.commit()


def idempotent_execute(registry, store: IdempotencyStore, name: str, args: dict,
                       scope: str = "") -> tuple[str, bool]:
    """Trả về (kết quả, đã_chạy_trước_đó)."""
    tool = registry.tools.get(name)
    if tool and tool.read_only:
        return registry.execute(name, args).content, False

    key = store.make_key(name, args, scope)
    cached = store.get(key)
    if cached is not None:
        return cached, True

    res = registry.execute(name, args)
    if res.ok:
        store.put(key, name, args, res.content)
    return (res.content if res.ok else f"Lỗi: {res.error}"), False
```

`leanai_core/retry_tool.py`:

```python
"""Retry cho tool, tôn trọng cờ retryable và read_only."""
from __future__ import annotations

import json
import random
import time


def retry_tool(registry, name: str, args: dict, *, max_attempts: int = 3,
               base: float = 0.5, on_retry=None):
    tool = registry.tools.get(name)
    if tool and not tool.read_only:
        return registry.execute(name, args)        # KHÔNG retry hành động ghi

    last = None
    for attempt in range(1, max_attempts + 1):
        res = registry.execute(name, args)
        retryable = False
        if res.ok:
            try:
                d = json.loads(res.content)
                retryable = bool(d.get("retryable")) if isinstance(d, dict) else False
                if not d.get("error"):
                    return res
            except (json.JSONDecodeError, TypeError):
                return res
        else:
            retryable = True
        last = res
        if not retryable or attempt == max_attempts:
            return res
        wait = base * 2 ** (attempt - 1)
        wait += random.uniform(0, wait)
        if on_retry:
            on_retry(attempt, wait)
        time.sleep(wait)
    return last
```

`exercises/day56/retry_test.py`:

```python
import json
from leanai_core.tools import ToolRegistry
from leanai_core.idempotency import IdempotencyStore, idempotent_execute
from leanai_core.retry_tool import retry_tool
from leanai_core.tool_guard import error_payload

reg = ToolRegistry()
store = IdempotencyStore()
SENT = []
_calls = {"flaky": 0}


@reg.register("flaky_read", "Đọc dữ liệu, hay lỗi tạm thời.",
              {"type": "object", "properties": {}, "required": []}, read_only=True)
def flaky_read():
    _calls["flaky"] += 1
    if _calls["flaky"] < 3:
        return json.loads(error_payload("quá tải", hint="thử lại", retryable=True))
    return {"data": "ok sau 3 lần"}


@reg.register("send_message", "GỬI tin nhắn thật cho khách. Không thể hoàn tác.",
              {"type": "object",
               "properties": {"customer_id": {"type": "string"},
                              "message": {"type": "string"}},
               "required": ["customer_id", "message"]},
              requires_approval=True, read_only=False)
def send_message(customer_id: str, message: str):
    SENT.append((customer_id, message))
    return {"status": "sent", "count": len(SENT)}


print("=== 1. Retry tool đọc ===")
res = retry_tool(reg, "flaky_read", {},
                 on_retry=lambda a, w: print(f"  lần {a} lỗi, chờ {w:.1f}s"))
print(f"  kết quả: {res.content} (gọi {_calls['flaky']} lần)")

print("\n=== 2. KHÔNG retry hành động ghi ===")
args = {"customer_id": "C001", "message": "Chị Lan ơi..."}
for i in range(3):
    out, cached = idempotent_execute(reg, store, "send_message", args, scope="job_2026_09_19")
    print(f"  lần {i+1}: {'từ cache (KHÔNG gửi lại)' if cached else 'gửi thật'} -> {out}")
print(f"  Số tin thực sự gửi: {len(SENT)} (phải = 1)")

print("\n=== 3. Nội dung khác -> gửi mới ===")
out, cached = idempotent_execute(reg, store, "send_message",
                                 {"customer_id": "C001", "message": "Nội dung khác"},
                                 scope="job_2026_09_19")
print(f"  {'cache' if cached else 'gửi thật'} | tổng đã gửi: {len(SENT)} (phải = 2)")
```

---

## 4. Bài tập

**Bài 1 — Ngân sách tổng.** Kết hợp 3 tầng retry với `LoopGuard` (Ngày 55). Đo trường hợp xấu nhất: một yêu cầu tốn tối đa bao nhiêu lần gọi API và bao nhiêu tiền?

**Bài 2 — Retry kế hoạch.** Cài: sau 2 lần thất bại, gửi cho model bản tóm tắt "đã thử gì, thất bại vì sao" và yêu cầu cách tiếp cận khác. Test trên 5 nhiệm vụ khó.

**Bài 3 — Scope của idempotency key.** Thử `scope` = ngày, = job_id, = rỗng. Trường hợp nào gây lỗi "không gửi được tin nhắn lần thứ hai dù cần gửi thật"? Rút ra quy tắc chọn scope.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 56 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Retry hoạt động cho tool đọc, có backoff + jitter
- [ ] **Không** retry tool ghi
- [ ] Idempotency chặn gửi trùng, chứng minh bằng test 3 lần gọi = 1 tin
- [ ] Tính được chi phí trường hợp xấu nhất
- [ ] Quiz ≥ 80%
