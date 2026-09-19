# NGÀY 64 — Logging & observability

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Log đủ để **debug một sự cố xảy ra 3 ngày trước** mà không cần chạy lại.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba câu hỏi log phải trả lời được

```
1. CHUYỆN GÌ ĐÃ XẢY RA?  — chuỗi sự kiện đầy đủ của một run
2. VÌ SAO NÓ LÀM VẬY?    — prompt, tool call, kết quả, quyết định
3. TỐN BAO NHIÊU?        — token, tiền, thời gian từng bước
```

Nếu log không trả lời được cả 3, bạn sẽ debug bằng cách đoán.

### 1.2 Log có cấu trúc, không phải print

```python
# ❌ print(f"Đang gọi tool {name}")
# ✅ log_event("tool_call", run_id=..., step=3, tool=name, args=..., ok=True, ms=142)
```

JSON Lines cho phép: grep, thống kê, nạp vào pandas, đẩy lên hệ thống giám sát.

### 1.3 Trace: cây span

```
run_id=abc123
├─ span: agent_run           2.4s  $0.0031
│  ├─ span: llm_call #1      0.8s  in=1240 out=85
│  ├─ span: tool get_customer 0.1s
│  ├─ span: llm_call #2      0.9s  in=1580 out=120
│  └─ span: tool calculate_refund 0.05s
```

Mỗi span: `trace_id`, `span_id`, `parent_id`, `name`, `start`, `duration`, `attributes`.
Đây là mô hình chuẩn (OpenTelemetry) — Ngày 68 sẽ làm đầy đủ.

### 1.4 Những gì TUYỆT ĐỐI không được log

| Không log | Cách xử lý |
|---|---|
| API key, token | lọc theo tên trường |
| Số điện thoại, CMND khách | mask: `090***4567` |
| Nội dung y tế nhạy cảm | log hash hoặc độ dài, không log nội dung |
| Toàn bộ prompt có dữ liệu khách | log hash + số token, bản đầy đủ lưu riêng có kiểm soát |

Lộ log = lộ dữ liệu khách hàng. Đây là rủi ro pháp lý thật.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| OpenTelemetry concepts | https://opentelemetry.io/docs/concepts/signals/traces/ |
| Structured logging | https://www.structlog.org/en/stable/why.html |

---

## 3. Thực hành (80 phút)

`leanai_core/logging.py` (hoàn thiện):

```python
"""Log có cấu trúc + trace span, có lọc dữ liệu nhạy cảm."""
from __future__ import annotations

import json
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("logs")
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_span_stack: ContextVar[tuple] = ContextVar("span_stack", default=())

SENSITIVE_KEYS = {"api_key", "authorization", "password", "token", "secret"}
PHONE = re.compile(r"\b(0\d{2})\d{3,4}(\d{3})\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        v = PHONE.sub(r"\1***\2", value)
        return EMAIL.sub("[email]", v)
    return value


def log_event(event: str, **fields) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event,
           "trace_id": _trace_id.get(""), **redact(fields)}
    stack = _span_stack.get(())
    if stack:
        rec["span_id"] = stack[-1]
    path = LOG_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


@dataclass
class Span:
    name: str
    span_id: str
    parent_id: str
    start: float
    attrs: dict = field(default_factory=dict)
    duration: float = 0.0


@contextmanager
def trace(name: str, **attrs):
    """Mở một span; tự động nối cha-con và ghi log khi kết thúc."""
    if not _trace_id.get(""):
        _trace_id.set(str(uuid.uuid4())[:12])
    stack = _span_stack.get(())
    span_id = str(uuid.uuid4())[:8]
    parent = stack[-1] if stack else ""
    _span_stack.set(stack + (span_id,))
    t0 = time.time()
    span = Span(name, span_id, parent, t0, attrs)
    log_event("span_start", span=name, span_id=span_id, parent_id=parent, **attrs)
    try:
        yield span
    except Exception as e:
        span.attrs["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        span.duration = time.time() - t0
        log_event("span_end", span=name, span_id=span_id, parent_id=parent,
                  ms=round(span.duration * 1000, 1), **span.attrs)
        _span_stack.set(stack)


def new_trace(trace_id: str = "") -> str:
    tid = trace_id or str(uuid.uuid4())[:12]
    _trace_id.set(tid)
    _span_stack.set(())
    return tid


def read_trace(trace_id: str, day: str = "") -> list[dict]:
    day = day or f"{datetime.now():%Y-%m-%d}"
    path = LOG_DIR / f"{day}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("trace_id") == trace_id:
            out.append(r)
    return out


def print_trace(trace_id: str, day: str = "") -> None:
    events = read_trace(trace_id, day)
    ends = {e["span_id"]: e for e in events if e["event"] == "span_end"}
    children: dict[str, list] = {}
    for e in ends.values():
        children.setdefault(e.get("parent_id", ""), []).append(e)

    def walk(parent: str, depth: int = 0):
        for e in sorted(children.get(parent, []), key=lambda x: x["ts"]):
            extra = " ".join(f"{k}={v}" for k, v in e.items()
                             if k not in ("ts", "event", "trace_id", "span_id",
                                          "parent_id", "span", "ms"))
            print(f"{'  ' * depth}├─ {e['span']:<22} {e['ms']:>8.1f}ms  {extra[:70]}")
            walk(e["span_id"], depth + 1)

    print(f"TRACE {trace_id}")
    walk("")
    total = sum(e["ms"] for e in ends.values() if not e.get("parent_id"))
    print(f"Tổng: {total:.0f}ms | {len(ends)} span")
```

`exercises/day64/trace_agent.py`:

```python
from leanai_core.logging import new_trace, trace, print_trace, log_event
from leanai_core.agent import Agent
from exercises.day52.toolset import registry

tid = new_trace()
agent = Agent(registry, max_steps=8)

with trace("agent_run", goal="tìm khách quá hạn"):
    with trace("planning"):
        pass
    run = agent.run("Khách quá hạn nào giá trị lớn nhất? Nếu huỷ hoàn bao nhiêu?")
    log_event("agent_result", answer_len=len(run.answer), steps=len(run.steps),
              cost=run.cost, sdt_test="0901234567")     # kiểm tra redact

print(run.trace())
print("\n" + "=" * 60)
print_trace(tid)
print("\nKiểm tra: số điện thoại trong log phải bị mask thành 090***567")
```

---

## 4. Bài tập

**Bài 1 — Điều tra sự cố.** Chạy 20 run. Chọn ngẫu nhiên 1 trace, chỉ dùng log (không chạy lại) trả lời: agent gọi tool gì, theo thứ tự nào, bước nào chậm nhất, tốn bao nhiêu tiền, vì sao dừng.

**Bài 2 — Kiểm tra rò rỉ.** Grep toàn bộ `logs/*.jsonl` tìm: số điện thoại đủ 10 số, chuỗi `sk-`, email. Phải **không tìm thấy gì**. Nếu có → vá `redact`.

**Bài 3 — Thống kê vận hành.** Viết script đọc log 1 ngày, in: số run, tỉ lệ thành công, tool dùng nhiều nhất, tool chậm nhất, chi phí trung bình, p95 latency. Đây là dashboard vận hành đầu tiên của bạn.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 64 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Log JSONL có trace_id, span_id, parent_id
- [ ] `print_trace` in được cây span với thời gian từng bước
- [ ] Không có dữ liệu nhạy cảm nào trong log (đã grep kiểm tra)
- [ ] Điều tra được một run cũ chỉ bằng log
- [ ] Có script thống kê vận hành theo ngày
- [ ] Quiz ≥ 80%
