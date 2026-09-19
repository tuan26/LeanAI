# NGÀY 55 — Tool error handling

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Lỗi tool **không bao giờ** làm chết agent — và agent biết tự tìm đường khác.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Bốn loại lỗi tool

| Loại | Ví dụ | Agent nên làm gì |
|---|---|---|
| **Tham số sai** | `customer_id="chị Lan"` | sửa tham số, gọi lại |
| **Không tìm thấy** | khách không tồn tại | đổi cách tiếp cận (tìm theo tên) |
| **Lỗi tạm thời** | timeout, 503 | retry với backoff (Ngày 56) |
| **Lỗi vĩnh viễn** | không có quyền, tool hỏng | báo người dùng, dừng nhánh đó |

### 1.2 Thông báo lỗi là chỉ dẫn cho model

```python
# ❌ model không biết làm gì tiếp
{"error": "KeyError: C999"}

# ✅ model tự sửa được
{"error": "không tìm thấy khách C999",
 "hint": "kiểm tra lại mã, hoặc dùng search_customers(query='tên khách')",
 "retryable": False,
 "available_ids_sample": ["C001", "C002", "C003"]}
```

### 1.3 Chống vòng lặp lỗi

Agent có thể lặp mãi: gọi sai → lỗi → gọi lại y hệt → lỗi...

Ba lớp chặn:
```
1. Giới hạn số lần gọi CÙNG tool với CÙNG tham số (≤ 2)
2. Giới hạn tổng số bước (≤ 15)
3. Giới hạn tổng chi phí phiên
```

### 1.4 Nguyên tắc fail-safe

> Khi không chắc chắn, agent phải **dừng và hỏi người**, không được đoán bừa rồi hành động.

Đặc biệt với tool ghi (gửi tin, đổi lịch, hoàn tiền). Ngày 61 sẽ làm kỹ.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Handling tool errors | https://docs.anthropic.com/en/docs/build-with-claude/tool-use/implement-tool-use |
| Google SRE — Handling overload | https://sre.google/sre-book/handling-overload/ |

---

## 3. Thực hành (80 phút)

`leanai_core/tool_guard.py`:

```python
"""Bảo vệ vòng lặp agent khỏi lỗi tool và vòng lặp vô hạn."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def _sig(name: str, args: dict) -> str:
    return hashlib.sha256(
        f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}".encode()
    ).hexdigest()[:12]


@dataclass
class LoopGuard:
    max_same_call: int = 2
    max_steps: int = 15
    max_cost: float = 0.50
    max_errors: int = 5

    steps: int = 0
    cost: float = 0.0
    errors: int = 0
    seen: dict[str, int] = field(default_factory=dict)

    def check_call(self, name: str, args: dict) -> str | None:
        """Trả về thông báo chặn, hoặc None nếu được phép."""
        s = _sig(name, args)
        self.seen[s] = self.seen.get(s, 0) + 1
        if self.seen[s] > self.max_same_call:
            return (f"ĐÃ CHẶN: bạn đã gọi {name} với đúng tham số này "
                    f"{self.seen[s]} lần và đều thất bại. Hãy thử CÁCH KHÁC "
                    f"hoặc báo cho người dùng biết bạn không làm được.")
        return None

    def check_step(self) -> str | None:
        self.steps += 1
        if self.steps > self.max_steps:
            return f"ĐÃ CHẶN: vượt {self.max_steps} bước. Hãy tổng kết những gì đã biết."
        if self.cost > self.max_cost:
            return f"ĐÃ CHẶN: vượt ngân sách ${self.max_cost}."
        if self.errors > self.max_errors:
            return f"ĐÃ CHẶN: quá {self.max_errors} lỗi liên tiếp."
        return None

    def record(self, ok: bool, cost: float = 0.0) -> None:
        self.cost += cost
        self.errors = 0 if ok else self.errors + 1

    def status(self) -> dict:
        return {"bước": self.steps, "chi phí": round(self.cost, 5),
                "lỗi liên tiếp": self.errors,
                "lần gọi trùng": sum(1 for v in self.seen.values() if v > 1)}


def error_payload(error: str, *, hint: str = "", retryable: bool = False,
                  extra: dict | None = None) -> str:
    return json.dumps({"error": error, "hint": hint, "retryable": retryable,
                       **(extra or {})}, ensure_ascii=False)
```

