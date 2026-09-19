# NGÀY 16 — LLM API request

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Viết `llm_client.py` — lớp bọc API mà bạn sẽ dùng **mọi ngày còn lại**. Nó phải tự đếm token, tự tính tiền, tự log.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Các tham số của một request

| Tham số | Ý nghĩa | Giá trị nên dùng |
|---|---|---|
| `model` | chọn model | cấu hình được, không hardcode |
| `messages` | hội thoại | list role/content |
| `system` | chỉ dẫn hệ thống | luôn có, đừng nhét vào user |
| `max_tokens` | giới hạn output | đặt sát nhu cầu để chặn chi phí |
| `temperature` | ngẫu nhiên | theo bảng tra Ngày 9 |
| `stop_sequences` | dừng sớm khi gặp chuỗi | hữu ích cho định dạng |

### 1.2 Response — những field phải đọc

```python
r.content[0].text      # nội dung
r.usage.input_tokens   # token vào  → tính tiền
r.usage.output_tokens  # token ra   → tính tiền
r.stop_reason          # "end_turn" | "max_tokens" | "stop_sequence" | "tool_use"
```

> **Luật:** nếu `stop_reason == "max_tokens"` thì câu trả lời **chưa hoàn chỉnh**. Không bao giờ parse JSON từ output bị cắt mà không kiểm tra field này.

### 1.3 Vì sao phải bọc API lại

Gọi SDK trực tiếp rải rác khắp nơi → khi cần đổi model, thêm log, thêm cache, đo latency, bạn phải sửa 40 chỗ. Bọc một lần:

```
Code của bạn  →  LLMClient  →  SDK  →  API
                     ↑
        chỗ duy nhất để thêm: log, cache, retry, đo lường, đổi provider
```

Đây là quyết định kiến trúc quan trọng nhất của Phase 2.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic Messages API | https://docs.anthropic.com/en/api/messages |
| Anthropic Python SDK | https://github.com/anthropics/anthropic-sdk-python |

---

## 3. Thực hành (80 phút)

`leanai_core/llm.py` — **file quan trọng nhất của Phase 2**:

```python
"""LLM client dùng chung cho toàn bộ 90 ngày."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from anthropic import Anthropic

from .config import cfg
from .logging import log_event


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    latency: float
    cost: float
    model: str

    @property
    def truncated(self) -> bool:
        return self.stop_reason == "max_tokens"

    def __str__(self) -> str:
        return (f"{self.text}\n---\n[{self.model}] in={self.input_tokens} "
                f"out={self.output_tokens} ${self.cost:.5f} {self.latency:.2f}s"
                f"{' TRUNCATED!' if self.truncated else ''}")


@dataclass
class Usage:
    """Theo dõi tổng chi tiêu trong một phiên chạy."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    by_tag: dict = field(default_factory=dict)

    def add(self, r: LLMResponse, tag: str = "default") -> None:
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        self.cost += r.cost
        t = self.by_tag.setdefault(tag, {"calls": 0, "cost": 0.0})
        t["calls"] += 1
        t["cost"] += r.cost

    def report(self) -> str:
        lines = [f"Tổng: {self.calls} lần gọi | in={self.input_tokens} "
                 f"out={self.output_tokens} | ${self.cost:.4f} "
                 f"(~{self.cost*25000:.0f}đ)"]
        for tag, v in sorted(self.by_tag.items(), key=lambda x: -x[1]["cost"]):
            lines.append(f"  {tag:<24} {v['calls']:>3} lần  ${v['cost']:.4f}")
        return "\n".join(lines)


class LLMClient:
    def __init__(self, model: str | None = None):
        cfg.check()
        self.client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
        self.model = model or cfg.MODEL
        self.usage = Usage()

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.0,
                 max_tokens: int = 1024, stop: list[str] | None = None,
                 tag: str = "default") -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], system=system,
                         temperature=temperature, max_tokens=max_tokens,
                         stop=stop, tag=tag)

    def chat(self, messages: list[dict], *, system: str = "", temperature: float = 0.0,
             max_tokens: int = 1024, stop: list[str] | None = None,
             tag: str = "default") -> LLMResponse:
        kwargs = dict(model=self.model, max_tokens=max_tokens,
                      temperature=temperature, messages=messages)
        if system:
            kwargs["system"] = system
        if stop:
            kwargs["stop_sequences"] = stop

        t0 = time.time()
        r = self.client.messages.create(**kwargs)
        latency = time.time() - t0

        cost = (r.usage.input_tokens * cfg.PRICE_IN
                + r.usage.output_tokens * cfg.PRICE_OUT) / 1e6

        resp = LLMResponse(
            text=r.content[0].text if r.content else "",
            input_tokens=r.usage.input_tokens,
            output_tokens=r.usage.output_tokens,
            stop_reason=r.stop_reason or "",
            latency=latency, cost=cost, model=self.model,
        )
        self.usage.add(resp, tag)
        log_event("llm_call", tag=tag, model=self.model,
                  input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                  latency=round(latency, 3), cost=round(cost, 6),
                  stop_reason=resp.stop_reason)

        if resp.truncated:
            print(f"  ⚠ Output bị cắt (max_tokens={max_tokens}). Kết quả KHÔNG hoàn chỉnh.")
        if self.usage.cost > cfg.DAILY_COST_LIMIT:
            print(f"  ⚠ Đã vượt ngân sách phiên: ${self.usage.cost:.3f} "
                  f"> ${cfg.DAILY_COST_LIMIT}")
        return resp
```