`exercises/day55/error_recovery.py`:

```python
"""Ngày 55: agent phải tự phục hồi khi tool lỗi."""
import json
import random
from anthropic import Anthropic

from leanai_core.config import cfg
from leanai_core.tools import ToolRegistry
from leanai_core.tool_guard import LoopGuard, error_payload

client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
reg = ToolRegistry()

DB = {"C001": {"ten": "Nguyễn Thị Lan", "con": 4},
      "C002": {"ten": "Trần Văn Bình", "con": 20}}


@reg.register("get_customer", "Lấy hồ sơ khách theo MÃ (dạng C001). "
              "KHÔNG nhận tên khách.",
              {"type": "object", "properties": {"customer_id": {"type": "string"}},
               "required": ["customer_id"]})
def get_customer(customer_id: str):
    cid = customer_id.upper()
    if cid not in DB:
        return json.loads(error_payload(
            f"không tìm thấy khách '{customer_id}'",
            hint="nếu bạn đang truyền TÊN, hãy dùng search_customers trước để lấy mã",
            retryable=False, extra={"sample_ids": list(DB)[:3]}))
    return DB[cid]


@reg.register("search_customers", "Tìm khách theo TÊN, trả về mã khách.",
              {"type": "object", "properties": {"query": {"type": "string"}},
               "required": ["query"]})
def search_customers(query: str):
    q = query.lower()
    return [{"customer_id": k, "ten": v["ten"]}
            for k, v in DB.items() if q in v["ten"].lower()]


@reg.register("flaky_service", "Dịch vụ hay lỗi tạm thời — dùng để test.",
              {"type": "object", "properties": {}, "required": []})
def flaky_service():
    if random.random() < 0.7:
        return json.loads(error_payload("dịch vụ tạm thời quá tải",
                                        hint="thử lại sau vài giây", retryable=True))
    return {"data": "ok"}


def run(question: str) -> str:
    guard = LoopGuard()
    messages = [{"role": "user", "content": question}]
    while True:
        blocked = guard.check_step()
        if blocked:
            messages.append({"role": "user", "content": blocked})

        r = client.messages.create(model=cfg.MODEL, max_tokens=900, temperature=0,
                                   tools=reg.api_tools(), messages=messages)
        guard.record(True, cost=0.0)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")

        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            stop = guard.check_call(b.name, b.input)
            if stop:
                print(f"  🛑 {stop[:80]}")
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": stop, "is_error": True})
                continue
            res = reg.execute(b.name, b.input)
            ok = res.ok and '"error"' not in res.content
            guard.record(ok)
            print(f"  {'✓' if ok else '✗'} {b.name}({json.dumps(b.input, ensure_ascii=False)[:60]})"
                  f" -> {res.content[:90]}")
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": res.content, "is_error": not ok})
        messages.append({"role": "user", "content": results})


for q in ["Khách tên Lan còn mấy buổi?",           # phải tự chuyển sang search
          "Lấy hồ sơ khách C999",                   # không tồn tại
          "Gọi flaky_service và cho tôi biết kết quả"]:
    print(f"\n{'='*70}\n{q}")
    print(f"\n=> {run(q)[:250]}")
```

---

## 4. Bài tập

**Bài 1 — Tự phục hồi.** Chạy 10 câu hỏi mà tool đầu tiên chắc chắn lỗi. Đo tỉ lệ agent tự tìm được đường khác. Cải thiện `hint` cho đến khi ≥ 80%.

**Bài 2 — Chặn vòng lặp.** Tạo tool luôn lỗi. Xác nhận `LoopGuard` chặn sau đúng 2 lần gọi trùng và agent chuyển hướng hoặc báo người dùng.

**Bài 3 — Ngân sách.** Đặt `max_cost` rất nhỏ. Xác nhận agent dừng đúng lúc và **vẫn tổng kết được** những gì đã làm, không chết giữa chừng.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 55 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Lỗi tool không làm chết agent
- [ ] Agent tự chuyển hướng khi có `hint` (≥ 80% ca)
- [ ] `LoopGuard` chặn được gọi trùng, vượt bước, vượt ngân sách
- [ ] Khi bị chặn, agent vẫn tổng kết được kết quả
- [ ] Quiz ≥ 80%