### Test

`exercises/day16/test_client.py`:

```python
from leanai_core.llm import LLMClient

llm = LLMClient()

r1 = llm.complete("RAG là gì? Trả lời 1 câu.", tag="định nghĩa")
print(r1)

r2 = llm.complete(
    "Liệt kê 5 lý do khách hàng spa không quay lại.",
    system="Bạn là chuyên gia vận hành spa. Trả lời gạch đầu dòng, mỗi ý ≤ 12 từ.",
    max_tokens=200, tag="phân tích")
print(r2)

# Cố tình cắt để thấy cảnh báo
r3 = llm.complete("Viết 500 từ về chăm sóc khách hàng.", max_tokens=30, tag="test cắt")
print("stop_reason:", r3.stop_reason, "| truncated:", r3.truncated)

print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — So sánh model.** Thêm phương thức `compare(prompt, models: list[str])` chạy cùng prompt qua nhiều model, in bảng: model | chất lượng (bạn chấm 1-5) | tokens | chi phí | latency. Chạy trên 3 prompt khác nhau.
*Kết luận cần rút ra:* model rẻ nhất đủ dùng cho tác vụ nào?

**Bài 2 — Ngân sách cứng.** Thêm tham số `hard_limit: float` vào `LLMClient.__init__`. Khi tổng chi phí vượt ngưỡng, **ném exception** thay vì chỉ cảnh báo. Test bằng cách đặt limit = 0.001 rồi gọi vài lần.

**Bài 3 — Dry run.** Thêm `dry_run: bool`: khi bật, không gọi API, chỉ đếm token và in ước tính chi phí. Cực hữu ích khi bạn chuẩn bị chạy 1000 request ở Ngày 89.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 16
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `leanai_core/llm.py` hoạt động, có Usage tracking
- [ ] Mọi lần gọi đều được ghi vào `logs/*.jsonl`
- [ ] Phát hiện và cảnh báo được output bị cắt
- [ ] `usage.report()` chia chi phí theo tag
- [ ] Bài 1 có bảng so sánh model bằng số liệu thật
- [ ] Quiz ≥ 80%

> Từ hôm nay, **không bao giờ** gọi SDK trực tiếp nữa. Mọi thứ đi qua `LLMClient`.
